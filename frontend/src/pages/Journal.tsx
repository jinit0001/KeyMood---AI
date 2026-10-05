import { useState } from "react";
import { useAppStore } from "../state/appStore";
import { MOOD_LABELS, MOOD_COLORS } from "../services/mockData";
import type { MoodLabel } from "../types";
import RiskBanner from "../components/RiskBanner";
import { assessRisk } from "../services/riskEngine";

export default function Journal() {
  const journal = useAppStore((s) => s.journal);
  const addJournalEntry = useAppStore((s) => s.addJournalEntry);
  const moodHistory = useAppStore((s) => s.moodHistory);

  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [mood, setMood] = useState<MoodLabel>("Calm");
  const [tags, setTags] = useState("");
  const [lastRisk, setLastRisk] = useState<ReturnType<typeof assessRisk> | null>(null);

  const handleSave = () => {
    if (!title.trim() || !text.trim()) return;
    addJournalEntry({
      title,
      text,
      mood,
      tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
    });
    const recentMoods = [...moodHistory.slice(-5).map((r) => r.mood), mood];
    setLastRisk(assessRisk(recentMoods, text));
    setTitle("");
    setText("");
    setTags("");
  };

  return (
    <div>
      <div className="page-header">
        <h1>Journal</h1>
        <p>A private space for your thoughts. Entries are analyzed for wellbeing signals, never shared without your consent.</p>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="field">
          <label>Title</label>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Give this entry a title" />
        </div>
        <div className="field">
          <label>Mood</label>
          <select value={mood} onChange={(e) => setMood(e.target.value as MoodLabel)}>
            {MOOD_LABELS.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Entry</label>
          <textarea rows={5} value={text} onChange={(e) => setText(e.target.value)} placeholder="What's on your mind?" />
        </div>
        <div className="field">
          <label>Tags (comma separated)</label>
          <input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="project, deadline, family" />
        </div>
        <button className="btn btn-primary" onClick={handleSave}>Save entry</button>
      </div>

      {lastRisk && <div style={{ marginBottom: 16 }}><RiskBanner risk={lastRisk} /></div>}

      <div className="section-title">Previous entries</div>
      {journal.length === 0 && <div className="empty-state">No entries yet.</div>}
      {journal.map((entry) => (
        <div key={entry.id} className="card" style={{ marginBottom: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div className="card-title">{entry.title}</div>
            <span className="badge" style={{ background: `${MOOD_COLORS[entry.mood]}22`, color: MOOD_COLORS[entry.mood] }}>
              {entry.mood}
            </span>
          </div>
          <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", margin: "8px 0" }}>{entry.text}</p>
          <div>
            {entry.tags.map((t) => <span key={t} className="tag">{t}</span>)}
          </div>
          <div style={{ fontSize: "0.72rem", color: "var(--text-faint)", marginTop: 8 }}>
            {new Date(entry.createdAt).toLocaleString()}
          </div>
        </div>
      ))}
    </div>
  );
}
