import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAppStore } from "../state/appStore";
import { crisisResourcesFor } from "../services/riskEngine";
import { MOOD_COLORS } from "../services/mockData";

export default function Companion() {
  const messages = useAppStore((s) => s.companionMessages);
  const sendCompanionMessage = useAppStore((s) => s.sendCompanionMessage);
  const loadCompanionHistory = useAppStore((s) => s.loadCompanionHistory);
  const currentMood = useAppStore((s) => s.currentMood);
  const country = useAppStore((s) => s.country);
  const [text, setText] = useState("");
  const [typing, setTyping] = useState(false);
  const [error, setError] = useState("");
  const [crisis, setCrisis] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadCompanionHistory().catch((err: unknown) =>
      setError(err instanceof Error ? err.message : "Could not load your chat history.")
    );
  }, [loadCompanionHistory]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, typing]);

  const handleSend = async () => {
    const toSend = text.trim();
    if (!toSend || typing) return;
    setText("");
    setError("");
    setTyping(true);
    try {
      const flagged = await sendCompanionMessage(toSend);
      if (flagged) setCrisis(true);
    } catch (err) {
      setText(toSend); // give the message back so nothing typed is lost
      setError(err instanceof Error ? err.message : "Could not send your message.");
    } finally {
      setTyping(false);
    }
  };

  const mood = currentMood?.mood ?? "Calm";

  return (
    <div>
      <div className="page-header">
        <h1>KeyMood Companion</h1>
        <p>Your supportive AI companion</p>
      </div>

      <div className="card" style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 10 }}>
        <span className="pulse-dot" style={{ background: MOOD_COLORS[mood] }} />
        <span style={{ fontSize: "0.85rem" }}>
          Current mood: <strong>{mood}</strong> &middot; Confidence: {currentMood?.confidence ?? 80}%
        </span>
      </div>

      {crisis && (
        <div className="card" style={{ marginBottom: 12, borderColor: "var(--danger)" }}>
          <p style={{ fontSize: "0.88rem", fontWeight: 600, marginBottom: 6 }}>
            You don't have to go through this alone.
          </p>
          <ul style={{ fontSize: "0.83rem", margin: "0 0 8px", paddingLeft: 18 }}>
            {crisisResourcesFor(country).map((r) => (
              <li key={r.label}><strong>{r.label}:</strong> {r.value}</li>
            ))}
          </ul>
          <p style={{ fontSize: "0.83rem" }}>
            You can also <Link to="/sos">open the SOS page</Link> to reach your trusted contacts.
          </p>
        </div>
      )}

      {error && <p style={{ color: "var(--danger)", fontSize: "0.82rem", marginBottom: 8 }}>{error}</p>}

      <div className="chat-shell" style={{ gridTemplateColumns: "1fr" }}>
        <div className="chat-main">
          <div className="chat-messages" ref={scrollRef}>
            {messages.map((m) => (
              <div key={m.id} className={`bubble ${m.from === "user" ? "mine" : "theirs"}`}>
                {m.text}
                <span className="time">{new Date(m.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
              </div>
            ))}
            {typing && <div className="typing-indicator">Companion is typing...</div>}
          </div>
          <div className="chat-input-row">
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void handleSend()}
              placeholder="Share what's on your mind..."
            />
            <button className="btn btn-primary" onClick={() => void handleSend()} disabled={typing}>Send</button>
          </div>
        </div>
      </div>
    </div>
  );
}
