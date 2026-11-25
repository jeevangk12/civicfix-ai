import json
from io import BytesIO
from uuid import UUID

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.complaint_models import Complaint
from app.db.intelligence_models import Analysis
from app.db.models import AuditLog
from app.services import gemini
from test_complaints import API, QUEUE, REPORTS, _admin, _citizen, _data, _report, _site, _staff


@pytest.fixture
def provider(client, settings):
    client.app.state.gemini = gemini.GeminiClient(settings.model_copy(update={
        "gemini_model": "gemini-fixture", "gemini_api_key": SecretStr("local-fixture"),
    }))


@pytest.mark.usefixtures("provider")
def test_valid_gemini_response_is_saved_as_recommendation(client, db, monkeypatch):
    site = _site(db)
    _, citizen = _citizen(client)
    _, staff = _staff(client, _admin(client, db), site)
    report = _report(site, description="Broken pipe reported by Synthetic citizen at example@example.org.")
    calls = []

    def respond(request, *, timeout):
        calls.append(json.loads(request.data))
        with Session(client.app.state.database_engine) as worker_db:
            assert worker_db.scalar(select(Complaint).where(Complaint.description == report["description"]))
        recommendation = {
            "category": "WATER_LEAKAGE", "summary": "Water escaping a broken pipe.", "priority": "CRITICAL",
            "priority_reason": "Uncontrolled discharge.", "recommended_department_code": site.department.code,
            "confidence": 0.93, "needs_human_review": False, "safety_flags": [],
        }
        return BytesIO(json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps(recommendation)}]}}]}).encode())

    monkeypatch.setattr(gemini, "urlopen", respond)
    case = _data(client.post(REPORTS, headers=citizen, json=report), 201)
    assert len(calls) == 1
    prompt = calls[0]["contents"][0]["parts"][0]["text"]
    assert "example@example.org" not in prompt and "Synthetic citizen" not in prompt
    analysis_url = f"{QUEUE}/{case['id']}/analysis"
    result = _data(client.get(analysis_url, headers=staff))
    assert result["status"] == "SUCCEEDED" and result["priority"] == "CRITICAL"
    assert result["needs_human_review"] and result["department"] == site.department.name
    assert result["confidence"] == 0.93 and case["category_id"] is None and case["status"] == "SUBMITTED"
    assert client.get(analysis_url, headers=citizen).status_code == 403
    record = db.scalar(select(Analysis).where(Analysis.complaint_id == UUID(case["id"])))
    assert record.model_name == "gemini-fixture" and record.completed_at >= record.started_at


@pytest.mark.usefixtures("provider")
@pytest.mark.parametrize(("failure", "expected", "attempts"), [
    ("bad json", "MALFORMED_RESPONSE", 1),
    ('{"confidence":5,"priority":"UNKNOWN"}', "MALFORMED_RESPONSE", 1),
    (None, "PROVIDER_UNAVAILABLE", 2),
])
def test_malformed_gemini_or_outage_preserves_complaint(client, db, monkeypatch, failure, expected, attempts):
    site = _site(db)
    _, citizen = _citizen(client)
    calls = []

    def respond(request, *, timeout):
        calls.append(timeout)
        if failure is None:
            raise TimeoutError("Synthetic provider diagnostics")
        return BytesIO(json.dumps({"candidates": [{"content": {"parts": [{"text": failure}]}}]}).encode())

    monkeypatch.setattr(gemini, "urlopen", respond)
    response = client.post(REPORTS, headers=citizen, json=_report(site))
    case = _data(response, 201)
    assert len(calls) == attempts
    assert _data(client.get(f"{REPORTS}/{case['id']}", headers=citizen))["status"] == "SUBMITTED"
    record = db.scalar(select(Analysis).where(Analysis.complaint_id == UUID(case["id"])))
    assert record.status == "FAILED" and record.sanitized_error_code == expected and record.summary is None
    assert "provider diagnostics" not in response.text and "sanitized_error_code" not in response.text


@pytest.mark.parametrize("decision", ["CONFIRMED_DUPLICATE", "NOT_DUPLICATE"])
def test_staff_review_duplicate_suggestions(client, db, decision):
    site = _site(db)
    admin = _admin(client, db)
    reviewer, staff = _staff(client, admin, site)
    _, outsider = _staff(client, admin, _site(db))
    _, citizen = _citizen(client)
    original = _data(client.post(REPORTS, headers=citizen, json=_report(site)), 201)
    follow_up = _data(client.post(REPORTS, headers=citizen, json=_report(site)), 201)
    endpoint = f"{QUEUE}/{follow_up['id']}/duplicates"
    (suggestion,) = _data(client.get(endpoint, headers=staff))
    assert suggestion["candidate_id"] == original["id"] and suggestion["review_status"] == "PENDING"
    review = f"{API}/authority/duplicates/{suggestion['id']}/review"
    payload = {"decision": decision, "reason": "Compared location and the reported damage."}
    assert client.get(endpoint, headers=outsider).status_code == 404
    assert client.post(review, headers=outsider, json=payload).status_code == 404
    decided = _data(client.post(review, headers=staff, json=payload))
    assert decided["review_status"] == decision and decided["reviewed_by"] == reviewer["id"]
    assert decided["reviewed_at"].endswith("Z")
    assert client.post(review, headers=staff, json=payload).status_code == 409
    assert len(_data(client.get(f"{REPORTS}/mine", headers=citizen))) == 2
    history = client.get(f"{REPORTS}/{follow_up['id']}/updates", headers=citizen)
    assert ("another report describes the same issue" in history.text) == (decision == "CONFIRMED_DUPLICATE")
    assert (original["public_reference"] in history.text) == (decision == "CONFIRMED_DUPLICATE")
    assert client.get(f"{API}/public/complaints/{original['public_reference']}").status_code == 404
    notices = _data(client.get(f"{API}/notifications", headers=citizen))
    assert any(row["type"] == "DUPLICATE_CONFIRMED" for row in notices) == (decision == "CONFIRMED_DUPLICATE")
    actions = db.scalars(select(AuditLog.action).where(AuditLog.entity_id == UUID(follow_up["id"]))).all()
    assert ("DUPLICATE_CONFIRMED" if decision == "CONFIRMED_DUPLICATE" else "DUPLICATE_DISMISSED") in actions
