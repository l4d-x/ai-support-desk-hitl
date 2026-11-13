# Deploying for free

Architecture: **Streamlit Community Cloud** (UI) → **Render** (FastAPI, Docker) → **Neon** (Postgres) +
**Qdrant Cloud** (vectors) + **Groq** (LLM). You create the accounts and paste the keys into each
dashboard; nothing secret is ever committed.

Free-tier limits change. The numbers below were checked in Nov 2026 from public docs and third-party
write-ups, so re-check each dashboard before relying on them.

## 1. Accounts and keys

| Service | What to create | You need |
|---|---|---|
| [Groq](https://console.groq.com) | API key | `GROQ_API_KEY` |
| [Neon](https://neon.com) | Project + database | connection string → `DATABASE_URL` (keep `sslmode=require`) |
| [Qdrant Cloud](https://cloud.qdrant.io) | Free cluster (optional) | `QDRANT_URL`, `QDRANT_API_KEY` |
| Shared secret | `python -c "import secrets; print(secrets.token_urlsafe(32))"` | `API_KEY` |

Leave `QDRANT_URL` empty to use an in-memory Qdrant that is rebuilt from `kb/*.md` on every start.
The KB is only 65 chunks, so this works fine and removes a dependency. Use Qdrant Cloud if you want
it on the resume; the keep-alive workflow below stops it being suspended.

Do not use Render's own Postgres (the free one expires after 30 days) or Supabase (free projects
pause after about a week idle).

## 2. API on Render

1. Push this repo to GitHub.
2. Render → **New → Blueprint** → pick the repo. It reads `render.yaml`.
3. Fill in the secret env vars: `GROQ_API_KEY`, `API_KEY`, `DATABASE_URL`, and optionally
   `QDRANT_URL` / `QDRANT_API_KEY`.
4. Wait for the first deploy, then check:
   - `curl https://<service>.onrender.com/health` → `{"status":"ok"}`
   - `curl https://<service>.onrender.com/health/deep` → database and vector_db both `true`

Free web services sleep after about 15 minutes without traffic and take roughly a minute to wake.
The Streamlit app shows a "waking up" message while it polls `/health`.

## 3. UI on Streamlit Community Cloud

1. share.streamlit.io → **New app** → this repo, branch `main`, main file `ui/Home.py`.
2. Advanced settings → Python 3.12, and paste your secrets (template: `ui/secrets.example.toml`):

   ```toml
   API_URL = "https://<service>.onrender.com"
   API_KEY = "<same value as on Render>"
   AGENT_PASSWORD = "<choose one>"
   ```
3. The app needs `ui/requirements.txt` only (Streamlit + requests); the heavy ML dependencies stay on
   the API service.

Streamlit apps with no traffic for 12 hours go to sleep and wake when someone visits.

## 4. Keep free tiers alive

Qdrant Cloud suspends free clusters after about a week idle and deletes them after about four.
Add a repository secret `API_URL` (the Render URL); `.github/workflows/keepalive.yml` then calls
`/health/deep` every four days, which wakes Render and touches Postgres and Qdrant.

## 5. Abuse protection (what it does and doesn't do)

- Every endpoint except `/health*` needs the `X-API-Key` header. The key lives in Streamlit's
  server-side secrets, not in the browser.
- Server-side caps: `MINUTE_TICKET_LIMIT` (burst), `EMAIL_DAILY_LIMIT`, `DAILY_TICKET_LIMIT`
  (global; this is the one that actually protects your Groq quota). Daily counters are stored in
  Postgres, so a sleeping host cannot reset them.
- The per-session cap in the UI is a courtesy: a visitor can refresh the page to reset it. The
  per-email cap is also weak, because anyone can type a different email. The global daily cap is
  the hard limit. Pick it below your Groq free-tier daily request quota (check the Groq console for
  the current figure for your model).
- If the key leaks: rotate `API_KEY` on Render and in Streamlit secrets, rotate the Groq key.

## 6. Local full stack

```bash
cp .env.example .env   # set GROQ_API_KEY and API_KEY
docker compose up --build
# API: http://localhost:8000/docs   UI: http://localhost:8501
```
