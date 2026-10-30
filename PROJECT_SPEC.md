# PROJECT_SPEC.md — AI-Powered Knowledge & Task Management Platform

> DigiPlus Technical Assessment · 3.5 hours · Author: Rushi (GitHub: Rushi745)
> Working name: **HandOff** — "Context that doesn't get lost when work changes hands."

---

## 0. Instructions for the AI coding agent (read first)

You are building this project with me inside a strict 3.5-hour window. Follow these rules:

1. **Build phase by phase** (Section 13). Do not start a phase until the previous phase's acceptance criteria pass.
2. **After every phase:** run the app, verify the acceptance criteria, then `git add . && git commit -m "<message from Section 13>" && git push`.
3. **Keep it simple.** Plain Flask + Jinja + Bootstrap 5 + vanilla JS `fetch`. No React, no build tools, no ORMs, no extra frameworks.
4. **Never hard-code secrets.** All config comes from environment variables (Section 15). Never log secrets or raw meeting notes.
5. **Layering is mandatory:** routes → services → repositories → MongoDB. Routes never touch Mongo directly. AI calls only go through `app/services/ai/`.
6. **Every AI feature must have a fallback** (Section 8.5). The app must never crash or show a raw stack trace when Gemini fails.
7. Write short docstrings on every service function; I must be able to explain all the code in an interview.
8. If time runs short, use the **cut list** in Section 13.8. Never cut: deployment, AI recap, AI fallback, logging, README.

---

## 1. Problem summary

Teams lose context when work changes hands: someone misses a meeting, a colleague goes on leave, or last week's action item never reaches this week's agenda. Information is scattered across notes, chats, docs, emails and recordings.

**We build** a web app that:
- captures meetings and work handovers (agenda, participants, notes, decisions, action items),
- uses AI to turn messy raw notes into a structured recap,
- tracks every action item until it's closed with a recorded outcome,
- carries open items into the next meeting while keeping their history,
- gives anyone who missed a meeting or is taking over a short AI catch-up brief,
- keeps a small knowledge base (docs + past meetings) and uses AI to link items to it,
- **Special feature:** *Leave Handover Mode* — one flow to hand over everything a person owns before they go on leave.

---

## 2. Requirements

### 2.1 Functional requirements

| ID | Requirement | Phase |
|---|---|---|
| FR-1 | Create, view, edit meetings and work transfers (type `meeting` or `handover`) with title, date, agenda, participants (with attended flag), raw notes, summary, decisions | 1 |
| FR-2 | Meeting lifecycle: `scheduled → completed → archived` | 1 |
| FR-3 | Action items with owner, due date, status, priority, description, outcome | 1 |
| FR-4 | Item lifecycle: `open → in_progress → blocked → done / dropped`; closing (`done`/`dropped`) **requires an outcome** | 1 |
| FR-5 | Full item history: every create / status change / reassignment / carry-forward / close is recorded with timestamp and actor | 1 |
| FR-6 | "Create next meeting" carries all open items forward, keeps one item record across meetings, logs history, and auto-adds them to the new agenda | 1 |
| FR-7 | Global items view with filters: status, owner, overdue, meeting | 1 |
| FR-8 | AI recap: raw notes → summary, decisions, action items (owner, due date, evidence). User reviews and accepts/edits before saving | 2 |
| FR-9 | AI catch-up brief for a selected person (missed meeting or taking over) | 3 |
| FR-10 | Knowledge base: add docs (paste text; PDF upload optional), list, view. Completed meetings are auto-indexed into the KB | 3 |
| FR-11 | AI linking: link action items and meetings to relevant KB docs with a reason | 3 |
| FR-12 | Dashboard: open, overdue, due this week, closed this week; overdue list; recent meetings | 1/5 |
| FR-13 | People management: name, email, role, status (`active` / `on_leave`) | 1 |
| FR-14 | **Special: Leave Handover Mode** (Section 11) | 4 |

### 2.2 Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 | Input validation on every write endpoint (Pydantic v2); consistent JSON error format (Section 10) |
| NFR-2 | Structured JSON logging to file + stdout, request ID per request, key domain events, AI calls with latency and outcome, errors with context, secrets redacted (Section 9) |
| NFR-3 | AI failures handled gracefully: timeout, retry, schema validation, fallback, clear UI message |
| NFR-4 | Data persisted in MongoDB Atlas; app works after restart/redeploy |
| NFR-5 | Deployed on a public URL (Render) with auto-deploy from GitHub `main` |
| NFR-6 | Clean, responsive UI: loading spinners on AI actions, toasts for success/error, empty states |
| NFR-7 | Maintainable code: layered architecture, small functions, config via env vars |

---

## 3. Tech stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | Jinja2 templates, Bootstrap 5 (CDN), Bootstrap Icons, vanilla JS (`fetch`) | Professional UI fast, no build step |
| Backend | Python 3.12, Flask 3 (app factory + blueprints) | Lightweight, quick to build |
| Validation | Pydantic v2 | Validates both API input and AI JSON output |
| Database | MongoDB Atlas (free M0), `pymongo[srv]` | Flexible nested documents (participants, decisions, history); survives Render redeploys (Render free disk is ephemeral) |
| AI | Google Gemini via `google-genai` SDK, model from env (`GEMINI_MODEL`, default `gemini-2.5-flash`; check AI Studio for current Flash name) | Free tier, native JSON schema output |
| Retrieval | scikit-learn `TfidfVectorizer` + cosine similarity | Candidate retrieval for KB linking without a vector DB |
| PDF (optional) | PyMuPDF (`pymupdf`) | Extract text from uploaded PDFs |
| Logging | Python `logging`, custom JSON formatter, `RotatingFileHandler` + stdout | Structured, traceable logs |
| Server | Gunicorn | Production WSGI server |
| Hosting | Render (free web service) + GitHub auto-deploy | Simple, connects directly to GitHub |
| Config | `python-dotenv` locally, Render env vars in prod | No secrets in code |

