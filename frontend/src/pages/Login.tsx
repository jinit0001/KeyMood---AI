import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAppStore } from "../state/appStore";

export default function Login() {
  const login = useAppStore((s) => s.login);
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError("Enter both email and password to continue.");
      return;
    }
    setBusy(true);
    try {
      await login(email, password);
      setError("");
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-brand">
          <span style={{ width: 9, height: 9, borderRadius: "50%", background: "var(--accent)", display: "inline-block" }} />
          KeyMood AI
        </div>

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Your password" />
          </div>
          {error && <p style={{ color: "var(--danger)", fontSize: "0.8rem", marginBottom: 12 }}>{error}</p>}
          <button type="submit" className="btn btn-primary" style={{ width: "100%" }} disabled={busy}>
            {busy ? "Logging in..." : "Log in"}
          </button>
        </form>

        <p className="auth-footer-link">
          New here? <Link to="/register">Create an account</Link>
        </p>
      </div>
    </div>
  );
}
