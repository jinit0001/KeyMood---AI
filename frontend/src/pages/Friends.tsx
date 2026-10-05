import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAppStore } from "../state/appStore";

function errText(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback;
}

export default function Friends() {
  const user = useAppStore((s) => s.user);
  const friends = useAppStore((s) => s.friends);
  const requests = useAppStore((s) => s.friendRequests);
  const loadSocial = useAppStore((s) => s.loadSocial);
  const sendFriendRequest = useAppStore((s) => s.sendFriendRequest);
  const acceptFriendRequest = useAppStore((s) => s.acceptFriendRequest);
  const rejectFriendRequest = useAppStore((s) => s.rejectFriendRequest);
  const startConversationWith = useAppStore((s) => s.startConversationWith);
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [friendCode, setFriendCode] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    loadSocial().catch((err: unknown) => setError(errText(err, "Could not load friends.")));
  }, [loadSocial]);

  const run = async (action: () => Promise<void>, success?: string) => {
    setError("");
    setNotice("");
    try {
      await action();
      if (success) setNotice(success);
    } catch (err) {
      setError(errText(err, "Something went wrong."));
    }
  };

  const filtered = friends.filter((f) => f.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <div>
      <div className="page-header">
        <h1>Friends</h1>
        <p>People you're connected with on KeyMood.</p>
      </div>

      {error && <p style={{ color: "var(--danger)", fontSize: "0.82rem", marginBottom: 8 }}>{error}</p>}
      {notice && <p style={{ color: "var(--accent-strong)", fontSize: "0.82rem", marginBottom: 8 }}>{notice}</p>}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="section-title" style={{ marginTop: 0 }}>Add a friend</div>
        <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: 8 }}>
          Share your friend code with someone, or paste theirs here.
        </p>
        <div style={{ fontSize: "0.78rem", marginBottom: 10, wordBreak: "break-all" }}>
          Your friend code: <code>{user?.id}</code>{" "}
          <button
            className="btn btn-secondary"
            onClick={() => {
              void navigator.clipboard?.writeText(user?.id ?? "");
              setNotice("Friend code copied.");
            }}
          >
            Copy
          </button>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            placeholder="Paste a friend code..."
            value={friendCode}
            onChange={(e) => setFriendCode(e.target.value)}
          />
          <button
            className="btn btn-primary"
            disabled={!friendCode.trim()}
            onClick={() =>
              void run(async () => {
                await sendFriendRequest(friendCode);
                setFriendCode("");
              }, "Friend request sent.")
            }
          >
            Send request
          </button>
        </div>
      </div>

      {requests.length > 0 && (
        <>
          <div className="section-title">Friend requests</div>
          <div className="grid grid-2" style={{ marginBottom: 16 }}>
            {requests.map((r) => (
              <div key={r.id} className="card" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span className="avatar">{r.name.slice(0, 2).toUpperCase()}</span>
                  <div style={{ fontWeight: 600, fontSize: "0.87rem" }}>{r.name}</div>
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  <button className="btn btn-primary" onClick={() => void run(() => acceptFriendRequest(r.id))}>Accept</button>
                  <button className="btn btn-secondary" onClick={() => void run(() => rejectFriendRequest(r.id))}>Reject</button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      <div className="section-title">My friends</div>
      <div className="card" style={{ marginBottom: 12 }}>
        <input placeholder="Search friends..." value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>
      <div className="grid grid-2">
        {filtered.map((f) => (
          <div key={f.id} className="card" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="avatar">{f.name.slice(0, 2).toUpperCase()}</span>
              <div style={{ fontWeight: 600, fontSize: "0.87rem" }}>{f.name}</div>
            </div>
            <button
              className="btn btn-secondary"
              onClick={() =>
                void run(async () => {
                  const id = await startConversationWith(f.id);
                  navigate(`/messages?c=${id}`);
                })
              }
            >
              Message
            </button>
          </div>
        ))}
        {filtered.length === 0 && <div className="empty-state">No friends yet - add one with their friend code above.</div>}
      </div>
    </div>
  );
}