### requirements.txt
```
flask>=3.0
gunicorn>=22.0
pymongo[srv]>=4.7
google-genai>=1.0
pydantic>=2.7
scikit-learn>=1.4
python-dotenv>=1.0
pymupdf>=1.24
```
After installing, run `pip freeze > requirements.lock.txt` (optional) to record exact versions.

---

## 4. Architecture

```
Browser (Jinja pages + Bootstrap + fetch)
        │  HTTP (HTML pages + JSON /api/*)
        ▼
┌──────────────────────── Flask app ────────────────────────┐
│ middleware.py   → request_id, access log, timing          │
│ web/ (pages)    api/ (JSON blueprints)                     │
│        │                │                                   │
│        ▼                ▼                                   │
│ services/  meeting · item · kb · handover · dashboard       │
│        │                         │                          │
│        │                 services/ai/                       │
│        │        gemini_client (timeout, retry, logging)     │
│        │        recap · brief · linker · handover_ai        │
│        │        fallback (rule-based)  · prompts            │
│        │                 services/retrieval.py (TF-IDF)     │
│        ▼                                                    │
│ repositories/ meetings · items · kb · people                │
└────────┬───────────────────────────────┬───────────────────┘
         ▼                               ▼
   MongoDB Atlas                   Google Gemini API
         
 Logs → logs/app.log (JSON lines, rotating) + stdout (Render Logs tab)
```

### Key flows

**AI recap:** user pastes notes → `POST /api/meetings/<id>/recap` → `recap_service` builds prompt with participants + today's date → `gemini_client` (timeout 30s, max 2 attempts, JSON schema) → Pydantic validate → post-validation (owner must be a participant, dates parsed, duplicate check vs open items) → returned as a **draft** → user edits/accepts in a review modal → `POST /api/meetings/<id>/recap/apply` saves summary, decisions, items.
If AI fails → rule-based fallback extraction → draft marked `source: "fallback"` → UI shows a yellow banner.

**Carry-forward:** `POST /api/meetings/<id>/next` → new meeting (copies participants, sets `previous_meeting_id`) → every open item from the source gets the new meeting id appended to `meeting_ids` + a `carried_forward` history event → agenda gets `Review: <item title>` lines.

**KB linking:** item/meeting text → TF-IDF top 5 candidates → Gemini picks relevant ones with a reason → validate returned ids ⊂ candidates → save `kb_links`.

---

## 5. Project structure

```
handoff/
├── app/
│   ├── __init__.py            # create_app(): config, logging, mongo, blueprints, error handlers, seed
│   ├── config.py              # Config class reading env vars
│   ├── extensions.py          # Mongo client + get_db()
│   ├── logging_setup.py       # JSON formatter, redaction filter, request-id filter, handlers
│   ├── middleware.py          # before/after request: request_id, timing, access log
│   ├── errors.py              # AppError, NotFound, ValidationFailed, Conflict, AIError + handlers
│   ├── utils.py               # ObjectId <-> str, serialize(), utcnow(), parse_date()
│   ├── schemas/
│   │   ├── person.py  meeting.py  item.py  kb.py  handover.py
│   │   └── ai.py              # RecapOut, BriefOut, LinkOut, HandoverBriefOut
│   ├── repositories/
│   │   ├── people_repo.py  meetings_repo.py  items_repo.py  kb_repo.py  briefs_repo.py
│   ├── services/
│   │   ├── people_service.py  meeting_service.py  item_service.py
│   │   ├── kb_service.py  handover_service.py  dashboard_service.py
│   │   ├── retrieval.py       # TF-IDF index (rebuilt when KB changes)
│   │   └── ai/
│   │       ├── gemini_client.py   # single entry point for all LLM calls
│   │       ├── prompts.py         # all prompt templates
│   │       ├── recap.py  brief.py  linker.py  handover_ai.py
│   │       └── fallback.py        # rule-based fallbacks
│   ├── api/                   # JSON blueprints, prefix /api
│   │   ├── health.py people.py meetings.py items.py kb.py handover.py dashboard.py
│   ├── web/
│   │   └── views.py           # page routes rendering templates
│   ├── templates/
│   │   ├── base.html  dashboard.html  people.html  items.html  kb_list.html  kb_detail.html  handover.html
│   │   ├── meetings/list.html  meetings/detail.html  meetings/new.html
│   │   └── partials/ toasts.html  item_row.html  history_timeline.html
│   └── static/
│       ├── css/app.css
│       └── js/ api.js (fetch wrapper + toasts) meeting.js items.js kb.js handover.js
├── scripts/
│   ├── seed.py                # idempotent seed (people, KB docs, 2 meetings, items)
│   └── sample_notes/          # messy raw notes for live AI demo (2–3 .txt files)
├── tests/                     # optional: test_ai_postvalidation.py, test_item_rules.py
├── logs/                      # gitignored
├── wsgi.py                    # from app import create_app; app = create_app()
├── requirements.txt
├── .env.example
├── .gitignore
├── PROJECT_SPEC.md            # this file
└── README.md
```

---

## 6. Data model (MongoDB collections)

All ids are `ObjectId`; API returns them as string `id`. All timestamps are UTC `datetime`.

### 6.1 `people`
```json
{
  "_id": "ObjectId",
  "name": "Priya Nair",
  "email": "priya@example.com",
  "role": "Product Manager",
  "status": "active",            // active | on_leave
  "leave": {"from": "2026-11-02", "to": "2026-11-16"},   // null when active
  "created_at": "datetime"
}
```
Index: unique on `email`.

