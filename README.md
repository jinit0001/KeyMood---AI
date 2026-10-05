# KeyMood AI

Keystroke-based mood detection with an AI companion, messaging, friends, journaling and an SOS / guardian escalation flow.

```
keymood/
  backend/             FastAPI + PostgreSQL + Redis   (Modules 1-10)
  frontend/            React + TypeScript + Vite
  docker-compose.yml   Postgres + Redis for local development
```

## What is connected to the real backend

| Frontend page | Backend module | Status |
|---|---|---|
| Register / Login / Logout | 1 - Auth (+ 2 - Profile for the display name) | Real API, JWT with automatic refresh |
| AI Companion | 10 - Companion | Real API; crisis messages create a risk event through Module 4 (SOS) |
| Messages | 9 - Messaging | Real API + WebSocket (live delivery) |
| Friends | 8 - Social | Real API (add by friend code, accept/decline, message) |
| Dashboard, Live Mood, Analytics, Journal, Recommendations, Goals, SOS, Guardian, Settings | 3-7 | **Still local demo data in the browser.** The backend endpoints exist and are tested, but these pages are not wired to them yet |

## Run it locally

You need: Docker, Python 3.12+, Node 20+.

```bash
# 1. Postgres + Redis
docker compose up -d

# 2. Backend  (http://localhost:8000, API docs at /docs)
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # Windows: copy .env.example .env
python scripts/generate_dev_keys.py  # creates the local JWT keypair in keys/
alembic upgrade head                 # creates all tables (migrations 0001-0009)
uvicorn app.main:app --reload

# 3. Frontend  (http://localhost:5173) - in a second terminal
cd frontend
cp .env.example .env                 # Windows: copy .env.example .env
npm install
npm run dev
```

Open http://localhost:5173, create an account, then:

1. **Companion** - chat; type a sentence like "I want to end my life" to see crisis handling (the message is flagged, an SOS risk event is recorded, and crisis resources are shown).
2. **Friends / Messages** - register a second account in a private window. Each account has a *friend code* on the Friends page: paste one into the other account, accept the request, press **Message**, and chat live between the two windows.

`DEV_AUTO_VERIFY_EMAIL=true` in `backend/.env` skips email verification so no SMTP server is needed. It is honoured only when `APP_ENV=development`.

## Tests

```bash
cd backend
python scripts/generate_dev_keys.py
pytest -v
```

The Module 9 and 10 unit tests use in-memory fakes. Real-database and WebSocket tests for those two modules are described at the bottom of `tests/test_messaging.py` and `tests/test_companion.py` but are not implemented yet.

## Known limitations (be upfront about these)

- The companion's replies are **rule-based keyword/mood routing, not an LLM**. Crisis detection is a small, auditable keyword list (`CRISIS_KEYWORDS` in `backend/app/services/companion.py`).
- The companion personalises replies using the latest mood from Module 3. The Live Mood page does not stream keystrokes to the backend yet, so until it does, the companion uses its generic replies.
- The Companion records a risk event and shows crisis resources; it does **not** contact anyone by itself. Per Module 4's design a guardian is only notified after the user confirms.
- The WebSocket connection registries (messaging and presence) are in-memory and single-process. Running several backend instances would need Redis pub/sub.
- Messaging has no media upload; the `media_attachments` table exists only as a foreign-key target.
- Sending a message over REST does not broadcast to other connected clients; the frontend sends over the WebSocket and falls back to REST only when the socket is down.
- Friends are added by pasting a friend code (the user's UUID) rather than searching by email, to avoid exposing which emails are registered.
- Google sign-in has no UI; the backend endpoint exists.
- Access tokens are kept in `localStorage` for simplicity. A production deployment should use httpOnly cookies.
