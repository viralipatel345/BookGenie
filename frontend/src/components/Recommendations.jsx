import React, { useState, useEffect, useRef } from "react";
import "./Recommendations.css";

function Recommendations({ book, user, onAuthRequired }) {
  const [recs, setRecs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [listSaved, setListSaved] = useState(false);
  const [copyMsg, setCopyMsg] = useState("");

  // AI Explain state: { [recId]: { text, loading, error, visible } }
  const [explanations, setExplanations] = useState({});
  const abortControllersRef = useRef({});

  useEffect(() => {
    if (!book?.id) return;
    setListSaved(false);
    setCopyMsg("");

    // Clear explanations and abort any in-flight streams when source book changes
    Object.values(abortControllersRef.current).forEach((ctrl) => ctrl.abort());
    abortControllersRef.current = {};
    setExplanations({});

    const fetchRecs = async () => {
      setLoading(true);
      setError("");

      try {
        const res = await fetch(`/api/recommend/${book.id}?number=5`);
        const data = await res.json();

        if (data.error) {
          setError(data.error);
          setRecs([]);
        } else {
          setRecs(data.similar_books || []);
        }
      } catch (err) {
        setError("Failed to load recommendations.");
        setRecs([]);
      } finally {
        setLoading(false);
      }
    };

    fetchRecs();
  }, [book]);

  const handleExplain = async (rec) => {
    if (!user) {
      onAuthRequired();
      return;
    }

    const recId = String(rec.id);

    // Toggle: hide if already loaded and visible
    if (explanations[recId]?.text && explanations[recId]?.visible) {
      setExplanations((prev) => ({
        ...prev,
        [recId]: { ...prev[recId], visible: false },
      }));
      return;
    }

    // Re-show if already loaded but hidden
    if (explanations[recId]?.text && !explanations[recId]?.visible) {
      setExplanations((prev) => ({
        ...prev,
        [recId]: { ...prev[recId], visible: true },
      }));
      return;
    }

    // Abort any previous request for this rec
    if (abortControllersRef.current[recId]) {
      abortControllersRef.current[recId].abort();
    }
    const ctrl = new AbortController();
    abortControllersRef.current[recId] = ctrl;

    setExplanations((prev) => ({
      ...prev,
      [recId]: { text: "", loading: true, error: "", visible: true },
    }));

    try {
      const res = await fetch("/api/recommend/explain", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${user.token}`,
        },
        body: JSON.stringify({ source_book: book, rec_book: rec }),
        signal: ctrl.signal,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        setExplanations((prev) => ({
          ...prev,
          [recId]: { text: "", loading: false, error: errData.error || "Failed to get explanation.", visible: true },
        }));
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop(); // keep incomplete last chunk

        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          const payload = line.slice(5).trim();
          if (payload === "[DONE]") {
            setExplanations((prev) => ({
              ...prev,
              [recId]: { ...prev[recId], loading: false },
            }));
            return;
          }
          if (payload.startsWith("[ERROR]")) {
            setExplanations((prev) => ({
              ...prev,
              [recId]: { ...prev[recId], loading: false, error: payload.slice(7).trim() },
            }));
            return;
          }
          const text = payload.replace(/\\n/g, "\n");
          setExplanations((prev) => ({
            ...prev,
            [recId]: {
              ...prev[recId],
              text: (prev[recId]?.text || "") + text,
            },
          }));
        }
      }

      setExplanations((prev) => ({
        ...prev,
        [recId]: { ...prev[recId], loading: false },
      }));
    } catch (err) {
      if (err.name === "AbortError") return;
      setExplanations((prev) => ({
        ...prev,
        [recId]: { text: "", loading: false, error: "Stream interrupted.", visible: true },
      }));
    }
  };

  const buildListText = () => {
    const lines = [`Books similar to "${book.title}":\n`];
    recs.forEach((r, i) => {
      const authors = r.authors ? r.authors.map((a) => a?.name ?? a).join(", ") : "";
      lines.push(`${i + 1}. ${r.title}${authors ? ` by ${authors}` : ""}`);
    });
    return lines.join("\n");
  };

  const handleShare = () => {
    const text = buildListText();
    navigator.clipboard.writeText(text).catch(() => {});
    const encoded = encodeURIComponent(text);
    window.open(`sms:?body=${encoded}`, "_self");
    setCopyMsg("Copied & SMS ready!");
    setTimeout(() => setCopyMsg(""), 3000);
  };

  const handleSaveList = async () => {
    if (!user) {
      onAuthRequired();
      return;
    }
    try {
      const res = await fetch("/api/lists/saved", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${user.token}`,
        },
        body: JSON.stringify({
          name: `Similar to "${book.title}"`,
          source_book: book,
          books: recs,
        }),
      });
      if (res.ok) setListSaved(true);
    } catch {}
  };

  const fallbackImage = "https://via.placeholder.com/128x192?text=No+Cover";

  return (
    <section className="recs">
      <h2 className="section-title">
        Because you liked <span className="highlight">{book.title}</span>
      </h2>

      {loading && (
        <div className="recs-loader">
          <div className="loader-dot"></div>
          <div className="loader-dot"></div>
          <div className="loader-dot"></div>
        </div>
      )}

      {error && <p className="error-msg">{error}</p>}

      {!loading && recs.length > 0 && (
        <>
          <div className="recs-actions">
            <button className="recs-btn" onClick={handleShare}>
              Share List
            </button>
            {copyMsg && <span className="copy-msg">{copyMsg}</span>}
            <button
              className="recs-btn recs-btn--save"
              onClick={handleSaveList}
              disabled={listSaved}
            >
              {listSaved ? "List Saved ✓" : "Save List"}
            </button>
          </div>

          <div className="recs-list">
            {recs.map((rec, index) => {
              const recId = String(rec.id || index);
              const expl = explanations[recId];
              const isLoading = expl?.loading;
              const isVisible = expl?.visible;
              const hasText = !!expl?.text;

              return (
                <React.Fragment key={rec.id || index}>
                  <div className="rec-card">
                    <div className="rec-card__cover">
                      <img
                        src={rec.image || fallbackImage}
                        alt={rec.title}
                        onError={(e) => { e.target.src = fallbackImage; }}
                      />
                    </div>
                    <div className="rec-card__info">
                      <h3 className="rec-card__title">{rec.title}</h3>
                      {rec.authors && (
                        <p className="rec-card__author">{rec.authors.map((a) => a?.name ?? a).join(", ")}</p>
                      )}
                      {rec.rating?.average && (
                        <p className="rec-card__rating">
                          <span className="star">★</span> {rec.rating.average.toFixed(1)}
                        </p>
                      )}
                      {user && (
                        <button
                          className={`ai-explain-btn${isLoading ? " ai-explain-btn--loading" : ""}`}
                          onClick={() => handleExplain(rec)}
                          disabled={isLoading}
                        >
                          {isLoading
                            ? "Thinking…"
                            : hasText && isVisible
                            ? "Hide Explanation"
                            : hasText && !isVisible
                            ? "Show Explanation"
                            : "AI Explain"}
                        </button>
                      )}
                    </div>
                  </div>

                  {expl && isVisible && (expl.text || expl.error) && (
                    <div className="ai-explanation">
                      {expl.error ? (
                        <p className="ai-explanation__error">{expl.error}</p>
                      ) : (
                        <p className="ai-explanation__text">
                          {expl.text}
                          {expl.loading && <span className="ai-explanation__cursor" />}
                        </p>
                      )}
                    </div>
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </>
      )}

      {!loading && !error && recs.length === 0 && (
        <p className="recs-empty">No recommendations found for this book.</p>
      )}
    </section>
  );
}

export default Recommendations;
