export type MoodLabel = "Calm" | "Focused" | "Stressed" | "Tired" | "Happy";

export interface MoodReading {
  mood: MoodLabel;
  confidence: number; // 0-100
  timestamp: string; // ISO
  features: KeystrokeFeatures;
  source?: "seed" | "live"; // "seed" = demo data shown before you've used the app; "live" = your own reading
}

export interface KeystrokeFeatures {
  typingSpeedWpm: number;
  avgHoldTimeMs: number;
  interKeyDelayMs: number;
  errorRate: number; // 0-1
  rhythmStability: number; // 0-100, higher = more stable
}

export interface User {
  id: string;
  name: string;
  email: string;
  createdAt: string;
  avatarInitials: string;
}

export interface ChatMessage {
  id: string;
  from: "user" | "companion" | string; // "user" = me; otherwise the other person's id (human chat)
  text: string;
  timestamp: string;
}

export interface Conversation {
  id: string;
  name: string;
  online: boolean;
  lastMessage: string;
  messages: ChatMessage[];
  memberIds: string[]; // every member's user id, including mine
  type: "direct" | "group";
}

export interface Friend {
  id: string;
  name: string;
  online: boolean;
  mutualMood?: MoodLabel;
}

export interface FriendRequest {
  id: string; // friend-request id (not the sender's user id)
  name: string;
}

export interface JournalEntry {
  id: string;
  title: string;
  text: string;
  mood: MoodLabel;
  tags: string[];
  createdAt: string;
}

export interface Recommendation {
  id: string;
  title: string;
  description: string;
  forMood: MoodLabel;
}

export interface Goal {
  id: string;
  title: string;
  progress: number; // 0-100
  streakDays: number;
}

export interface Guardian {
  id: string;
  name: string;
  relation: string;
  contact: string;
  notified: boolean;
}

export interface RiskAssessment {
  level: "low" | "medium" | "high";
  reasons: string[];
}

export interface FLStatus {
  modelVersion: string;
  participants: number;
  trainingRounds: number;
  validationAccuracy: number;
}
