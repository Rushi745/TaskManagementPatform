# HandOff — AI-Powered Knowledge & Task Management Platform

> *Context that doesn't get lost when work changes hands.*

- **Live app:** https://handoff-knjn.onrender.com. It is on Render's free tier, so the first load can take about 50 seconds.
- **Login:** Team ID `digiplus`, then e.g. User ID `rahul` with password `rahul@digiplus` (all accounts are listed [below](#login-and-demo-accounts)).
- **Repository:** https://github.com/Rushi745/TaskManagementPatform
- Built for the DigiPlus technical assessment by Rushi ([@Rushi745](https://github.com/Rushi745)).

---

## Contents
1. [Problem and solution](#1-problem-and-solution)
2. [Features](#2-features)
3. [Special feature: Leave Handover Mode](#3-special-feature-leave-handover-mode)
4. [How to use it (demo walkthrough)](#4-how-to-use-it-demo-walkthrough)
5. [Login and demo accounts](#login-and-demo-accounts)
6. [Tech stack](#6-tech-stack)
7. [Architecture](#7-architecture)
8. [Data model and data source](#8-data-model-and-data-source)
9. [AI configuration](#9-ai-configuration)
10. [Logging](#10-logging)
11. [Validation and error handling](#11-validation-and-error-handling)
12. [API reference](#12-api-reference)
13. [Running locally](#13-running-locally)
14. [Deployment](#14-deployment)
15. [Testing](#15-testing)
16. [Approach](#16-approach)
17. [Assumptions](#17-assumptions)
18. [Known limitations and future work](#18-known-limitations-and-future-work)

---

## 1. Problem and solution
**Problem.** Teams lose context every time work changes hands. Someone misses a meeting, a colleague goes on leave, or last week's action item never makes it onto this week's agenda. The information is scattered across notes, chats, documents, emails and recordings.

**Solution.** HandOff is a web app that:
- **captures** meetings and work handovers: agenda, participants and attendance, notes, decisions and action items;
- uses **AI** to turn messy raw notes into a structured recap: summary, decisions, and action items with owners and due dates;
- **tracks every action item until it is closed with a recorded outcome**, keeping a full history;
- **carries open items** into the next meeting without duplicating them or losing their history;
- writes an **AI catch-up brief** for anyone who missed a meeting or is taking over work;
- keeps a **knowledge base** of team documents and past meetings, and uses AI to **link** items and meetings to the relevant documents;
- and, as its special feature, offers **Leave Handover Mode**, which transfers someone's work **and the knowledge behind it** before they go on leave.

## 2. Features
| Assessment outcome | How HandOff does it | Where in the app |
|---|---|---|
| Create and persist meetings or work transfers (agenda, participants, notes, decisions, action items) | Meetings with an agenda, participants with an "attended" flag, raw notes, summary and decisions; handovers are stored as `type: handover` records | **Meetings → New meeting**; **Handover** |
| View and manage their lifecycle; track items (owner, due date, status) until closed | Meeting `scheduled → completed → archived`; item `open → in_progress → blocked → done / dropped`; every change is recorded in the item's history | Meeting page buttons; **Action Items** page and side panel |
| Carry open items forward, keeping their history | **Create next meeting** moves every unfinished item into the new meeting. It is the same item record: `meeting_ids` grows, a `carried_forward` event is logged, and the new agenda gets "Review: …" lines | Completed meeting → **Create next meeting** |
| AI: raw information → structured recap | ✨ **Generate AI recap**: summary, decisions, open questions, and action items with owner, due date, priority and an evidence quote. Nothing is saved until a human reviews and accepts it | Meeting → **Notes & Recap** tab |
| AI catch-up brief for whoever missed it or is taking over | ✨ **Generate brief**: what happened, the decisions that affect you, your action items, open questions, what to read next | Meeting → **Catch me up** tab |
| Knowledge base (team docs, past meetings) + AI linking | Paste documents; completed meetings are indexed automatically; ✨ **Find related docs** links items and meetings to documents, with a reason for each | **Knowledge Base**; meeting **Knowledge links** tab; item side panel |
| Record the outcome of each item | Closing an item as `done` or `dropped` **requires an outcome** of at least 5 characters, enforced by the server (HTTP 409). Reopening requires a reason and keeps the old outcome in history | **Close** button on any item |
| Validation and error handling | Pydantic v2 on every write; one JSON error format; field-level messages and a request reference in the UI | Everywhere |
| Structured logging | JSON logs with a request ID, domain events, AI latency and outcome, and secrets redacted | `logs/app.log` and stdout |
| Make it special | **Leave Handover Mode** (section 3) | **Handover** |
| Extra | Team login with pre-generated accounts; every change is attributed to the logged-in person | **Login** page |

**Dashboard.** It shows open, overdue, due-this-week and closed-this-week counts, the overdue items, recent meetings, people on leave, and a **"Handed over to you"** list for the logged-in person.

**Labels on items:**
| Label | Meaning |
|---|---|
| `carried ×N` | The item has moved forward N times into later meetings or handovers. A high number means it keeps slipping |
| `handed over` | The item was received through Leave Handover; open it to read the notes |
| `⚠ review` | The AI was unsure about this item: the owner was not a participant, the date was unclear, or confidence was low |
| Red due date | Overdue: the due date has passed and the item is not done or dropped |
| `AI` / `keyword match` | How a knowledge link was chosen: by the AI with a reason, or by keyword similarity when the AI was unavailable |

## 3. Special feature: Leave Handover Mode
**Why.** "A colleague goes on leave" is the sharpest pain point in the problem statement. Today, someone has to hunt manually through meetings for everything that person owns, and the *why* behind each task leaves with them. Handing over ownership is not enough: **the knowledge has to transfer too.**

**How it works (`/handover`, a 3-step wizard):**
1. **Select** the person going on leave and their leave dates.
2. **Review and assign.** HandOff lists every open item the person owns, grouped 🔴 overdue, 🟠 due before the leave ends, and 🟢 later or undated. The AI then writes:
   - an **overview** and the **risks** (e.g. items due during the leave with no obvious owner);
   - for each item, a **context note**: why it exists, what was decided, and what is left;
   - for each item, a **suggested new owner** with a reason. It prefers people who attended the item's meetings and have fewer open items, and it only suggests real, active people.

   The person leaving **edits each note** and adds what only they know: where the pull request is, who to ask, what is half-done. Every suggested owner can be changed, or everything can be assigned to one person.
3. **Execute.**
   - Each item is reassigned, with a history event `Leave handover: A → B`.
   - **The knowledge travels with the item:** the note is stored on the task (`handover_notes`). The new owner sees a "Handed over by…" card as soon as they open the task, and the item appears under **"Handed over to you"** on their dashboard.
   - A **handover record** (a meeting of `type: handover`) is created with the full brief. It appears in the Meetings list and is indexed into the knowledge base.
   - The person is marked **on leave**, which shows on the dashboard and the People page.
   - The event `handover.executed` is logged.

**Value.** The riskiest moment for lost context becomes a two-minute, auditable process. The new owner gets the *why*, not just a task title, and items due during the leave are surfaced first so nothing slips.

## 4. How to use it (demo walkthrough)
1. **Log in** as `priya` / `priya@digiplus`, with Team ID `digiplus`.
2. **Dashboard:** look at the counts and the overdue list.
3. **Meetings → Sprint 22 Planning:** the open items from Sprint 21 show `carried ×1`.
4. **Notes & Recap:** paste the contents of `scripts/sample_notes/sprint_notes.txt` and click **✨ Generate AI recap**.
   - "Karan from design" is not a participant, so that item comes back unassigned with `⚠ review`.
   - Relative dates such as "next Fri" become real dates.
   - Edit anything you like, then **Save recap & items**.
5. **Action items:** open one, change its status, try to close it without an outcome (this is rejected), then close it with an outcome. Check its history.
6. **Knowledge links → ✨ Find related docs.**
7. **Catch me up:** choose an absent person and click **✨ Generate brief**.
8. **Mark completed**, then **Create next meeting**: the open items move over and the agenda fills itself.
9. **Handover:** choose Rahul and click **Preview**. Edit a note, assign the items to Sneha, then **Execute**.
10. **Log out**, then log in as `sneha` / `sneha@digiplus`. The dashboard shows **"Handed over to you"**; open an item to read Rahul's note.

More sample inputs are in `scripts/sample_notes/`: `client_call.txt` (an email thread) and `handover_chat.txt` (a Slack-style chat).

## Login and demo accounts
Accounts are **pre-generated** for the team. There is no sign-up page or API. Log in with **Team ID** `digiplus`:

| User ID | Person | Role | Password |
|---|---|---|---|
| `priya` | Priya Nair | Product Manager | `priya@digiplus` |
| `rahul` | Rahul Mehta | Backend Engineer | `rahul@digiplus` |
| `sneha` | Sneha Iyer | QA Engineer | `sneha@digiplus` |
| `vikram` | Vikram Rao | DevOps Engineer | `vikram@digiplus` |
| `ananya` | Ananya Gupta | Frontend Engineer | `ananya@digiplus` |
| `aarav` | Aarav Shah | Engineering Manager | `aarav@digiplus` |

- Passwords are stored only as salted hashes (Werkzeug) and are never returned by the API.
- The session cookie is `HttpOnly` and `SameSite=Lax`, and also `Secure` in production.
- Every page and `/api/*` call except `/login` and `/health` requires login: pages redirect to the login page, and the API returns 401.
- The logged-in person is recorded as the actor in item history and in the logs (`auth.login`, `auth.login_failed`).
- Demo passwords are deterministic so evaluators can log in. A production system would issue random passwords and force a change on first login. The team ID comes from the `TEAM_ID` environment variable.

## 6. Tech stack
| Layer | Technology | Why |
|---|---|---|
| Language / framework | Python 3.10+ (3.12 on Render), **Flask 3** (app factory + blueprints) | Lightweight and quick to build; easy to explain |
| Frontend | **Jinja2** templates, **Bootstrap 5** + Bootstrap Icons (CDN), **vanilla JavaScript** (`fetch`) | A professional UI with no build step |
| Validation | **Pydantic v2** | Validates both API input and AI output |
| Database | **MongoDB Atlas** (free M0) via **PyMongo** | Nested documents (participants, decisions, history) fit naturally; data persists across Render redeploys |
| AI | **Groq** (`openai/gpt-oss-120b`), **Cerebras** (`gpt-oss-120b`), **Google Gemini** (`google-genai`), with automatic failover; **httpx** for OpenAI-compatible calls | Free tiers are rate-limited, so failover keeps the AI available |
| Retrieval | **scikit-learn** TF-IDF + cosine similarity | Cheap candidate search and duplicate detection without a vector database |
| Auth | Flask sessions + Werkzeug password hashing | Simple and secure enough for a single team |
| Logging | Python `logging`, custom JSON formatter, `RotatingFileHandler` | Structured, traceable logs |
| Server / hosting | **Gunicorn** on **Render** (free), auto-deploy from GitHub (`render.yaml`) | Simple continuous deployment |
| Tests | **pytest** + **mongomock** (in-memory MongoDB) | Fast tests with no external services |

## 7. Architecture
```
Browser (Jinja pages + Bootstrap + fetch)
        │  HTML pages + JSON /api/*
        ▼
Flask app
  middleware.py   request ID, timing, access log
  auth.py         login required, current user = actor
  api/ + web/     routes: parse + validate input, call a service, return JSON/HTML
        ▼
  services/       business rules (meetings, items, carry-forward, handover, KB, dashboard)
        │             └── services/ai/  llm_client (the ONLY place that calls an LLM)
        │                               recap · brief · linker · handover_ai · fallback · prompts
        │             └── services/retrieval.py  TF-IDF index over the knowledge base
        ▼
  repositories/   MongoDB queries only
        ▼
MongoDB Atlas            Groq / Cerebras / Gemini
Logs → logs/app.log (JSON lines, rotating) + stdout (Render "Logs" tab)
```
**Rules followed.** Routes never touch the database; repositories contain only queries; business rules live in services, so the UI cannot bypass them. All AI calls go through `llm_client.generate_json`, and every AI feature has a fallback.

**Project layout**
```
app/
  __init__.py        create_app(): config, logging, Mongo, seed, credentials, blueprints
  config.py          all settings from environment variables
  auth.py            login/logout, login guard, pre-generated credentials
  middleware.py      request ID + access log
  errors.py          AppError types + one JSON error format
  logging_setup.py   JSON formatter, request-ID filter, secret redaction
  extensions.py      Mongo client, indexes
  utils.py           ids, dates, serialization
  schemas/           Pydantic models (input + AI output)
  repositories/      people, meetings, items, kb, briefs
  services/          people, meeting, item, kb, handover, dashboard, retrieval
  services/ai/       llm_client, prompts, recap, brief, linker, handover_ai, fallback
  api/               JSON endpoints        web/  page routes
  templates/         Jinja pages           static/  css + js
scripts/  seed.py (demo data), reset_db.py, sample_notes/
tests/    pytest suite
render.yaml  wsgi.py  requirements.txt  .env.example
```

## 8. Data model and data source
**Collections in MongoDB Atlas, database `handoff`:**
| Collection | One document is | Key fields |
|---|---|---|
| `people` | a team member | name, email (unique), role, status `active`/`on_leave`, leave dates, username, password_hash |
| `meetings` | a meeting **or** a handover record | type, title, date, status, agenda[], participants[{person_id, name, attended}], raw_notes, summary, decisions[], recap_source, previous_meeting_id, kb_links[], handover{from, to, leave dates, brief, item_ids} |
| `action_items` | a task | title, description, owner, due_date, priority, status, outcome, origin_meeting_id, **meeting_ids[]**, source (`ai`/`fallback`/`manual`), evidence, needs_review, kb_links[], **history[]**, **handover_notes[]**, closed_at |
| `kb_docs` | a knowledge document | title, content (plain text), tags, source (`seed`/`manual`/`meeting`), meeting_id |
| `briefs` | a generated catch-up brief (audit trail) | kind, meeting_id, person_id, content, source |

**Why MongoDB.** Meetings embed their participants and decisions, and items embed their full history and handover notes. An item is **one document across many meetings**: carry-forward and handover only append to `meeting_ids` and `history`, so nothing is ever copied. `is_overdue` and `carry_count` are computed, not stored.

**Data source**
- **Demo data:** `scripts/seed.py` creates a fictional team (6 people), 8 realistic team documents, 3 meetings (Sprint 21 Planning, Payments Incident Review, and Sprint 22 Planning created by carry-forward) and 13 action items in mixed states, including overdue, blocked and done items with outcomes. It runs automatically when the database is empty.
- **Sample raw notes** for live AI demos are in `scripts/sample_notes/`.
- **User data:** everything created in the app is saved to Atlas immediately and survives restarts and redeploys.
- **Reset:** `python -m scripts.reset_db` wipes the database and reseeds it. This deletes all data.

## 9. AI configuration
**Providers**, set in environment variables (providers without a key are skipped):
| Variable | Default | Notes |
|---|---|---|
| `AI_PROVIDER_ORDER` | `groq,cerebras,gemini` | Order in which providers are tried |
| `GROQ_API_KEY` / `GROQ_MODEL` | – / `openai/gpt-oss-120b` | Free key at console.groq.com (primary) |
| `CEREBRAS_API_KEY` / `CEREBRAS_MODEL` | – / `gpt-oss-120b` | Free key at cloud.cerebras.ai (backup) |
| `GEMINI_API_KEY` / `GEMINI_MODEL` / `GEMINI_FALLBACK_MODEL` | – / `gemini-3.8-flash` / `gemini-3.5-flash-lite` | Optional third provider |
| `AI_TIMEOUT_SECONDS` / `AI_MAX_ATTEMPTS` | `30` / `2` | Per-call timeout; attempts per provider |

**Where AI is used:**
| Feature | Input | Output |
|---|---|---|
| Recap | raw notes, participants, meeting date, existing open items | summary, decisions, open questions, action items (owner, due date, priority, evidence quote, confidence) |
| Catch-up brief | meeting summary, decisions, all items, the person's own items, linked docs | headline, what happened, decisions affecting you, your items, open questions, read next |
| KB linking | item or meeting text + top-5 TF-IDF candidate documents | relevant: yes/no + a one-sentence reason per candidate |
| Handover | the person's open items (origin meeting, decisions, history, docs) + available people with workloads | overview, risks, per-item context, suggested owner + reason |

All prompts are in `app/services/ai/prompts.py`. Each one tells the model to use only the given data and never to invent facts, owners, dates or ids.

**Data flow:** text → prompt → provider (JSON mode, with the schema embedded in the prompt; Gemini uses native schema output) → Pydantic validation → deterministic post-checks → shown to the user as a draft or preview.

**Reliability:**
1. **Constrained output:** JSON mode plus Pydantic schemas.
2. **Retry with feedback:** invalid JSON is retried on the same provider, with the validation error appended to the prompt.
3. **Failover:** rate limits, timeouts and server errors move straight on to the next provider.
4. **Post-validation:**
   - the owner must be a meeting participant, otherwise `null` + `needs_review`;
   - dates must parse and fall within a year;
   - confidence below 0.6 is flagged;
   - near-duplicates of open items are flagged (TF-IDF similarity above 0.8);
   - KB link ids must come from the retrieved candidates (no hallucinated documents);
   - handover item ids and owner names must be real and active people.
5. **Human in the loop:** the recap is only a draft until it is accepted; handover notes and owners are editable before execution.
6. **Fallbacks for every feature:** rule-based recap extraction (TODO / Action / `@name` lines, "agreed/decided" lines), a template brief, keyword-only linking, and template handover notes with a workload-based owner suggestion. The UI shows a yellow "AI unavailable" banner or a "Generated without AI" badge, and the app never crashes because of the AI.

## 10. Logging
- **Format:** one JSON object per line, with the fields `ts, level, logger, request_id, event, message` plus event-specific fields.
- **Outputs:** `logs/app.log` (rotating, 5 MB × 5 files) and stdout, which appears in Render's Logs tab.
- **Request ID:** taken from the `X-Request-ID` header or generated in `before_request`. It is injected into every log line by a filter, returned in the `X-Request-ID` response header and in error bodies, and shown in error toasts as "Ref: …", so a user's report can be matched to the logs.
- **No secrets:** a redaction filter masks Google, Groq and Cerebras API keys and Mongo URI credentials, and masks any field named password, token, secret, api_key or authorization. Raw notes and document text are never logged; only their lengths are (`notes_chars`). Password hashes are never serialized.
- **Levels:** INFO for normal events, WARNING for retries, fallbacks, validation failures and failed logins, ERROR for failed AI calls and unhandled exceptions (with the stack trace).

**Events:** `http.request`, `auth.login`, `auth.login_failed`, `auth.logout`, `meeting.created`, `meeting.status_changed`, `meeting.next_created`, `item.created`, `item.reassigned`, `item.status_changed`, `item.closed`, `item.carried_forward`, `kb.doc_added`, `kb.linked`, `recap.requested`, `recap.applied`, `brief.generated`, `ai.call` (success, retry, failed or fallback, with provider, model, attempt, latency_ms, input_chars and output_chars), `handover.previewed`, `handover.executed`, `validation.failed`, `error.unhandled`.

```json
{"ts":"2026-10-30T07:12:01.123Z","level":"INFO","logger":"app.items","request_id":"0340f20c…","event":"item.closed","message":"item.closed","item_id":"6ae4…","status":"done","outcome_chars":29}
{"ts":"2026-10-30T07:12:03.410Z","level":"INFO","logger":"app.items","request_id":"77586615…","event":"item.reassigned","message":"item.reassigned","item_id":"6ae4…","from_owner":"Rahul Mehta","to_owner":"Sneha Iyer","reason":"Leave handover: Rahul Mehta → Sneha Iyer"}
{"ts":"2026-10-30T07:12:05.902Z","level":"INFO","logger":"app.ai","request_id":"9f5e8546…","event":"ai.call","message":"ai.call","operation":"recap","provider":"groq","model":"openai/gpt-oss-120b","attempt":1,"outcome":"success","latency_ms":1840,"input_chars":2310,"output_chars":1422}
```

## 11. Validation and error handling
- Every write endpoint validates its body with Pydantic. Titles are 3–200 characters, notes are at most 20,000 characters, KB content is 20–50,000 characters, dates are `YYYY-MM-DD`, and status, priority and type values are restricted to their allowed options. ObjectIds are checked, and an invalid id returns 404.
- Business rules are enforced in the services:
  - closing an item requires an outcome;
  - reopening requires a reason;
  - a closed item cannot be edited;
  - only a completed meeting can be carried forward, and only once;
  - a meeting needs a participant before it can be completed;
  - a handover only accepts the leaving person's own open items and active new owners;
  - an item's owner must be an existing person.
- **One error format:** `{"error":{"code","message","details":[{"field","msg"}],"request_id"}}`

| Situation | HTTP | code |
|---|---|---|
| Invalid input | 422 | `VALIDATION_ERROR` |
| Unknown id | 404 | `NOT_FOUND` |
| Rule violation (e.g. closing without an outcome) | 409 | `CONFLICT` |
| Not logged in | 401 | `UNAUTHORIZED` |
| Malformed JSON | 400 | `BAD_REQUEST` |
| AI failed and no fallback possible | 503 | `AI_UNAVAILABLE` |
| Anything else | 500 | `INTERNAL_ERROR` (a generic message; the full trace goes only to the logs) |

- The frontend also validates fields (`required`, `minlength`), but the backend is the source of truth. Errors appear as toasts listing each field message and the request reference.

## 12. API reference
Base path `/api`; requests and responses are JSON; every response carries `X-Request-ID`; login is required except for `/health`.
| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | `{status, db, ai, providers}` |
| GET / PATCH | `/api/people`, `/api/people/<id>` | list people; update role or status |
| GET / POST | `/api/meetings` (`?type=&status=`) | list or create meetings |
| GET / PATCH | `/api/meetings/<id>` | meeting with its items; edit agenda, notes, summary, decisions, attendance |
| POST | `/api/meetings/<id>/status` | lifecycle transition |
| POST | `/api/meetings/<id>/next` | create the next meeting and carry open items forward |
| POST | `/api/meetings/<id>/recap` | **AI** recap draft (not saved) |
| POST | `/api/meetings/<id>/recap/apply` | save the reviewed recap |
| POST | `/api/meetings/<id>/brief` | **AI** catch-up brief `{person_id, mode: missed|takeover}` |
| POST | `/api/meetings/<id>/link` | **AI** link the meeting to KB documents |
| GET / POST | `/api/items` (`?status=&owner_id=&overdue=true&meeting_id=`) | list (filtered) or create items |
| GET / PATCH | `/api/items/<id>` | item with history; change status, owner, due date or priority |
| POST | `/api/items/<id>/close` · `/reopen` | close with an outcome; reopen with a note |
| POST | `/api/items/<id>/link` | **AI** link the item to KB documents |
| GET / POST | `/api/kb` (`?q=`), `/api/kb/<id>` | list or search documents; add one; a document with its backlinks |
| POST | `/api/handover/preview` | the person's items by urgency + **AI** brief + suggested owners |
| POST | `/api/handover/execute` | reassign items with their notes, create the handover record, mark the person on leave |
| GET | `/api/dashboard` | stats, overdue items, recent meetings, people on leave, items handed over to you |

**Pages:** `/login`, `/` (dashboard), `/meetings`, `/meetings/new`, `/meetings/<id>`, `/items`, `/kb`, `/kb/<id>`, `/handover`, `/people`.

## 13. Running locally
```bash
git clone https://github.com/Rushi745/TaskManagementPatform.git && cd TaskManagementPatform
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
#   set MONGODB_URI (Atlas) and at least one AI key (GROQ_API_KEY recommended)
#   or use MONGODB_URI=mongomock://local for a throwaway in-memory database
flask --app wsgi run --port 5001        # macOS uses port 5000 for AirPlay
# open http://127.0.0.1:5001  → Team ID digiplus, rahul / rahul@digiplus
```
To reset the demo data, run `python -m scripts.reset_db`.

## 14. Deployment
- **Hosting:** a Render web service on the free plan, created from `render.yaml` (Blueprint) and auto-deployed on every push to `main`.
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `gunicorn wsgi:app --workers 1 --threads 4 --timeout 120`. One worker means seeding runs once and the in-memory TF-IDF cache stays consistent; the long timeout is needed because AI calls can be slow.
- **Health check path:** `/health`
- **Environment variables:**
  - set in the Render dashboard (secrets): `MONGODB_URI`, `GROQ_API_KEY` (and optionally `CEREBRAS_API_KEY` / `GEMINI_API_KEY`);
  - set by `render.yaml`: `PYTHON_VERSION`, `FLASK_ENV=production`, `SECRET_KEY` (generated), `TEAM_ID`, `SEED_ON_STARTUP`, `AI_PROVIDER_ORDER`.
- **Database:** MongoDB Atlas M0. Network access is `0.0.0.0/0`, because Render's outbound IPs change, and the app uses a dedicated database user with read/write access only.
- **Secrets** live only in `.env` (gitignored) and in Render's environment settings. They are never committed.

## 15. Testing
```bash
python -m pytest -q        # 26 tests, using an in-memory MongoDB (mongomock); no network or API keys needed
```
The tests cover:
- AI post-validation: owner grounding, date sanity, low confidence, duplicate detection;
- the LLM client: retry on invalid JSON, provider failover, all providers failing, the request format;
- the recap fallback and the recap apply step;
- the KB linker: hallucinated ids are dropped, and keyword fallback works;
- the catch-up brief fallback;
- KB validation and search;
- the item close rule (409 without an outcome);
- handover preview grouping, execution, AI post-validation, and notes travelling with the item;
- login: required login, wrong password or team, no sign-up, no hash leaks, actor attribution.

## 16. Approach
1. **Read the problem as "context loss at hand-off moments"** (a missed meeting, a new week, leave) and designed one item record that follows the work across all of them.
2. **Built in phases, each one demo-able and committed:**
   1. skeleton, configuration, structured logging and the health check;
   2. the domain core: people, meetings, items, history, carry-forward, seed data and the dashboard;
   3. the AI recap with validation and fallback;
   4. the knowledge base, AI linking and the catch-up brief;
   5. Leave Handover Mode;
   6. login, documentation and deployment.
3. **Rules live on the server,** in the service layer: an outcome is required to close, history is recorded on every change, and carry-forward keeps one record. The UI is a thin client.
4. **AI is treated as an unreliable dependency:** schema-constrained, validated, post-checked, human-reviewed, failed over between providers, and backed by rule-based fallbacks.
5. **Trade-offs:**
   - TF-IDF instead of a vector database: fast and needs no infrastructure, but it only matches words;
   - server-rendered pages with small JavaScript modules instead of a single-page app: quick to build and easy to explain;
   - team login without roles: everything is still attributed to a person;
   - free-tier hosting and AI: it costs nothing, at the price of cold starts and rate limits.

## 17. Assumptions
- A single team with pre-generated accounts; every logged-in teammate currently has the same permissions.
- Recordings, emails and chats are provided as pasted text transcripts.
- Dates are calendar days (`YYYY-MM-DD`) in UTC.
- "Overdue" means the due date is before today and the item is not done or dropped.
- AI output is advisory: it is never saved without human review, except for briefs and links, which change no task data.

## 18. Known limitations and future work
**Limitations**
- No roles or permissions yet: any logged-in user can edit, reassign or hand over anything. Every change is attributed to that user.
- Demo passwords are deterministic; there is no password change or reset.
- No PDF or audio upload, and no email, Slack or calendar integration.
- TF-IDF retrieval only matches words, so synonyms can be missed.
- Free tiers bring Render cold starts (about 50 seconds) and LLM rate limits; the latter is mitigated by failover and fallbacks.
- `logs/app.log` lives on Render's ephemeral disk; stdout logs are kept in Render's dashboard. Production would ship logs to a log service.
- The AI can still misread notes, which is why the review step and the `⚠ review` flags exist.

**Future work**
- Roles and permissions: users edit only their own items, and a manager runs handovers for others.
- Random initial passwords with a forced change on first login.
- A "mark as reviewed" toggle for AI-created items.
- A person page answering "what was X working on lately", with an AI summary.
- An AI assistant panel on the dashboard.
- Audio transcription, plus email and Slack ingestion.
- Embedding-based search.
- Reminders and a follow-up radar for stale items.
