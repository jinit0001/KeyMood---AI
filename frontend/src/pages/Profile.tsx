import { useState } from "react";
import { useAppStore } from "../state/appStore";

export default function Profile() {
  const user = useAppStore((s) => s.user);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(user?.name ?? "");

  return (
    <div>
      <div className="page-header">
        <h1>Profile</h1>
        <p>Your account information.</p>
      </div>

      <div className="card" style={{ maxWidth: 480 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 18 }}>
          <span className="avatar" style={{ width: 56, height: 56, fontSize: "1.3rem" }}>
            {user?.avatarInitials}
          </span>
          <div>
            <div style={{ fontWeight: 700 }}>{user?.name}</div>
            <div style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>{user?.email}</div>
          </div>
        </div>

        {editing ? (
          <>
            <div className="field">
              <label>Name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <button className="btn btn-primary" onClick={() => setEditing(false)}>Save</button>
          </>
        ) : (
          <>
            <div className="feature-row"><span>Name</span><span className="value">{user?.name}</span></div>
            <div className="feature-row"><span>Email</span><span className="value">{user?.email}</span></div>
            <div className="feature-row">
              <span>Account created</span>
              <span className="value">{user ? new Date(user.createdAt).toLocaleDateString() : "--"}</span>
            </div>
            <button className="btn btn-secondary" style={{ marginTop: 12 }} onClick={() => setEditing(true)}>
              Edit profile
            </button>
          </>
        )}
      </div>
    </div>
  );
}
