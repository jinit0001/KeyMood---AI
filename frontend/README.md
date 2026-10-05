# KeyMood AI — Frontend (Faculty Demo Build)

A multi-page React + TypeScript + Vite application demonstrating the KeyMood AI
product vision: keystroke-based mood detection, an AI companion, human
messaging, journaling, recommendations, goals, and an SOS/Guardian escalation
flow.

Auth, the AI companion, messaging and friends talk to the KeyMood FastAPI
backend (see the repository root README). The remaining pages (dashboard,
live mood, analytics, journal, goals, SOS/guardian, settings) still run on
local demo data in the browser.

Set the backend address in `.env` (copy `.env.example`):

```
VITE_API_URL=http://localhost:8000
```

---

## 1. Install dependencies

```
npm install
```

## 2. Run locally (development)

```
npm run dev
```

Opens at `http://localhost:5173`. Hot-reloads on save.

## 3. Build for production / deployment

```
npm run build
npm run preview
```

`npm run build` outputs static files to `dist/` — deployable to any static
host (Vercel, Netlify, GitHub Pages, etc.) with zero server-side setup,
since there is no real backend call in this build.

## 4. Backend

**Not included in this build.** The original project plan calls for FastAPI +
PostgreSQL + Redis + WebSockets etc. (see the wider KeyMood AI architecture
notes). None of that is required to run or demo this frontend — everything
below runs on in-memory mock services instead.

## 5. Environment variables

None required for the demo build. If/when the real backend and an LLM-backed
AI Companion are wired in, you'd add something like:

```
VITE_API_BASE_URL=https://your-backend-url
```

No API keys belong in frontend code — that integration point is a backend
concern (see `src/services/companionEngine.ts` for where the swap happens).

---

## What's real vs. demo/mock in this build

| Area | Status |
|---|---|
| Multi-page navigation, routing, protected routes | Real |
| Login / Register | **Demo auth** — any non-empty credentials succeed; state persists via `localStorage` (zustand `persist`). Swap in `src/pages/Login.tsx` / `Register.tsx` for real `POST /api/v1/auth/...` calls. |
| Live keystroke tracking (typing speed, hold time, inter-key delay, error rate, rhythm stability) | **Real, computed live in the browser** from actual keyboard events (`src/services/keystrokeEngine.ts`). No typed text is ever stored — only timing data. |
| Mood inference from keystroke features | Real rule-based classifier (not the trained ML model from the original minor project) — deterministic thresholds standing in for a real model. |
| Risk scoring (SOS trigger logic) | Real logic — combines mood trend + crisis-language keyword detection (`src/services/riskEngine.ts`). Rule-based, not clinical. |
| AI Companion chat | **Demo** — deterministic local response engine (`src/services/companionEngine.ts`), not a live LLM call. Structured so an OpenAI-compatible API call can replace it. |
| Human-to-human messaging | **Demo** — local mock conversations, no real backend/WebSocket. |
| Friends, Journal, Recommendations, Goals, Guardian contacts | **Demo data + working local state** — fully interactive (add/remove/update), persisted to `localStorage`, but not synced to any server. |
| SOS flow | **Demo** — simulates risk assessment + guardian notification with a delay; does not send real SMS/email. |
| Federated learning panel (Settings page) | **Simulated numbers**, clearly labeled as demonstration data. |

---

## Known limitations

- No real backend — this is a frontend-only demo build.
- Mood inference is rule-based, not the trained ML model from the earlier
  minor-project work — swapping in a real model is a backend/API concern.
- Emergency alerts are simulated (logged in-app), not real SMS/email —
  wiring up Twilio/SMTP is the next concrete step, and the guardian
  notification code (`src/state/appStore.ts`, `notifyGuardian`) is already
  structured for that swap.
- Data resets if `localStorage` is cleared — there is no server-side
  persistence yet.
- The crisis-keyword detection is intentionally simple/coarse — it's a
  triage layer meant to route people to real human help, not a diagnostic
  tool.

---

## Faculty demonstration walkthrough

1. **Login** with any email/password (or "Continue with Google") →
   lands on **Dashboard**.
2. **Dashboard** — show the current mood card, the mood trend chart, the
   wellness summary cards, and the AI insight line.
3. **Live Mood Detection** — click "Start monitoring," type a sentence into
   the box, and point out the live feature readout (WPM, hold time,
   inter-key delay, error rate, rhythm stability) updating in real time.
   Click "Stop monitoring" to lock in a reading and show the risk badge.
4. **AI Companion** — have a short exchange; show the current-mood context
   line and how replies adapt to mood.
5. **Messages** — switch between conversations to show it isn't just an
   AI-only product.
6. **Analytics** — show the mood/stress/focus trend charts and the
   auto-generated insight line.
7. **Journal** — write an entry, show it appearing in the history below.
8. **Goals**, **Recommendations**, **Friends** — quick pass through to show
   they're live and interactive, not static mockups.
9. **Guardian** — add a guardian contact, click "Test notification."
10. **SOS** — walk through Activate → confirmation → risk assessment →
    guardian notified. Explicitly mention this is a simulated notification
    for the demo, and that the app is not a replacement for emergency
    services.
11. **Settings** — show the privacy toggles and the federated learning
    status panel, and explain those numbers are a simulation of the
    federated learning architecture that is part of the wider system design.

Throughout, it's fine — and honestly a stronger story — to be upfront that
this is a working, running front-end demonstrating the full product
vision, backed by mock data where the real backend doesn't exist yet, with
clear seams (`src/services/`) for wiring in FastAPI, WebSockets, and a real
ML model next.
