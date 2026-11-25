from dataclasses import dataclass
from decimal import Decimal
from secrets import randbelow, token_hex
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.db.complaint_models import Complaint, ComplaintAssignment, ComplaintVisibility
from app.db.models import AuditLog, Department, Organization, Role, ServiceArea
from app.services import complaints
from app.services.auth import add_user
from app.services.complaint_routing import _contains

API = "/api/v1"
REPORTS = f"{API}/complaints"
QUEUE = f"{API}/authority/complaints"
PASSWORD = "local complaint test phrase"


@dataclass(frozen=True)
class Site:
    organization: Organization
    department: Department
    area: ServiceArea
    latitude: float
    longitude: float


def _ring(x, y, margin):
    return [
        [x - margin, y - margin], [x + margin, y - margin], [x + margin, y + margin],
        [x - margin, y + margin], [x - margin, y - margin],
    ]


def _site(db, *, organization=None, department=None, center=None):
    if organization is None:
        organization = Organization(name="Synthetic water-service organization")
        db.add(organization)
        db.flush()
    if department is None:
        department = Department(organization_id=organization.id, code=uuid4().hex, name="Water maintenance")
        db.add(department)
    latitude, longitude = center or ((randbelow(130_000) - 65_000) / 1000, (randbelow(280_000) - 140_000) / 1000)
    area = ServiceArea(
        organization_id=organization.id,
        name="Synthetic service area",
        boundary_geojson={"type": "Polygon", "coordinates": [_ring(longitude, latitude, 0.0002)]},
    )
    db.add(area)
    db.commit()
    return Site(organization, department, area, latitude, longitude)


def _account(full_name):
    return {"full_name": full_name, "email": f"{uuid4()}@example.com", "password": PASSWORD}


def _data(response, status=200):
    assert response.status_code == status, response.text
    return response.json()["data"]


def _login(client, account):
    credentials = {"email": account["email"], "password": account["password"]}
    result = _data(client.post(f"{API}/auth/login", json=credentials, headers={"X-CivicFix-CSRF": "1"}))
    return {"Authorization": f"Bearer {result['access_token']}"}


def _citizen(client):
    account = _account("Synthetic citizen")
    created = _data(client.post(f"{API}/auth/register", json=account), 201)
    return created, _login(client, account)


def _admin(client, db):
    account = _account("Synthetic platform administrator")
    add_user(db, account["full_name"], account["email"], account["password"], Role.ADMIN)
    db.commit()
    return _login(client, account)


def _staff(client, admin, site, *, department=None, area=None):
    account = _account("Synthetic water-service staff")
    payload = {
        **account,
        "organization_id": str(site.organization.id),
        "department_ids": [str((department or site.department).id)],
        "service_area_ids": [str((area or site.area).id)],
    }
    record = _data(client.post(f"{API}/admin/staff", headers=admin, json=payload), 201)
    return record["user"], _login(client, account)


def _report(site, **fields):
    return {
        "title": "Leaking water pipe",
        "description": "Water has been flowing from a broken pipe since this morning.",
        "latitude": site.latitude,
        "longitude": site.longitude,
        "location_label": "Synthetic private address",
        **fields,
    }


def _review(client, staff, complaint_id):
    return _data(client.post(f"{QUEUE}/{complaint_id}/review", headers=staff, json={
        "reason": "Verified that the report concerns water infrastructure.",
        "public_message": "The water team reviewed your report.",
    }))


def _assignment(site, assignee=None):
    return {
        "department_id": str(site.department.id),
        "assigned_staff_id": assignee,
        "reason": "Water maintenance handles damaged supply pipes.",
        "public_message": "The water maintenance department is handling the repair.",
    }


