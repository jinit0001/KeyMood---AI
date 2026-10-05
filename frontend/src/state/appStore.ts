import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  User,
  MoodReading,
  MoodLabel,
  Conversation,
  ChatMessage,
  Friend,
  FriendRequest,
  JournalEntry,
  Goal,
  Guardian,
  RiskAssessment,
} from "../types";
import {
  seedMoodHistory,
  seedJournal,
  seedGoals,
  seedGuardians,
  seedFLStatus,
} from "../services/mockData";
import { assessRisk } from "../services/riskEngine";
import {
  apiAcceptRequest,
  apiCompanionHistory,
  apiCompanionSend,
  apiConversations,
  apiCreateDirectConversation,
  apiDeclineRequest,
  apiDisplayNames,
  apiFriendIds,
  apiFriendRequests,
  apiLogin,
  apiLogout,
  apiMessages,
  apiProfile,
  apiRegister,
  apiSendFriendRequest,
  apiSendMessage,
  closeMessagingSocket,
  setAuthLostHandler,
  socketSend,
} from "../services/api";
import type { CompanionMessageDto, ConversationDto, MessageDto } from "../services/api";

interface AlertLogEntry {
  guardianId: string;
  guardianName: string;
  time: string;
  reason: string;
}

interface AppState {
  // auth (real backend: Module 1 + Module 2 profile)
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;

  // mood
  moodHistory: MoodReading[];
  currentMood: MoodReading | null;
  recordMoodReading: (reading: MoodReading) => RiskAssessment;

  // messaging (Module 9, real backend)
  conversations: Conversation[];
  loadConversations: () => Promise<void>;
  openConversation: (conversationId: string) => Promise<void>;
  sendMessage: (conversationId: string, text: string) => Promise<void>;
  receiveSocketMessage: (m: MessageDto) => Promise<void>;
  startConversationWith: (friendId: string) => Promise<string>;

  // AI companion (Module 10, real backend)
  companionMessages: ChatMessage[];
  loadCompanionHistory: () => Promise<void>;
  /** Resolves to true when the backend flagged the message as crisis-level. */
  sendCompanionMessage: (text: string) => Promise<boolean>;

  // social (Module 8, real backend)
  friends: Friend[];
  friendRequests: FriendRequest[];
  loadSocial: () => Promise<void>;
  sendFriendRequest: (userId: string) => Promise<void>;
  acceptFriendRequest: (id: string) => Promise<void>;
  rejectFriendRequest: (id: string) => Promise<void>;

  // journal
  journal: JournalEntry[];
  addJournalEntry: (entry: Omit<JournalEntry, "id" | "createdAt">) => void;

  // goals
  goals: Goal[];
  updateGoalProgress: (id: string, progress: number) => void;

  // guardians / SOS
  guardians: Guardian[];
  addGuardian: (g: Omit<Guardian, "id" | "notified">) => void;
  removeGuardian: (id: string) => void;
  notifyGuardian: (id: string, reason: string) => void;
  alertLog: AlertLogEntry[];
  sosActive: boolean;
  activateSOS: () => void;
  deactivateSOS: () => void;

  // federated learning (display-only simulation)
  flStatus: ReturnType<typeof seedFLStatus>;

  // settings
  settings: {
    keystrokeMonitoring: boolean;
    journalRiskAnalysis: boolean;
    guardianSharing: boolean;
  };
  updateSetting: (key: keyof AppState["settings"], value: boolean) => void;

  country: "IN" | "US" | "UK" | "INTL";
  setCountry: (c: AppState["country"]) => void;
}

const GREETING: ChatMessage = {
  id: "c0",
  from: "companion",
  text: "Hi, I'm your KeyMood companion. How are you feeling right now?",
  timestamp: new Date().toISOString(),
};

/** Server-owned data that must be wiped whenever the signed-in user changes. */
const SIGNED_OUT = {
  conversations: [] as Conversation[],
  companionMessages: [GREETING] as ChatMessage[],
  friends: [] as Friend[],
  friendRequests: [] as FriendRequest[],
};

