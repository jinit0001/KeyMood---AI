# Module 1 (Authentication) — Status

**Module 1 HAS been runtime-verified against a real PostgreSQL database
and real Redis, in a session with working network access. This
supersedes the previous version of this document, which was written in
an environment where installing dependencies and running a database
was not possible.**

---

## What was actually done

- Installed all dependencies from `requirements.txt` — found and fixed
  a real bug: `requests` was missing (needed transitively by the Google
  OAuth library).
- Stood up a real PostgreSQL 16 database and ran `alembic upgrade head`
  — migration applies cleanly.
- Generated a real RS256 JWT keypair and ran the full test suite
  (`tests/test_auth_api.py`, `tests/test_auth_service.py`,
  `tests/test_security.py`) — **96/96 pass**, but see the critical
  finding below: those tests use in-memory fakes for the repositories,
  which is exactly why the next bug went undetected until real
  end-to-end HTTP testing.
- Ran real HTTP requests against the live app (not TestClient +
  fakes) — register, verify-email, login — hitting the actual
  SQLAlchemy repositories and a real Postgres database, with only
  email/Google OAuth faked (genuinely external services this
  environment can't reach).

## Critical bug found and fixed: writes were never committed

`app/infrastructure/db/session.py`'s `get_db()` never called
`session.commit()`. SQLAlchemy's default behavior on `session.close()`
without a prior commit is to roll back any pending transaction —
meaning **every write in the entire app, across every module, would
silently vanish** the moment a request finished. Confirmed empirically:
a real registration request returned `201 Created` with a real
`user_id`, but a fresh `psql` connection immediately afterward found no
such row.

Fixed: `get_db()` now commits on success and rolls back on any
exception. Re-verified the same way — the row (and its auto-created
`user_profiles` row) now genuinely persists across requests. Full test
suite re-run after the fix: no regressions (96/96 still pass).

This bug was invisible to the existing fakes-based test suite by
design — fakes don't have transactions to roll back. It only surfaces
under real end-to-end testing, which is why Module 2's testing
approach (see `MODULE_2_STATUS.md`) deliberately runs real HTTP
requests against real Postgres for at least one full test file per
module, in addition to fakes-based unit tests.

## Second bug found and fixed: deleted accounts could still log in

Found while testing Module 2's account-deletion endpoint against real
Postgres: `AuthService.login()` checked for `UserStatus.SUSPENDED` but
never checked `UserStatus.DELETED`. A soft-deleted account (password
hash untouched by design, per SECURITY.md's retention policy) could
still authenticate and receive a valid token pair. Fixed: `login()`
now rejects `DELETED` accounts with the same `InvalidCredentialsError`
used for a wrong password (deliberately not a distinct error, to avoid
leaking account-deletion status to an unauthenticated caller — same
reasoning as not revealing whether an email is registered).

## Known limitations (unchanged, still real)

- Rate limiting (`app/core/rate_limit.py`) needs real Redis; not
  something a unit test should depend on, so it's faked in the test
  suite (`FakeAsyncRedis`), same as the original design.
- SMTP sending is untested against a real mail server — `SmtpEmailSender`
  is faked in all tests. This is appropriate (no real mail server
  available in any CI environment either) but is worth a manual
  smoke-test against a real SMTP provider before production use.
- Google OAuth (`GoogleOAuthProvider`) is faked in all tests for the
  same reason — needs a real Google Cloud project + client ID to
  verify end-to-end, which is a deployment-time concern, not a code
  concern.
- Account export (`/settings/export`, added in Module 2) creates a
  real request record but has no real background worker — see
  `MODULE_2_STATUS.md`.