def test_leaking_pipe_workflow(client, db):
    site = _site(db)
    admin = _admin(client, db)
    reviewer, reviewer_headers = _staff(client, admin, site)
    technician, technician_headers = _staff(client, admin, site)
    owner, citizen = _citizen(client)
    categories = _data(client.get(f"{API}/public/categories"))
    category_id = next(category["id"] for category in categories if category["code"] == "WATER_LEAKAGE")

    created = _data(client.post(REPORTS, headers=citizen, json=_report(site, category_id=category_id)), 201)
    complaint_id = created["id"]
    reference = created["public_reference"]
    assert created["status"] == "SUBMITTED" and created["visibility"] == "PRIVATE"
    assert reference.startswith("CF-") and len(reference.split("-")[-1]) == 6
    assert client.get(f"{API}/public/complaints/{reference}").status_code == 404
    mine = client.get(f"{REPORTS}/mine?page_size=1", headers=citizen)
    assert [row["public_reference"] for row in _data(mine)] == [reference]
    assert mine.json()["meta"]["total"] == 1
    assert _data(client.get(f"{REPORTS}/{complaint_id}", headers=citizen)) == created
    assert "organization_id" not in created
    scoped_queue = _data(client.get(f"{QUEUE}?status=SUBMITTED", headers=reviewer_headers))
    assert [row["id"] for row in scoped_queue] == [complaint_id]

    reviewed = _review(client, reviewer_headers, complaint_id)
    assert reviewed["status"] == "UNDER_REVIEW"
    assert reviewed["organization_id"] == str(site.organization.id)
    assert reviewed["service_area_id"] == str(site.area.id)
    assignment = _assignment(site, technician["id"])
    assigned = _data(client.post(f"{QUEUE}/{complaint_id}/assignments", headers=reviewer_headers, json=assignment), 201)
    assert assigned["status"] == "ASSIGNED" and assigned["assigned_staff_id"] == technician["id"]
    assert _data(client.post(f"{QUEUE}/{complaint_id}/status", headers=technician_headers, json={
        "status": "IN_PROGRESS", "reason": "Crew arrived and isolated the broken pipe.",
        "public_message": "Repair work is underway.",
    }))["status"] == "IN_PROGRESS"

    internal_note = "Internal dispatch note about a private property access code."
    _data(client.post(f"{QUEUE}/{complaint_id}/updates", headers=technician_headers, json={
        "message": internal_note, "visibility": "INTERNAL",
    }), 201)
    _data(client.post(f"{QUEUE}/{complaint_id}/updates", headers=technician_headers, json={
        "message": "The damaged pipe section has been replaced.", "visibility": "PUBLIC",
    }), 201)
    resolved = _data(client.post(f"{QUEUE}/{complaint_id}/status", headers=technician_headers, json={
        "status": "RESOLVED", "reason": "Crew completed and pressure-tested the repair.",
        "resolution_description": "A pressure test found no leaks at the replacement joint.",
        "public_message": "The leaking pipe was repaired.",
    }))
    assert resolved["status"] == "RESOLVED" and resolved["resolved_at"].endswith("Z")

    history_result = client.get(f"{REPORTS}/{complaint_id}/updates", headers=citizen)
    citizen_history = _data(history_result)
    statuses = [row["new_status"] for row in citizen_history if row["new_status"] is not None]
    assert statuses == ["SUBMITTED", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS", "RESOLVED"]
    assert citizen_history[-1]["message"] == "The leaking pipe was repaired."
    assert any(row["message"] == "The damaged pipe section has been replaced." for row in citizen_history)
    assert internal_note not in history_result.text
    assert all(set(row) == {"id", "old_status", "new_status", "message", "created_at"} for row in citizen_history)
    assert all(row["created_at"].endswith("Z") for row in citizen_history)
    citizen_detail = _data(client.get(f"{REPORTS}/{complaint_id}", headers=citizen))
    assert citizen_detail["status"] == "RESOLVED" and "resolution_description" not in citizen_detail

    staff_history = _data(client.get(f"{REPORTS}/{complaint_id}/updates", headers=reviewer_headers))
    assert [row["actor_id"] for row in staff_history[:4]] == [owner["id"], reviewer["id"], reviewer["id"], technician["id"]]
    assert all(row["reason"] for row in staff_history)
    assert any(row["message"] == internal_note and row["visibility"] == "INTERNAL" for row in staff_history)
    record = db.scalar(select(ComplaintAssignment).where(ComplaintAssignment.complaint_id == UUID(complaint_id)))
    assert (str(record.assigned_by), str(record.assigned_staff_id), record.reason) == (
        reviewer["id"], technician["id"], assignment["reason"],
    )
    assert record.assigned_at is not None
    audit = db.scalars(select(AuditLog).where(AuditLog.entity_id == UUID(complaint_id)).order_by(AuditLog.created_at)).all()
    assert [row.action for row in audit] == [
        "COMPLAINT_SUBMITTED", "COMPLAINT_REVIEWED", "COMPLAINT_ASSIGNED", "COMPLAINT_STATUS_CHANGED",
        "COMPLAINT_NOTE_ADDED", "COMPLAINT_NOTE_ADDED", "COMPLAINT_STATUS_CHANGED",
    ]
    assert audit[-1].event_metadata["new_status"] == "RESOLVED"
    assert internal_note not in str([event.event_metadata for event in audit])
    print(f"{reference} | {' -> '.join(statuses)} | citizen retrieved {len(citizen_history)} visible history entries")


def test_denied_access_and_invalid_transition_leave_state_and_history_unchanged(client, db):
    site = _site(db)
    other = _site(db)
    other_area = _site(db, organization=site.organization, department=site.department)
    other_department = Department(organization_id=site.organization.id, code="OTHER", name="Other department")
    db.add(other_department)
    db.commit()
    admin = _admin(client, db)
    _, staff = _staff(client, admin, site)
    outsider, outside_org = _staff(client, admin, other)
    _, outside_area = _staff(client, admin, site, area=other_area.area)
    _, outside_department = _staff(client, admin, site, department=other_department)
    _, citizen = _citizen(client)
    _, other_citizen = _citizen(client)
    assert client.post(REPORTS, json=_report(site)).status_code == 401
    report = _data(client.post(REPORTS, headers=citizen, json=_report(site)), 201)
    path = f"{REPORTS}/{report['id']}"
    status = f"{QUEUE}/{report['id']}/status"
    assignments = f"{QUEUE}/{report['id']}/assignments"
    assert client.get(path, headers=other_citizen).status_code == 404
    assert client.get(f"{path}/updates", headers=other_citizen).status_code == 404
    assert _data(client.get(f"{REPORTS}/mine", headers=other_citizen)) == []
    assert client.post(status, headers=citizen, json={"status": "UNDER_REVIEW", "reason": "Unauthorized."}).status_code == 403

    _review(client, staff, report["id"])
    assert client.post(assignments, headers=staff, json=_assignment(other)).status_code == 422
    assert client.post(assignments, headers=staff, json=_assignment(site, outsider["id"])).status_code == 422
    _data(client.post(assignments, headers=staff, json=_assignment(site)), 201)
    before = _data(client.get(f"{path}/updates", headers=staff))
    for headers in (outside_org, outside_area, outside_department):
        assert client.post(status, headers=headers, json={"status": "IN_PROGRESS", "reason": "Outside scope."}).status_code == 404
        assert client.get(path, headers=headers).status_code == 404
        assert _data(client.get(QUEUE, headers=headers)) == []
    assert client.post(status, headers=staff, json={
        "status": "RESOLVED", "reason": "Skipping work.", "resolution_description": "No repair was performed.",
    }).status_code == 409
    assert _data(client.get(path, headers=citizen))["status"] == "ASSIGNED"
    assert _data(client.get(f"{path}/updates", headers=staff)) == before
    assert len(db.scalars(select(ComplaintAssignment).where(ComplaintAssignment.complaint_id == UUID(report["id"]))).all()) == 1


def test_history_write_failure_rolls_back_status(client, db, monkeypatch):
    site = _site(db)
    _, staff = _staff(client, _admin(client, db), site)
    _, citizen = _citizen(client)
    report = _data(client.post(REPORTS, headers=citizen, json=_report(site)), 201)
    path = f"{REPORTS}/{report['id']}"
    before = _data(client.get(f"{path}/updates", headers=staff))

    def fail_after_flush(session, complaint, *args, **kwargs):
        session.flush()
        assert complaint.status == "UNDER_REVIEW"
        raise RuntimeError("simulated history write failure")

    monkeypatch.setattr(complaints, "_record_update", fail_after_flush)
    with pytest.raises(RuntimeError, match="simulated history write failure"):
        client.post(f"{QUEUE}/{report['id']}/review", headers=staff, json={"reason": "Checked the report."})
    assert _data(client.get(path, headers=staff))["status"] == "SUBMITTED"
    assert _data(client.get(f"{path}/updates", headers=staff)) == before
    assert len(db.scalars(select(AuditLog).where(AuditLog.entity_id == UUID(report["id"]))).all()) == 1


def test_create_is_idempotent_retries_reference_collision_and_validates_coordinates(client, db, monkeypatch):
    site = _site(db)
    _, citizen = _citizen(client)
    _, second = _citizen(client)
    key = str(uuid4())
    first_ref, second_ref = token_hex(3), token_hex(3)
    refs = iter([first_ref, first_ref, second_ref])
    monkeypatch.setattr(complaints, "token_hex", lambda _: next(refs))
    assert client.post(REPORTS, headers=citizen, json=_report(site, latitude=91)).status_code == 422
    assert client.post(REPORTS, headers=citizen, json=_report(site, title=" ")).status_code == 422
    payload = _report(site)
    headers = {**citizen, "Idempotency-Key": key}
    first = _data(client.post(REPORTS, headers=headers, json=payload), 201)
    assert _data(client.post(REPORTS, headers=headers, json=payload)) == first
    assert client.post(REPORTS, headers=headers, json={**payload, "title": "A different pipe"}).status_code == 409
    second_result = _data(client.post(REPORTS, headers={**second, "Idempotency-Key": key}, json=payload), 201)
    assert second_result["id"] != first["id"] and second_result["public_reference"] != first["public_reference"]
    assert second_result["public_reference"].endswith(second_ref.upper())
    assert len(_data(client.get(f"{REPORTS}/{first['id']}/updates", headers=citizen))) == 1


def test_public_detail_requires_approved_summary_and_uses_an_allowlist(client, db):
    site = _site(db)
    owner, citizen = _citizen(client)
    report = _data(client.post(REPORTS, headers=citizen, json=_report(site)), 201)
    url = f"{API}/public/complaints/{report['public_reference']}"
    assert client.get(url).status_code == 404
    stored = db.get(Complaint, UUID(report["id"]))
    stored.visibility = ComplaintVisibility.APPROXIMATE
    db.commit()
    assert client.get(url).status_code == 404
    stored.approved_public_summary = "Water leak near a roadway"
    db.commit()
    public = _data(client.get(url))
    assert set(public) == {"public_reference", "title", "category", "status", "created_on", "updated_on"}
    assert public["title"] == "Water leak near a roadway"
    assert owner["id"] not in str(public) and owner["email"] not in str(public)
    assert report["title"] not in str(public) and report["location_label"] not in str(public)


def test_overlapping_service_areas_leave_the_report_unrouted(client, db):
    site = _site(db)
    _site(db, center=(site.latitude, site.longitude))
    _, staff = _staff(client, _admin(client, db), site)
    _, citizen = _citizen(client)
    report = _data(client.post(REPORTS, headers=citizen, json=_report(site)), 201)
    stored = db.get(Complaint, UUID(report["id"]))
    assert stored.organization_id is None and stored.service_area_id is None
    assert _data(client.get(QUEUE, headers=staff)) == []
    assert client.post(f"{QUEUE}/{report['id']}/review", headers=staff, json={"reason": "Cannot claim an overlap."}).status_code == 404
    assert _data(client.get(f"{REPORTS}/{report['id']}", headers=citizen))["visibility"] == "PRIVATE"


def test_service_area_polygon_holes_and_multipolygon_boundaries():
    geometry = {
        "type": "MultiPolygon",
        "coordinates": [[_ring(0, 0, 3), _ring(0, 0, 1)], [_ring(8, 8, 1)]],
    }
    assert _contains(geometry, Decimal(2), Decimal(0))
    assert _contains(geometry, Decimal(3), Decimal(0))
    assert _contains(geometry, Decimal(8), Decimal(8))
    assert not _contains(geometry, Decimal(0), Decimal(0))
    assert not _contains(geometry, Decimal(1), Decimal(0))
    assert not _contains(geometry, Decimal(20), Decimal(20))
