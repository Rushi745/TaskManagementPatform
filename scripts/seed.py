"""Idempotent seed: people, KB docs, 2 completed meetings + 1 scheduled (via carry-forward). Safe to re-run."""
import logging
from datetime import timedelta

from app.repositories import kb_repo, people_repo
from app.schemas.meeting import Decision, MeetingCreate, MeetingUpdate
from app.services import item_service, kb_service, meeting_service
from app.utils import oid, today_start, utcnow

log = logging.getLogger("app.seed")

PEOPLE = [
    ("Priya Nair", "Product Manager"), ("Rahul Mehta", "Backend Engineer"), ("Sneha Iyer", "QA Engineer"),
    ("Vikram Rao", "DevOps Engineer"), ("Ananya Gupta", "Frontend Engineer"), ("Aarav Shah", "Engineering Manager"),
]

KB = [
    ("Deployment Runbook", ["devops", "release"],
     "How we deploy services to production. 1) Merge to main only after CI is green and one approval. 2) The deploy pipeline builds a container image and rolls it out to staging automatically. 3) Run the smoke test suite against staging; a failing smoke test blocks promotion. 4) Promote to production using a canary: 10% of traffic for 15 minutes, then 50%, then 100%. 5) Watch error rate and p95 latency dashboards during rollout. Rollback: run the rollback job to redeploy the previous image tag; database migrations must be backward compatible so a rollback never needs a schema change. Deployments are frozen on Fridays after 3pm and during declared incidents. After every production deploy, post the release notes in the engineering channel and update the release checklist. The DevOps engineer on call owns the pipeline and the staging database."),
    ("Release Checklist", ["release"],
     "Before every release confirm: all tickets in the release are verified by QA; regression tests for checkout and payments pass; release notes are drafted; feature flags have a documented default; database migrations were reviewed and are backward compatible; the rollback plan is written down; monitoring dashboards and alerts cover new endpoints; customer support has been briefed on user-facing changes. After the release: verify health checks, watch error rates for 30 minutes, announce completion, and schedule a short retrospective if anything went wrong. The release manager signs off the checklist and records the version and date. Hotfixes follow the same checklist in a shortened form but still require a second reviewer."),
    ("API Design Guidelines", ["backend", "api"],
     "All public APIs are JSON over HTTPS and versioned in the path (/v1). Use nouns for resources and HTTP verbs for actions. Return 201 on creation, 204 on empty success, 422 for validation problems and 409 for state conflicts. Errors use one format: code, message, details and a request id. Mutating endpoints that clients may retry, such as payments, must accept an idempotency key header and return the original result for a repeated key. Paginate every list endpoint with limit and cursor parameters. Never expose internal ids that reveal ordering; use opaque ids. Document every endpoint with an example request and response before implementation starts, and review the contract in the design review."),
    ("Q4 Product Roadmap", ["product", "roadmap"],
     "Q4 goals: ship the redesigned checkout (v2) by November 10, reduce failed payments by 30 percent through retry and idempotency improvements, launch the customer feedback portal in early December, and complete the mobile performance project. Risks: the payments gateway documentation is incomplete, QA capacity is limited during the holiday season, and the checkout redesign depends on the frontend component library upgrade. Milestones: October - payment retry fix and staging database upgrade; November - checkout v2 release and incident alerting; December - feedback portal and year-end stabilization. Product reviews the roadmap every sprint planning and records changes as decisions."),
    ("Incident Response Process", ["ops", "incident"],
     "Severity levels: SEV1 customer-facing outage or payment failures, SEV2 degraded functionality, SEV3 minor issue. When an alert fires the on-call engineer acknowledges within 5 minutes, opens an incident channel, and assigns an incident commander. The commander coordinates, a scribe records the timeline, and a communications lead updates support and status page every 30 minutes for SEV1. First priority is mitigation: roll back the last deploy, disable the feature flag or fail over. Root cause analysis comes after service is restored. Within 3 working days publish a blameless postmortem with timeline, impact, root cause, what went well, and action items with owners and due dates. Action items from postmortems are tracked until closed and reviewed in the next engineering meeting."),
    ("Code Review Policy", ["engineering"],
     "Every change needs at least one approving review from a code owner before merge. Pull requests should be small, ideally under 400 changed lines, and include a description, test evidence and a link to the ticket. Reviewers respond within one working day. Review for correctness, security, readability and test coverage; style issues are handled by the linter, not by humans. Authors must not merge their own pull request. Changes touching payments, authentication or data migrations need two approvals including one senior engineer. Blocking comments must be resolved or explicitly deferred with a follow-up ticket. Large refactors are split into mechanical and behavioural pull requests."),
    ("Payments Service Architecture", ["backend", "payments"],
     "The payments service accepts checkout requests from the web and mobile apps, creates a payment record, and calls an external gateway to authorize and capture funds. Components: the API layer, a payment state machine (created, authorized, captured, failed, refunded), a retry worker that re-submits transient gateway failures with exponential backoff, and a webhook consumer that reconciles gateway events. The database stores payment attempts and their gateway references. Known weaknesses: the retry worker can double-submit when a timeout hides a successful capture because requests carry no idempotency key, and gateway outages are only visible through customer complaints because there is no alert on failure rate. Planned improvements: idempotency keys on every gateway call, a failure-rate alert, and a reconciliation job."),
    ("Customer Feedback Summary - October", ["product", "feedback"],
     "October feedback came from 214 support tickets, 38 interviews and app store reviews. Top themes: 1) Checkout failures and duplicate charges frustrate customers, especially on mobile. 2) Users want order status notifications by email and push. 3) Search results are slow on large catalogs. 4) The new dashboard is praised but users ask for export to CSV. Net promoter score dropped from 41 to 36, driven by payment issues. Positive: onboarding is clearer and support response time improved to under four hours. Recommendations: prioritize payment reliability, schedule the notifications work for Q1, and investigate search performance."),
]


