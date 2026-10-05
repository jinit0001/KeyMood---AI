import { useAppStore } from "../state/appStore";
import { recommendationsFor } from "../services/mockData";

export default function Recommendations() {
  const currentMood = useAppStore((s) => s.currentMood);
  const mood = currentMood?.mood ?? "Calm";
  const recs = recommendationsFor(mood);

  return (
    <div>
      <div className="page-header">
        <h1>Recommendations</h1>
        <p>Personalized for your current mood: <strong>{mood}</strong></p>
      </div>

      <div className="grid grid-2">
        {recs.map((r) => (
          <div key={r.id} className="card">
            <div className="card-title">{r.title}</div>
            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: 6 }}>{r.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
