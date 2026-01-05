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
