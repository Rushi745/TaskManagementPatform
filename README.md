# HandOff — AI-Powered Knowledge & Task Management Platform

Live: `<RENDER_URL>` · Repo: `<GITHUB_URL>`
*Context that doesn't get lost when work changes hands.* (DigiPlus technical assessment, built in one sitting.)

## Overview
Teams lose context when someone misses a meeting, a colleague goes on leave, or last week's action item never reaches this week's agenda. HandOff captures meetings and work handovers (agenda, participants, notes, decisions, action items), uses AI to turn messy raw notes into a structured recap, tracks every action item until it is closed **with a recorded outcome**, carries open items into the next meeting without losing their history, gives anyone who missed a meeting an AI catch-up brief, and keeps a small knowledge base that AI links to items and meetings. The special feature, **Leave Handover Mode**, hands over everything a person owns in one audited flow.

## Features (mapped to the assessment outcomes)
| Outcome | Where |
|---|---|
| Create/persist meetings & work transfers | `/meetings/new`, handover records from `/handover`; stored in MongoDB Atlas |
| Lifecycle + track items (owner, due, status) | meeting `scheduled → completed → archived`; item `open → in_progress → blocked → done/dropped` |
| Carry open items forward, keep history | "Create next meeting": one item record, `meeting_ids` grows, `carried_forward` history event, agenda auto-filled |
| AI structured recap | Notes & Recap tab → reviewable draft (summary, decisions, items with owner/date/evidence) |
| AI catch-up brief | Catch me up tab (missed meeting / taking over) |
| Knowledge base + AI linking | `/kb` (paste docs; completed meetings auto-indexed), "Find related docs" on items and meetings |
| Outcome of each item | closing `done`/`dropped` requires an outcome (>= 5 chars), enforced server-side (HTTP 409) |
| Validation & error handling | Pydantic v2 on every write, one JSON error format, toasts in the UI with a request id |
| Logging | structured JSON logs, request id, AI latency/outcome, secrets redacted |
| **Special feature** | **Leave Handover Mode** (below) |
| Login | pre-generated team accounts, no sign-up; every change is attributed to the logged-in person |

## Tech stack & architecture
| Layer | Choice | Why |
|---|---|---|
| Backend | Python, Flask (app factory + blueprints) | small and quick to build |
| Frontend | Jinja2, Bootstrap 5, vanilla JS `fetch` | professional UI, no build step |
| Validation | Pydantic v2 | validates API input **and** AI output |
| Database | MongoDB Atlas (`pymongo`) | nested documents (participants, decisions, history); persists across Render redeploys |
| AI | Groq, Cerebras, Gemini with automatic failover | see below |
| Retrieval | scikit-learn TF-IDF + cosine similarity | cheap candidate search before the LLM judges |
| Server | Gunicorn on Render | auto-deploy from GitHub |

```
Browser (Jinja pages + fetch)
   │  HTML + JSON /api/*
Flask: middleware (request id, access log) → api/ + web/ → services/ → repositories/ → MongoDB Atlas
                                                      └── services/ai/ → llm_client → Groq / Cerebras / Gemini
Logs → logs/app.log (JSON lines, rotating) + stdout
```
Layering is strict: routes never touch Mongo, repositories contain only queries, and **all** LLM calls go through `app/services/ai/llm_client.py`.

## Data model
Collections: `people`, `meetings` (also holds handover records, `type: handover`), `action_items`, `kb_docs`, `briefs`. MongoDB fits because meetings embed participants and decisions and items embed their full `history`. An action item is **one document** that lists every meeting it has appeared in (`meeting_ids`), so carry-forward never duplicates items and the history stays continuous. `is_overdue` and `carry_count` are derived, not stored.

## Login (demo credentials)
Accounts are **pre-generated** for the team; there is no sign-up page or API. Log in with **Team ID** `digiplus`, a **User ID**, and the password:

