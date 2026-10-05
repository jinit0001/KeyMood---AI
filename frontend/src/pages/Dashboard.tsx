import { Link } from "react-router-dom";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { useAppStore } from "../state/appStore";
import { MOOD_COLORS, effectiveMoodHistory } from "../services/mockData";
import type { MoodLabel } from "../types";

const MOOD_SCORE: Record<MoodLabel, number> = { Stressed: 1, Tired: 2, Calm: 3, Focused: 4, Happy: 5 };

function timeOfDayLabel(iso: string) {
  const h = new Date(iso).getHours();
  if (h < 12) return "Morning";
  if (h < 17) return "Afternoon";
  return "Evening";
}

export default function Dashboard() {
  const user = useAppStore((s) => s.user);
  const rawHistory = useAppStore((s) => s.moodHistory);
  const moodHistory = effectiveMoodHistory(rawHistory);
  const latest = moodHistory[moodHistory.length - 1];
  const mood: MoodLabel = latest?.mood ?? "Calm";
  const confidence = latest?.confidence ?? 80;

  const chartData = moodHistory.slice(-9).map((r) => ({
    label: timeOfDayLabel(r.timestamp),
    score: MOOD_SCORE[r.mood],
    mood: r.mood,
  }));

  const stress = mood === "Stressed" ? 72 : 34;
  const focus = mood === "Focused" ? 81 : 52;
  const energy = mood === "Tired" ? 28 : 66;
  const stability = 70;

  const insight = insightFor(mood);

  return (
    <div>
      <div className="page-header">
        <h1>Good {greetingWord()}, {user?.name}</h1>
        <p>Here's how you're doing today.</p>
      </div>

      <div className="grid grid-2" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-title">Current mood</div>
          <div className="mood-display" style={{ textAlign: "left", padding: "10px 0" }}>
            <span className="pulse-dot" style={{ background: MOOD_COLORS[mood] }} />
            <span className="label" style={{ color: MOOD_COLORS[mood] }}>{mood.toUpperCase()}</span>
            <div className="confidence">Confidence: {confidence}%</div>
          </div>
          <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
            Your typing patterns currently indicate a {mood.toLowerCase()} state.
          </p>
        </div>

        <div className="card">
          <div className="card-title">Mood trend today</div>
          <div className="card-subtitle" style={{ marginBottom: 8 }}>Behavioral signal, not a diagnosis</div>
          <ResponsiveContainer width="100%" height={130}>
            <LineChart data={chartData}>
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: "var(--text-faint)" }} axisLine={false} tickLine={false} />
              <YAxis hide domain={[0, 5]} />
              <Tooltip formatter={(_, __, item: any) => [item.payload.mood, "Mood"]} />
              <Line type="monotone" dataKey="score" stroke="var(--accent)" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="section-title">Wellness summary</div>
      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <SummaryCard label="Stress" value={stress} />
        <SummaryCard label="Focus" value={focus} />
        <SummaryCard label="Energy" value={energy} />
        <SummaryCard label="Mood stability" value={stability} />
      </div>

      <div className="card" style={{ marginBottom: 16, background: "var(--accent-soft)", border: "1px solid var(--accent)" }}>
        <div className="card-title" style={{ color: "var(--accent-strong)" }}>AI insight</div>
        <p style={{ fontSize: "0.87rem", color: "var(--accent-strong)" }}>{insight}</p>
      </div>

      <div className="section-title">Quick actions</div>
      <div className="grid grid-4">
        <QuickAction to="/mood" label="Detect mood" />
        <QuickAction to="/companion" label="Talk to companion" />
        <QuickAction to="/messages" label="Message a friend" />
        <QuickAction to="/journal" label="Write journal" />
      </div>
      <div style={{ marginTop: 12 }}>
        <Link to="/sos" className="btn btn-danger">Emergency support (SOS)</Link>
      </div>
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="card">
      <div className="card-subtitle">{label}</div>
      <div style={{ fontSize: "1.3rem", fontWeight: 700, margin: "6px 0" }}>{value}%</div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

function QuickAction({ to, label }: { to: string; label: string }) {
  return (
    <Link to={to} className="card" style={{ textDecoration: "none", textAlign: "center", fontSize: "0.85rem", fontWeight: 600 }}>
      {label}
    </Link>
  );
}

function greetingWord() {
  const h = new Date().getHours();
  if (h < 12) return "morning";
  if (h < 17) return "afternoon";
  return "evening";
}

function insightFor(mood: MoodLabel): string {
  switch (mood) {
    case "Stressed":
      return "Your stress level appears slightly higher than usual this afternoon. A short break or breathing exercise may help.";
    case "Tired":
      return "Your energy readings have dipped compared to earlier today. Consider a short break before your next task.";
    case "Focused":
      return "You're holding a strong focus streak today — a good window for deep work.";
    case "Happy":
      return "Today's readings are trending positive. Worth noting what's contributing to it.";
    default:
      return "Your readings look steady today. A good moment to plan ahead or check in with a friend.";
  }
}