### 6.2 `meetings`
```json
{
  "_id": "ObjectId",
  "type": "meeting",               // meeting | handover
  "title": "Sprint 22 Planning",
  "date": "datetime",
  "status": "scheduled",           // scheduled | completed | archived
  "agenda": ["Review: Fix payment retry bug", "Q4 roadmap check-in"],
  "participants": [{"person_id": "ObjectId", "name": "Priya Nair", "attended": true}],
  "raw_notes": "string",
  "summary": "string|null",
  "decisions": [{"text": "Ship v2 checkout on Nov 10", "made_by": "Priya Nair|null"}],
  "recap_source": "ai|fallback|manual|null",
  "previous_meeting_id": "ObjectId|null",
  "handover": {                    // only when type == handover
    "from_person_id": "ObjectId", "to_person_id": "ObjectId|null",
    "reason": "leave", "leave_from": "date", "leave_to": "date",
    "brief": "string", "item_ids": ["ObjectId"]
  },
  "kb_links": [{"doc_id": "ObjectId", "title": "string", "reason": "string", "method": "ai|tfidf"}],
  "created_at": "datetime", "updated_at": "datetime"
}
```
Indexes: `date` desc, `status`.

### 6.3 `action_items`
```json
{
  "_id": "ObjectId",
  "title": "Fix payment retry bug",
  "description": "string",
  "owner_id": "ObjectId|null",
  "owner_name": "Rahul Mehta|null",
  "due_date": "datetime|null",
  "priority": "medium",            // low | medium | high
  "status": "open",                // open | in_progress | blocked | done | dropped
  "outcome": "string|null",        // REQUIRED when status is done/dropped
  "origin_meeting_id": "ObjectId",
  "meeting_ids": ["ObjectId"],     // every meeting this item has appeared in (carry-forward)
  "source": "ai|fallback|manual",
  "evidence": "quote from notes|null",   // AI grounding
  "needs_review": false,           // true if AI owner/date was uncertain
  "kb_links": [{"doc_id": "ObjectId", "title": "string", "reason": "string", "method": "ai|tfidf"}],
  "history": [
    {"at": "datetime", "event": "created|status_changed|reassigned|carried_forward|closed|reopened|due_changed",
     "by": "string", "from": "any", "to": "any", "note": "string|null", "request_id": "string"}
  ],
  "closed_at": "datetime|null",
  "created_at": "datetime", "updated_at": "datetime"
}
```
Indexes: `status`, `owner_id`, `due_date`, `meeting_ids`.
Derived (computed in service, not stored): `is_overdue = due_date < now and status not in (done, dropped)`, `carry_count = len(meeting_ids) - 1`.

### 6.4 `kb_docs`
```json
{
  "_id": "ObjectId",
  "title": "Deployment Runbook",
  "content": "string",
  "tags": ["devops", "release"],
  "source": "seed|manual|upload|meeting",
  "meeting_id": "ObjectId|null",   // set when source == meeting (auto-indexed on completion)
  "created_at": "datetime"
}
```

### 6.5 `briefs` (audit/cache of generated catch-up & handover briefs)
```json
{"_id": "ObjectId", "kind": "catchup|handover", "meeting_id": "ObjectId|null",
 "person_id": "ObjectId", "content": {"...": "BriefOut JSON"}, "source": "ai|fallback", "created_at": "datetime"}
```

### 6.6 Business rules
- Item owner must exist in `people`. AI-proposed owners not in the participant list → `owner_id = null`, `needs_review = true`.
- Closing (`done`/`dropped`) requires `outcome` with at least 5 characters; sets `closed_at`.
- Reopening a closed item requires a `note`; clears `closed_at`, keeps old outcome in history.
- Cannot carry forward from a meeting that isn't `completed`.
- A meeting can be marked `completed` only if it has a title and at least one participant. On completion, its summary + decisions are upserted into `kb_docs` with `source: "meeting"`.
- Handover meetings require `from_person_id`.
- `due_date` must be a valid date; dates in the past are allowed but flagged overdue.

---

## 7. API design

Base path `/api`. JSON in/out. Every response has header `X-Request-ID`.

| Method | Path | Body / query | Description |
|---|---|---|---|
| GET | `/health` | – | `{"status":"ok","db":"ok|down","ai":"configured|missing"}` |
| GET | `/api/people` | – | list people |
| POST | `/api/people` | `{name,email,role}` | create person |
| PATCH | `/api/people/<id>` | `{role?,status?}` | update |
| GET | `/api/meetings` | `?type=&status=` | list meetings |
| POST | `/api/meetings` | `{type,title,date,agenda[],participant_ids[],raw_notes?}` | create |
| GET | `/api/meetings/<id>` | – | meeting + its items + linked docs |
| PATCH | `/api/meetings/<id>` | partial fields | edit (agenda, notes, attended flags, summary, decisions) |
| POST | `/api/meetings/<id>/status` | `{status}` | lifecycle transition |
| POST | `/api/meetings/<id>/recap` | `{raw_notes?}` | **AI** → draft recap (not saved) |
| POST | `/api/meetings/<id>/recap/apply` | `{summary,decisions[],items[]}` | save reviewed recap |
| POST | `/api/meetings/<id>/brief` | `{person_id}` | **AI** catch-up brief |
| POST | `/api/meetings/<id>/next` | `{title,date}` | create next meeting with open items carried |
| POST | `/api/meetings/<id>/link` | – | **AI** link meeting to KB |
| GET | `/api/items` | `?status=&owner_id=&overdue=true&meeting_id=` | list/filter |
| POST | `/api/items` | `{title,owner_id,due_date,priority,meeting_id,description?}` | create manual item |
| GET | `/api/items/<id>` | – | item + history |
| PATCH | `/api/items/<id>` | `{status?,owner_id?,due_date?,priority?,note?}` | update (logs history; reassignment logs `item.reassigned`) |
| POST | `/api/items/<id>/close` | `{status: done|dropped, outcome}` | close with outcome |
| POST | `/api/items/<id>/reopen` | `{note}` | reopen |
| POST | `/api/items/<id>/link` | – | **AI** link item to KB |
| GET | `/api/kb` | `?q=` | list/search docs |
| POST | `/api/kb` | `{title,content,tags[]}` | add doc |
| POST | `/api/kb/upload` | multipart PDF (≤5 MB) | add doc from PDF (optional) |
| GET | `/api/kb/<id>` | – | doc + items/meetings linked to it (backlinks) |
| POST | `/api/handover/preview` | `{from_person_id, leave_from, leave_to}` | open items grouped by urgency + **AI** handover brief + suggested owners |
| POST | `/api/handover/execute` | `{from_person_id, assignments:[{item_id,to_person_id}], leave_from, leave_to, note?}` | reassign, create handover record, set person on_leave |
| GET | `/api/dashboard` | – | stats + overdue list + recent meetings + people on leave |

