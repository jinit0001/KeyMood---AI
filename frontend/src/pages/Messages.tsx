import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAppStore } from "../state/appStore";
import { closeMessagingSocket, openMessagingSocket } from "../services/api";

function errText(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback;
}

export default function Messages() {
  const conversations = useAppStore((s) => s.conversations);
  const loadConversations = useAppStore((s) => s.loadConversations);
  const openConversation = useAppStore((s) => s.openConversation);
  const sendMessage = useAppStore((s) => s.sendMessage);
  const receiveSocketMessage = useAppStore((s) => s.receiveSocketMessage);
  const [searchParams] = useSearchParams();
  const requestedId = searchParams.get("c");
  const [activeId, setActiveId] = useState(requestedId ?? "");
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  const active = conversations.find((c) => c.id === activeId) ?? conversations[0];
  const activeConvId = active?.id;

  // Initial load of the conversation list
  useEffect(() => {
    loadConversations()
      .catch((err: unknown) => setError(errText(err, "Could not load conversations.")))
      .finally(() => setLoading(false));
  }, [loadConversations]);

  // Live updates over the messaging WebSocket
  useEffect(() => {
    openMessagingSocket((ev) => {
      if (ev.type === "message.new") {
        void receiveSocketMessage({
          id: String(ev.id),
          conversation_id: String(ev.conversation_id),
          sender_id: String(ev.sender_id),
          content: String(ev.content),
          created_at: String(ev.created_at),
        });
      } else if (ev.type === "error") {
        setError(String(ev.message ?? "Message could not be sent."));
      }
    });
    return () => closeMessagingSocket();
  }, [receiveSocketMessage]);

  // Load history whenever a different conversation is selected
  useEffect(() => {
    if (!activeConvId) return;
    openConversation(activeConvId).catch((err: unknown) => setError(errText(err, "Could not load messages.")));
  }, [activeConvId, openConversation]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [active?.messages.length]);

  const handleSend = async () => {
    const toSend = text.trim();
    if (!toSend || !active) return;
    setText("");
    setError("");
    try {
      await sendMessage(active.id, toSend);
    } catch (err) {
      setText(toSend);
      setError(errText(err, "Could not send your message."));
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1>Messages</h1>
        <p>Connect with people, not just AI.</p>
      </div>

      {error && <p style={{ color: "var(--danger)", fontSize: "0.82rem", marginBottom: 8 }}>{error}</p>}

      {!loading && conversations.length === 0 ? (
        <div className="card empty-state">
          No conversations yet. <Link to="/friends">Add a friend</Link>, then press "Message" to start chatting.
        </div>
      ) : (
        <div className="chat-shell">
          <div className="chat-list">
            {conversations.map((c) => (
              <div
                key={c.id}
                className={`chat-list-item${c.id === active?.id ? " active" : ""}`}
                onClick={() => setActiveId(c.id)}
              >
                <span className="avatar" style={{ width: 30, height: 30, fontSize: "0.7rem" }}>
                  {c.name.slice(0, 2).toUpperCase()}
                </span>
                <div>
                  <div className="name">{c.name}</div>
                  <div className="preview">{c.lastMessage}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="chat-main">
            {active && (
              <>
                <div className="chat-header">
                  <span className="avatar" style={{ width: 30, height: 30, fontSize: "0.7rem" }}>
                    {active.name.slice(0, 2).toUpperCase()}
                  </span>
                  <div style={{ fontWeight: 600, fontSize: "0.88rem" }}>{active.name}</div>
                </div>
                <div className="chat-messages" ref={scrollRef}>
                  {active.messages.map((m) => (
                    <div key={m.id} className={`bubble ${m.from === "user" ? "mine" : "theirs"}`}>
                      {m.text}
                      <span className="time">
                        {new Date(m.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>
                  ))}
                </div>
                <div className="chat-input-row">
                  <input
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && void handleSend()}
                    placeholder={`Message ${active.name}...`}
                  />
                  <button className="btn btn-primary" onClick={() => void handleSend()}>Send</button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
