import { useState } from "react";
import { Link } from "react-router-dom";
import { useAppStore } from "../state/appStore";
import { crisisResourcesFor, COUNTRY_OPTIONS, type CountryCode } from "../services/riskEngine";

export default function SOS() {
  const sosActive = useAppStore((s) => s.sosActive);
  const activateSOS = useAppStore((s) => s.activateSOS);
  const deactivateSOS = useAppStore((s) => s.deactivateSOS);
  const guardians = useAppStore((s) => s.guardians);
  const notifyGuardian = useAppStore((s) => s.notifyGuardian);
  const currentMood = useAppStore((s) => s.currentMood);
  const country = useAppStore((s) => s.country);
  const setCountry = useAppStore((s) => s.setCountry);

  const [confirming, setConfirming] = useState(false);
  const [stage, setStage] = useState<"idle" | "assessing" | "notified">("idle");

  const handleActivate = () => {
    activateSOS();
    setStage("assessing");
    setTimeout(() => {
      guardians.forEach((g) => notifyGuardian(g.id, "SOS activated by user"));
      setStage("notified");
    }, 1400);
  };

  const handleReset = () => {
    deactivateSOS();
    setStage("idle");
    setConfirming(false);
  };

  return (
    <div>
      <div className="page-header">
        <h1>SOS</h1>
        <p>If you feel that you or someone else may be in immediate danger, use the emergency support flow.</p>
      </div>

      {!sosActive ? (
        <div className="sos-hero">
          <h2 style={{ color: "var(--danger)" }}>Emergency Support</h2>
          <p style={{ fontSize: "0.87rem", color: "var(--text-muted)", marginTop: 8, maxWidth: 420, marginInline: "auto" }}>
            This activates a risk assessment and notifies your trusted guardian. KeyMood AI is not a substitute
            for emergency services — if you or someone else is in immediate danger, please contact local emergency
            services directly.
          </p>

          {!confirming ? (
            <button className="sos-button" onClick={() => setConfirming(true)}>ACTIVATE SOS</button>
          ) : (
            <div style={{ marginTop: 20 }}>
              <p style={{ fontWeight: 600, marginBottom: 12 }}>Are you sure you want to activate SOS?</p>
              <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
                <button className="btn btn-danger" onClick={handleActivate}>Yes, activate</button>
                <button className="btn btn-secondary" onClick={() => setConfirming(false)}>Cancel</button>
              </div>
            </div>
          )}

          <div style={{ marginTop: 24, textAlign: "left", maxWidth: 420, marginInline: "auto" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
              <p style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--text-muted)" }}>
                Immediate resources:
              </p>
              <select
                value={country}
                onChange={(e) => setCountry(e.target.value as CountryCode)}
                style={{ width: "auto", fontSize: "0.78rem", padding: "4px 8px" }}
              >
                {COUNTRY_OPTIONS.map((c) => (
                  <option key={c.code} value={c.code}>{c.label}</option>
                ))}
              </select>
            </div>
            <ul style={{ fontSize: "0.83rem", paddingLeft: 18 }}>
              {crisisResourcesFor(country).map((r) => (
                <li key={r.label}><strong>{r.label}:</strong> {r.value}</li>
              ))}
            </ul>
          </div>
        </div>
      ) : (
        <div className="sos-active-banner">
          <h2>SOS active</h2>
          {stage === "assessing" && <p style={{ marginTop: 8, fontSize: "0.9rem" }}>Running risk assessment...</p>}
          {stage === "notified" && (
            <>
              <p style={{ marginTop: 8, fontSize: "0.9rem" }}>
                Risk assessment complete.{" "}
                {guardians.length > 0
                  ? `Your guardian(s) have been notified (${guardians.map((g) => g.name).join(", ")}).`
                  : "No guardian is on file — consider adding one so alerts have somewhere to go."}
              </p>
              <p style={{ marginTop: 6, fontSize: "0.85rem", opacity: 0.9 }}>
                Current behavioral signal: {currentMood?.mood ?? "Unknown"} ({currentMood?.confidence ?? "--"}% confidence)
              </p>
              <div style={{ marginTop: 14, display: "flex", gap: 10 }}>
                <button className="btn btn-secondary" onClick={handleReset}>Close</button>
                <Link to="/guardian" className="btn btn-secondary">Manage guardians</Link>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