### Page routes (Jinja)
`/` dashboard · `/meetings` · `/meetings/new` · `/meetings/<id>` · `/items` · `/kb` · `/kb/<id>` · `/handover` · `/people`

---

## 8. AI design

### 8.1 Gemini client (`services/ai/gemini_client.py`)
Single function used by every AI feature:
```python
def generate_json(operation: str, prompt: str, schema: type[BaseModel]) -> BaseModel:
    """Call Gemini with JSON schema output. Timeout, retry once on failure
    (appending the validation error to the prompt), log latency + outcome.
    Raises AIError if all attempts fail."""
```
Implementation notes:
```python
from google import genai
from google.genai import types
client = genai.Client(api_key=cfg.GEMINI_API_KEY,
                      http_options=types.HttpOptions(timeout=cfg.AI_TIMEOUT_SECONDS * 1000))
resp = client.models.generate_content(
    model=cfg.GEMINI_MODEL,
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,   # Pydantic model
        temperature=0.2,
    ),
)
data = schema.model_validate_json(resp.text)
```
- `AI_MAX_ATTEMPTS=2`, 1s backoff between attempts.
- On `ValidationError` / JSON error: retry with "Your previous output was invalid: <error>. Return valid JSON only."
- If `GEMINI_API_KEY` missing → raise `AIError("AI not configured")` immediately → fallback path.
- Log one `ai.call` event per attempt (Section 9.3).

### 8.2 AI output schemas (`schemas/ai.py`)
```python
class RecapItem(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    owner: str | None          # must be a participant name or null
    due_date: str | None       # YYYY-MM-DD or null
    priority: Literal["low","medium","high"] = "medium"
    evidence: str              # short quote from the notes supporting this item
    confidence: float = Field(ge=0, le=1)

class RecapOut(BaseModel):
    summary: str               # 3–5 sentences
    decisions: list[str]
    action_items: list[RecapItem]
    open_questions: list[str] = []

class BriefOut(BaseModel):
    headline: str
    what_happened: list[str]           # max 4 bullets
    decisions_affecting_you: list[str]
    your_action_items: list[str]
    open_questions: list[str]
    read_next: list[str]               # KB doc titles

class LinkDecision(BaseModel):
    doc_id: str
    relevant: bool
    reason: str
class LinkOut(BaseModel):
    links: list[LinkDecision]

class HandoverItemNote(BaseModel):
    item_id: str
    context: str                       # what the new owner needs to know
    suggested_owner: str | None        # person name from provided list
    suggestion_reason: str | None
class HandoverBriefOut(BaseModel):
    overview: str
    items: list[HandoverItemNote]
    risks: list[str]
```

### 8.3 Prompts (`services/ai/prompts.py`)

**RECAP_PROMPT**
```
You are an assistant that turns raw meeting notes into a structured recap.
Today's date: {today}. Meeting date: {meeting_date}.
Participants (the ONLY valid owners): {participant_names}
Existing open action items (avoid duplicates): {open_item_titles}

Rules:
- Use ONLY information present in the notes. Do not invent facts, owners or dates.
- owner must exactly match one participant name, otherwise null.
- Convert relative dates ("next Friday", "EOW") to YYYY-MM-DD using the meeting date; if no date is stated, null.
- evidence must be a short exact quote from the notes (max 20 words).
- confidence: 0–1, how clearly the notes state this item and its owner.
- decisions are things that were agreed, not tasks.
- summary: 3–5 sentences, neutral tone.

Notes:
"""
{raw_notes}
"""
```

**BRIEF_PROMPT**
```
Write a short catch-up brief for {person_name} ({role}), who {reason: "missed this meeting" | "is taking over this work"}.
Use only the data below. Max ~150 words total. Be specific: names, dates, numbers.
Meeting: {title} on {date}
Summary: {summary}
Decisions: {decisions}
All action items (title | owner | due | status): {items}
Items owned by {person_name}: {own_items}
Linked documents: {doc_titles}
```

**LINK_PROMPT**
```
Decide which knowledge-base documents are genuinely relevant to this {item|meeting}.
Text: """{text}"""
Candidate documents (id | title | excerpt):
{candidates}
Return one decision per candidate. Only use the given ids. reason: one sentence.
```

**HANDOVER_PROMPT**
```
{from_name} ({from_role}) is going on leave from {leave_from} to {leave_to}.
Write a handover brief for whoever takes over. For each item give the context the new owner needs
(why it exists, what was decided, what's left), and suggest a new owner ONLY from this list:
{available_people_with_roles_and_open_item_counts}
Prefer people who attended the item's meetings and have fewer open items.
Items (id | title | due | status | origin meeting | related decisions | history summary | linked docs):
{items}
Also list risks (e.g. items due during the leave window with no obvious owner).
```

