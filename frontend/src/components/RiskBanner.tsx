import { useState } from "react";
import { Link } from "react-router-dom";
import type { RiskAssessment } from "../types";
import { crisisResourcesFor } from "../services/riskEngine";
import { useAppStore } from "../state/appStore";

export default function RiskBanner({ risk }: { risk: RiskAssessment }) {
  const [showResources, setShowResources] = useState(false);
  const guardians = useAppStore((s) => s.guardians);
  const notifyGuardian = useAppStore((s) => s.notifyGuardian);
  const country = useAppStore((s) => s.country);
  const [sent, setSent] = useState(false);

  const badgeClass = `badge badge-${risk.level}`;
  const levelLabel = risk.level === "low" ? "Low risk" : risk.level === "medium" ? "Medium risk" : "High risk";

  return (
    <div className="card">
      <span className={badgeClass}>{levelLabel}</span>
      <ul style={{ margin: "10px 0 0", paddingLeft: 18, fontSize: "0.83rem", color: "var(--text-muted)" }}>
        {risk.reasons.map((r, i) => (
          <li key={i}>{r}</li>
        ))}
      </ul>

      {risk.level === "high" && (
        <div style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--border)" }}>
          <p style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: 8 }}>
            If you're going through something difficult, you don't have to handle it alone.
          </p>
          <button className="btn btn-secondary" style={{ marginBottom: 10 }} onClick={() => setShowResources((s) => !s)}>
            {showResources ? "Hide" : "Show"} crisis resources
          </button>
          {showResources && (
            <ul style={{ fontSize: "0.83rem", marginBottom: 10, paddingLeft: 18 }}>
              {crisisResourcesFor(country).map((r) => (
                <li key={r.label}><strong>{r.label}:</strong> {r.value}</li>
              ))}
            </ul>
          )}

          {sent ? (
            <p style={{ fontSize: "0.83rem", color: "var(--accent-strong)" }}>Guardian notified.</p>
          ) : guardians.length > 0 ? (
            <button
              className="btn btn-danger"
              onClick={() => {
                notifyGuardian(guardians[0].id, risk.reasons.join(" "));
                setSent(true);
              }}
            >
              Notify {guardians[0].name}
            </button>
          ) : (
            <p style={{ fontSize: "0.83rem" }}>
              No guardian on file yet. <Link to="/guardian">Add one</Link> so this alert has somewhere to go.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
