import React, { useState } from "react";
import "./BookCard.css";

function BookCard({ book, onSelect, isSelected, user, onAuthRequired }) {
  const [saved, setSaved] = useState(false);
  const fallbackImage = "https://via.placeholder.com/128x192?text=No+Cover";

  const toggleSave = async (e) => {
    e.stopPropagation();
    if (!user) {
      onAuthRequired();
      return;
    }

    const newSaved = !saved;
    setSaved(newSaved); // optimistic

    try {
      if (newSaved) {
        await fetch("/api/books/saved", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${user.token}`,
          },
          body: JSON.stringify({ book_id: book.id, book_data: book }),
        });
      } else {
        await fetch(`/api/books/saved?book_id=${book.id}`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${user.token}` },
        });
      }
    } catch {
      setSaved(!newSaved); // revert on error
    }
  };

  return (
    <div
      className={`book-card ${isSelected ? "book-card--selected" : ""}`}
      onClick={onSelect}
    >
      <div className="book-card__cover">
        <img
          src={book.image || fallbackImage}
          alt={book.title}
          onError={(e) => { e.target.src = fallbackImage; }}
        />
      </div>
      <div className="book-card__info">
        <h3 className="book-card__title">{book.title}</h3>
        {book.authors && (
          <p className="book-card__author">
            {book.authors.map((a) => a?.name ?? a).join(", ")}
          </p>
        )}
        {book.rating?.average && (
          <div className="book-card__rating">
            <span className="star">★</span> {book.rating.average.toFixed(1)}
          </div>
        )}
      </div>
      {isSelected && <div className="book-card__badge">Selected</div>}
      <button
        className={`book-card__save ${saved ? "book-card__save--saved" : ""}`}
        onClick={toggleSave}
        title={saved ? "Remove from saved" : "Save book"}
      >
        {saved ? "♥" : "♡"}
      </button>
    </div>
  );
}

export default BookCard;
