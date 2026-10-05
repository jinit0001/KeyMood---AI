import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAppStore } from "../state/appStore";

export default function Register() {
  const register = useAppStore((s) => s.register);
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !email || !password) {
      setError("Please fill in all fields.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (!consent) {
      setError("Please accept the privacy notice to continue.");
      return;
    }
    setBusy(true);
    try {
      await register(name, email, password);
      setError("");
      setSuccess(true);
      setTimeout(() => {
        navigate("/");
      }, 900);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed.");
    } finally {
      setBusy(false);
    }
  };

  if (success) {
    return (
      <div className="auth-wrap">
        <div className="auth-card" style={{ textAlign: "center" }}>
          <h3>Account created</h3>
          <p style={{ color: "var(--text-muted)", marginTop: 8, fontSize: "0.88rem" }}>
            Welcome to KeyMood AI, {name}. Taking you to your dashboard...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-brand">
          <span style={{ width: 9, height: 9, borderRadius: "50%", background: "var(--accent)", display: "inline-block" }} />
          Create your account
        </div>

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="name">Name</label>
            <input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" />
          </div>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            <p style={{ fontSize: "0.72rem", color: "var(--text-faint)", marginTop: 4 }}>
              At least 10 characters with upper and lower case, a number and a symbol.
            </p>
          </div>
          <div className="field">
            <label htmlFor="confirm">Confirm password</label>
            <input id="confirm" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </div>
          <div className="field" style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
            <input
              type="checkbox"
              id="consent"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              style={{ width: "auto", marginTop: 3 }}
            />
            <label htmlFor="consent" style={{ fontWeight: 400, textTransform: "none", letterSpacing: 0 }}>
              I agree to the privacy policy and understand how my behavioral data is used.
            </label>
          </div>
          {error && <p style={{ color: "var(--danger)", fontSize: "0.8rem", marginBottom: 12 }}>{error}</p>}
          <button type="submit" className="btn btn-primary" style={{ width: "100%" }} disabled={busy}>
            {busy ? "Creating account..." : "Create account"}
          </button>
        </form>

        <p className="auth-footer-link">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  );
}
