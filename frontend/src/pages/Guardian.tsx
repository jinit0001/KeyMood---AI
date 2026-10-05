import { useState } from "react";
import { useAppStore } from "../state/appStore";

export default function GuardianPage() {
  const guardians = useAppStore((s) => s.guardians);
  const addGuardian = useAppStore((s) => s.addGuardian);
  const removeGuardian = useAppStore((s) => s.removeGuardian);
  const notifyGuardian = useAppStore((s) => s.notifyGuardian);
  const alertLog = useAppStore((s) => s.alertLog);

  const [name, setName] = useState("");
  const [relation, setRelation] = useState("");
  const [contact, setContact] = useState("");
  const [testSentId, setTestSentId] = useState<string | null>(null);

  const handleAdd = () => {
    if (!name || !contact) return;
    addGuardian({ name, relation, contact });
    setName(""); setRelation(""); setContact("");
  };

  return (
    <div>
      <div className="page-header">
        <h1>Trusted Guardian</h1>
        <p>Guardian contact information is protected and only used for emergency escalation.</p>
      </div>

      <div className="section-title">Your guardians</div>
      {guardians.length === 0 && <div className="empty-state">No guardians added yet.</div>}
      <div className="grid grid-2" style={{ marginBottom: 16 }}>
        {guardians.map((g) => (
          <div key={g.id} className="card">
            <div className="card-title">{g.name}</div>
            <div className="card-subtitle">{g.relation || "Guardian"} &middot; {g.contact}</div>
            <div style={{ marginTop: 10, display: "flex", gap: 6, flexWrap: "wrap" }}>
              <button
                className="btn btn-secondary"
                onClick={() => { notifyGuardian(g.id, "Test notification"); setTestSentId(g.id); }}
              >
                Test notification
              </button>
              <button className="btn btn-ghost" onClick={() => removeGuardian(g.id)}>Remove</button>
            </div>
            {testSentId === g.id && (
              <p style={{ fontSize: "0.78rem", color: "var(--accent-strong)", marginTop: 6 }}>
                Test notification sent (demo mode).
              </p>
            )}
          </div>
        ))}
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">Add a guardian</div>
        <div className="grid grid-3" style={{ marginTop: 10 }}>
          <div className="field"><label>Name</label><input value={name} onChange={(e) => setName(e.target.value)} /></div>
          <div className="field"><label>Relationship</label><input value={relation} onChange={(e) => setRelation(e.target.value)} placeholder="Parent, friend..." /></div>
          <div className="field"><label>Phone or email</label><input value={contact} onChange={(e) => setContact(e.target.value)} /></div>
        </div>
        <button className="btn btn-primary" onClick={handleAdd}>Add guardian</button>
      </div>

      {alertLog.length > 0 && (
        <>
          <div className="section-title">Notification history</div>
          <div className="card">
            {alertLog.map((a, i) => (
              <div key={i} className="feature-row">
                <span>{a.guardianName} &middot; {a.reason}</span>
                <span className="value">{new Date(a.time).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
