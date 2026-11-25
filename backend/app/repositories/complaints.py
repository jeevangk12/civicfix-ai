from typing import TypeVar
from uuid import UUID

from sqlalchemy import Select, false, func, or_, select
from sqlalchemy.orm import Session

from app.db.complaint_models import Complaint, ComplaintUpdate, UpdateVisibility
from app.db.models import Role, StaffDepartmentMembership, StaffProfile, StaffServiceAreaMembership, User
from app.schemas.auth import StaffScope
from app.schemas.complaints import PageParams
from app.services.access import find_staff_scope

Item = TypeVar("Item")


def scoped_complaints(scope: StaffScope | None) -> Select[tuple[Complaint]]:
    statement = select(Complaint)
    if scope is None or not scope.department_ids or not scope.service_area_ids:
        return statement.where(false())
    return statement.where(
        Complaint.organization_id == scope.organization_id,
        Complaint.service_area_id.in_(scope.service_area_ids),
        or_(Complaint.assigned_department_id.is_(None), Complaint.assigned_department_id.in_(scope.department_ids)),
    )


def eligible_staff(department_ids: list[UUID], service_area_id: UUID | None) -> Select[tuple[UUID, User]]:
    return (
        select(StaffDepartmentMembership.department_id, User)
        .join(StaffProfile, StaffProfile.id == StaffDepartmentMembership.staff_profile_id)
        .join(User, User.id == StaffProfile.user_id)
        .join(StaffServiceAreaMembership, StaffServiceAreaMembership.staff_profile_id == StaffProfile.id)
        .where(
            StaffDepartmentMembership.department_id.in_(department_ids),
            StaffServiceAreaMembership.service_area_id == service_area_id,
            User.is_active, User.role == Role.STAFF,
        )
        .order_by(User.full_name, User.id)
    )


def visible_complaint(db: Session, viewer: User, complaint_id: UUID, *, lock: bool = False) -> Complaint | None:
    statement = select(Complaint)
    if viewer.role == Role.CITIZEN:
        statement = statement.where(Complaint.citizen_id == viewer.id)
    elif viewer.role == Role.STAFF:
        statement = scoped_complaints(find_staff_scope(db, viewer.id))
    elif viewer.role != Role.ADMIN:
        return None
    statement = statement.where(Complaint.id == complaint_id)
    return db.scalar(statement.with_for_update() if lock else statement)


def updates_for(complaint_id: UUID, citizen_view: bool) -> Select[tuple[ComplaintUpdate]]:
    statement = select(ComplaintUpdate).where(ComplaintUpdate.complaint_id == complaint_id)
    if citizen_view:
        statement = statement.where(ComplaintUpdate.visibility == UpdateVisibility.PUBLIC)
    return statement.order_by(ComplaintUpdate.created_at, ComplaintUpdate.id)


def paginated(db: Session, statement: Select[tuple[Item]], params: PageParams) -> tuple[list[Item], int]:
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
    items = db.scalars(statement.offset((params.page - 1) * params.page_size).limit(params.page_size)).all()
    return list(items), int(total or 0)
