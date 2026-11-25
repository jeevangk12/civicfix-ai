from uuid import uuid4

from test_complaints import API, QUEUE, REPORTS, _admin, _assignment, _citizen, _data, _report, _review, _site, _staff

NOTIFICATIONS = f"{API}/notifications"


def test_notifications_and_feedback_are_owner_only(client, db):
    site = _site(db)
    admin = _admin(client, db)
    assignee, staff = _staff(client, admin, site)
    _, colleague = _staff(client, admin, site)
    _, owner = _citizen(client)
    _, other = _citizen(client)
    submission = {**owner, "Idempotency-Key": str(uuid4())}
    case = _data(client.post(REPORTS, headers=submission, json=_report(site)), 201)
    assert _data(client.post(REPORTS, headers=submission, json=_report(site)))["id"] == case["id"]
    own = _data(client.get(NOTIFICATIONS, headers=owner))
    assert [(item["type"], item["resource_id"]) for item in own] == [("COMPLAINT_SUBMITTED", case["id"])]
    assert _data(client.get(f"{NOTIFICATIONS}/unread-count", headers=owner)) == {"count": 1}
    _data(client.post(REPORTS, headers=other, json=_report(site, title="Broken valve elsewhere")), 201)

    case_id = case["id"]
    feedback_path = f"{REPORTS}/{case_id}/feedback"
    assert client.post(feedback_path, headers=owner, json={"rating": 4}).status_code == 409
    _review(client, staff, case_id)
    staff_path = f"{QUEUE}/{case_id}"
    _data(client.post(f"{staff_path}/assignments", headers=staff, json=_assignment(site, assignee["id"])), 201)
    assert [item["type"] for item in _data(client.get(NOTIFICATIONS, headers=staff))] == ["COMPLAINT_ASSIGNED"]
    assert _data(client.get(NOTIFICATIONS, headers=colleague)) == []
    assert client.post(f"{staff_path}/status", headers=staff, json={
        "status": "RESOLVED", "reason": "Premature completion.", "resolution_description": "None.",
    }).status_code == 409
    assert _data(client.get(f"{NOTIFICATIONS}/unread-count", headers=owner)) == {"count": 3}
    _data(client.post(f"{staff_path}/status", headers=staff, json={
        "status": "IN_PROGRESS", "reason": "Team began repair.", "public_message": "The crew is at the site.",
    }))
    internal = "Synthetic internal maintenance details."
    _data(client.post(f"{staff_path}/updates", headers=staff, json={"visibility": "INTERNAL", "message": internal}), 201)
    _data(client.post(f"{staff_path}/status", headers=staff, json={
        "status": "RESOLVED", "reason": internal, "resolution_description": internal,
        "public_message": "Water service was restored.",
    }))

    response = client.get(NOTIFICATIONS, headers=owner)
    notifications = _data(response)
    assert [row["type"] for row in notifications] == [
        "COMPLAINT_RESOLVED", "COMPLAINT_STATUS_CHANGED", "COMPLAINT_STATUS_CHANGED",
        "COMPLAINT_STATUS_CHANGED", "COMPLAINT_SUBMITTED",
    ]
    assert internal not in response.text and all(row["resource_id"] == case_id for row in notifications)
    assert _data(client.get(NOTIFICATIONS + "?page_size=1", headers=owner)) == notifications[:1]
    notification_id = notifications[0]["id"]
    item = f"{NOTIFICATIONS}/{notification_id}"
    assert client.get(item).status_code == 401
    assert client.get(item, headers=other).status_code == 404
    assert client.patch(item + "/read", headers=other).status_code == 404
    assert all(row["resource_id"] != case_id for row in _data(client.get(NOTIFICATIONS, headers=other)))
    marked = _data(client.patch(item + "/read", headers=owner))["read_at"]
    assert marked.endswith("Z")
    assert _data(client.patch(item + "/read", headers=owner))["read_at"] == marked
    assert _data(client.get(f"{NOTIFICATIONS}/unread-count", headers=owner)) == {"count": 4}
    assert _data(client.patch(f"{NOTIFICATIONS}/read-all", headers=owner)) == {"updated": 4}
    assert _data(client.patch(f"{NOTIFICATIONS}/read-all", headers=owner)) == {"updated": 0}
    assert _data(client.get(f"{NOTIFICATIONS}/unread-count", headers=other)) == {"count": 1}

    history = client.get(f"{REPORTS}/{case_id}/updates", headers=owner)
    assert _data(history)[-1]["message"] == "Water service was restored." and internal not in history.text
    assert client.get(feedback_path, headers=other).status_code == 404
    assert client.post(feedback_path, headers=other, json={"rating": 5}).status_code == 404
    assert client.post(feedback_path, headers=staff, json={"rating": 5}).status_code == 403
    assert _data(client.get(feedback_path, headers=owner)) is None
    assert client.post(feedback_path, headers=owner, json={"rating": 6}).status_code == 422
    assert client.post(feedback_path, headers=owner, json={"rating": 4, "comment": "x" * 1001}).status_code == 422
    feedback = _data(client.post(feedback_path, headers=owner, json={"rating": 5, "comment": "  Fixed promptly.  "}), 201)
    assert feedback["rating"] == 5 and feedback["comment"] == "Fixed promptly."
    assert _data(client.get(feedback_path, headers=owner)) == feedback
    assert client.post(feedback_path, headers=owner, json={"rating": 4}).status_code == 409


def test_rejection_and_department_assignment_notifications(client, db):
    site = _site(db)
    admin = _admin(client, db)
    _, staff = _staff(client, admin, site)
    _, colleague = _staff(client, admin, site)
    _, outsider = _staff(client, admin, _site(db, organization=site.organization, department=site.department))
    _, citizen = _citizen(client)
    rejected = _data(client.post(REPORTS, headers=citizen, json=_report(site, title="Historical pipe issue")), 201)
    _data(client.post(f"{QUEUE}/{rejected['id']}/status", headers=staff, json={
        "status": "REJECTED", "reason": "Outside the applicable reporting policy.",
    }))
    assert _data(client.get(NOTIFICATIONS, headers=citizen))[0]["type"] == "COMPLAINT_REJECTED"
    case = _data(client.post(REPORTS, headers=citizen, json=_report(site)), 201)
    _review(client, staff, case["id"])
    _data(client.post(f"{QUEUE}/{case['id']}/assignments", headers=staff, json=_assignment(site)), 201)
    assert _data(client.get(NOTIFICATIONS, headers=colleague))[0]["resource_id"] == case["id"]
    assert _data(client.get(NOTIFICATIONS, headers=outsider)) == []
