import React, { useState, useRef } from "react";
import "./BookSearch.css";

function BookSearch({ onSearch, loading, earliestYear, setEarliestYear, history, onHistorySelect }) {
  const [query, setQuery] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const blurTimeout = useRef(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query.trim(), earliestYear);
      setShowHistory(false);
    }
  };

  const handleFocus = () => {
    clearTimeout(blurTimeout.current);
    if (history && history.length > 0) setShowHistory(true);
  };

  const handleBlur = () => {
    blurTimeout.current = setTimeout(() => setShowHistory(false), 150);
  };

  const handleHistoryClick = (item) => {
    setQuery(item.query);
    setShowHistory(false);
    onHistorySelect(item);
  };

  const currentYear = new Date().getFullYear();

  return (
    <div className="search-wrapper">
      <form className="search-bar" onSubmit={handleSubmit}>
        <input
          type="text"
          className="search-input"
          placeholder="Search for books, authors, or genres..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={handleFocus}
          onBlur={handleBlur}
          disabled={loading}
        />
        <button className="search-btn" type="submit" disabled={loading || !query.trim()}>
          {loading ? "Searching..." : "Search"}
        </button>
      </form>

      {showHistory && history && history.length > 0 && (
        <ul className="history-dropdown">
          {history.map((item) => (
            <li key={item.id} onMouseDown={() => handleHistoryClick(item)}>
              <span className="history-icon">↩</span>
              {item.query}
              {item.earliest_year && (
                <span className="history-year">({item.earliest_year}+)</span>
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="year-filter">
        <label className="year-filter__label">
          <input
            type="checkbox"
            checked={earliestYear !== null && earliestYear !== undefined}
            onChange={(e) => {
              if (e.target.checked) setEarliestYear(currentYear);
              else setEarliestYear(null);
            }}
          />
          Recent books only
        </label>
        {earliestYear !== null && earliestYear !== undefined && (
          <input
            type="number"
            className="year-input"
            value={earliestYear}
            min="1900"
            max={currentYear}
            onChange={(e) => setEarliestYear(parseInt(e.target.value) || currentYear)}
          />
        )}
      </div>
    </div>
  );
}

export default BookSearch;
