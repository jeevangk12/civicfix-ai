from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.db.complaint_models import Category, Complaint
from app.db.intelligence_models import DuplicateSuggestion
from app.db.models import Department
from test_complaints import API, _admin, _citizen, _data, _site, _staff


def _buckets(result, key):
    return {item["label"]: item["count"] for item in result[key]}


def test_dashboards_match_scoped_postgres_fixture(client, db):
    site = _site(db)
    area2 = _site(db, organization=site.organization, department=site.department)
    other_org = _site(db)
    other_dept = Department(organization_id=site.organization.id, code="ROADS", name="Road services")
    db.add(other_dept)
    db.commit()
    admin = _admin(client, db)
    reviewer, staff = _staff(client, admin, site)
    first, citizen = _citizen(client)
    second, other_citizen = _citizen(client)
    category = db.scalar(select(Category).where(Category.code == "WATER_LEAKAGE"))
    now = datetime.now(UTC)

    def report(owner, status, *, zone=site, department=None, age=2, hours=None, **fields):
        created = now - timedelta(days=age)
        case = Complaint(
            citizen_id=UUID(owner["id"]), organization_id=zone.organization.id, service_area_id=zone.area.id,
            category_id=category.id, title="Synthetic chart report", description="Fixture for PostgreSQL aggregates.",
            latitude=zone.latitude, longitude=zone.longitude, status=status, public_reference=f"CF-{uuid4().hex[:12]}",
            created_at=created, updated_at=created, assigned_department_id=department.id if department else None,
            resolved_at=created + timedelta(hours=hours) if hours is not None else None, **fields,
        )
        db.add(case)
        return case

    pending = report(first, "SUBMITTED", age=3, ai_analysis_status="FAILED")
    assigned = report(first, "ASSIGNED", department=site.department, assigned_staff_id=UUID(reviewer["id"]),
                      confirmed_priority="HIGH", ai_analysis_status="SUCCEEDED")
    resolved = report(first, "RESOLVED", department=site.department, hours=10, confirmed_priority="MEDIUM")
    report(first, "CLOSED", zone=area2, department=site.department, hours=14)
    report(second, "UNDER_REVIEW", department=other_dept)
    report(second, "REJECTED", zone=other_org, department=other_org.department, age=40)
    db.flush()
    db.add_all([
        DuplicateSuggestion(complaint_id=assigned.id, candidate_complaint_id=pending.id,
                            similarity_score=0.88, distance_meters=5, detection_method="fixture"),
        DuplicateSuggestion(complaint_id=resolved.id, candidate_complaint_id=pending.id,
                            similarity_score=0.8, distance_meters=8, detection_method="fixture", review_status="NOT_DUPLICATE"),
    ])
    db.commit()

    citizen_data = _data(client.get(f"{API}/citizen/dashboard", headers=citizen))
    assert (citizen_data["total"], citizen_data["open"], citizen_data["resolved"]) == (4, 2, 2)
    assert _buckets(citizen_data, "by_status")["CLOSED"] == 1
    assert all(row["id"] in {str(pending.id), str(assigned.id), str(resolved.id)} or row["status"] == "CLOSED"
               for row in citizen_data["recent"])
    assert _data(client.get(f"{API}/citizen/dashboard", headers=other_citizen))["total"] == 2

    staff_data = _data(client.get(f"{API}/authority/dashboard", headers=staff))
    assert (staff_data["total"], staff_data["open"], staff_data["assigned_open"], staff_data["resolved"]) == (3, 2, 1, 1)
    assert _buckets(staff_data, "by_priority") == {"HIGH": 1, "MEDIUM": 1, "Unconfirmed": 1}
    assert [row["id"] for row in staff_data["oldest_pending"]] == [str(pending.id), str(assigned.id)]
    assert [area["id"] for area in staff_data["areas"]] == [str(site.area.id)]
    filtered_url = f"{API}/authority/dashboard?category_id={category.id}&service_area_id="
    assert _data(client.get(filtered_url + str(site.area.id), headers=staff))["total"] == 3
    assert _data(client.get(filtered_url + str(area2.area.id), headers=staff))["total"] == 0
    assert client.get(f"{API}/authority/dashboard", headers=citizen).status_code == 403
    assert client.get(f"{API}/admin/dashboard", headers=staff).status_code == 403

    admin_data = _data(client.get(f"{API}/admin/dashboard?organization_id={site.organization.id}", headers=admin))
    assert (admin_data["total"], admin_data["open"], admin_data["resolved"]) == (5, 3, 2)
    assert admin_data["average_resolution_hours"] == 12
    assert _buckets(admin_data, "by_category") == {category.name: 5}
    assert sorted(_buckets(admin_data, "by_department").values()) == [1, 1, 3]
    assert _buckets(admin_data, "by_analysis_status") == {"FAILED": 1, "SUCCEEDED": 1, "SKIPPED": 3}
    assert _buckets(admin_data, "by_duplicate_decision") == {"PENDING": 1, "NOT_DUPLICATE": 1}
    assert len(admin_data["trend"]) == 30 and sum(bucket["count"] for bucket in admin_data["trend"]) == 5
    global_data = _data(client.get(f"{API}/admin/dashboard", headers=admin))
    assert global_data["total"] == db.scalar(select(func.count(Complaint.id)))