function toUser(id: string, name: string, email: string): User {
  return { id, name, email, createdAt: new Date().toISOString(), avatarInitials: (name[0] || "U").toUpperCase() };
}

function toCompanionChat(m: CompanionMessageDto): ChatMessage {
  return { id: m.id, from: m.role === "user" ? "user" : "companion", text: m.content, timestamp: m.created_at };
}

function toChatMessage(m: MessageDto, me: string): ChatMessage {
  return { id: m.id, from: m.sender_id === me ? "user" : m.sender_id, text: m.content, timestamp: m.created_at };
}

function toConversation(d: ConversationDto, me: string, prev?: Conversation): Conversation {
  const others = d.members.filter((x) => x.user_id !== me);
  const name = d.type === "group" ? d.title || others.map((x) => x.display_name).join(", ") : others[0]?.display_name ?? "Unknown";
  return {
    id: d.id,
    name,
    online: false,
    type: d.type,
    memberIds: d.members.map((x) => x.user_id),
    lastMessage: d.last_message?.content ?? "",
    messages: prev?.messages ?? [],
  };
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      user: null,
      login: async (email, password) => {
        await apiLogin(email.trim().toLowerCase(), password);
        const profile = await apiProfile();
        set({ ...SIGNED_OUT, user: toUser(profile.user_id, profile.display_name, email.trim().toLowerCase()) });
      },
      register: async (name, email, password) => {
        const normalized = email.trim().toLowerCase();
        await apiRegister(name.trim(), normalized, password);
        // Register returns no tokens, so sign in right after.
        await apiLogin(normalized, password);
        const profile = await apiProfile();
        set({ ...SIGNED_OUT, user: toUser(profile.user_id, profile.display_name, normalized) });
      },
      logout: () => {
        void apiLogout(); // reads the refresh token synchronously, then clears local tokens
        closeMessagingSocket();
        set({ ...SIGNED_OUT, user: null });
      },

      moodHistory: seedMoodHistory(),
      currentMood: null,
      recordMoodReading: (reading) => {
        const history = [...get().moodHistory, reading].slice(-50);
        set({ moodHistory: history, currentMood: reading });
        const recentMoods: MoodLabel[] = history.slice(-6).map((r) => r.mood);
        return assessRisk(recentMoods);
      },

      conversations: [],
      loadConversations: async () => {
        const me = get().user?.id ?? "";
        const dtos = await apiConversations();
        const existing = new Map<string, Conversation>(get().conversations.map((c) => [c.id, c]));
        set({ conversations: dtos.map((d) => toConversation(d, me, existing.get(d.id))) });
      },
      openConversation: async (conversationId) => {
        const me = get().user?.id ?? "";
        const msgs = await apiMessages(conversationId);
        set({
          conversations: get().conversations.map((c) =>
            c.id === conversationId
              ? { ...c, messages: msgs.map((m) => toChatMessage(m, me)), lastMessage: msgs.length ? msgs[msgs.length - 1].content : c.lastMessage }
              : c
          ),
        });
      },
      sendMessage: async (conversationId, text) => {
        // Prefer the live socket; the server broadcasts the saved message back to
        // every member (including me), which receiveSocketMessage() appends.
        if (socketSend({ type: "message.send", conversation_id: conversationId, content: text })) return;
        const saved = await apiSendMessage(conversationId, text);
        await get().receiveSocketMessage(saved);
      },
      receiveSocketMessage: async (m) => {
        const me = get().user?.id ?? "";
        if (!get().conversations.some((c) => c.id === m.conversation_id)) {
          // a conversation someone else just started with me
          await get().loadConversations();
          await get().openConversation(m.conversation_id);
          return;
        }
        set({
          conversations: get().conversations.map((c) =>
            c.id !== m.conversation_id || c.messages.some((x) => x.id === m.id)
              ? c
              : { ...c, messages: [...c.messages, toChatMessage(m, me)], lastMessage: m.content }
          ),
        });
      },
      startConversationWith: async (friendId) => {
        await get().loadConversations();
        const found = get().conversations.find((c) => c.type === "direct" && c.memberIds.includes(friendId));
        if (found) return found.id;
        const created = await apiCreateDirectConversation(friendId);
        await get().loadConversations();
        return created.id;
      },

      companionMessages: [GREETING],
      loadCompanionHistory: async () => {
        const history = await apiCompanionHistory(100);
        set({ companionMessages: history.length ? history.map(toCompanionChat) : [GREETING] });
      },
      sendCompanionMessage: async (text) => {
        const optimistic: ChatMessage = {
          id: `pending-${Date.now()}`,
          from: "user",
          text,
          timestamp: new Date().toISOString(),
        };
        set({ companionMessages: [...get().companionMessages, optimistic] });
        try {
          const reply = await apiCompanionSend(text);
          set({ companionMessages: [...get().companionMessages, toCompanionChat(reply)] });
          return reply.flagged_crisis;
        } catch (err) {
          set({ companionMessages: get().companionMessages.filter((m) => m.id !== optimistic.id) });
          throw err;
        }
      },

      friends: [],
      friendRequests: [],
      loadSocial: async () => {
        const me = get().user?.id ?? "";
        const [friendIds, requests] = await Promise.all([apiFriendIds(), apiFriendRequests()]);
        const incoming = requests.filter((r) => r.receiver_id === me);
        const names = await apiDisplayNames([...friendIds, ...incoming.map((r) => r.sender_id)]);
        set({
          friends: friendIds.map((id) => ({ id, name: names[id] ?? "Unknown user", online: false })),
          friendRequests: incoming.map((r) => ({ id: r.id, name: names[r.sender_id] ?? "Unknown user" })),
        });
      },
      sendFriendRequest: async (userId) => {
        await apiSendFriendRequest(userId.trim());
      },
      acceptFriendRequest: async (id) => {
        await apiAcceptRequest(id);
        await get().loadSocial();
      },
      rejectFriendRequest: async (id) => {
        await apiDeclineRequest(id);
        await get().loadSocial();
      },

      journal: seedJournal(),
      addJournalEntry: (entry) =>
        set({
          journal: [
            { ...entry, id: crypto.randomUUID(), createdAt: new Date().toISOString() },
            ...get().journal,
          ],
        }),

      goals: seedGoals(),
      updateGoalProgress: (id, progress) =>
        set({
          goals: get().goals.map((g) => (g.id === id ? { ...g, progress } : g)),
        }),

      guardians: seedGuardians(),
      addGuardian: (g) =>
        set({
          guardians: [...get().guardians, { ...g, id: crypto.randomUUID(), notified: false }],
        }),
      removeGuardian: (id) =>
        set({ guardians: get().guardians.filter((g) => g.id !== id) }),
      notifyGuardian: (id, reason) => {
        const guardian = get().guardians.find((g) => g.id === id);
        if (!guardian) return;
        set({
          guardians: get().guardians.map((g) => (g.id === id ? { ...g, notified: true } : g)),
          alertLog: [
            {
              guardianId: id,
              guardianName: guardian.name,
              time: new Date().toISOString(),
              reason,
            },
            ...get().alertLog,
          ],
        });
      },
      alertLog: [],
      sosActive: false,
      activateSOS: () => set({ sosActive: true }),
      deactivateSOS: () => set({ sosActive: false }),

      flStatus: seedFLStatus(),

      settings: {
        keystrokeMonitoring: true,
        journalRiskAnalysis: true,
        guardianSharing: true,
      },
      updateSetting: (key, value) =>
        set({ settings: { ...get().settings, [key]: value } }),

      country: "IN",
      setCountry: (c) => set({ country: c }),
    }),
    {
      name: "keymood-demo-store",
      // Messages, companion chat and friends belong to the server and are
      // re-fetched after login - never cached in localStorage.
      partialize: (state) => {
        const { conversations, companionMessages, friends, friendRequests, ...rest } = state;
        void conversations; void companionMessages; void friends; void friendRequests;
        return rest;
      },
    }
  )
);

// A dead session (refresh token rejected) signs the user out everywhere.
setAuthLostHandler(() => useAppStore.setState({ ...SIGNED_OUT, user: null }));