| User ID | Person | Password |
|---|---|---|
| `priya` | Priya Nair, Product Manager | `priya@digiplus` |
| `rahul` | Rahul Mehta, Backend Engineer | `rahul@digiplus` |
| `sneha` | Sneha Iyer, QA Engineer | `sneha@digiplus` |
| `vikram` | Vikram Rao, DevOps Engineer | `vikram@digiplus` |
| `ananya` | Ananya Gupta, Frontend Engineer | `ananya@digiplus` |
| `aarav` | Aarav Shah, Engineering Manager | `aarav@digiplus` |

Passwords are stored only as salted hashes (Werkzeug) and never returned by the API. The session cookie is HttpOnly + SameSite=Lax (+ Secure in production). Every page and `/api/*` call except `/login` and `/health` requires login (pages redirect, the API returns 401), and the logged-in person is recorded as the actor in item history and logs (`auth.login`, `auth.login_failed`). Demo passwords are deterministic so evaluators can log in; production would issue random passwords and force a change on first login. Team ID comes from `TEAM_ID`.

## AI configuration
- **Providers** (set keys in env; unused providers are skipped): Groq (`openai/gpt-oss-120b`), Cerebras (`gpt-oss-120b`), Gemini. Order via `AI_PROVIDER_ORDER` (default `groq,cerebras,gemini`). Free tiers are rate limited, so a throttled provider fails over to the next one immediately.
- **Where AI is used:** recap, catch-up brief, KB linking, handover brief + owner suggestions.
- **Prompts:** `app/services/ai/prompts.py` (each prompt forbids inventing facts, owners or dates and asks for quoted evidence).
- **Data flow:** raw text → prompt → provider (JSON mode, schema embedded in the prompt; Gemini uses native schema output) → Pydantic validation → deterministic post-checks → draft shown to the user.
- **Reliability:** timeout, retry with the validation error appended to the prompt, provider failover, then a **rule-based fallback** for every feature (UI shows a yellow banner or "Generated without AI"). Post-checks: owner must be a participant (else null + "needs review"); dates must parse and be within a year; confidence < 0.6 flagged; near-duplicate of an open item flagged (TF-IDF > 0.8); KB link ids not among the retrieved candidates are dropped; handover item ids and owner names must be real. The recap is always a **draft the human accepts or edits** before anything is saved.

## Data source
Seeded demo data (`scripts/seed.py`, idempotent): 6 people, 8 team docs, 3 meetings (two completed with items, one created by carry-forward). Messy sample notes for live demos are in `scripts/sample_notes/`. User-created data is persisted in MongoDB Atlas. `python -m scripts.reset_db` wipes and reseeds.

## Logging
JSON, one object per line, to `logs/app.log` (rotating 5 MB × 5) and stdout. Every line has `ts, level, logger, request_id, event`. The request id is generated (or taken from `X-Request-ID`) in `before_request`, injected into every log line by a filter, returned in the response header and in error bodies, and shown in error toasts ("Ref: …"). A redaction filter masks Google/Groq/Cerebras keys and Mongo URI credentials; raw notes and document text are never logged (only `notes_chars`).
```
{"ts":"2026-10-30T07:12:01.123Z","level":"INFO","logger":"app.items","request_id":"0340f20c…","event":"item.closed","status":"done","outcome_chars":29}
{"ts":"2026-10-30T07:12:01.123Z","level":"INFO","logger":"app.items","request_id":"77586615…","event":"item.reassigned","from_owner":"Sneha Iyer","to_owner":"Aarav Shah","reason":"cover"}
{"ts":"2026-10-30T07:12:01.123Z","level":"INFO","logger":"app.ai","event":"ai.call","operation":"recap","provider":"groq","model":"openai/gpt-oss-120b","attempt":1,"outcome":"success","latency_ms":1840,"input_chars":2310,"output_chars":1422}
```
Events: `http.request, meeting.created/status_changed/next_created, item.created/reassigned/status_changed/closed/carried_forward, kb.doc_added, kb.linked, recap.requested/applied, brief.generated, ai.call (success/retry/failed/fallback), handover.previewed/executed, validation.failed, error.unhandled`.