### 8.4 Post-validation (AI reliability — explain this in the interview)
After the schema check, `recap.py` applies deterministic checks:
1. **Owner grounding:** owner not in participant names (case-insensitive match) → `owner = null`, `needs_review = true`.
2. **Date sanity:** unparseable date → null; date > 1 year away → null + `needs_review`.
3. **Low confidence:** `confidence < 0.6` → `needs_review = true`.
4. **Duplicate detection:** TF-IDF similarity of new item title vs existing open items > 0.8 → mark `possible_duplicate_of: <item_id>` in the draft.
5. **Linker id check:** drop any `doc_id` not in the candidate list (prevents hallucinated ids).
6. **Human-in-the-loop:** the recap is a draft; the user accepts/edits each item before saving.

### 8.5 Fallbacks (`services/ai/fallback.py`)
| Feature | Fallback when AI fails | UI message |
|---|---|---|
| Recap | Regex extraction: lines starting with `TODO`, `Action:`, `AI:`, `- [ ]`, or containing `@Name` → items; owner = matched participant name; lines with `decided`/`agreed` → decisions; summary = first 3 non-empty lines | Yellow banner: "AI unavailable — basic extraction used. Please review." |
| Catch-up brief | Template built from stored summary, decisions, the person's items | "Generated without AI" badge |
| KB linking | TF-IDF top 3 with score ≥ 0.15, reason = "Keyword similarity (AI unavailable)", `method: "tfidf"` | Badge "keyword match" |
| Handover brief | Template listing items grouped by urgency; suggested owner = participant of the item's origin meeting with fewest open items | "Generated without AI" badge |

All fallbacks set `source: "fallback"` and log `ai.call` with `outcome: "fallback"`.

### 8.6 Retrieval (`services/retrieval.py`)
- `TfidfVectorizer(stop_words="english", ngram_range=(1,2), max_features=5000)` fitted on `title + " " + content` of all `kb_docs`.
- Cache the fitted matrix in memory; rebuild when a doc is added (simple `dirty` flag).
- `search(query, k=5) -> [(doc, score)]`.

---

## 9. Logging spec

### 9.1 Setup (`logging_setup.py`)
- Root logger level from `LOG_LEVEL` (default `INFO`).
- Handlers: `RotatingFileHandler("logs/app.log", maxBytes=5_000_000, backupCount=5)` + `StreamHandler(sys.stdout)`, both with the JSON formatter.
- `RequestIdFilter`: injects `request_id` from `flask.g` (or `"-"` outside a request).
- `RedactionFilter`: masks
  - Google API keys: regex `AIza[0-9A-Za-z_\-]{35}` → `AIza***`
  - Mongo URIs credentials: `mongodb(\+srv)?://[^:]+:[^@]+@` → `mongodb+srv://***:***@`
  - any extra field named `password`, `api_key`, `token`, `secret`, `authorization` → `***`
- Never log `raw_notes` or doc content — log lengths (`notes_chars`) only.

### 9.2 Format (one JSON object per line)
```json
{"ts":"2026-10-30T07:12:01.123Z","level":"INFO","logger":"app.items","request_id":"6f1c…",
 "event":"item.reassigned","message":"Item reassigned","item_id":"…","from_owner":"Rahul Mehta","to_owner":"Sneha Iyer","reason":"leave handover"}
```

### 9.3 Events to log
| Event | Level | Fields |
|---|---|---|
| `http.request` | INFO | method, path, status, duration_ms, ip |
| `meeting.created` / `meeting.status_changed` | INFO | meeting_id, type, from, to |
| `meeting.next_created` | INFO | from_meeting_id, new_meeting_id, carried_count |
| `item.created` | INFO | item_id, meeting_id, owner, source |
| `item.reassigned` | INFO | item_id, from_owner, to_owner, reason |
| `item.status_changed` | INFO | item_id, from, to |
| `item.closed` | INFO | item_id, status, outcome_chars |
| `item.carried_forward` | INFO | item_id, from_meeting_id, to_meeting_id |
| `kb.doc_added` | INFO | doc_id, source, chars |
| `ai.call` | INFO / WARNING on retry / ERROR on fail | operation (recap/brief/link/handover), model, attempt, latency_ms, outcome (success/retry/failed/fallback), input_chars, output_chars, error_type |
| `handover.executed` | INFO | from_person, item_count, assignments |
| `validation.failed` | WARNING | path, errors |
| `error.unhandled` | ERROR | path, exception type, stack trace (`exc_info=True`) |

### 9.4 Request ID (`middleware.py`)
- `before_request`: `g.request_id = request.headers.get("X-Request-ID") or uuid4().hex`; `g.start = time.perf_counter()`.
- `after_request`: set `X-Request-ID` header; log `http.request` with duration (skip `/static`).
- Error responses include `request_id`; the UI toast shows it ("Ref: 6f1c…") so a user can report it.

---

## 10. Validation & error handling

### 10.1 Error response format
```json
{"error": {"code": "VALIDATION_ERROR", "message": "Invalid input", "details": [{"field": "due_date", "msg": "Invalid date"}], "request_id": "6f1c…"}}
```

