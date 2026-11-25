from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditLog,
    Department,
    Organization,
    Role,
    ServiceArea,
    StaffDepartmentMembership,
    StaffProfile,
    StaffServiceAreaMembership,
    User,
)
from app.schemas.auth import ProvisionedStaff, StaffInput, StaffScope, UserDetails
from app.services.auth import add_user


class InvalidStaffScope(Exception):
    pass


def provision_staff(db: Session, admin: User, payload: StaffInput) -> ProvisionedStaff:
    organization = db.get(Organization, payload.organization_id)
    if organization is None or not organization.is_active:
        raise InvalidStaffScope("Select an active organization.")

    departments = set(
        db.scalars(
            select(Department.id).where(
                Department.organization_id == organization.id, Department.is_active, Department.id.in_(payload.department_ids)
            )
        )
    )
    areas = set(
        db.scalars(
            select(ServiceArea.id).where(
                ServiceArea.organization_id == organization.id, ServiceArea.is_active, ServiceArea.id.in_(payload.service_area_ids)
            )
        )
    )
    if departments != payload.department_ids or areas != payload.service_area_ids:
        raise InvalidStaffScope("Select active departments and service areas in the staff member's organization.")

    user = add_user(db, payload.full_name, payload.email, payload.password, Role.STAFF)
    profile = StaffProfile(user_id=user.id, organization_id=organization.id, staff_title=payload.staff_title)
    db.add(profile)
    db.flush()
    db.add_all(
        StaffDepartmentMembership(staff_profile_id=profile.id, department_id=item, organization_id=organization.id)
        for item in departments
    )
    db.add_all(
        StaffServiceAreaMembership(staff_profile_id=profile.id, service_area_id=item, organization_id=organization.id)
        for item in areas
    )
    db.add(
        AuditLog(
            actor_id=admin.id,
            organization_id=organization.id,
            action="STAFF_PROVISIONED",
            entity_type="user",
            entity_id=user.id,
        )
    )
    db.commit()
    scope = StaffScope(organization_id=organization.id, department_ids=sorted(departments), service_area_ids=sorted(areas))
    return ProvisionedStaff(user=UserDetails.model_validate(user), scope=scope)


def find_staff_scope(db: Session, staff_id: UUID, organization_id: UUID | None = None) -> StaffScope | None:
    statement = (
        select(StaffProfile)
        .join(Organization, Organization.id == StaffProfile.organization_id)
        .where(StaffProfile.user_id == staff_id, Organization.is_active)
    )
    if organization_id is not None:
        statement = statement.where(Organization.id == organization_id)
    profile = db.scalar(statement)
    if profile is None:
        return None
    departments = db.scalars(
        select(Department.id)
        .join(StaffDepartmentMembership, StaffDepartmentMembership.department_id == Department.id)
        .where(StaffDepartmentMembership.staff_profile_id == profile.id, Department.is_active)
        .order_by(Department.id)
    ).all()
    areas = db.scalars(
        select(ServiceArea.id)
        .join(StaffServiceAreaMembership, StaffServiceAreaMembership.service_area_id == ServiceArea.id)
        .where(StaffServiceAreaMembership.staff_profile_id == profile.id, ServiceArea.is_active)
        .order_by(ServiceArea.id)
    ).all()
    return StaffScope(
        organization_id=profile.organization_id, department_ids=list(departments), service_area_ids=list(areas)
    )
