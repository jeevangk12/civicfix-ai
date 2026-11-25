from uuid import uuid4

from test_complaints import (
    API, QUEUE, REPORTS, _admin, _assignment, _citizen, _data, _report, _review, _site, _staff,
)


def test_scoped_workflow_and_admin_audit(client, db):
    site = _site(db)
    admin = _admin(client, db)
    reviewer, staff = _staff(client, admin, site)
    _, outsider = _staff(client, admin, _site(db))
    _, citizen = _citizen(client)
    case = _data(client.post(REPORTS, headers=citizen, json=_report(site)), 201)
    case_id = case["id"]
    endpoint = f"{QUEUE}/{case_id}"
    assert client.get(QUEUE, headers=citizen).status_code == 403
    assert client.get(f"{REPORTS}/{case_id}", headers=outsider).status_code == 404
    assert client.get(f"{endpoint}/assignment-options", headers=outsider).status_code == 404
    assert _data(client.get(f"{endpoint}/assignment-options", headers=staff)) == [{
        "id": str(site.department.id), "name": site.department.name,
        "staff": [{"id": reviewer["id"], "name": reviewer["full_name"]}],
    }]
    priority = {"priority": "HIGH", "reason": "Confirmed active water loss at the main."}
    assert client.patch(f"{endpoint}/priority", headers=outsider, json=priority).status_code == 404
    _review(client, staff, case_id)
    _data(client.post(f"{endpoint}/assignments", headers=staff, json=_assignment(site, reviewer["id"])), 201)
    assert _data(client.patch(f"{endpoint}/priority", headers=staff, json=priority))["confirmed_priority"] == "HIGH"
    category_id = next(row["id"] for row in _data(client.get(f"{API}/public/categories")) if row["code"] == "WATER_LEAKAGE")
    category = _data(client.patch(f"{endpoint}/category", headers=staff, json={
        "category_id": category_id, "reason": "Confirmed by maintenance.",
    }))
    assert category["category_confirmed"] and category["category_id"] == category_id
    for status, resolution in (("IN_PROGRESS", None), ("RESOLVED", "Replacement joint passed pressure testing.")):
        result = _data(client.post(f"{endpoint}/status", headers=staff, json={
            "status": status, "reason": "Work crew confirmed the update.",
            "resolution_description": resolution, "public_message": "Water line repair update.",
        }))
        assert result["status"] == status
    history = _data(client.get(f"{REPORTS}/{case_id}/updates", headers=citizen))
    assert all(priority["reason"] not in str(row) for row in history)
    assert history[-1]["new_status"] == "RESOLVED"
    audit_url = f"{API}/admin/audit-logs?entity_id={case_id}"
    assert client.get(audit_url, headers=staff).status_code == 403
    assert client.get(audit_url, headers=citizen).status_code == 403
    records = _data(client.get(audit_url, headers=admin))
    expected = {
        "COMPLAINT_ASSIGNED": ("assigned_staff_id", reviewer["id"]),
        "COMPLAINT_PRIORITY_CHANGED": ("new_priority", "HIGH"),
        "COMPLAINT_CATEGORY_CHANGED": ("new_category_id", category_id),
        "COMPLAINT_STATUS_CHANGED": ("new_status", "RESOLVED"),
    }
    for action, (key, value) in expected.items():
        record = next(row for row in records if row["action"] == action and row["event_metadata"].get(key) == value)
        assert record["actor_id"] == reviewer["id"] and record["actor_name"] == reviewer["full_name"]
        assert record["created_at"].endswith("Z") and record["entity_id"] == case_id


def test_admin_department_category_and_mapping(client, db):
    site, other = _site(db), _site(db)
    admin = _admin(client, db)
    _, staff = _staff(client, admin, site)
    base = f"{API}/admin"
    fields = {"name": "Distribution group", "code": "TEST_" + uuid4().hex, "description": None, "is_active": True}
    payload = {**fields, "organization_id": str(site.organization.id)}
    assert client.post(f"{base}/departments", json=payload, headers=staff).status_code == 403
    created = _data(client.post(f"{base}/departments", json=payload, headers=admin), 201)
    assert created["organization_id"] == payload["organization_id"]
    assert client.post(f"{base}/departments", json=payload, headers=admin).status_code == 409
    updated = _data(client.patch(f"{base}/departments/{created['id']}", headers=admin, json={
        **fields, "name": "Distribution team",
    }))
    assert updated["name"] == "Distribution team"
    category = _data(client.post(f"{base}/categories", headers=admin, json=fields), 201)
    path = f"{base}/categories/{category['id']}/mappings"
    url = f"{path}/{site.organization.id}"
    assert client.patch(url, headers=admin, json={"department_id": str(other.department.id)}).status_code == 422
    assert _data(client.patch(url, headers=admin, json={"department_id": updated["id"]}))["department_id"] == updated["id"]
    assert _data(client.get(path, headers=admin))[0]["department_id"] == updated["id"]
    assert _data(client.patch(url, headers=admin, json={"department_id": None})) is None
    assert _data(client.get(path, headers=admin)) == []
    inactive = _data(client.patch(f"{base}/categories/{category['id']}", headers=admin, json={**fields, "is_active": False}))
    assert not inactive["is_active"]
    assert all(row["id"] != category["id"] for row in _data(client.get(f"{API}/public/categories?page_size=100")))
