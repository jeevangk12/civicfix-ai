from argparse import ArgumentParser
from getpass import getpass

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Department, Organization, Role, ServiceArea, User
from app.db.session import create_database_engine
from app.schemas.auth import AccountInput, StaffInput
from app.services.access import find_staff_scope, provision_staff
from app.services.auth import add_user

LATITUDE = 12.345678
LONGITUDE = 76.543210
ORGANIZATION = "CivicFix synthetic staging authority"
DEPARTMENT = "STAGING_WATER"
AREA = "Synthetic water-service area"


def _stage_scope(db: Session) -> tuple[Organization, Department, ServiceArea]:
    organization = db.execute(select(Organization).where(Organization.name == ORGANIZATION)).scalar_one_or_none()
    if organization is None:
        organization = Organization(name=ORGANIZATION)
        db.add(organization)
        db.flush()
    department = db.scalar(select(Department).where(
        Department.organization_id == organization.id, Department.code == DEPARTMENT,
    ))
    if department is None:
        department = Department(organization_id=organization.id, code=DEPARTMENT, name="Synthetic water repairs")
        db.add(department)
    area = db.execute(select(ServiceArea).where(
        ServiceArea.organization_id == organization.id, ServiceArea.name == AREA,
    )).scalar_one_or_none()
    if area is None:
        x, y, offset = LONGITUDE, LATITUDE, .001
        ring = [
            [x - offset, y - offset], [x + offset, y - offset], [x + offset, y + offset],
            [x - offset, y + offset], [x - offset, y - offset],
        ]
        area = ServiceArea(
            organization_id=organization.id, name=AREA,
            boundary_geojson={"type": "Polygon", "coordinates": [ring]},
        )
        db.add(area)
    db.flush()
    return organization, department, area


def _account(parser: ArgumentParser, email: str, name: str) -> AccountInput:
    password = getpass(f"{name} password (12–128 characters): ")
    if password != getpass("Confirm password: "):
        parser.error("Passwords differ.")
    try:
        return AccountInput(email=email, full_name=name, password=password)
    except ValidationError:
        parser.error("Enter a valid synthetic account email and a password of 12–128 characters.")


def main() -> None:
    parser = ArgumentParser(description="Create scoped synthetic smoke-test accounts in the configured staging database.")
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--staff-email", required=True)
    args = parser.parse_args()
    settings = Settings()
    if settings.app_env != "staging":
        parser.error("Set APP_ENV=staging and connect to the separate staging database.")
    emails = [args.admin_email.strip().lower(), args.staff_email.strip().lower()]
    if emails[0] == emails[1] or any(not email.endswith("@example.com") for email in emails):
        parser.error("Use two distinct synthetic @example.com addresses.")

    engine = create_database_engine(settings)
    try:
        with Session(engine, expire_on_commit=False) as db:
            users = {user.email: user for user in db.scalars(select(User).where(User.email.in_(emails)))}
            admin, staff = (users.get(email) for email in emails)
            if admin and (admin.role != Role.ADMIN or not admin.is_active):
                parser.error("The existing administrator address belongs to an inactive or different role.")
            if staff and (staff.role != Role.STAFF or not staff.is_active):
                parser.error("The existing staff address belongs to an inactive or different role.")
            admin_input = None if admin else _account(parser, emails[0], "Synthetic staging administrator")
            staff_input = None if staff else _account(parser, emails[1], "Synthetic staging reviewer")

            organization, department, area = _stage_scope(db)
            if staff:
                scope = find_staff_scope(db, staff.id, organization.id)
                if scope is None or department.id not in scope.department_ids or area.id not in scope.service_area_ids:
                    parser.error("The existing staff account lacks the synthetic service scope.")
            if admin_input:
                admin = add_user(db, admin_input.full_name, admin_input.email, admin_input.password, Role.ADMIN)
            if staff_input:
                assert admin is not None
                provision_staff(db, admin, StaffInput(
                    **staff_input.model_dump(), organization_id=organization.id,
                    department_ids={department.id}, service_area_ids={area.id},
                ))
            db.commit()
    finally:
        engine.dispose()
    print(f"Synthetic staging scope ready. Submit the test report at {LATITUDE:.6f}, {LONGITUDE:.6f}.")


if __name__ == "__main__":
    main()
