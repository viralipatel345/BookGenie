import os
import json
import datetime
import requests
import jwt
import anthropic
import chromadb
import rag_engine
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from functools import wraps
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

load_dotenv()

app = Flask(__name__)
CORS(app)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///bookgenie.db"
app.config["JWT_SECRET"] = os.environ.get("JWT_SECRET", "bookgenie-dev-secret")
db = SQLAlchemy(app)

_chroma_client = chromadb.PersistentClient(path="./chroma_data")
_embedding_fn = DefaultEmbeddingFunction()   # all-MiniLM-L6-v2, local ONNX
_books_collection = _chroma_client.get_or_create_collection(
    name="books",
    embedding_function=_embedding_fn,
    metadata={"hnsw:space": "cosine"},
)
_anthropic_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

API_KEY = "3d6f26b0b18e4e0a80e53112907e78e9"
BASE_URL = "https://api.bigbookapi.com"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class SavedBook(db.Model):
    __tablename__ = "saved_books"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    book_id = db.Column(db.Integer, nullable=False)
    book_data = db.Column(db.Text, nullable=False)  # JSON
    saved_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "book_id"),)


class SavedList(db.Model):
    __tablename__ = "saved_lists"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.Text, nullable=False)
    source_book = db.Column(db.Text, nullable=False)  # JSON
    books_data = db.Column(db.Text, nullable=False)   # JSON array
    saved_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class SearchHistory(db.Model):
    __tablename__ = "search_history"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    query = db.Column(db.Text, nullable=False)
    earliest_year = db.Column(db.Integer, nullable=True)
    searched_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "query"),)


with app.app_context():
    db.create_all()


# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid token"}), 401
        token = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, app.config["JWT_SECRET"], algorithms=["HS256"])
            request.user_id = payload["user_id"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Original routes (preserved + year filter added to search)
# ---------------------------------------------------------------------------

@app.route("/api/search", methods=["GET"])
def search_books():
    """Search for books by query string."""
    query = request.args.get("query", "")
    number = request.args.get("number", 10)
    earliest_year = request.args.get("earliest_year")

    if not query:
        return jsonify({"error": "Query parameter is required"}), 400

    params = {
        "query": query,
        "number": number,
        "api-key": API_KEY,
    }
    if earliest_year:
        params["earliest-publish-year"] = earliest_year

    try:
        response = requests.get(f"{BASE_URL}/search-books", params=params)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/book/<int:book_id>", methods=["GET"])
def get_book(book_id):
    """Get detailed info about a specific book."""
    try:
        response = requests.get(f"{BASE_URL}/{book_id}", params={"api-key": API_KEY})
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/recommend/<int:book_id>", methods=["GET"])
def recommend_books(book_id):
    """Get similar book recommendations based on a book ID."""
    number = request.args.get("number", 5)
    try:
        response = requests.get(f"{BASE_URL}/{book_id}/similar", params={
            "number": number,
            "api-key": API_KEY
        })
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already taken"}), 409

    user = User(username=username, password=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()

    token = jwt.encode(
        {"user_id": user.id, "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)},
        app.config["JWT_SECRET"],
        algorithm="HS256"
    )
    return jsonify({"token": token, "username": user.username}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({"error": "Invalid username or password"}), 401

    token = jwt.encode(
        {"user_id": user.id, "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)},
        app.config["JWT_SECRET"],
        algorithm="HS256"
    )
    return jsonify({"token": token, "username": user.username})


# ---------------------------------------------------------------------------
# Saved Books
# ---------------------------------------------------------------------------

@app.route("/api/books/saved", methods=["GET"])
@require_auth
def list_saved_books():
    books = SavedBook.query.filter_by(user_id=request.user_id).order_by(SavedBook.saved_at.desc()).all()
    return jsonify([json.loads(b.book_data) for b in books])


@app.route("/api/books/saved", methods=["POST"])
@require_auth
def save_book():
    data = request.get_json() or {}
    book_id = data.get("book_id")
    book_data = data.get("book_data")
    if not book_id or not book_data:
        return jsonify({"error": "book_id and book_data are required"}), 400

    existing = SavedBook.query.filter_by(user_id=request.user_id, book_id=book_id).first()
    if existing:
        return jsonify({"message": "Already saved"}), 200

    saved = SavedBook(user_id=request.user_id, book_id=book_id, book_data=json.dumps(book_data))
    db.session.add(saved)
    db.session.commit()
    return jsonify({"message": "Saved"}), 201


@app.route("/api/books/saved", methods=["DELETE"])
@require_auth
def unsave_book():
    book_id = request.args.get("book_id", type=int)
    if not book_id:
        return jsonify({"error": "book_id is required"}), 400

    saved = SavedBook.query.filter_by(user_id=request.user_id, book_id=book_id).first()
    if saved:
        db.session.delete(saved)
        db.session.commit()
    return jsonify({"message": "Removed"})


# ---------------------------------------------------------------------------
# Saved Lists
# ---------------------------------------------------------------------------

@app.route("/api/lists/saved", methods=["GET"])
@require_auth
def list_saved_lists():
    lists = SavedList.query.filter_by(user_id=request.user_id).order_by(SavedList.saved_at.desc()).all()
    return jsonify([{
        "id": l.id,
        "name": l.name,
        "source_book": json.loads(l.source_book),
        "books": json.loads(l.books_data),
        "saved_at": l.saved_at.isoformat()
    } for l in lists])


@app.route("/api/lists/saved", methods=["POST"])
@require_auth
def save_list():
    data = request.get_json() or {}
    name = data.get("name")
    source_book = data.get("source_book")
    books = data.get("books")
    if not name or not source_book or books is None:
        return jsonify({"error": "name, source_book, and books are required"}), 400

    lst = SavedList(
        user_id=request.user_id,
        name=name,
        source_book=json.dumps(source_book),
        books_data=json.dumps(books)
    )
    db.session.add(lst)
    db.session.commit()
    return jsonify({"id": lst.id, "message": "List saved"}), 201


@app.route("/api/lists/saved/<int:list_id>", methods=["DELETE"])
@require_auth
def delete_list(list_id):
    lst = SavedList.query.filter_by(id=list_id, user_id=request.user_id).first()
    if not lst:
        return jsonify({"error": "Not found"}), 404
    db.session.delete(lst)
    db.session.commit()
    return jsonify({"message": "Deleted"})


# ---------------------------------------------------------------------------
# Search History
# ---------------------------------------------------------------------------

@app.route("/api/history", methods=["GET"])
@require_auth
def list_history():
    history = (
        SearchHistory.query
        .filter_by(user_id=request.user_id)
        .order_by(SearchHistory.searched_at.desc())
        .limit(20)
        .all()
    )
    return jsonify([{
        "id": h.id,
        "query": h.query,
        "earliest_year": h.earliest_year,
        "searched_at": h.searched_at.isoformat()
    } for h in history])


@app.route("/api/history", methods=["POST"])
@require_auth
def add_history():
    data = request.get_json() or {}
    query = (data.get("query") or "").strip()
    earliest_year = data.get("earliest_year")

    if not query:
        return jsonify({"error": "query is required"}), 400

    existing = SearchHistory.query.filter_by(user_id=request.user_id, query=query).first()
    if existing:
        existing.searched_at = datetime.datetime.utcnow()
        existing.earliest_year = earliest_year
        db.session.commit()
        return jsonify({"id": existing.id, "message": "Updated"})

    entry = SearchHistory(user_id=request.user_id, query=query, earliest_year=earliest_year)
    db.session.add(entry)
    db.session.commit()
    return jsonify({"id": entry.id, "message": "Added"}), 201


@app.route("/api/history/<int:entry_id>", methods=["DELETE"])
@require_auth
def delete_history_entry(entry_id):
    entry = SearchHistory.query.filter_by(id=entry_id, user_id=request.user_id).first()
    if not entry:
        return jsonify({"error": "Not found"}), 404
    db.session.delete(entry)
    db.session.commit()
    return jsonify({"message": "Deleted"})


@app.route("/api/history", methods=["DELETE"])
@require_auth
def clear_history():
    SearchHistory.query.filter_by(user_id=request.user_id).delete()
    db.session.commit()
    return jsonify({"message": "History cleared"})


# ---------------------------------------------------------------------------
# RAG — Book Indexing
# ---------------------------------------------------------------------------

@app.route("/api/books/index", methods=["POST"])
def index_books():
    """Fire-and-forget: upsert books into ChromaDB vector store."""
    data = request.get_json() or {}
    books = data.get("books", [])
    if not books:
        return jsonify({"indexed": 0})

    ids, documents, metadatas = [], [], []
    for book in books:
        book_id = str(book.get("id", ""))
        if not book_id:
            continue
        title = book.get("title") or ""
        authors_raw = book.get("authors") or []
        if authors_raw and isinstance(authors_raw[0], dict):
            authors_str = ", ".join(a.get("name", "") for a in authors_raw)
        else:
            authors_str = ", ".join(str(a) for a in authors_raw)
        description = (book.get("description") or "")[:500]
        doc_text = f"{title} by {authors_str}. {description}".strip()

        image = book.get("image") or ""
        ids.append(book_id)
        documents.append(doc_text)
        metadatas.append({"title": title, "authors": authors_str, "image": image})

    if ids:
        _books_collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    return jsonify({"indexed": len(ids)})


# ---------------------------------------------------------------------------
# RAG + Claude — AI Explanation (SSE streaming)
# ---------------------------------------------------------------------------

@app.route("/api/recommend/explain", methods=["POST"])
@require_auth
def explain_recommendation():
    """Stream a Claude explanation of why rec_book suits a fan of source_book."""
    data = request.get_json() or {}
    source_book = data.get("source_book") or {}
    rec_book = data.get("rec_book") or {}

    source_id = str(source_book.get("id", ""))
    rec_id = str(rec_book.get("id", ""))

    def _book_summary(b):
        authors_raw = b.get("authors") or []
        if authors_raw and isinstance(authors_raw[0], dict):
            authors_str = ", ".join(a.get("name", "") for a in authors_raw)
        else:
            authors_str = ", ".join(str(a) for a in authors_raw)
        desc = (b.get("description") or "")[:300]
        return f'"{b.get("title", "Unknown")}" by {authors_str}. {desc}'.strip()

    # Query ChromaDB for 3 related books (excluding source and rec)
    rag_context = ""
    try:
        source_query = _book_summary(source_book)
        exclude_ids = [x for x in [source_id, rec_id] if x]
        where_clause = {"id": {"$nin": exclude_ids}} if exclude_ids else None
        results = _books_collection.query(
            query_texts=[source_query],
            n_results=3,
            where=where_clause,
        )
        docs = (results.get("documents") or [[]])[0]
        if docs:
            rag_context = "\n".join(f"- {d}" for d in docs)
    except Exception:
        rag_context = ""

    system_prompt = (
        "You are a knowledgeable literary assistant for BookGenie. "
        "Explain in exactly 2-3 sentences why a recommended book is a great match "
        "for someone who loved the source book. Focus on shared themes, tone, genre, "
        "writing style, and emotional resonance. No bullet points. Be specific."
    )

    user_message = (
        f"Source book (the one the reader loved):\n{_book_summary(source_book)}\n\n"
        f"Recommended book (explain why it suits this reader):\n{_book_summary(rec_book)}"
    )
    if rag_context:
        user_message += f"\n\nRelated books for additional context:\n{rag_context}"

    def generate():
        try:
            with _anthropic_client.messages.stream(
                model="claude-opus-4-6",
                thinking={"type": "enabled", "budget_tokens": 512},
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            ) as stream:
                for event in stream:
                    if (
                        hasattr(event, "type")
                        and event.type == "content_block_delta"
                        and hasattr(event, "delta")
                        and getattr(event.delta, "type", None) == "text_delta"
                    ):
                        chunk = event.delta.text
                        yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Book Oracle — Multi-turn RAG Chat (SSE streaming)
# ---------------------------------------------------------------------------

ORACLE_SYSTEM_PROMPT = (
    "You are Book Oracle, the literary AI assistant for BookGenie. "
    "Help users discover books through conversation. "
    "When books are provided as RAG context, reference them specifically by title and author. "
    "Keep responses concise: 2-3 sentences plus 1-3 specific book recommendations. "
    "If no books are in the library yet, warmly suggest the user search for books first to build the library. "
    "Be warm and knowledgeable, like a great independent bookshop owner who loves matching readers with perfect books."
)


@app.route("/api/chat", methods=["POST"])
@require_auth
def chat():
    """Stream a multi-turn Book Oracle conversation with RAG context from ChromaDB."""
    data = request.get_json() or {}
    messages = data.get("messages", [])

    if not messages:
        return jsonify({"error": "messages are required"}), 400

    # Extract last user message for ChromaDB query
    last_user_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user_msg = m.get("content", "")
            break

    # Query ChromaDB for related books
    rag_books = []
    rag_context = ""
    try:
        if last_user_msg and _books_collection.count() > 0:
            results = _books_collection.query(
                query_texts=[last_user_msg],
                n_results=min(3, _books_collection.count()),
            )
            docs = (results.get("documents") or [[]])[0]
            metas = (results.get("metadatas") or [[]])[0]
            for doc, meta in zip(docs, metas):
                rag_books.append({
                    "title": meta.get("title", ""),
                    "authors": meta.get("authors", ""),
                    "image": meta.get("image", ""),
                })
            if docs:
                rag_context = "\n".join(f"- {d}" for d in docs)
    except Exception:
        rag_context = ""

    # Build messages for Claude — inject RAG context into last user message
    claude_messages = []
    for i, m in enumerate(messages):
        role = m.get("role")
        content = m.get("content", "")
        if role == "user" and i == len(messages) - 1 and rag_context:
            content = (
                f"{content}\n\n"
                f"[Books in your library that may be relevant:]\n{rag_context}"
            )
        if role in ("user", "assistant"):
            claude_messages.append({"role": role, "content": content})

    def generate():
        # First, send the sources as structured data
        sources_payload = json.dumps({"books": rag_books})
        yield f"data: [SOURCES]{sources_payload}\n\n"

        try:
            with _anthropic_client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=512,
                system=ORACLE_SYSTEM_PROMPT,
                messages=claude_messages,
            ) as stream:
                for event in stream:
                    if (
                        hasattr(event, "type")
                        and event.type == "content_block_delta"
                        and hasattr(event, "delta")
                        and getattr(event.delta, "type", None) == "text_delta"
                    ):
                        chunk = event.delta.text
                        # Escape newlines so SSE stays valid
                        safe_chunk = chunk.replace("\n", "\\n")
                        yield f"data: {safe_chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# FAISS RAG — new endpoints (do not modify existing endpoints above)
# ---------------------------------------------------------------------------

@app.route("/api/index-books", methods=["POST"])
def faiss_index_books():
    """Chunk, embed, and store a list of book objects in the FAISS index."""
    data = request.get_json() or {}
    books = data.get("books", [])

    if not books:
        return jsonify({"error": "Provide a non-empty 'books' list"}), 400

    try:
        count = rag_engine.index_books(books)
        return jsonify({"success": True, "chunks_indexed": count, "books_received": len(books)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/recommend-smart", methods=["POST"])
def recommend_smart():
    """RAG-powered recommendation: retrieve top-5 chunks then ask Claude."""
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not anthropic_api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY is not set. Add it to backend/.env"}), 500

    data = request.get_json() or {}
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"error": "'query' field is required"}), 400

    try:
        answer = rag_engine.recommend_smart(query, anthropic_api_key)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if answer is None:
        return jsonify({
            "error": "No books indexed yet. Use POST /api/index-books first to add books."
        }), 404

    return jsonify({"query": query, "recommendation": answer})


@app.route("/api/clear-index", methods=["POST"])
def clear_faiss_index():
    """Delete the FAISS index from disk."""
    deleted = rag_engine.clear_index()
    if deleted:
        return jsonify({"success": True, "message": "FAISS index deleted."})
    return jsonify({"success": False, "message": "No FAISS index found on disk."})


@app.route("/api/rag-status", methods=["GET"])
def rag_status():
    """Return whether a FAISS index exists and how many vectors it holds."""
    status = rag_engine.get_index_status()
    return jsonify(status)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
