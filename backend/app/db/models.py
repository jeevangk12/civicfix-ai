from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Role(StrEnum):
    CITIZEN = "CITIZEN"
    STAFF = "STAFF"
    ADMIN = "ADMIN"


class User(Timestamps, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"))
    is_active: Mapped[bool] = mapped_column(server_default=true())
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Organization(Timestamps, Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(180))
    organization_type: Mapped[str | None] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(server_default=true())


class Department(Timestamps, Base):
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_departments_organization_code"),
        UniqueConstraint("id", "organization_id", name="uq_departments_id_organization"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    code: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(server_default=true())


class ServiceArea(Timestamps, Base):
    __tablename__ = "service_areas"
    __table_args__ = (UniqueConstraint("id", "organization_id", name="uq_service_areas_id_organization"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
    boundary_geojson: Mapped[dict | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(server_default=true())


class StaffProfile(Timestamps, Base):
    __tablename__ = "staff_profiles"
    __table_args__ = (UniqueConstraint("id", "organization_id", name="uq_staff_profiles_id_organization"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    staff_title: Mapped[str | None] = mapped_column(String(120))


class StaffDepartmentMembership(Base):
    __tablename__ = "staff_department_memberships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["staff_profile_id", "organization_id"], ["staff_profiles.id", "staff_profiles.organization_id"]
        ),
        ForeignKeyConstraint(
            ["department_id", "organization_id"], ["departments.id", "departments.organization_id"]
        ),
    )

    staff_profile_id: Mapped[UUID] = mapped_column(primary_key=True)
    department_id: Mapped[UUID] = mapped_column(primary_key=True)
    organization_id: Mapped[UUID] = mapped_column()


class StaffServiceAreaMembership(Base):
    __tablename__ = "staff_service_area_memberships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["staff_profile_id", "organization_id"], ["staff_profiles.id", "staff_profiles.organization_id"]
        ),
        ForeignKeyConstraint(
            ["service_area_id", "organization_id"], ["service_areas.id", "service_areas.organization_id"]
        ),
    )

    staff_profile_id: Mapped[UUID] = mapped_column(primary_key=True)
    service_area_id: Mapped[UUID] = mapped_column(primary_key=True)
    organization_id: Mapped[UUID] = mapped_column()


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"
    __table_args__ = (Index("ix_refresh_sessions_user_family", "user_id", "family_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    family_id: Mapped[UUID] = mapped_column()
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    replaced_by_session_id: Mapped[UUID | None] = mapped_column(ForeignKey("refresh_sessions.id"))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    organization_id: Mapped[UUID | None] = mapped_column(ForeignKey("organizations.id"))
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[UUID | None] = mapped_column()
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB)
    ip_hash: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
