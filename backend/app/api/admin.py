from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.access import AdminUser
from app.api.complaints import Pagination, _page
from app.api.deps import Database
from app.api.responses import success
from app.db.complaint_models import Category
from app.db.intelligence_models import CategoryDepartmentMapping
from app.db.models import AuditLog, Department, Organization, Role, ServiceArea, User
from app.repositories.complaints import paginated
from app.schemas.auth import DataResponse, UserDetails
from app.schemas.complaints import PageResponse, ProgressText, UtcTimestamp

router = APIRouter(prefix="/admin", tags=["platform administration"])


class NamedRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    is_active: bool


class AreaRead(NamedRecord):
    organization_id: UUID


class SettingsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9_-]{1,60}$")]
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    description: ProgressText | None = None
    is_active: bool = True


class DepartmentInput(SettingsInput):
    organization_id: UUID


class DepartmentRead(AreaRead):
    code: str
    description: str | None


class MappingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    department_id: UUID | None


class CategoryRead(NamedRecord):
    code: str
    description: str | None


class MappingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    organization_id: UUID
    department_id: UUID


class AuditRead(BaseModel):
    id: UUID
    actor_id: UUID | None
    actor_name: str | None
    organization_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID | None
    event_metadata: dict | None
    created_at: UtcTimestamp


@router.get("/users")
def get_users(
    request: Request, db: Database, admin: AdminUser, params: Pagination, role: Role | None = None
) -> PageResponse[UserDetails]:
    query = select(User).order_by(User.created_at.desc(), User.id)
    if role is not None:
        query = query.where(User.role == role)
    rows, total = paginated(db, query, params)
    return _page(request, [UserDetails.model_validate(row) for row in rows], params, total)


@router.get("/organizations")
def get_organizations(request: Request, db: Database, admin: AdminUser) -> DataResponse[list[NamedRecord]]:
    rows = db.scalars(select(Organization).order_by(Organization.name, Organization.id))
    return success(request, [NamedRecord.model_validate(row) for row in rows])


@router.get("/service-areas")
def get_areas(request: Request, db: Database, admin: AdminUser, organization_id: UUID) -> DataResponse[list[AreaRead]]:
    rows = db.scalars(
        select(ServiceArea).where(ServiceArea.organization_id == organization_id).order_by(ServiceArea.name, ServiceArea.id)
    )
    return success(request, [AreaRead.model_validate(row) for row in rows])


@router.get("/departments")
def get_departments(
    request: Request, db: Database, admin: AdminUser, organization_id: UUID | None = None
) -> DataResponse[list[DepartmentRead]]:
    query = select(Department).order_by(Department.name, Department.id)
    if organization_id is not None:
        query = query.where(Department.organization_id == organization_id)
    return success(request, [DepartmentRead.model_validate(row) for row in db.scalars(query)])


def _save_settings(
    db: Session, admin: User, row: Department | Category, payload: SettingsInput, entity_type: str, created: bool,
) -> None:
    changes = {}
    for field, value in payload.model_dump(exclude={"organization_id"}).items():
        previous = getattr(row, field)
        if previous != value:
            changes[field] = {"from": previous, "to": value}
            setattr(row, field, value)
    try:
        db.flush()
        db.add(AuditLog(
            actor_id=admin.id, organization_id=row.organization_id if isinstance(row, Department) else None,
            action=f"{entity_type.upper()}_{'CREATED' if created else 'UPDATED'}",
            entity_type=entity_type, entity_id=row.id, event_metadata=changes,
        ))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This code is already in use.") from None


@router.post("/departments", status_code=201)
def create_department(
    request: Request, db: Database, admin: AdminUser, payload: DepartmentInput,
) -> DataResponse[DepartmentRead]:
    organization = db.get(Organization, payload.organization_id, with_for_update={"read": True})
    if organization is None or not organization.is_active:
        raise HTTPException(422, "Select an active organization.")
    row = Department(organization_id=organization.id)
    db.add(row)
    _save_settings(db, admin, row, payload, "department", True)
    return success(request, DepartmentRead.model_validate(row))


