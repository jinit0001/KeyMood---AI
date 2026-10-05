import { useNavigate } from "react-router-dom";
import { useAppStore } from "../state/appStore";
import { COUNTRY_OPTIONS, type CountryCode } from "../services/riskEngine";

export default function Settings() {
  const settings = useAppStore((s) => s.settings);
  const updateSetting = useAppStore((s) => s.updateSetting);
  const flStatus = useAppStore((s) => s.flStatus);
  const logout = useAppStore((s) => s.logout);
  const country = useAppStore((s) => s.country);
  const setCountry = useAppStore((s) => s.setCountry);
  const navigate = useNavigate();

  return (
    <div>
      <div className="page-header">
        <h1>Settings</h1>
        <p>Manage your account, privacy, and preferences.</p>
      </div>

      <div className="section-title">Privacy</div>
      <div className="card" style={{ marginBottom: 16 }}>
        <ToggleRow
          label="Keystroke monitoring"
          description="Allow KeyMood to analyze typing behavior for mood detection."
          checked={settings.keystrokeMonitoring}
          onChange={(v) => updateSetting("keystrokeMonitoring", v)}
        />
        <ToggleRow
          label="Journal risk analysis"
          description="Scan journal entries for wellbeing risk signals."
          checked={settings.journalRiskAnalysis}
          onChange={(v) => updateSetting("journalRiskAnalysis", v)}
        />
        <ToggleRow
          label="Guardian sharing"
          description="Allow high-risk alerts to be sent to your trusted guardian."
          checked={settings.guardianSharing}
          onChange={(v) => updateSetting("guardianSharing", v)}
        />
        <div className="toggle-row">
          <div>
            <div style={{ fontSize: "0.87rem", fontWeight: 600 }}>Region</div>
            <div style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
              Used to show the right crisis resources for SOS and high-risk alerts.
            </div>
          </div>
          <select
            value={country}
            onChange={(e) => setCountry(e.target.value as CountryCode)}
            style={{ width: "auto" }}
          >
            {COUNTRY_OPTIONS.map((c) => (
              <option key={c.code} value={c.code}>{c.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="section-title">AI preferences &amp; federated learning</div>
      <div className="card" style={{ marginBottom: 16 }}>
        <p style={{ fontSize: "0.83rem", color: "var(--text-muted)", marginBottom: 12 }}>
          Your local model improves the shared global model without your raw data ever leaving your device —
          only encrypted, aggregated model updates are shared. Figures below are a demonstration/simulation.
        </p>
        <div className="feature-row"><span>Model version</span><span className="value">{flStatus.modelVersion}</span></div>
        <div className="feature-row"><span>Participants</span><span className="value">{flStatus.participants}</span></div>
        <div className="feature-row"><span>Training rounds</span><span className="value">{flStatus.trainingRounds}</span></div>
        <div className="feature-row"><span>Validation accuracy</span><span className="value">{(flStatus.validationAccuracy * 100).toFixed(0)}%</span></div>
      </div>

      <div className="section-title">Security</div>
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="feature-row"><span>Password</span><span className="value">Last changed --</span></div>
        <div className="feature-row"><span>Two-factor authentication</span><span className="value">Not enabled</span></div>
      </div>

      <div className="section-title">Account</div>
      <div className="card">
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button className="btn btn-secondary">Export data</button>
          <button className="btn btn-danger">Delete account</button>
          <button className="btn btn-secondary" onClick={() => { logout(); navigate("/login"); }}>Log out</button>
        </div>
      </div>
    </div>
  );
}

function ToggleRow({ label, description, checked, onChange }: { label: string; description: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="toggle-row">
      <div>
        <div style={{ fontSize: "0.87rem", fontWeight: 600 }}>{label}</div>
        <div style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>{description}</div>
      </div>
      <label className="switch">
        <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
        <span className="slider" />
      </label>
    </div>
  );
}
