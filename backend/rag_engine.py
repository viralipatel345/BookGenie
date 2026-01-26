"""
rag_engine.py — FAISS-based RAG engine for BookGenie

Uses HuggingFaceEmbeddings (all-MiniLM-L6-v2, free/local) for embeddings
and ChatAnthropic (Claude) as the LLM.
"""

import os
import shutil
from typing import Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_anthropic import ChatAnthropic
from langchain.memory import ConversationBufferWindowMemory
from langchain_core.messages import HumanMessage, SystemMessage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAISS_INDEX_PATH = os.path.join(os.path.dirname(__file__), "faiss_index")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
RAG_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = (
    "You are a book recommendation assistant. Use ONLY the provided book context "
    "to make recommendations. If the context doesn't contain relevant books, say so. "
    "Always include the book title and author in your recommendations and explain why "
    "each book matches the user's request."
)

# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

_embeddings: Optional[HuggingFaceEmbeddings] = None
_vector_store: Optional[FAISS] = None
_memory = ConversationBufferWindowMemory(k=5, return_messages=True, memory_key="chat_history")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        print(f"[RAG] Loading HuggingFace embedding model ({EMBEDDING_MODEL})…")
        _embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        print("[RAG] Embedding model ready.")
    return _embeddings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def index_books(books: list) -> int:
    """
    Chunk book descriptions, embed with all-MiniLM-L6-v2, and store in FAISS.
    Merges into any existing on-disk index and saves back to disk.
    Returns the number of text chunks indexed.
    """
    global _vector_store

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    embeddings = _get_embeddings()

    texts, metadatas = [], []

    for book in books:
        title = book.get("title") or "Unknown Title"
        authors_raw = book.get("authors") or []
        if authors_raw and isinstance(authors_raw[0], dict):
            authors_str = ", ".join(a.get("name", "") for a in authors_raw)
        else:
            authors_str = ", ".join(str(a) for a in authors_raw)
        description = book.get("description") or ""

        full_text = f"Title: {title}\nAuthor: {authors_str}\nDescription: {description}"
        chunks = splitter.split_text(full_text)
        print(f"[RAG] Chunking '{title}' by {authors_str} → {len(chunks)} chunk(s)")

        for chunk in chunks:
            texts.append(chunk)
            metadatas.append({"title": title, "authors": authors_str})

    if not texts:
        print("[RAG] No text to index.")
        return 0

    print(f"[RAG] Embedding {len(texts)} chunks…")

    if _vector_store is not None:
        # Already loaded in memory — just add
        _vector_store.add_texts(texts, metadatas=metadatas)
    elif os.path.exists(FAISS_INDEX_PATH):
        # Load from disk and merge
        print("[RAG] Loading existing FAISS index to merge into…")
        _vector_store = FAISS.load_local(
            FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True
        )
        _vector_store.add_texts(texts, metadatas=metadatas)
    else:
        # Brand-new index
        _vector_store = FAISS.from_texts(texts, embeddings, metadatas=metadatas)

    os.makedirs(FAISS_INDEX_PATH, exist_ok=True)
    _vector_store.save_local(FAISS_INDEX_PATH)
    total = _vector_store.index.ntotal
    print(f"[RAG] Index saved to {FAISS_INDEX_PATH} (total vectors: {total})")
    return len(texts)


def load_index() -> Optional[FAISS]:
    """Load the FAISS index from disk if not already in memory. Returns store or None."""
    global _vector_store
    if _vector_store is not None:
        return _vector_store
    if os.path.exists(FAISS_INDEX_PATH):
        print("[RAG] Loading FAISS index from disk…")
        _vector_store = FAISS.load_local(
            FAISS_INDEX_PATH, _get_embeddings(), allow_dangerous_deserialization=True
        )
        print(f"[RAG] Index loaded ({_vector_store.index.ntotal} vectors).")
        return _vector_store
    return None


def get_index_status() -> dict:
    """Return whether the FAISS index exists and how many vectors it holds."""
    exists = os.path.exists(FAISS_INDEX_PATH)
    vector_count = 0
    if exists:
        store = load_index()
        if store is not None:
            vector_count = store.index.ntotal
    return {"exists": exists, "vector_count": vector_count}


def clear_index() -> bool:
    """Delete the FAISS index from disk and reset the in-memory store. Returns True if deleted."""
    global _vector_store
    _vector_store = None
    if os.path.exists(FAISS_INDEX_PATH):
        shutil.rmtree(FAISS_INDEX_PATH)
        print("[RAG] FAISS index cleared.")
        return True
    return False


def recommend_smart(query: str, anthropic_api_key: str) -> Optional[str]:
    """
    Retrieve top-5 similar chunks from FAISS, then ask Claude for recommendations.
    Uses ConversationBufferWindowMemory (k=5) for multi-turn context.
    Returns the LLM response string, or None if no FAISS index exists yet.
    """
    store = load_index()
    if store is None:
        return None

    print(f"[RAG] Similarity search for: '{query}'")
    docs = store.similarity_search(query, k=5)
    print(f"[RAG] Retrieved {len(docs)} chunk(s).")

    context = "\n\n".join(
        f"{i + 1}. {doc.page_content}" for i, doc in enumerate(docs)
    )

    llm = ChatAnthropic(
        model=RAG_MODEL,
        temperature=0.3,
        api_key=anthropic_api_key,
    )

    # Load conversation history (up to k=5 turns)
    history_vars = _memory.load_memory_variables({})
    chat_history = history_vars.get("chat_history", [])

    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    messages.extend(chat_history)
    messages.append(
        HumanMessage(
            content=f"User query: {query}\n\nRelevant books from the library:\n{context}"
        )
    )

    print("[RAG] Calling Claude with retrieved context…")
    response = llm.invoke(messages)
    answer = response.content
    print("[RAG] Claude response received.")

    # Persist this turn in memory
    _memory.save_context({"input": query}, {"output": answer})

    return answer