@router.patch("/departments/{department_id}")
def update_department(
    request: Request, db: Database, admin: AdminUser, department_id: UUID, payload: SettingsInput,
) -> DataResponse[DepartmentRead]:
    row = db.get(Department, department_id, with_for_update=True)
    if row is None:
        raise HTTPException(404, "Department not found.")
    _save_settings(db, admin, row, payload, "department", False)
    return success(request, DepartmentRead.model_validate(row))


@router.get("/categories")
def get_categories(request: Request, db: Database, admin: AdminUser) -> DataResponse[list[CategoryRead]]:
    rows = db.scalars(select(Category).order_by(Category.sort_order, Category.code))
    return success(request, [CategoryRead.model_validate(row) for row in rows])


@router.post("/categories", status_code=201)
def create_category(
    request: Request, db: Database, admin: AdminUser, payload: SettingsInput,
) -> DataResponse[CategoryRead]:
    row = Category()
    db.add(row)
    _save_settings(db, admin, row, payload, "category", True)
    return success(request, CategoryRead.model_validate(row))


@router.patch("/categories/{category_id}")
def update_category(
    request: Request, db: Database, admin: AdminUser, category_id: UUID, payload: SettingsInput,
) -> DataResponse[CategoryRead]:
    row = db.get(Category, category_id, with_for_update=True)
    if row is None:
        raise HTTPException(404, "Category not found.")
    _save_settings(db, admin, row, payload, "category", False)
    return success(request, CategoryRead.model_validate(row))


@router.get("/categories/{category_id}/mappings")
def get_mappings(request: Request, db: Database, admin: AdminUser, category_id: UUID) -> DataResponse[list[MappingRead]]:
    rows = db.scalars(select(CategoryDepartmentMapping).where(CategoryDepartmentMapping.category_id == category_id))
    return success(request, [MappingRead.model_validate(row) for row in rows])


@router.patch("/categories/{category_id}/mappings/{organization_id}")
def update_mapping(
    request: Request, db: Database, admin: AdminUser, category_id: UUID, organization_id: UUID, payload: MappingInput,
) -> DataResponse[MappingRead | None]:
    if db.get(Category, category_id, with_for_update=True) is None:
        raise HTTPException(404, "Category not found.")
    existing = db.get(CategoryDepartmentMapping, (organization_id, category_id))
    old_department_id = existing.department_id if existing else None
    if old_department_id == payload.department_id:
        return success(request, MappingRead.model_validate(existing) if existing else None)
    if payload.department_id is None:
        db.delete(existing)
        mapping = None
    else:
        department = db.get(Department, payload.department_id, with_for_update={"read": True})
        if department is None or department.organization_id != organization_id or not department.is_active:
            raise HTTPException(422, "Select an active department in the chosen organization.")
        mapping = db.merge(CategoryDepartmentMapping(
            category_id=category_id, organization_id=organization_id, department_id=department.id,
        ))
    db.add(AuditLog(
        actor_id=admin.id, organization_id=organization_id, action="CATEGORY_MAPPING_UPDATED",
        entity_type="category", entity_id=category_id,
        event_metadata={
            "old_department_id": str(old_department_id) if old_department_id else None,
            "new_department_id": str(payload.department_id) if payload.department_id else None,
        },
    ))
    db.commit()
    return success(request, MappingRead.model_validate(mapping) if mapping else None)


@router.get("/audit-logs")
def get_audit(
    request: Request, db: Database, admin: AdminUser, params: Pagination,
    entity_id: UUID | None = None, action: Annotated[str | None, Field(max_length=100)] = None,
) -> PageResponse[AuditRead]:
    query = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    if entity_id is not None:
        query = query.where(AuditLog.entity_id == entity_id)
    if action:
        query = query.where(AuditLog.action == action.upper())
    records, total = paginated(db, query, params)
    actor_ids = {record.actor_id for record in records if record.actor_id is not None}
    names = dict(db.execute(select(User.id, User.full_name).where(User.id.in_(actor_ids))).all())
    return _page(request, [
        AuditRead(
            id=row.id, actor_id=row.actor_id, actor_name=names.get(row.actor_id), organization_id=row.organization_id,
            action=row.action, entity_type=row.entity_type, entity_id=row.entity_id,
            event_metadata=row.event_metadata, created_at=row.created_at,
        )
        for row in records
    ], params, total)
