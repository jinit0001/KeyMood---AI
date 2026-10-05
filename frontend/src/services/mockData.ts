import type {
  MoodLabel,
  MoodReading,
  JournalEntry,
  Recommendation,
  Goal,
  Guardian,
  FLStatus,
} from "../types";

export const MOOD_LABELS: MoodLabel[] = ["Calm", "Focused", "Stressed", "Tired", "Happy"];

export const MOOD_COLORS: Record<MoodLabel, string> = {
  Calm: "#4f9d8f",
  Focused: "#4f7ecb",
  Stressed: "#d6644d",
  Tired: "#9b8f6b",
  Happy: "#e3b23c",
};

function iso(hoursAgo: number): string {
  return new Date(Date.now() - hoursAgo * 3600 * 1000).toISOString();
}

function atHour(hour: number, minute = 0): string {
  const d = new Date();
  d.setHours(hour, minute, 0, 0);
  return d.toISOString();
}

// Fixed clock times spanning morning -> evening, so the trend chart and
// "highest stress period" / "best focus period" stats have real variety
// to compute from, regardless of what time the demo happens to run.
export function seedMoodHistory(): MoodReading[] {
  const sequence: { mood: MoodLabel; hour: number; minute: number; confidence: number }[] = [
    { mood: "Calm", hour: 8, minute: 0, confidence: 82 },
    { mood: "Focused", hour: 9, minute: 30, confidence: 88 },
    { mood: "Focused", hour: 10, minute: 45, confidence: 91 },
    { mood: "Focused", hour: 11, minute: 30, confidence: 85 },
    { mood: "Stressed", hour: 14, minute: 0, confidence: 74 },
    { mood: "Stressed", hour: 15, minute: 15, confidence: 80 },
    { mood: "Stressed", hour: 16, minute: 0, confidence: 77 },
    { mood: "Tired", hour: 19, minute: 0, confidence: 69 },
    { mood: "Tired", hour: 20, minute: 30, confidence: 71 },
  ];
  return sequence.map((s) => ({
    mood: s.mood,
    confidence: s.confidence,
    timestamp: atHour(s.hour, s.minute),
    source: "seed" as const,
    features: {
      typingSpeedWpm: 40 + Math.random() * 30,
      avgHoldTimeMs: 80 + Math.random() * 40,
      interKeyDelayMs: 120 + Math.random() * 100,
      errorRate: Math.random() * 0.1,
      rhythmStability: 60 + Math.random() * 35,
    },
  }));
}

export function seedJournal(): JournalEntry[] {
  return [
    {
      id: "j1",
      title: "Late night before submission",
      text: "Felt a bit overwhelmed prepping the demo, but the risk-alert flow finally works end to end.",
      mood: "Stressed",
      tags: ["project", "deadline"],
      createdAt: iso(20),
    },
    {
      id: "j2",
      title: "Good focus session",
      text: "Two hours of deep work on the analytics page, felt great.",
      mood: "Focused",
      tags: ["work"],
      createdAt: iso(50),
    },
  ];
}

export function recommendationsFor(mood: MoodLabel): Recommendation[] {
  const map: Record<MoodLabel, Recommendation[]> = {
    Stressed: [
      { id: "r1", title: "5-minute breathing exercise", description: "A short box-breathing session to reset your nervous system.", forMood: "Stressed" },
      { id: "r2", title: "Take a short walk", description: "Even 10 minutes outside can lower stress markers.", forMood: "Stressed" },
      { id: "r3", title: "Break the task down", description: "Split what you're working on into smaller, clearer steps.", forMood: "Stressed" },
      { id: "r4", title: "Talk to someone", description: "Message a friend or your AI companion about what's on your mind.", forMood: "Stressed" },
    ],
    Tired: [
      { id: "r5", title: "Take a proper break", description: "Step away from the screen for at least 15 minutes.", forMood: "Tired" },
      { id: "r6", title: "Hydrate", description: "Dehydration is a common hidden driver of fatigue.", forMood: "Tired" },
      { id: "r7", title: "Reduce screen time tonight", description: "Consider wrapping up work earlier than usual.", forMood: "Tired" },
      { id: "r8", title: "Protect your sleep window", description: "Aim for a consistent wind-down routine.", forMood: "Tired" },
    ],
    Focused: [
      { id: "r9", title: "Keep going", description: "You're in a strong deep-work state — protect it.", forMood: "Focused" },
      { id: "r10", title: "Minimize distractions", description: "Silence notifications for the next block of time.", forMood: "Focused" },
      { id: "r11", title: "Schedule your next break", description: "Plan a break before focus naturally fades.", forMood: "Focused" },
    ],
    Happy: [
      { id: "r12", title: "Note what helped", description: "Write down what contributed to this mood in your journal.", forMood: "Happy" },
      { id: "r13", title: "Connect with someone", description: "Good moments are worth sharing.", forMood: "Happy" },
      { id: "r14", title: "Keep the habit going", description: "Whatever led here, consider making it routine.", forMood: "Happy" },
    ],
    Calm: [
      { id: "r15", title: "Good baseline", description: "This is a solid state to plan or reflect from.", forMood: "Calm" },
      { id: "r16", title: "Set an intention", description: "A calm moment is a good time to set your next goal.", forMood: "Calm" },
    ],
  };
  return map[mood];
}

export function seedGoals(): Goal[] {
  return [
    { id: "g1", title: "Study 2 hours", progress: 70, streakDays: 4 },
    { id: "g2", title: "Sleep before 11 PM", progress: 40, streakDays: 1 },
    { id: "g3", title: "Take 3 breaks", progress: 90, streakDays: 6 },
    { id: "g4", title: "Exercise", progress: 30, streakDays: 2 },
    { id: "g5", title: "Journal daily", progress: 60, streakDays: 3 },
  ];
}

export function seedGuardians(): Guardian[] {
  return [
    { id: "guardian-1", name: "Mom", relation: "Parent", contact: "+91 90000 00000", notified: false },
  ];
}

/**
 * Once the user has taken at least one live keystroke reading, stats and
 * charts should reflect their own session rather than being diluted by
 * the canned demo history shown before they've used the app.
 */
export function effectiveMoodHistory<T extends { source?: "seed" | "live" }>(history: T[]): T[] {
  const live = history.filter((r) => r.source === "live");
  return live.length > 0 ? live : history;
}

export function seedFLStatus(): FLStatus {
  return {
    modelVersion: "v0.4.2-sim",
    participants: 4,
    trainingRounds: 12,
    validationAccuracy: 0.81,
  };
}
