import json
from types import SimpleNamespace

import pytest

from app.config import Config
from app.errors import AIError
from app.schemas.ai import RecapOut
from app.services.ai import llm_client
from app.services.ai.fallback import recap_fallback
from app.services.ai.recap import post_validate

PARTS = [{"person_id": "a1", "name": "Rahul Mehta"}, {"person_id": "a2", "name": "Sneha Iyer"}]


def _raw(**kw):
    base = {"title": "Fix bug", "owner": "Rahul Mehta", "due_date": "2026-11-06", "priority": "medium", "evidence": "x", "confidence": 0.9}
    base.update(kw)
    return {"summary": "s", "decisions": [], "open_questions": [], "action_items": [base]}


def test_owner_not_participant_is_nulled_and_flagged():
    it = post_validate(_raw(owner="Karan"), PARTS, [])["items"][0]
    assert it["owner_id"] is None and it["needs_review"] is True


def test_owner_first_name_resolves():
    assert post_validate(_raw(owner="rahul"), PARTS, [])["items"][0]["owner_name"] == "Rahul Mehta"


def test_bad_and_far_dates_are_dropped():
    assert post_validate(_raw(due_date="garbage"), PARTS, [])["items"][0]["due_date"] is None
    far = post_validate(_raw(due_date="2031-01-01"), PARTS, [])["items"][0]
    assert far["due_date"] is None and far["needs_review"]


def test_low_confidence_needs_review():
    assert post_validate(_raw(confidence=0.3), PARTS, [])["items"][0]["needs_review"]


def test_duplicate_detected():
    existing = [{"_id": "i1", "title": "Fix payment retry bug"}]
    it = post_validate(_raw(title="Fix payment retry bug"), PARTS, existing)["items"][0]
    assert it["possible_duplicate_of"]["id"] == "i1"


def test_fallback_extracts_items_decisions():
    notes = "Sprint sync\nTODO: Rahul fix retry bug 2026-11-06\n@Sneha write tests\nWe agreed to ship Nov 10"
    out = recap_fallback(notes, PARTS)
    assert [i["owner"] for i in out["action_items"]] == ["Rahul Mehta", "Sneha Iyer"]
    assert out["decisions"] and out["summary"]


GOOD = json.dumps({"summary": "ok", "decisions": [], "action_items": [], "open_questions": []})


@pytest.fixture()
def two_providers(monkeypatch):
    monkeypatch.setattr(Config, "GROQ_API_KEY", "g-key")
    monkeypatch.setattr(Config, "CEREBRAS_API_KEY", "c-key")
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")
    monkeypatch.setattr(llm_client.time, "sleep", lambda s: None)


def _script(monkeypatch, replies):
    """replies: {provider_name: [reply or Exception, ...]}. Records the provider call order."""
    calls = []

    def fake_call(p, attempt, prompt, schema):
        calls.append(p.name)
        r = replies[p.name].pop(0)
        if isinstance(r, Exception):
            raise r
        return r, p.model

    monkeypatch.setattr(llm_client, "_call", fake_call)
    return calls


def test_invalid_json_retries_same_provider(monkeypatch, two_providers):
    calls = _script(monkeypatch, {"groq": ["not json", GOOD], "cerebras": []})
    assert llm_client.generate_json("recap", "p", RecapOut).summary == "ok"
    assert calls == ["groq", "groq"]


def test_transport_error_fails_over_to_next_provider(monkeypatch, two_providers):
    calls = _script(monkeypatch, {"groq": [RuntimeError("429")], "cerebras": [GOOD]})
    assert llm_client.generate_json("recap", "p", RecapOut).summary == "ok"
    assert calls == ["groq", "cerebras"]


def test_all_providers_fail_raises_aierror(monkeypatch, two_providers):
    _script(monkeypatch, {"groq": [RuntimeError("x")], "cerebras": [RuntimeError("x"), RuntimeError("x")]})
    with pytest.raises(AIError):
        llm_client.generate_json("recap", "p", RecapOut)


def test_no_keys_raises_aierror():
    with pytest.raises(AIError):
        llm_client.generate_json("recap", "p", RecapOut)


