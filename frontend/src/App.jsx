import React, { useState, useEffect } from "react";
import BookSearch from "./components/BookSearch";
import BookCard from "./components/BookCard";
import Recommendations from "./components/Recommendations";
import AuthModal from "./components/AuthModal";
import UserPanel from "./components/UserPanel";
import "./App.css";

function App() {
  const [books, setBooks] = useState([]);
  const [selectedBook, setSelectedBook] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Auth state
  const [user, setUser] = useState(null);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authMode, setAuthMode] = useState("login");
  const [showUserPanel, setShowUserPanel] = useState(false);

  // Search state
  const [searchHistory, setSearchHistory] = useState([]);
  const [earliestYear, setEarliestYear] = useState(null);

  // Hydrate from localStorage on mount
  useEffect(() => {
    const token = localStorage.getItem("bg_token");
    const username = localStorage.getItem("bg_username");
    if (token && username) {
      setUser({ token, username });
      fetchHistory(token);
    }
  }, []);

  const fetchHistory = async (token) => {
    try {
      const res = await fetch("/api/history", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setSearchHistory(data);
      }
    } catch {}
  };

  const handleAuth = ({ token, username }) => {
    localStorage.setItem("bg_token", token);
    localStorage.setItem("bg_username", username);
    setUser({ token, username });
    setShowAuthModal(false);
    fetchHistory(token);
  };

  const handleLogout = () => {
    localStorage.removeItem("bg_token");
    localStorage.removeItem("bg_username");
    setUser(null);
    setSearchHistory([]);
    setShowUserPanel(false);
  };

  const searchBooks = async (query, year) => {
    setLoading(true);
    setError("");
    setSelectedBook(null);

    let url = `/api/search?query=${encodeURIComponent(query)}`;
    if (year) url += `&earliest_year=${year}`;

    try {
      const res = await fetch(url);
      const data = await res.json();

      if (data.error) {
        setError(data.error);
        setBooks([]);
      } else {
        const foundBooks = (data.books || []).flat();
        setBooks(foundBooks);

        if (foundBooks.length > 0) {
          fetch("/api/books/index", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ books: foundBooks }),
          }).catch(() => {});
        }
      }

      // Log to history if logged in
      if (user?.token) {
        fetch("/api/history", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${user.token}`,
          },
          body: JSON.stringify({ query, earliest_year: year || null }),
        })
          .then(() => fetchHistory(user.token))
          .catch(() => {});
      }
    } catch (err) {
      setError("Failed to fetch books. Is the backend running?");
      setBooks([]);
    } finally {
      setLoading(false);
    }
  };

  const onAuthRequired = () => {
    setAuthMode("login");
    setShowAuthModal(true);
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-top">
          <div className="logo">
            <span className="logo-icon">📚</span>
            <h1>BookGenie</h1>
          </div>
          <button
            className="account-btn"
            onClick={() => {
              if (user) setShowUserPanel(true);
              else {
                setAuthMode("login");
                setShowAuthModal(true);
              }
            }}
          >
            {user ? `👤 ${user.username}` : "Sign In"}
          </button>
        </div>
        <p className="tagline">Discover your next favorite read</p>
      </header>

      <main className="app-main">
        <BookSearch
          onSearch={searchBooks}
          loading={loading}
          earliestYear={earliestYear}
          setEarliestYear={setEarliestYear}
          history={searchHistory}
          onHistorySelect={(item) => {
            setEarliestYear(item.earliest_year);
            searchBooks(item.query, item.earliest_year);
          }}
        />

        {error && <p className="error-msg">{error}</p>}

        {loading && (
          <div className="loader">
            <div className="loader-dot"></div>
            <div className="loader-dot"></div>
            <div className="loader-dot"></div>
          </div>
        )}

        {!loading && books.length > 0 && (
          <section className="results">
            <h2 className="section-title">Search Results</h2>
            <div className="book-grid">
              {books.map((book) => (
                <BookCard
                  key={book.id}
                  book={book}
                  onSelect={() => setSelectedBook(book)}
                  isSelected={selectedBook?.id === book.id}
                  user={user}
                  onAuthRequired={onAuthRequired}
                />
              ))}
            </div>
          </section>
        )}

        {selectedBook && (
          <Recommendations
            book={selectedBook}
            user={user}
            onAuthRequired={onAuthRequired}
          />
        )}
      </main>

      <footer className="app-footer">
        <p>Built by Virali · Powered by BigBookAPI</p>
      </footer>

      {showAuthModal && (
        <AuthModal
          mode={authMode}
          setMode={setAuthMode}
          onAuth={handleAuth}
          onClose={() => setShowAuthModal(false)}
        />
      )}

      {showUserPanel && (
        <UserPanel
          user={user}
          onClose={() => setShowUserPanel(false)}
          onLogout={handleLogout}
          searchHistory={searchHistory}
          onDeleteHistory={(id) => {
            fetch(`/api/history/${id}`, {
              method: "DELETE",
              headers: { Authorization: `Bearer ${user.token}` },
            }).then(() => fetchHistory(user.token));
          }}
          onClearHistory={() => {
            fetch("/api/history", {
              method: "DELETE",
              headers: { Authorization: `Bearer ${user.token}` },
            }).then(() => setSearchHistory([]));
          }}
        />
      )}
    </div>
  );
}

export default App;
