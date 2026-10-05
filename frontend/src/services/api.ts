// Thin client for the KeyMood FastAPI backend (Modules 1-10).
//
// Only the modules the UI is wired to are covered here: auth, profile,
// companion (Module 10), messaging (Module 9) and social (Module 8).
// Everything else in the app still runs on local demo data.

const API_URL: string = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";
const API_PREFIX = "/api/v1";
const TOKEN_KEY = "keymood-auth-tokens";

// ---------------------------------------------------------------- tokens

interface Tokens {
  access: string;
  refresh: string;
}

function readTokens(): Tokens | null {
  try {
    const raw = localStorage.getItem(TOKEN_KEY);
    return raw ? (JSON.parse(raw) as Tokens) : null;
  } catch {
    return null;
  }
}

function writeTokens(t: Tokens | null): void {
  try {
    if (t) localStorage.setItem(TOKEN_KEY, JSON.stringify(t));
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // storage unavailable (private mode) - the session simply won't persist
  }
}

export function hasSession(): boolean {
  return readTokens() !== null;
}

export function clearSession(): void {
  writeTokens(null);
  closeMessagingSocket();
}

let authLostHandler: (() => void) | null = null;
/** The store registers this so a dead session (refresh failed) logs the user out. */
export function setAuthLostHandler(fn: () => void): void {
  authLostHandler = fn;
}

// ---------------------------------------------------------------- core fetch

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function toApiError(res: Response): Promise<ApiError> {
  let code = "ERROR";
  let message = `Request failed (${res.status})`;
  try {
    const body = await res.json();
    // Backend envelope (see error_handlers.py) or FastAPI's default {detail}
    const err = body?.error ?? body;
    if (typeof err?.message === "string") message = err.message;
    else if (typeof body?.detail === "string") message = body.detail;
    else if (Array.isArray(body?.detail) && body.detail[0]?.msg) message = String(body.detail[0].msg);
    if (typeof err?.code === "string") code = err.code;
    const details: unknown = err?.details?.errors;
    if (Array.isArray(details)) {
      const texts = details.filter((d): d is string => typeof d === "string");
      if (texts.length) message = `${message} ${texts.join(" ")}`;
    }
  } catch {
    // non-JSON error body
  }
  return new ApiError(res.status, code, message);
}

let refreshing: Promise<boolean> | null = null;