| Exception | HTTP | code |
|---|---|---|
| Pydantic `ValidationError` / `ValidationFailed` | 422 | `VALIDATION_ERROR` |
| `NotFound` (bad/missing ObjectId) | 404 | `NOT_FOUND` |
| `Conflict` (invalid transition, e.g. close without outcome, carry from non-completed) | 409 | `CONFLICT` |
| `AIError` (only if no fallback possible) | 503 | `AI_UNAVAILABLE` |
| Malformed JSON body | 400 | `BAD_REQUEST` |
| PDF too large / wrong type | 413 / 415 | `FILE_TOO_LARGE` / `UNSUPPORTED_FILE` |
| Anything else | 500 | `INTERNAL_ERROR` (generic message, full trace only in logs) |

### 10.2 Input rules (Pydantic)
- `title`: 3–200 chars, stripped. `raw_notes`: ≤ 20,000 chars. KB `content`: 20–50,000 chars.
- `email`: valid format (`EmailStr` needs `email-validator`; otherwise a simple regex).
- `due_date`, `date`: ISO `YYYY-MM-DD`.
- `status`, `priority`, `type`: `Literal[...]`.
- ObjectId strings validated with a helper → 404 if invalid.
- Frontend also validates (HTML5 `required`, `minlength`) but the backend is the source of truth.

---

## 11. Special feature — Leave Handover Mode

**Problem it solves:** the problem statement's sharpest pain point is "a colleague goes on leave". Today that means someone manually hunting through meetings for everything the person owns. Leave Handover Mode does it in one guided flow.

