import { useAppStore } from "../state/appStore";

export default function Goals() {
  const goals = useAppStore((s) => s.goals);
  const updateGoalProgress = useAppStore((s) => s.updateGoalProgress);

  return (
    <div>
      <div className="page-header">
        <h1>Goals & Habits</h1>
        <p>Small, consistent steps connected to your emotional wellness.</p>
      </div>

      <div className="grid grid-2">
        {goals.map((g) => (
          <div key={g.id} className="card">
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <div className="card-title">{g.title}</div>
              <span className="tag">{g.streakDays} day streak</span>
            </div>
            <div style={{ margin: "10px 0" }}>
              <div className="progress-track">
                <div className="progress-fill" style={{ width: `${g.progress}%` }} />
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-faint)", marginTop: 4 }}>{g.progress}% complete</div>
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <button
                className="btn btn-secondary"
                onClick={() => updateGoalProgress(g.id, Math.max(0, g.progress - 10))}
              >
                -10%
              </button>
              <button
                className="btn btn-primary"
                onClick={() => updateGoalProgress(g.id, Math.min(100, g.progress + 10))}
              >
                Mark progress
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
