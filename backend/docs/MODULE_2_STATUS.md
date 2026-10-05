# Module 2 (Profile & Settings) — Status

**Module 2 has been runtime-verified against a real PostgreSQL database
and real Redis, in the same session as Module 1's re-verification.**

---

## What was built

Following API_SPEC.md §2 (Profile) and §11 (Settings) exactly:

- `GET/PATCH /profile/me` — display_name, avatar_url, bio, timezone
- `GET/PATCH /settings/privacy` — 5 granular data-category toggles
- `GET/PATCH /settings/notifications` — 5 per-category toggles
- `GET/PATCH /settings/ai-preferences` — companion tone, coaching
  frequency, feature opt-outs
- `POST /settings/export` — 202 Accepted, creates a real pending
  request record
- `DELETE /settings/account` — password re-confirmation, soft-delete,
  session revocation

Clean Architecture, same layering as Module 1: `domain/profile/`
(entities + repository Protocols, no framework dependencies) →
`services/` (ProfileService, SettingsService) → `infrastructure/db/`
(SQLAlchemy models + repositories) → `api/v1/` (FastAPI routers +
Pydantic schemas).

## Schema gap-fill, documented

`user_settings` and `data_export_requests` are **not in DATABASE.md** —
the Settings endpoints were specified in API_SPEC.md but the underlying
storage schema never was. Filled reasonably:
- `user_settings`: one row per user, three JSONB columns (privacy,
  notifications, ai_preferences) — follows the same JSONB convention
  DATABASE.md already uses elsewhere (`companion_memory.value`,
  `recommendations.payload`).
- `data_export_requests`: id, user_id, status, download_url,
  expires_at, requested_at, completed_at.

Full reasoning is in `app/domain/profile/entities.py` docstrings, kept
next to the code rather than only in this doc.

## Testing approach — two layers, deliberately

1. **Unit tests with fakes** (`test_profile_service.py`,
   `test_settings_service.py`, 26 tests) — fast, exercise business logic
   (validation rules, partial updates, error paths) in isolation.

2. **Real end-to-end API tests against real Postgres**
   (`test_profile_settings_api.py`, 16 tests) — deliberately NOT using
   fakes for the database layer. This is the layer that actually
   exercises the new SQL repositories, including the specific risk
   area fakes can't touch: JSONB round-tripping (dataclass → dict →
   JSONB → dict → dataclass). Only email sending and Google OAuth are
   faked (genuinely external services unavailable in this
   environment); Postgres, the user/profile/settings/export
   repositories, and the real `get_db` commit lifecycle are all real.

This second layer is what caught both real bugs described in
`MODULE_1_STATUS.md` (the missing commit, and deleted accounts being
able to log in) — neither would have been visible from fakes-based
testing alone, which is why it's a permanent part of this module's
test suite rather than a one-off debugging step.

**112/112 tests pass** (96 from Module 1, unaffected by these changes,
plus 16 new real-DB Profile/Settings tests).

## Known limitations, stated plainly

- **Data export is not actually implemented.** `POST /settings/export`
  creates a real `pending` request row so the contract shape is
  genuine and testable, but nothing ever processes it — no background
  worker, no file generation, no actual download link. Wiring a real
  job (e.g. Celery/RQ + object storage) is a concrete next module, not
  silently faked as already working.
- **Account deletion only does the immediate part.** Soft-delete
  (`status=DELETED`, `deleted_at` set) and session revocation happen
  for real. The 30-day hard-purge described in SECURITY.md §9 is an
  ops/scheduler concern (a cron job or scheduled task hitting the DB),
  not something this module builds.
- **OAuth-only accounts can't delete via this endpoint.**
  `DELETE /settings/account` requires password re-confirmation;
  accounts created via Google OAuth have no password
  (`password_hash IS NULL`). API_SPEC.md doesn't address this case.
  Currently such a request is rejected the same way a wrong password
  would be — functionally safe (nothing gets deleted incorrectly) but
  not a real solution. Flagging rather than quietly working around it.
- **Privacy/notification/AI-preference categories are gap-filled**, not
  sourced from any enumerated requirement — see entities.py docstrings.
  Reasonable and consistent with what's collected elsewhere in the
  architecture, but worth a deliberate review pass rather than treating
  the current 5+5+3 fields as final.
