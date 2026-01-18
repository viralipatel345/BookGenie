import React, { useState } from "react";
import "./AuthModal.css";

function AuthModal({ mode, setMode, onAuth, onClose }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const endpoint = mode === "register" ? "/api/auth/register" : "/api/auth/login";
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();

      if (!res.ok) {
        setError(data.error || "Something went wrong");
      } else {
        onAuth({ token: data.token, username: data.username });
      }
    } catch {
      setError("Network error. Is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-overlay" onClick={onClose}>
      <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
        <button className="auth-close" onClick={onClose}>✕</button>

        <div className="auth-tabs">
          <button
            className={`auth-tab ${mode === "login" ? "auth-tab--active" : ""}`}
            onClick={() => { setMode("login"); setError(""); }}
          >
            Sign In
          </button>
          <button
            className={`auth-tab ${mode === "register" ? "auth-tab--active" : ""}`}
            onClick={() => { setMode("register"); setError(""); }}
          >
            Register
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <h2 className="auth-title">
            {mode === "login" ? "Welcome back" : "Create an account"}
          </h2>

          <div className="auth-field">
            <label>Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter username"
              autoFocus
              required
            />
          </div>

          <div className="auth-field">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password"
              required
            />
          </div>

          {error && <p className="auth-error">{error}</p>}

          <button className="auth-submit" type="submit" disabled={loading}>
            {loading ? "Please wait..." : mode === "login" ? "Sign In" : "Create Account"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default AuthModal;
