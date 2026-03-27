# 📚 BookGenie

A book recommendation app powered by BigBookAPI. Search for books and get personalized recommendations based on your picks.

## Project Structure

```
BookGenie/
├── backend/
│   ├── app.py              # Flask API server
│   ├── .env                # API keys (don't commit!)
│   └── requirements.txt    # Python dependencies
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── index.js        # React entry point
│   │   ├── index.css       # Global styles
│   │   ├── App.jsx         # Main app component
│   │   ├── App.css         # App styles
│   │   └── components/
│   │       ├── BookSearch.jsx   # Search bar
│   │       ├── BookSearch.css
│   │       ├── BookCard.jsx     # Book display card
│   │       ├── BookCard.css
│   │       ├── Recommendations.jsx  # Similar books
│   │       └── Recommendations.css
│   └── package.json
├── .gitignore
└── README.md
```

## Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
python app.py
```

The Flask server runs on http://localhost:5000.

### Frontend

```bash
cd frontend
npm install
npm start
```

The React app runs on http://localhost:3000 and proxies API requests to the Flask backend.

## How It Works

1. **Search** — Type a query to find books via BigBookAPI
2. **Select** — Click a book to select it
3. **Discover** — Get similar book recommendations based on your selection

---

## RAG Features (FAISS + Claude)

BookGenie includes a local RAG (Retrieval-Augmented Generation) layer powered by:
- **HuggingFace `all-MiniLM-L6-v2`** for free, local embeddings (no API key needed)
- **FAISS** for fast vector similarity search (index persisted to `backend/faiss_index/`)
- **Claude (`claude-sonnet-4-6`)** via `langchain-anthropic` as the LLM

### Setup

Add your Anthropic API key to `backend/.env`:
```
ANTHROPIC_API_KEY=your-anthropic-api-key-here
```

### RAG Endpoints

#### `POST /api/index-books`
Index a list of books (from BigBookAPI search results) into the FAISS vector store.

```bash
curl -X POST http://localhost:5001/api/index-books \
  -H "Content-Type: application/json" \
  -d '{
    "books": [
      {
        "title": "Dune",
        "authors": [{"name": "Frank Herbert"}],
        "description": "A epic science fiction novel about politics, religion, and survival on a desert planet."
      }
    ]
  }'
```

Response:
```json
{"success": true, "chunks_indexed": 3, "books_received": 1}
```

---

#### `POST /api/recommend-smart`
RAG-powered recommendations: retrieves the top-5 most relevant book chunks from FAISS and sends them as context to Claude.

```bash
curl -X POST http://localhost:5001/api/recommend-smart \
  -H "Content-Type: application/json" \
  -d '{"query": "a heartwarming story about friendship"}'
```

```bash
curl -X POST http://localhost:5001/api/recommend-smart \
  -H "Content-Type: application/json" \
  -d '{"query": "dark sci-fi about survival in space"}'
```

Response:
```json
{
  "query": "dark sci-fi about survival in space",
  "recommendation": "Based on the books in your library, I recommend..."
}
```

> If no books have been indexed yet, returns a 404 with: `"No books indexed yet. Use POST /api/index-books first."`

---

#### `GET /api/rag-status`
Check whether a FAISS index exists and how many vectors it holds.

```bash
curl http://localhost:5001/api/rag-status
```

Response:
```json
{"exists": true, "vector_count": 42}
```

---

#### `POST /api/clear-index`
Delete the FAISS index from disk.

```bash
curl -X POST http://localhost:5001/api/clear-index
```

Response:
```json
{"success": true, "message": "FAISS index deleted."}
```

---

### Typical Workflow

1. Search for books in the UI (or via `/api/search`)
2. Index them: `POST /api/index-books` with the books array
3. Ask for smart recommendations: `POST /api/recommend-smart` with your query
4. Check index status anytime: `GET /api/rag-status`
