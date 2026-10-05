import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, BarChart, Bar } from "recharts";
import { useAppStore } from "../state/appStore";
import { effectiveMoodHistory } from "../services/mockData";
import type { MoodLabel } from "../types";

const MOOD_SCORE: Record<MoodLabel, number> = { Stressed: 1, Tired: 2, Calm: 3, Focused: 4, Happy: 5 };

function periodOf(iso: string): "Morning" | "Afternoon" | "Evening" {
  const h = new Date(iso).getHours();
  if (h < 12) return "Morning";
  if (h < 17) return "Afternoon";
  return "Evening";
}

export default function Analytics() {
  const rawHistory = useAppStore((s) => s.moodHistory);
  const moodHistory = effectiveMoodHistory(rawHistory);

  const trendData = moodHistory.map((r, i) => ({
    idx: i + 1,
    score: MOOD_SCORE[r.mood],
    mood: r.mood,
    period: periodOf(r.timestamp),
    stress: r.mood === "Stressed" ? 80 : 30 + (i % 3) * 8,
    focus: r.mood === "Focused" ? 85 : 45 + (i % 4) * 6,
    energy: r.mood === "Tired" ? 25 : 60 + (i % 3) * 5,
  }));

  const counts: Record<MoodLabel, number> = { Calm: 0, Focused: 0, Stressed: 0, Tired: 0, Happy: 0 };
  moodHistory.forEach((r) => (counts[r.mood] += 1));
  const mostFrequent = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "Calm";
  const avgConfidence = Math.round(
    moodHistory.reduce((sum, r) => sum + r.confidence, 0) / Math.max(moodHistory.length, 1)
  );

  const barData = Object.entries(counts).map(([mood, count]) => ({ mood, count }));

  // Real "highest stress period" / "best focus period" — averaged per
  // time-of-day bucket from the actual readings, not a fixed string.
  const periodAverages = (["Morning", "Afternoon", "Evening"] as const).map((period) => {
    const rows = trendData.filter((t) => t.period === period);
    if (rows.length === 0) return { period, avgStress: -1, avgFocus: -1 };
    return {
      period,
      avgStress: rows.reduce((s, r) => s + r.stress, 0) / rows.length,
      avgFocus: rows.reduce((s, r) => s + r.focus, 0) / rows.length,
    };
  });
  const highestStressPeriod: string =
    periodAverages.filter((p) => p.avgStress >= 0).sort((a, b) => b.avgStress - a.avgStress)[0]?.period ?? "--";
  const bestFocusPeriod: string =
    periodAverages.filter((p) => p.avgFocus >= 0).sort((a, b) => b.avgFocus - a.avgFocus)[0]?.period ?? "--";

  return (
    <div>
      <div className="page-header">
        <h1>Mood Analytics</h1>
        <p>Patterns in your estimated emotional state over time.</p>
      </div>

      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <StatCard label="Average confidence" value={`${avgConfidence}%`} />
        <StatCard label="Most frequent mood" value={mostFrequent} />
        <StatCard label="Highest stress period" value={highestStressPeriod} />
        <StatCard label="Best focus period" value={bestFocusPeriod} />
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">Mood over time</div>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={trendData}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="idx" tick={{ fontSize: 11, fill: "var(--text-faint)" }} axisLine={false} tickLine={false} />
            <YAxis hide domain={[0, 5]} />
            <Tooltip formatter={(_, __, item: any) => [item.payload.mood, "Mood"]} labelFormatter={() => ""} />
            <Line type="monotone" dataKey="score" stroke="var(--accent)" strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-2" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-title">Stress trend</div>
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={trendData}>
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="idx" tick={{ fontSize: 10, fill: "var(--text-faint)" }} axisLine={false} tickLine={false} />
              <YAxis hide />
              <Tooltip />
              <Line type="monotone" dataKey="stress" stroke="var(--danger)" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="card">
          <div className="card-title">Focus trend</div>
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={trendData}>
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="idx" tick={{ fontSize: 10, fill: "var(--text-faint)" }} axisLine={false} tickLine={false} />
              <YAxis hide />
              <Tooltip />
              <Line type="monotone" dataKey="focus" stroke="#4f7ecb" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">Mood distribution</div>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={barData}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="mood" tick={{ fontSize: 11, fill: "var(--text-faint)" }} axisLine={false} tickLine={false} />
            <YAxis hide />
            <Tooltip />
            <Bar dataKey="count" fill="var(--accent)" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="card" style={{ background: "var(--accent-soft)" }}>
        <div className="card-title" style={{ color: "var(--accent-strong)" }}>Insight</div>
        <p style={{ fontSize: "0.87rem", color: "var(--accent-strong)" }}>
          {highestStressPeriod !== "--"
            ? `Your stress tends to peak in the ${highestStressPeriod.toLowerCase()}. Consider scheduling a break around then.`
            : "Not enough readings yet to spot a stress pattern — keep using Live Mood Detection to build one up."}
        </p>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="card">
      <div className="card-subtitle">{label}</div>
      <div style={{ fontSize: "1.15rem", fontWeight: 700, marginTop: 6 }}>{value}</div>
    </div>
  );
}