def run_seed():
    """Seed everything if the database is empty; returns True when seeding ran."""
    if people_repo.count() > 0:
        return False
    log.info("Seeding database", extra={"event": "seed.started"})
    now, today = utcnow(), today_start()
    for name, role in PEOPLE:
        people_repo.insert({"name": name, "email": f"{name.split()[0].lower()}@digiplus-demo.com", "role": role,
                            "status": "active", "leave": None, "created_at": now})
    by = {p["name"]: p for p in people_repo.list_all()}
    pid = lambda n: str(by[n]["_id"])
    for title, tags, content in KB:
        kb_repo.insert({"title": title, "content": content, "tags": tags, "source": "seed", "meeting_id": None, "created_at": now})
    day = lambda n: (today + timedelta(days=n)).strftime("%Y-%m-%d")

    # --- Sprint 21 Planning (completed, 14 days ago) ---
    s21 = meeting_service.create_meeting(MeetingCreate(
        type="meeting", title="Sprint 21 Planning", date=day(-14),
        agenda=["Sprint goals", "Payment retry bug", "Staging database upgrade", "Q4 roadmap check-in"],
        participant_ids=[pid(n) for n in ("Priya Nair", "Rahul Mehta", "Sneha Iyer", "Vikram Rao", "Ananya Gupta")],
        raw_notes="Priya opened with sprint goals. Retry bug is the top priority, Rahul to fix. Vikram upgrades staging DB. Ananya (absent) owns the checkout UI."), "seed")
    sid = str(s21["_id"])
    meeting_service.update_meeting(sid, MeetingUpdate(
        summary="The team agreed the payment retry bug is the top priority for the sprint and scheduled the staging database upgrade ahead of the checkout v2 release. Ananya was absent but her checkout UI work was confirmed. Roadmap updates for Q4 are to be drafted by product.",
        decisions=[Decision(text="Ship checkout v2 on November 10", made_by="Priya Nair"),
                   Decision(text="Fix the payment retry bug before any new payment features", made_by="Aarav Shah")],
        attendance={pid(n): True for n in ("Priya Nair", "Rahul Mehta", "Sneha Iyer", "Vikram Rao")}))
    mk = lambda **kw: item_service.create_item(meeting_id=sid, source="manual", actor="seed", **kw)
    mk(title="Fix payment retry bug", owner_id=pid("Rahul Mehta"), due_date=day(-5), priority="high",
       description="Retry worker re-submits captured payments after gateway timeouts.")
    a = mk(title="Upgrade staging database", owner_id=pid("Vikram Rao"), due_date=day(-3), priority="medium")
    item_service.close_item(a["_id"], "done", "Upgraded staging to Postgres 15; smoke tests green.", "Vikram Rao")
    b = mk(title="Finalize checkout UI redesign", owner_id=pid("Ananya Gupta"), due_date=day(-2), priority="medium")
    item_service.close_item(b["_id"], "done", "Redesign merged; behind feature flag until release.", "Ananya Gupta")
    c = mk(title="Write regression tests for checkout", owner_id=pid("Sneha Iyer"), due_date=day(3), priority="medium")
    from app.schemas.item import ItemUpdate
    item_service.update_item(c["_id"], ItemUpdate(status="in_progress"), "Sneha Iyer")
    mk(title="Draft Q4 roadmap update", owner_id=pid("Priya Nair"), due_date=day(6), priority="low")
    mk(title="Rotate staging database credentials", owner_id=pid("Vikram Rao"), due_date=day(-6), priority="high",
       description="Old credentials were shared in chat during the DB upgrade.")
    mk(title="Share October customer feedback with the team", owner_id=pid("Priya Nair"), due_date=day(-3), priority="medium")
    mk(title="Fix mobile checkout button alignment", owner_id=pid("Ananya Gupta"), due_date=day(-1), priority="high",
       description="Pay button is cut off on small Android screens.")
    mk(title="Prepare checkout v2 release notes", owner_id=pid("Ananya Gupta"), due_date=day(8), priority="medium")
    mk(title="Approve Q4 hiring plan", owner_id=pid("Aarav Shah"), due_date=day(10), priority="low")
    meeting_service.change_status(sid, "completed", "seed")

    # --- Payments Incident Review (completed, 7 days ago) ---
    inc = meeting_service.create_meeting(MeetingCreate(
        type="meeting", title="Payments Incident Review", date=day(-7),
        agenda=["Timeline", "Root cause", "Follow-ups"],
        participant_ids=[pid(n) for n in ("Rahul Mehta", "Vikram Rao", "Sneha Iyer", "Aarav Shah")],
        raw_notes="Gateway timeouts caused duplicate charges for 40 customers. No alert fired."), "seed")
    iid = str(inc["_id"])
    meeting_service.update_meeting(iid, MeetingUpdate(
        summary="A gateway timeout caused duplicate charges for about 40 customers because retries carried no idempotency key and no alert existed on payment failure rate. The team agreed on idempotency keys, a failure-rate alert and a published postmortem.",
        decisions=[Decision(text="Add idempotency keys to all gateway calls", made_by="Aarav Shah")],
        attendance={pid(n): True for n in ("Rahul Mehta", "Vikram Rao", "Sneha Iyer", "Aarav Shah")}))
    mk2 = lambda **kw: item_service.create_item(meeting_id=iid, source="manual", actor="seed", **kw)
    i1 = mk2(title="Add idempotency keys to payment API", owner_id=pid("Rahul Mehta"), due_date=day(5), priority="high")
    item_service.update_item(i1["_id"], ItemUpdate(status="blocked", note="Waiting on gateway documentation"), "Rahul Mehta")
    mk2(title="Set up alert on payment failure rate", owner_id=pid("Vikram Rao"), due_date=day(2), priority="high")
    mk2(title="Write and publish incident postmortem", owner_id=pid("Rahul Mehta"), due_date=day(4), priority="medium")
    meeting_service.change_status(iid, "completed", "seed")
    # KB links for the incident meeting (hand-picked at seed time)
    from app.extensions import get_db
    docs = {d["title"]: d for d in kb_repo.list_all()}
    links = [{"doc_id": docs[t]["_id"], "title": t, "reason": r, "method": "ai"} for t, r in (
        ("Incident Response Process", "Defines the postmortem and action-item follow-up expected after this incident."),
        ("Payments Service Architecture", "Describes the retry worker and missing idempotency keys behind this incident."))]
    get_db().meetings.update_one({"_id": inc["_id"]}, {"$set": {"kb_links": links}})

    # --- Sprint 22 Planning (scheduled, created via carry-forward) ---
    meeting_service.create_next(sid, "Sprint 22 Planning", day(2), "seed")
    log.info("Seeding finished", extra={"event": "seed.finished"})
    return True
