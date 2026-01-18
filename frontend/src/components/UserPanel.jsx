import React, { useState, useEffect } from "react";
import "./UserPanel.css";

function UserPanel({ user, onClose, onLogout, searchHistory, onDeleteHistory, onClearHistory }) {
  const [activeTab, setActiveTab] = useState("history");
  const [savedBooks, setSavedBooks] = useState([]);
  const [savedLists, setSavedLists] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (activeTab === "books") fetchSavedBooks();
    if (activeTab === "lists") fetchSavedLists();
  }, [activeTab]);

  const fetchSavedBooks = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/books/saved", {
        headers: { Authorization: `Bearer ${user.token}` },
      });
      if (res.ok) setSavedBooks(await res.json());
    } catch {}
    setLoading(false);
  };

  const fetchSavedLists = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/lists/saved", {
        headers: { Authorization: `Bearer ${user.token}` },
      });
      if (res.ok) setSavedLists(await res.json());
    } catch {}
    setLoading(false);
  };

  const deleteList = async (id) => {
    await fetch(`/api/lists/saved/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${user.token}` },
    });
    setSavedLists((prev) => prev.filter((l) => l.id !== id));
  };

  const unsaveBook = async (book) => {
    await fetch(`/api/books/saved?book_id=${book.id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${user.token}` },
    });
    setSavedBooks((prev) => prev.filter((b) => b.id !== book.id));
  };

  const fallback = "https://via.placeholder.com/128x192?text=No+Cover";

  return (
    <div className="panel-overlay" onClick={onClose}>
      <div className="user-panel" onClick={(e) => e.stopPropagation()}>
        <div className="panel-header">
          <span className="panel-username">👤 {user.username}</span>
          <div className="panel-header-actions">
            <button className="panel-logout" onClick={onLogout}>Logout</button>
            <button className="panel-close" onClick={onClose}>✕</button>
          </div>
        </div>

        <div className="panel-tabs">
          {["history", "books", "lists"].map((tab) => (
            <button
              key={tab}
              className={`panel-tab ${activeTab === tab ? "panel-tab--active" : ""}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab === "history" ? "History" : tab === "books" ? "My Books" : "My Lists"}
            </button>
          ))}
        </div>

        <div className="panel-content">
          {/* History Tab */}
          {activeTab === "history" && (
            <>
              {searchHistory.length > 0 && (
                <button className="clear-all-btn" onClick={onClearHistory}>Clear All</button>
              )}
              {searchHistory.length === 0 && (
                <p className="panel-empty">No search history yet.</p>
              )}
              <ul className="history-list">
                {searchHistory.map((item) => (
                  <li key={item.id} className="history-item">
                    <span className="history-query">{item.query}</span>
                    {item.earliest_year && (
                      <span className="history-item-year">{item.earliest_year}+</span>
                    )}
                    <button
                      className="history-delete"
                      onClick={() => onDeleteHistory(item.id)}
                    >✕</button>
                  </li>
                ))}
              </ul>
            </>
          )}

          {/* Books Tab */}
          {activeTab === "books" && (
            <>
              {loading && <p className="panel-loading">Loading...</p>}
              {!loading && savedBooks.length === 0 && (
                <p className="panel-empty">No saved books yet.</p>
              )}
              <div className="saved-books-grid">
                {savedBooks.map((book) => (
                  <div key={book.id} className="saved-book-card">
                    <img
                      src={book.image || fallback}
                      alt={book.title}
                      onError={(e) => { e.target.src = fallback; }}
                    />
                    <div className="saved-book-info">
                      <p className="saved-book-title">{book.title}</p>
                      {book.authors && (
                        <p className="saved-book-author">
                          {book.authors.map((a) => a?.name ?? a).join(", ")}
                        </p>
                      )}
                    </div>
                    <button className="saved-book-remove" onClick={() => unsaveBook(book)}>✕</button>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Lists Tab */}
          {activeTab === "lists" && (
            <>
              {loading && <p className="panel-loading">Loading...</p>}
              {!loading && savedLists.length === 0 && (
                <p className="panel-empty">No saved lists yet.</p>
              )}
              {savedLists.map((list) => (
                <div key={list.id} className="saved-list-card">
                  <div className="saved-list-header">
                    <span className="saved-list-name">{list.name}</span>
                    <button className="saved-list-delete" onClick={() => deleteList(list.id)}>✕</button>
                  </div>
                  <ul className="saved-list-books">
                    {list.books.slice(0, 3).map((b, i) => (
                      <li key={i}>{b.title}</li>
                    ))}
                    {list.books.length > 3 && (
                      <li className="saved-list-more">+{list.books.length - 3} more</li>
                    )}
                  </ul>
                </div>
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default UserPanel;