def test_recap_endpoint_falls_back_without_key_and_apply_saves(client, people):
    m = client.post("/api/meetings", json={"title": "Sync", "date": "2026-11-03", "participant_ids": list(people.values()),
                                           "raw_notes": "Weekly sync\nTODO: Rahul fix the retry bug 2026-11-06\nWe agreed to ship Nov 10"}).json
    d = client.post(f"/api/meetings/{m['id']}/recap", json={}).json
    assert d["source"] == "fallback" and d["warning"] and d["items"][0]["owner_name"] == "Rahul Mehta"
    r = client.post(f"/api/meetings/{m['id']}/recap/apply", json={"summary": d["summary"], "decisions": d["decisions"], "source": "fallback",
                    "items": [{"title": i["title"], "owner_id": i["owner_id"], "due_date": i["due_date"], "needs_review": i["needs_review"]} for i in d["items"]]})
    assert r.status_code == 201
    items = client.get(f"/api/items?meeting_id={m['id']}").json
    assert items[0]["source"] == "fallback"


def test_recap_requires_notes(client, people):
    m = client.post("/api/meetings", json={"title": "Sync", "date": "2026-11-03"}).json
    assert client.post(f"/api/meetings/{m['id']}/recap", json={}).status_code == 422


def test_close_without_outcome_is_409(client, people):
    m = client.post("/api/meetings", json={"title": "Sync", "date": "2026-11-03"}).json
    i = client.post("/api/items", json={"title": "Do thing", "meeting_id": m["id"]}).json
    assert client.post(f"/api/items/{i['id']}/close", json={"status": "done"}).status_code == 409
    assert client.post(f"/api/items/{i['id']}/close", json={"status": "done", "outcome": "Finished it"}).status_code == 200