## Special feature: Leave Handover Mode (`/handover`)
**Why:** "a colleague goes on leave" is the sharpest pain point in the problem statement. Today someone manually hunts through meetings for everything the person owns. This turns the riskiest moment for lost context into a two-minute, auditable process.
1. **Select** the person and leave dates.
2. **Preview:** all their open items grouped 🔴 overdue / 🟠 due by the end of leave / 🟢 later; an AI overview, per-item context ("why it exists, what was decided, what's left"), risks, and a suggested new owner per item (prefers people who attended the item's meetings and have the lightest load). Everything is editable; bulk-assign is available.
3. **Execute:** items are reassigned with `reassigned` history events, a `handover` record (with the brief) is created and indexed in the KB, the person is marked **on leave** (shown on the dashboard), and `handover.executed` is logged. The new owner gets the *why*, not just a task title, and nothing slips during the leave window.

## API
JSON, base `/api`; every response carries `X-Request-ID`. Errors: `{"error":{"code","message","details":[{field,msg}],"request_id"}}` (422 validation, 404, 409 conflict such as closing without an outcome, 503 only if no fallback exists).

| | |
|---|---|
| `GET /health` | db + AI status |
| `GET/POST /api/people`, `PATCH /api/people/<id>` | people |
| `GET/POST /api/meetings`, `GET/PATCH /api/meetings/<id>` | meetings |
| `POST /api/meetings/<id>/status` · `/next` · `/recap` · `/recap/apply` · `/brief` · `/link` | lifecycle, carry-forward, AI |
| `GET/POST /api/items`, `GET/PATCH /api/items/<id>` | items (filters: status, owner_id, overdue, meeting_id) |
| `POST /api/items/<id>/close` · `/reopen` · `/link` | outcome, reopen, AI linking |
| `GET/POST /api/kb`, `GET /api/kb/<id>` | knowledge base (search `?q=`, backlinks) |
| `POST /api/handover/preview` · `/execute` | special feature |
| `GET /api/dashboard` | stats, overdue, recent meetings, people on leave |

## Running locally
```
git clone <repo> && cd <repo>
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # fill MONGODB_URI and at least one AI key (or use MONGODB_URI=mongomock:// for an in-memory DB)
flask --app wsgi run --port 5001     # macOS uses port 5000 for AirPlay
python -m pytest -q
```

## Deployment
Render web service (free) connected to GitHub `main`, auto-deploy on. `render.yaml` describes it. Build `pip install -r requirements.txt`; start `gunicorn wsgi:app --workers 1 --threads 4 --timeout 120` (one worker so seeding runs once; long timeout because AI calls can be slow); health check `/health`. Env vars: see `.env.example` (set `MONGODB_URI` and the AI keys in the Render dashboard). MongoDB Atlas M0 with network access `0.0.0.0/0` (Render's IPs change) and a dedicated database user.

## Approach
I split the work into phases that each end in something demo-able: skeleton + logging + health + deploy path → domain core (items, history, carry-forward) → AI recap → knowledge base, linking and brief → the special feature → polish. The domain rules (outcome required to close, history on every change, carry-forward keeps one record) live in services and are enforced server-side, so the UI cannot bypass them. AI is treated as an unreliable component: constrained output, validated, post-checked, human-reviewed, with fallbacks. Key trade-offs: TF-IDF instead of a vector DB (fast, no infrastructure; lexical only); simple team login without roles; server-rendered pages with small vanilla-JS islands instead of a SPA.

## Assumptions
- One team with pre-generated accounts; every logged-in teammate has the same permissions (no roles yet), and every change is attributed to them.
- Recordings/emails are represented as pasted text transcripts.
- Dates are UTC `YYYY-MM-DD`.

## Known limitations
- No roles/permissions (e.g. only a manager may run a handover); no real email, Slack or calendar integration; no PDF upload (pasted text only).
- TF-IDF retrieval is lexical; embeddings would catch synonyms.
- Free-tier LLM rate limits (mitigated by failover + fallbacks); free-tier cold start on Render (~50 s first request).
- `logs/app.log` is ephemeral on Render's free disk (stdout logs remain in Render's dashboard); production would ship logs to a log service.
- AI can still misread notes; the review step and "needs review" flags exist for that reason.

## Future improvements
Roles and permissions, random passwords with forced change, audio transcription, email/Slack ingestion, embeddings, reminders and notifications, a "follow-up radar" for stale items.
