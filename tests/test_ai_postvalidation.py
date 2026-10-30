import json
from types import SimpleNamespace

import pytest

from app.config import Config
from app.errors import AIError
from app.schemas.ai import RecapOut
from app.services.ai import gemini_client
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


class _Fake:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), 0
        self.models = SimpleNamespace(generate_content=self._gen)

    def _gen(self, **kw):
        self.calls += 1
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return SimpleNamespace(text=r)


GOOD = json.dumps({"summary": "ok", "decisions": [], "action_items": [], "open_questions": []})


def _patch(monkeypatch, fake):
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gemini_client, "_get_client", lambda: fake)
    monkeypatch.setattr(gemini_client.time, "sleep", lambda s: None)


def test_client_retries_invalid_json_then_succeeds(monkeypatch):
    fake = _Fake(["not json", GOOD])
    _patch(monkeypatch, fake)
    assert gemini_client.generate_json("recap", "p", RecapOut).summary == "ok" and fake.calls == 2


def test_client_raises_aierror_after_attempts(monkeypatch):
    fake = _Fake([RuntimeError("boom"), RuntimeError("boom")])
    _patch(monkeypatch, fake)
    with pytest.raises(AIError):
        gemini_client.generate_json("recap", "p", RecapOut)


def test_client_without_key_raises():
    with pytest.raises(AIError):
        gemini_client.generate_json("recap", "p", RecapOut)


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