/** Exchange the refresh token for a new pair. Returns false if the session is dead. */
export function refreshTokens(): Promise<boolean> {
  if (refreshing) return refreshing;
  const tokens = readTokens();
  if (!tokens) return Promise.resolve(false);
  refreshing = (async () => {
    try {
      const res = await fetch(`${API_URL}${API_PREFIX}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: tokens.refresh }),
      });
      if (!res.ok) return false;
      const data = (await res.json()) as { access_token: string; refresh_token: string };
      writeTokens({ access: data.access_token, refresh: data.refresh_token });
      return true;
    } catch {
      return false;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

async function request<T>(path: string, init: RequestInit = {}, authed = true, retry = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (authed) {
    const tokens = readTokens();
    if (tokens) headers.set("Authorization", `Bearer ${tokens.access}`);
  }

  let res: Response;
  try {
    res = await fetch(`${API_URL}${API_PREFIX}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "NETWORK", `Cannot reach the KeyMood server at ${API_URL}. Is the backend running?`);
  }

  if (res.status === 401 && authed && retry) {
    if (await refreshTokens()) return request<T>(path, init, authed, false);
    clearSession();
    authLostHandler?.();
  }
  if (!res.ok) throw await toApiError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function post<T>(path: string, body?: unknown, authed = true): Promise<T> {
  return request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }, authed);
}

// ---------------------------------------------------------------- auth + profile

export interface Profile {
  user_id: string;
  display_name: string;
}

export async function apiRegister(displayName: string, email: string, password: string): Promise<void> {
  await post("/auth/register", { display_name: displayName, email, password }, false);
}

export async function apiLogin(email: string, password: string): Promise<void> {
  const data = await post<{ access_token: string; refresh_token: string }>("/auth/login", { email, password }, false);
  writeTokens({ access: data.access_token, refresh: data.refresh_token });
}

export function apiProfile(): Promise<Profile> {
  return request<Profile>("/profile/me");
}

export async function apiLogout(): Promise<void> {
  const tokens = readTokens();
  try {
    if (tokens) await post("/auth/logout", { refresh_token: tokens.refresh });
  } catch {
    // logging out locally must always succeed
  }
  clearSession();
}

// ---------------------------------------------------------------- companion (Module 10)

export interface CompanionMessageDto {
  id: string;
  session_id: string;
  role: "user" | "companion";
  content: string;
  flagged_crisis: boolean;
  created_at: string;
}

export function apiCompanionHistory(limit = 100): Promise<CompanionMessageDto[]> {
  return request<CompanionMessageDto[]>(`/companion/history?limit=${limit}`);
}

/** Returns the companion's reply. The user's own message is stored server-side. */
export function apiCompanionSend(content: string): Promise<CompanionMessageDto> {
  return post<CompanionMessageDto>("/companion/message", { content });
}

// ---------------------------------------------------------------- social (Module 8)

export interface FriendRequestDto {
  id: string;
  sender_id: string;
  receiver_id: string;
  status: string;
  created_at: string;
}

export function apiFriendIds(): Promise<string[]> {
  return request<string[]>("/social/friends?limit=100");
}

export function apiFriendRequests(): Promise<FriendRequestDto[]> {
  return request<FriendRequestDto[]>("/social/requests?status=pending");
}

export function apiSendFriendRequest(receiverId: string): Promise<FriendRequestDto> {
  return post<FriendRequestDto>("/social/requests", { receiver_id: receiverId });
}

export async function apiAcceptRequest(id: string): Promise<void> {
  await post(`/social/requests/${id}/accept`);
}

export async function apiDeclineRequest(id: string): Promise<void> {
  await post(`/social/requests/${id}/decline`);
}

export async function apiDisplayNames(ids: string[]): Promise<Record<string, string>> {
  if (ids.length === 0) return {};
  const qs = ids.map((i) => `ids=${encodeURIComponent(i)}`).join("&");
  return request<Record<string, string>>(`/social/names?${qs}`);
}

// ---------------------------------------------------------------- messaging (Module 9)

export interface ConversationDto {
  id: string;
  type: "direct" | "group";
  title: string | null;
  created_at: string;
  members: { user_id: string; display_name: string }[];
  last_message: { content: string; sender_id: string; created_at: string } | null;
}

export interface MessageDto {
  id: string;
  conversation_id: string;
  sender_id: string;
  content: string;
  created_at: string;
}

export function apiConversations(): Promise<ConversationDto[]> {
  return request<ConversationDto[]>("/messaging/conversations");
}

export function apiCreateDirectConversation(friendId: string): Promise<{ id: string }> {
  return post<{ id: string }>("/messaging/conversations", { type: "direct", member_ids: [friendId] });
}

export async function apiMessages(conversationId: string): Promise<MessageDto[]> {
  const page = await request<{ messages: MessageDto[]; has_more: boolean }>(
    `/messaging/conversations/${conversationId}/messages?limit=100`
  );
  // backend pages newest-first; the UI wants oldest-first
  return [...page.messages].reverse();
}

export function apiSendMessage(conversationId: string, content: string): Promise<MessageDto> {
  return post<MessageDto>(`/messaging/conversations/${conversationId}/messages`, { content });
}

// ---------------------------------------------------------------- messaging WebSocket

export interface SocketEvent {
  type: string;
  [key: string]: unknown;
}

let socket: WebSocket | null = null;
let socketWanted = false;
let socketHandler: ((e: SocketEvent) => void) | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

function wsBase(): string {
  return API_URL.replace(/^http/, "ws");
}

function connect(): void {
  const tokens = readTokens();
  if (!tokens || !socketWanted || socket) return;
  const ws = new WebSocket(`${wsBase()}${API_PREFIX}/messaging/ws?token=${encodeURIComponent(tokens.access)}`);
  socket = ws;
  ws.onmessage = (ev: MessageEvent) => {
    try {
      socketHandler?.(JSON.parse(String(ev.data)) as SocketEvent);
    } catch {
      // ignore malformed frames
    }
  };
  ws.onclose = () => {
    const wasCurrent = socket === ws;
    if (wasCurrent) socket = null;
    // a socket we closed on purpose (or replaced) must not trigger a reconnect
    if (!socketWanted || !wasCurrent) return;
    // access tokens are short-lived: refresh before reconnecting
    reconnectTimer = setTimeout(() => {
      void refreshTokens().then(() => connect());
    }, 2000);
  };
}

export function openMessagingSocket(onEvent: (e: SocketEvent) => void): void {
  socketHandler = onEvent;
  socketWanted = true;
  if (!socket) connect();
}

export function closeMessagingSocket(): void {
  socketWanted = false;
  socketHandler = null;
  if (reconnectTimer) clearTimeout(reconnectTimer);
  reconnectTimer = null;
  socket?.close();
  socket = null;
}

/** Sends over the live socket. Returns false if it isn't open (caller falls back to REST). */
export function socketSend(payload: Record<string, unknown>): boolean {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(payload));
    return true;
  }
  return false;
}
