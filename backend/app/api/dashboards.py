from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Date, Select, cast, extract, func, select
from sqlalchemy.orm import Session

from app.api.access import AdminUser, StaffUser
from app.api.complaints import Citizen
from app.api.deps import Database
from app.api.responses import success
from app.db.complaint_models import Category, Complaint, ComplaintStatus
from app.db.intelligence_models import DuplicateSuggestion
from app.db.models import Department, Organization, ServiceArea
from app.repositories.complaints import scoped_complaints
from app.schemas.auth import DataResponse
from app.schemas.complaints import ComplaintSummary
from app.services.access import find_staff_scope

router = APIRouter(tags=["dashboards"])

S = ComplaintStatus
OPEN = (S.SUBMITTED, S.UNDER_REVIEW, S.ASSIGNED, S.IN_PROGRESS)
RESOLVED = (S.RESOLVED, S.CLOSED)


class Bucket(BaseModel):
    label: str
    count: int


class Counts(BaseModel):
    total: int
    open: int
    resolved: int
    by_status: list[Bucket]


class CitizenDashboard(Counts):
    recent: list[ComplaintSummary]


class AreaOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str


class StaffDashboard(Counts):
    assigned_open: int
    by_priority: list[Bucket]
    oldest_pending: list[ComplaintSummary]
    areas: list[AreaOption]


class AdminDashboard(Counts):
    trend: list[Bucket]
    by_category: list[Bucket]
    by_priority: list[Bucket]
    by_department: list[Bucket]
    average_resolution_hours: float | None
    by_analysis_status: list[Bucket]
    by_duplicate_decision: list[Bucket]


def _counts(db: Session, reports: Select[tuple[Complaint]]) -> Counts:
    rows = dict(db.execute(
        reports.with_only_columns(Complaint.status, func.count(Complaint.id)).group_by(Complaint.status),
    ).all())
    return Counts(
        total=sum(rows.values()), open=sum(rows.get(status, 0) for status in OPEN),
        resolved=sum(rows.get(status, 0) for status in RESOLVED),
        by_status=[Bucket(label=status, count=rows.get(status, 0)) for status in S],
    )


def _priorities(db: Session, reports: Select[tuple[Complaint]]) -> list[Bucket]:
    priority = Complaint.confirmed_priority
    return [
        Bucket(label=value if value is not None else "Unconfirmed", count=count)
        for value, count in db.execute(
            reports.with_only_columns(priority, func.count(Complaint.id)).group_by(priority).order_by(priority),
        )
    ]


@router.get("/citizen/dashboard")
def citizen_dashboard(request: Request, db: Database, citizen: Citizen) -> DataResponse[CitizenDashboard]:
    reports = select(Complaint).where(Complaint.citizen_id == citizen.id)
    counts = _counts(db, reports)
    recent = db.scalars(reports.order_by(Complaint.created_at.desc(), Complaint.id).limit(5))
    return success(request, CitizenDashboard(
        **counts.model_dump(), recent=[ComplaintSummary.model_validate(row) for row in recent],
    ))


@router.get("/authority/dashboard")
def staff_dashboard(
    request: Request, db: Database, staff: StaffUser, category_id: UUID | None = None, service_area_id: UUID | None = None,
) -> DataResponse[StaffDashboard]:
    scope = find_staff_scope(db, staff.id)
    reports = scoped_complaints(scope)
    if category_id is not None:
        reports = reports.where(Complaint.category_id == category_id)
    if service_area_id is not None:
        reports = reports.where(Complaint.service_area_id == service_area_id)
    counts = _counts(db, reports)
    pending = reports.where(Complaint.status.in_(OPEN))
    assigned_open = db.scalar(
        pending.with_only_columns(func.count(Complaint.id)).where(Complaint.assigned_staff_id == staff.id),
    )
    oldest = db.scalars(pending.order_by(Complaint.created_at, Complaint.id).limit(5)).all()
    areas = db.scalars(
        select(ServiceArea).where(ServiceArea.id.in_(scope.service_area_ids)).order_by(ServiceArea.name, ServiceArea.id)
    ).all() if scope else []
    return success(request, StaffDashboard(
        **counts.model_dump(), assigned_open=assigned_open or 0, by_priority=_priorities(db, reports),
        oldest_pending=[ComplaintSummary.model_validate(row) for row in oldest],
        areas=[AreaOption.model_validate(area) for area in areas],
    ))


def _trend(db: Session, reports: Select[tuple[Complaint]]) -> list[Bucket]:
    first = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=29)
    day = cast(func.timezone("UTC", Complaint.created_at), Date)
    totals = dict(db.execute(
        reports.with_only_columns(day, func.count(Complaint.id))
        .where(Complaint.created_at >= first, Complaint.created_at < first + timedelta(days=30)).group_by(day),
    ).all())
    days = (first.date() + timedelta(days=index) for index in range(30))
    return [Bucket(label=value.isoformat(), count=totals.get(value, 0)) for value in days]


@router.get("/admin/dashboard")
def admin_dashboard(
    request: Request, db: Database, admin: AdminUser, organization_id: UUID | None = None,
) -> DataResponse[AdminDashboard]:
    reports = select(Complaint)
    if organization_id is not None:
        reports = reports.where(Complaint.organization_id == organization_id)
    counts = _counts(db, reports)
    category_counts = db.execute(
        reports.with_only_columns(Category.name, func.count(Complaint.id))
        .outerjoin(Category, Category.id == Complaint.category_id).group_by(Category.id, Category.name)
        .order_by(func.count(Complaint.id).desc(), Category.name, Category.id),
    )
    department_label = Department.name + " · " + Organization.name
    department_counts = db.execute(
        reports.with_only_columns(department_label, func.count(Complaint.id))
        .outerjoin(Department, Department.id == Complaint.assigned_department_id)
        .outerjoin(Organization, Organization.id == Department.organization_id)
        .group_by(Department.id, department_label).order_by(func.count(Complaint.id).desc(), department_label, Department.id),
    )
    analysis = Complaint.ai_analysis_status
    analysis_counts = db.execute(
        reports.with_only_columns(analysis, func.count(Complaint.id)).group_by(analysis).order_by(analysis),
    )
    decision = DuplicateSuggestion.review_status
    duplicates = db.execute(
        reports.with_only_columns(decision, func.count(DuplicateSuggestion.id), maintain_column_froms=True)
        .join(DuplicateSuggestion, DuplicateSuggestion.complaint_id == Complaint.id).group_by(decision).order_by(decision),
    )
    hours = db.scalar(
        reports.with_only_columns(func.avg(extract("epoch", Complaint.resolved_at - Complaint.created_at)) / 3600)
        .where(Complaint.status.in_(RESOLVED), Complaint.resolved_at.is_not(None)),
    )
    return success(request, AdminDashboard(
        **counts.model_dump(), trend=_trend(db, reports),
        by_category=[Bucket(label=name or "Uncategorized", count=count) for name, count in category_counts],
        by_priority=_priorities(db, reports),
        by_department=[Bucket(label=name or "Unassigned", count=count) for name, count in department_counts],
        average_resolution_hours=round(float(hours), 2) if hours is not None else None,
        by_analysis_status=[Bucket(label=status, count=count) for status, count in analysis_counts],
        by_duplicate_decision=[Bucket(label=status, count=count) for status, count in duplicates],
    ))