def test_openai_compatible_request_shape(monkeypatch):
    """Groq/Cerebras call: auth header, JSON-object mode, schema in prompt, content parsed from choices."""
    seen = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        seen.update(url=url, body=json, headers=headers)
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"choices": [{"message": {"content": GOOD}}]})

    monkeypatch.setattr(llm_client.httpx, "post", fake_post)
    monkeypatch.setattr(Config, "GROQ_API_KEY", "g-key")
    monkeypatch.setattr(Config, "CEREBRAS_API_KEY", "")
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")
    assert llm_client.generate_json("recap", "hello", RecapOut).summary == "ok"
    assert seen["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert seen["headers"]["Authorization"] == "Bearer g-key"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert "action_items" in seen["body"]["messages"][1]["content"]


def test_linker_drops_hallucinated_ids_and_keeps_valid(client, monkeypatch):
    from app.schemas.ai import LinkDecision, LinkOut
    from app.schemas.kb import KBCreate
    from app.services import kb_service
    from app.services.ai import linker

    doc = kb_service.add_doc(KBCreate(title="Deployment Runbook", content="How to deploy services to production with canary rollout and rollback."))
    fake = LinkOut(links=[LinkDecision(doc_id=str(doc["_id"]), relevant=True, reason="About deploys"),
                          LinkDecision(doc_id="000000000000000000000000", relevant=True, reason="invented")])
    monkeypatch.setattr(linker, "generate_json", lambda *a, **k: fake)
    links, source = linker.find_links("action item", "Deploy the service to production with a rollback plan")
    assert source == "ai" and [l["title"] for l in links] == ["Deployment Runbook"]


def test_linker_fallback_uses_tfidf_without_ai(client):
    from app.schemas.kb import KBCreate
    from app.services import kb_service
    from app.services.ai import linker

    kb_service.add_doc(KBCreate(title="Incident Response Process", content="Severity levels, on-call engineer acknowledges incidents, postmortem within three days."))
    links, source = linker.find_links("action item", "Write incident postmortem for the payments outage on-call")
    assert source == "fallback" and links and links[0]["method"] == "tfidf"


def test_brief_fallback_for_absent_person(client, people):
    m = client.post("/api/meetings", json={"title": "Sync", "date": "2026-11-03", "participant_ids": list(people.values())}).json
    client.post("/api/items", json={"title": "Fix retry bug", "meeting_id": m["id"], "owner_id": people["Rahul"]})
    r = client.post(f"/api/meetings/{m['id']}/brief", json={"person_id": people["Rahul"]})
    assert r.status_code == 200 and r.json["source"] == "fallback"
    assert any("Fix retry bug" in x for x in r.json["content"]["your_action_items"])


def test_kb_validation_and_search(client):
    assert client.post("/api/kb", json={"title": "ab", "content": "short"}).status_code == 422
    client.post("/api/kb", json={"title": "Release Checklist", "content": "Confirm regression tests pass and rollback plan exists before every release."})
    assert client.get("/api/kb?q=rollback release").json[0]["title"] == "Release Checklist"


def _seed_handover(client, people):
    m = client.post("/api/meetings", json={"title": "Sprint", "date": "2026-11-03", "participant_ids": list(people.values())}).json
    ids = [client.post("/api/items", json={"title": t, "meeting_id": m["id"], "owner_id": people["Rahul"], "due_date": d}).json["id"]
           for t, d in (("Old overdue task", "2020-01-01"), ("Due soon task", "2099-01-05"), ("Much later task", "2099-12-31"))]
    return m, ids


def test_handover_preview_groups_and_validates(client, people):
    _, ids = _seed_handover(client, people)
    r = client.post("/api/handover/preview", json={"from_person_id": people["Rahul"], "leave_from": "2099-01-01", "leave_to": "2099-01-15"})
    assert r.status_code == 200 and r.json["source"] == "fallback"
    urg = {i["title"]: i["urgency"] for i in r.json["items"]}
    assert urg == {"Old overdue task": "overdue", "Due soon task": "during", "Much later task": "after"}
    assert all(i["suggested_owner_id"] and i["suggested_owner_id"] != people["Rahul"] for i in r.json["items"])
    bad = client.post("/api/handover/preview", json={"from_person_id": people["Rahul"], "leave_from": "2099-02-01", "leave_to": "2099-01-01"})
    assert bad.status_code == 422


def test_handover_execute_reassigns_logs_history_and_marks_leave(client, people):
    _, ids = _seed_handover(client, people)
    payload = {"from_person_id": people["Rahul"], "leave_from": "2099-01-01", "leave_to": "2099-01-15", "note": "back soon",
               "assignments": [{"item_id": i, "to_person_id": people["Sneha"]} for i in ids]}
    r = client.post("/api/handover/execute", json=payload)
    assert r.status_code == 201 and r.json["reassigned"] == 3
    item = client.get(f"/api/items/{ids[0]}").json
    assert item["owner_name"] == "Sneha Iyer" and "reassigned" in [h["event"] for h in item["history"]]
    rahul = [p for p in client.get("/api/people").json if p["id"] == people["Rahul"]][0]
    assert rahul["status"] == "on_leave"
    rec = client.get(f"/api/meetings/{r.json['meeting_id']}").json
    assert rec["type"] == "handover" and rec["status"] == "completed" and len(rec["handover"]["item_ids"]) == 3
    # second attempt: items are no longer Rahul's -> validation error, nothing changes
    assert client.post("/api/handover/execute", json=payload).status_code == 422


def test_handover_ai_output_is_post_validated(client, people, monkeypatch):
    from app.schemas.ai import HandoverBriefOut, HandoverItemNote
    from app.services.ai import handover_ai

    _, ids = _seed_handover(client, people)
    fake = HandoverBriefOut(overview="AI overview", risks=["r1"], items=[
        HandoverItemNote(item_id=ids[0], context="AI context", suggested_owner="Sneha Iyer", suggestion_reason="QA knows it"),
        HandoverItemNote(item_id="invented-id", context="x", suggested_owner="Sneha Iyer", suggestion_reason="x"),
        HandoverItemNote(item_id=ids[1], context="ctx2", suggested_owner="Nobody Real", suggestion_reason="x")])
    monkeypatch.setattr(handover_ai, "generate_json", lambda *a, **k: fake)
    r = client.post("/api/handover/preview", json={"from_person_id": people["Rahul"], "leave_from": "2099-01-01", "leave_to": "2099-01-15"}).json
    assert r["source"] == "ai" and r["overview"] == "AI overview"
    by = {i["id"]: i for i in r["items"]}
    assert by[ids[0]]["context"] == "AI context" and by[ids[0]]["suggested_owner_name"] == "Sneha Iyer"
    assert by[ids[1]]["suggested_owner_name"] in ("Sneha Iyer", "Priya Nair")   # invented owner replaced by heuristic
    assert by[ids[2]]["context"]                                                  # missing note filled by template
