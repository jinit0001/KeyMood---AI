# Module 1 (Authentication) — Local Verification Guide

Everything in this document was written against the actual generated
project structure under `backend/`. Commands are given for **Windows
PowerShell** first (since that's the target dev machine), with the
Linux/macOS equivalent immediately after where it differs.

None of this has been executed in the sandbox that generated this code
— PyPI/apt access was blocked there (see `MODULE_1_STATUS.md`). Run it
here to get the first real execution.

---

## 1. Environment setup

**Python version required:** 3.12 (the project was written against 3.12;
3.11+ should work, but 3.12 is what's verified via static analysis).

```powershell
# Windows PowerShell — from the backend/ project root
python --version                     # confirm 3.11+
python -m venv venv
venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

```bash
# Linux / macOS
python3 --version
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks the activation script with an execution-policy
error, run once (as your own user, not admin):
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

---

## 2. Configuration (.env)

```powershell
Copy-Item .env.example .env
```
```bash
cp .env.example .env
```

Then edit `.env` and set at minimum:
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` to match the
  database you create in step 4.
- `GOOGLE_CLIENT_ID` — only required if you intend to exercise the
  `/auth/google` endpoint against real Google tokens. Leave blank
  otherwise; the endpoint will correctly reject calls with
  `INVALID_GOOGLE_TOKEN` rather than crash.
- `SMTP_HOST`/`SMTP_PORT` — point at a local dev mail catcher (step 3.3)
  or a real SMTP relay.

**Never commit the real `.env`** — it's already covered by `.gitignore`.

---

## 3. RSA keypair (RS256 JWT signing)

The repo does not ship a real keypair for you — generate your own.

```powershell
# Windows PowerShell — requires OpenSSL (ships with Git for Windows,
# or install via: winget install ShiningLight.OpenSSL.Light)
mkdir keys
openssl genrsa -out keys\dev_jwt_private.pem 2048
openssl rsa -in keys\dev_jwt_private.pem -pubout -out keys\dev_jwt_public.pem
```

```bash
# Linux / macOS
mkdir -p keys
openssl genrsa -out keys/dev_jwt_private.pem 2048
openssl rsa -in keys/dev_jwt_private.pem -pubout -out keys/dev_jwt_public.pem
```

Confirm `.env` points at these files:
```
JWT_PRIVATE_KEY_PATH=./keys/dev_jwt_private.pem
JWT_PUBLIC_KEY_PATH=./keys/dev_jwt_public.pem
```

`keys/` is gitignored — never commit real keys, dev or prod.

---

## 4. Infrastructure — PostgreSQL

Simplest path is Docker, if you have Docker Desktop installed (works
identically on Windows/macOS/Linux):

```powershell
docker run -d --name keymood-postgres `
  -e POSTGRES_USER=keymood `
  -e POSTGRES_PASSWORD=changeme `
  -e POSTGRES_DB=keymood `
  -p 5432:5432 `
  postgres:16
```
```bash
docker run -d --name keymood-postgres \
  -e POSTGRES_USER=keymood \
  -e POSTGRES_PASSWORD=changeme \
  -e POSTGRES_DB=keymood \
  -p 5432:5432 \
  postgres:16
```

Match `.env`'s `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` to
whatever you used above.

If you'd rather install PostgreSQL natively on Windows, use the official
installer from postgresql.org and create the DB/user with `psql` or
pgAdmin — the app doesn't care how the database was created.

---

## 5. Infrastructure — Redis

```powershell
docker run -d --name keymood-redis -p 6379:6379 redis:7
```
```bash
docker run -d --name keymood-redis -p 6379:6379 redis:7
```

Redis is used for rate limiting only in this module (per the approved
MVP scope) — no other feature depends on it yet.

---

## 6. Database migrations (Alembic)

From the `backend/` root, with the venv active:

```powershell
alembic upgrade head
```
```bash
alembic upgrade head
```

**Verify it worked:**
```powershell
docker exec -it keymood-postgres psql -U keymood -d keymood -c "\dt"
```
Expect to see: `users`, `user_profiles`, `oauth_identities`,
`email_verifications`, `password_resets`, `refresh_tokens`,
`alembic_version`.

Check the approved `role` column exists:
```powershell
docker exec -it keymood-postgres psql -U keymood -d keymood -c "\d users"
```
Expect a `role` column, `character varying(20)`, default `'user'`.

Check `refresh_tokens` structure:
```powershell
docker exec -it keymood-postgres psql -U keymood -d keymood -c "\d refresh_tokens"
```
Expect columns `id, user_id, token_hash, jti, expires_at, revoked_at,
created_at`, with unique indexes on `token_hash` and `jti`.

---

## 7. Start the backend

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 8. Run the test suite

```powershell
pytest -v
```
```bash
pytest -v
```

With coverage (install `pytest-cov` first if you want this — it's not
in `requirements.txt` by default):
```powershell
pip install pytest-cov
pytest --cov=app --cov-report=term-missing
```

Run just the fast, no-DB unit tests (security + service layer):
```powershell
pytest tests/test_security.py tests/test_auth_service.py -v
```

Run just the API-level tests (also no real DB — uses dependency
overrides with in-memory fakes, per the module's test design):
```powershell
pytest tests/test_auth_api.py -v
```

---

## 9. Manual verification

### 9.1 Health checks
```powershell
curl http://localhost:8000/health/liveness
curl http://localhost:8000/health/readiness
```
`readiness` should report `"database": "ok"` once Postgres is reachable.

### 9.2 API documentation
Open in a browser: `http://localhost:8000/docs` (Swagger UI) or
`http://localhost:8000/redoc`. Both are auto-generated by FastAPI from
the Pydantic schemas — no separate doc-writing step needed. (Disabled
automatically if `APP_ENV=production`.)

### 9.3 Authentication smoke test

```powershell
# 1. Register
curl -X POST http://localhost:8000/api/v1/auth/register `
  -H "Content-Type: application/json" `
  -d '{\"email\":\"you@example.com\",\"password\":\"Str0ng!Passw0rd\",\"display_name\":\"You\"}'

# 2. Check your SMTP catcher (e.g. Mailpit UI at http://localhost:8025)
#    for the verification email, and copy the token out of the link.

# 3. Verify
curl -X POST http://localhost:8000/api/v1/auth/verify-email `
  -H "Content-Type: application/json" `
  -d '{\"token\":\"PASTE_TOKEN_HERE\"}'

# 4. Login
curl -X POST http://localhost:8000/api/v1/auth/login `
  -H "Content-Type: application/json" `
  -d '{\"email\":\"you@example.com\",\"password\":\"Str0ng!Passw0rd\"}'
# -> copy access_token and refresh_token from the response

# 5. Refresh (rotates the token — the old refresh_token becomes unusable)
curl -X POST http://localhost:8000/api/v1/auth/refresh `
  -H "Content-Type: application/json" `
  -d '{\"refresh_token\":\"PASTE_REFRESH_TOKEN_HERE\"}'

# 6. Logout (requires Authorization header with the access token)
curl -X POST http://localhost:8000/api/v1/auth/logout `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer PASTE_ACCESS_TOKEN_HERE" `
  -d '{\"refresh_token\":\"PASTE_REFRESH_TOKEN_HERE\"}'
```

On Linux/macOS, the same `curl` commands work but drop the PowerShell
line-continuation backtick (`` ` ``) in favor of `\`, and single quotes
don't need escaped double quotes inside JSON:
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"Str0ng!Passw0rd","display_name":"You"}'
```

A successful walk through steps 1–6 with no unexpected errors is the
practical definition of "Module 1 works end-to-end" locally.