**Flow (page `/handover`, 3-step wizard):**
1. **Select** the person going on leave + leave dates.
2. **Preview** (`POST /api/handover/preview`):
   - All their open items across all meetings, grouped: 🔴 Overdue · 🟠 Due during leave · 🟢 Due after leave / no date.
   - AI handover brief: overview, per-item context (why it exists, decisions, what's left, linked docs), risks.
   - AI-suggested new owner per item with a reason (only from active people; prefers meeting participants with lighter load). The user can change every suggestion or bulk-assign everything to one person.
3. **Execute** (`POST /api/handover/execute`):
   - Reassigns each item (history event `reassigned`, note "Leave handover: <from> → <to>"), logs `item.reassigned` per item.
   - Creates a `meetings` record with `type: "handover"` containing the brief and item ids → it appears in the meetings list and timeline.
   - Sets the person's status to `on_leave` with dates (shown on the dashboard).
   - Logs `handover.executed`.
   - Success screen: links to the handover record + "Copy brief" button.

**Why it adds value (put this in the README):** it turns the riskiest moment for lost context into a 2-minute, auditable process; the new owner gets the "why", not just a task title; nothing slips through during the leave window because items due in that window are flagged first.

**Stretch (only if time):** "Follow-up radar" on the dashboard — items overdue or untouched for 7+ days, with an AI-drafted nudge message for the owner.

---

## 12. UI spec

Bootstrap 5 navbar: **Dashboard · Meetings · Action Items · Knowledge Base · Handover · People**. Footer shows app version.

| Page | Contents |
|---|---|
| Dashboard `/` | 4 stat cards (Open, Overdue, Due this week, Closed this week); Overdue items table; Recent meetings; People on leave |
| Meetings `/meetings` | Table: title, type badge, date, status badge, open items count; "New meeting" and "New handover" buttons |
| New meeting | Form: type, title, date, participants (multi-select from people), agenda (one per line), raw notes (textarea) |
| Meeting detail `/meetings/<id>` | Header with status + actions (Mark completed, Create next meeting, Archive). Tabs: **Overview** (agenda, participants with attended toggle, "Carried from" link) · **Notes & Recap** (raw notes, "✨ Generate AI recap" → review modal with editable rows: accept checkbox, title, owner dropdown, due date, priority, evidence tooltip, ⚠ needs-review badge, duplicate warning) · **Decisions** · **Action items** (table with status dropdown, Close button → modal requiring outcome, "carried ×N" badge, overdue red) · **Knowledge links** ("✨ Find related docs") · **Catch me up** (person dropdown, absent participants first → brief card) |
| Action items `/items` | Filter bar (status, owner, overdue toggle, meeting); table; click row → offcanvas with details + history timeline + KB links |
| Knowledge base `/kb` | Search box; doc cards with tags and source badge; "Add document" modal (paste text; PDF upload tab if built) |
| KB doc `/kb/<id>` | Content + "Linked from" (items and meetings) |
| Handover `/handover` | 3-step wizard (Section 11) |
| People `/people` | Table with status badge; add person form |

UX rules: spinner + disabled button during AI calls; toast for every success/error (error toast shows request id); empty states with a call to action; status colors: open=secondary, in_progress=primary, blocked=warning, done=success, dropped=dark, overdue=danger.

`static/js/api.js` exposes `api(method, url, body)` that parses the JSON error format and shows a toast.

---

## 13. Phase-wise build plan (3.5 h)

### Phase 0 — Setup & first deploy (0:00–0:25)
Tasks:
- [ ] GitHub repo `handoff` (or `knowledge-task-platform`), clone, `python -m venv venv`, install requirements.
- [ ] `.gitignore` (`venv/ .env logs/ __pycache__/ *.pyc .DS_Store`), `.env.example`.
- [ ] MongoDB Atlas: free M0 cluster, DB user, Network Access `0.0.0.0/0`, copy URI.
- [ ] Gemini API key from Google AI Studio.
- [ ] `config.py`, `extensions.py` (Mongo client, ping on startup), `logging_setup.py`, `middleware.py`, `errors.py`, `create_app()`, `/health`, `base.html` with navbar.
- [ ] `wsgi.py`, push, create Render web service (Section 15), add env vars.

Acceptance: live URL `/health` returns `{"status":"ok","db":"ok","ai":"configured"}`; `logs/app.log` locally contains JSON lines with `request_id`; response has `X-Request-ID` header.
Commit: `chore: project skeleton, config, structured logging, health check`

### Phase 1 — Core domain (0:25–1:15)
Tasks:
- [ ] Schemas, repositories, services for people, meetings, items.
- [ ] Item rules: lifecycle, close-requires-outcome, reopen, history on every change, reassignment events.
- [ ] Meeting lifecycle + `next` (carry-forward) + agenda auto-fill.
- [ ] `scripts/seed.py` (Section 14), run on startup if `SEED_ON_STARTUP=true` and collections empty.
- [ ] Pages: dashboard (stats + overdue), meetings list/new/detail (Overview, Decisions, Action items tabs), items page with filters + history offcanvas, people page.
Acceptance: create meeting → add items → change status → close with outcome (fails without outcome with 409) → create next meeting → open items appear with "carried ×1" and history shows `carried_forward`; logs show `meeting.created`, `item.reassigned`, `item.closed`.
Commits: `feat: people, meetings and action items with lifecycle and history` · `feat: carry-forward open items to next meeting` · `feat: seed data and dashboard`

### Phase 2 — AI recap (1:15–1:55)
Tasks:
- [ ] `gemini_client.generate_json` with timeout, retry, logging.
- [ ] `RECAP_PROMPT`, `RecapOut`, post-validation (Section 8.4), fallback (Section 8.5).
- [ ] `/recap` (draft) and `/recap/apply` endpoints.
- [ ] Review modal UI with editable rows, needs-review and duplicate badges, fallback banner.
Acceptance: pasting `scripts/sample_notes/sprint_notes.txt` produces summary, decisions and items with owners/dates; an owner not in participants comes back null + needs-review; setting an invalid `GEMINI_API_KEY` still produces a fallback draft with a banner; `ai.call` logs show latency and outcome.
Commit: `feat: AI recap with schema validation, post-checks and fallback`

### Phase 3 — Catch-up brief + Knowledge base + linking (1:55–2:25)
Tasks:
- [ ] KB CRUD (paste text), KB pages, auto-index completed meetings into KB.
- [ ] `retrieval.py` TF-IDF.
- [ ] `linker.py` (TF-IDF candidates → Gemini → id check) for items and meetings; fallback.
- [ ] `brief.py` + "Catch me up" tab; store in `briefs`.
Acceptance: "Find related docs" on an item about deployment links "Deployment Runbook" with a reason; KB doc page shows backlinks; catch-up brief for an absent participant mentions their own items and relevant decisions.
Commits: `feat: knowledge base with TF-IDF retrieval and AI linking` · `feat: AI catch-up brief`

### Phase 4 — Special feature: Leave Handover Mode (2:25–2:55)
Tasks: handover service, preview + execute endpoints, `HANDOVER_PROMPT`, fallback, 3-step wizard page, handover record in meetings list, on-leave on dashboard.
Acceptance: choose a person with 3+ open items → preview groups by urgency + AI brief + suggested owners → execute → items reassigned with history, handover record visible, person shows on leave, `handover.executed` logged.
Commit: `feat: leave handover mode with AI brief and owner suggestions`

### Phase 5 — Polish (2:55–3:15)
- [ ] Empty states, loading spinners, toasts with request id, overdue highlighting, responsive check.
- [ ] Validate all forms (frontend + backend messages displayed in the UI).
- [ ] PDF upload (only if everything else works).
Commit: `feat: UX polish, validation messages, empty states`

### Phase 6 — README & final deploy (3:15–3:30)
- [ ] Write README (Section 17).
- [ ] Push; confirm Render deploy succeeded.
- [ ] Run the smoke test (Section 16) **on the live URL**.
Commit: `docs: README with AI config, logging, special feature, approach and limitations`

### 13.8 Cut list (in this order, only if behind schedule)
1. PDF upload 2. Follow-up radar stretch 3. AI owner suggestions in handover (keep manual bulk assign) 4. Duplicate detection 5. Tests 6. KB backlinks page.
**Never cut:** deploy, AI recap + fallback, catch-up brief, carry-forward, logging, README, special feature (simplify instead of cutting).

---

## 14. Seed data (`scripts/seed.py`, idempotent)

**People (6):** Priya Nair – Product Manager · Rahul Mehta – Backend Engineer · Sneha Iyer – QA Engineer · Vikram Rao – DevOps Engineer · Ananya Gupta – Frontend Engineer · Aarav Shah – Engineering Manager. Emails `firstname@digiplus-demo.com`.

**KB docs (8, 150–300 words each, realistic content written by the agent):**
1. Deployment Runbook (devops) 2. Release Checklist (release) 3. API Design Guidelines (backend) 4. Q4 Product Roadmap (product) 5. Incident Response Process (ops) 6. Code Review Policy (engineering) 7. Payments Service Architecture (backend, payments) 8. Customer Feedback Summary – October (product).

**Meetings (2 completed + 1 scheduled):**
- "Sprint 21 Planning" (2 weeks ago, completed): 5 participants, Ananya absent; summary, 2 decisions, 5 items (2 done with outcomes, 1 overdue, 2 open).
- "Payments Incident Review" (last week, completed): 4 participants; 3 items (1 blocked, 2 open), linked to Incident Response Process + Payments Service Architecture.
- "Sprint 22 Planning" (in 2 days, scheduled), created via carry-forward from Sprint 21 so carried items show history.

**Sample raw notes for live demo (`scripts/sample_notes/`):**
- `sprint_notes.txt` — messy, informal: abbreviations, relative dates ("by next Fri", "EOW"), "@Rahul", one owner not in the participant list, one decision, one vague item.
- `client_call.txt` — email-thread style notes.
- `handover_chat.txt` — Slack-style chat log of someone handing over work.

---

## 15. Configuration & deployment

### 15.1 `.env.example`
```
FLASK_ENV=development
SECRET_KEY=change-me
MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>/?retryWrites=true&w=majority
MONGODB_DB=handoff
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
AI_TIMEOUT_SECONDS=30
AI_MAX_ATTEMPTS=2
LOG_LEVEL=INFO
LOG_DIR=logs
SEED_ON_STARTUP=true
MAX_UPLOAD_MB=5
```

### 15.2 Render
- New → Web Service → connect GitHub repo → branch `main`, auto-deploy on.
- Runtime: Python · Build: `pip install -r requirements.txt`
- Start: `gunicorn wsgi:app --workers 1 --threads 4 --timeout 120`
  (1 worker avoids duplicate seeding and fork issues with the Mongo client; 120s timeout because AI calls can be slow — the default 30s would kill them.)
- Health check path: `/health` · Instance: Free.
- Env vars: everything in `.env.example` with real values, plus `PYTHON_VERSION=3.12.3`, `FLASK_ENV=production`.
- Notes: free tier sleeps after ~15 min idle (first request ~50s) → open the URL before the demo. Disk is ephemeral → `logs/app.log` resets on redeploy (document in README); data is safe in Atlas.
- Fallback host if Render fails: Railway (same GitHub flow, same env vars). If AWS is required: EC2 + gunicorn + nginx, Atlas stays.

### 15.3 Git workflow
- Single `main` branch, small commits after each phase (messages in Section 13), conventional prefixes `feat: fix: chore: docs:`.
- Never commit `.env`. If a secret is committed, rotate it immediately.

---

## 16. Smoke test checklist (run locally after each phase, and on the live URL at the end)
- [ ] `/health` ok (db + ai)
- [ ] Create a person; duplicate email is rejected with a clear message
- [ ] Create meeting with participants and agenda
- [ ] Paste sample notes → AI recap draft → edit one owner → apply → items saved with `source: ai`
- [ ] Close an item without outcome → error shown; with outcome → closed
- [ ] Reassign an item → history + `item.reassigned` log
- [ ] Mark meeting completed → appears in KB
- [ ] Create next meeting → open items carried with history
- [ ] Catch-up brief for an absent participant
- [ ] Find related docs for an item → sensible links with reasons
- [ ] Leave handover end-to-end
- [ ] Break the API key → recap/brief/linking still work via fallback with banners
- [ ] Invalid input (bad date, empty title) → 422 with field messages in UI
- [ ] `logs/app.log`: JSON lines, request ids, `ai.call` with latency, no API key or Mongo password

---

## 17. README template

```
# HandOff — AI-Powered Knowledge & Task Management Platform
Live: <render-url>   ·   Repo: <github-url>

## Overview
One paragraph: the problem and what the app does.

## Features
Bullets mapped to the assessment outcomes + special feature.

## Tech stack & architecture
Table + architecture diagram + layering explanation (routes → services → repositories → MongoDB; AI isolated in services/ai).

## Data model
Collections and why MongoDB (nested participants/decisions/history; one item record across meetings via meeting_ids).

## AI configuration
- Provider/model: Google Gemini (<model>), set via GEMINI_MODEL / GEMINI_API_KEY.
- Where AI is used: recap, catch-up brief, KB linking, handover brief + owner suggestions.
- Prompts: in app/services/ai/prompts.py (summarise rules).
- Reliability: JSON schema output, Pydantic validation, retry with error feedback, timeout,
  post-validation (owner grounding, date sanity, confidence, duplicate check, id check),
  human review before saving, rule-based fallbacks.

## Data source
Seeded demo data (people, 8 team docs, 3 meetings) + sample raw notes in scripts/sample_notes.
User-created data persisted in MongoDB Atlas.

## Logging
Format, fields, events, request id flow, file location + rotation, redaction.
Example log lines.

## Special feature: Leave Handover Mode
What it does + why it adds value.

## API
Endpoint table (link to section in this README).

## Running locally
git clone … · python -m venv venv · pip install -r requirements.txt · cp .env.example .env · flask --app wsgi run

## Deployment
Render + Atlas setup, env vars, start command.

## Approach
How I broke down the problem, phase order, key decisions and trade-offs.

## Assumptions
- Single team, no authentication (actor name chosen in UI).
- Recordings/emails are represented as pasted text transcripts.
- Dates in UTC.

## Known limitations
- No auth/roles; no real email/Slack/calendar integration.
- TF-IDF retrieval is lexical; embeddings would improve semantic matching.
- Log file is ephemeral on Render's free tier (stdout logs are kept in Render's dashboard); production would ship logs to a log service.
- Free-tier cold starts; Gemini free-tier rate limits.
- AI can still misread notes — mitigated by review step and needs-review flags.

## Future improvements
Auth, audio transcription, email/Slack ingestion, embeddings, reminders/notifications.
```

---

## 18. Interview prep — decisions I must be able to explain
- **Why Flask + MongoDB?** Fast to build; nested documents fit meetings/history; Atlas persists while Render's disk is ephemeral.
- **How carry-forward keeps history:** one item document, `meeting_ids` grows, `history` gets a `carried_forward` event — no duplicated items.
- **How AI is made reliable:** schema-constrained output, Pydantic, retry with error feedback, deterministic post-checks, human review, fallbacks.
- **Why TF-IDF + LLM for linking:** cheap retrieval narrows candidates; the LLM judges relevance and explains why; id check prevents hallucinated links.
- **How request IDs work:** generated in `before_request`, stored in `g`, injected into every log line by a filter, returned in the header and in error responses.
- **How secrets stay out of logs:** env vars only, redaction filter on keys/URIs, no raw notes logged.
- **Why the special feature matters:** it targets the exact "colleague goes on leave" scenario from the problem statement.
- **What I'd do with more time:** auth, embeddings, transcription, integrations, notifications.
