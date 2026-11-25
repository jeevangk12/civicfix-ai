from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint, DateTime, Enum, ForeignKey, ForeignKeyConstraint, Index, Numeric, String,
    Text, UniqueConstraint, func, text, true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base, Timestamps


class ComplaintStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"


class ComplaintVisibility(StrEnum):
    PRIVATE = "PRIVATE"
    APPROXIMATE = "APPROXIMATE"
    PUBLIC = "PUBLIC"


class UpdateVisibility(StrEnum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"


class AnalysisStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class Priority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


ANALYSIS_TYPE = Enum(AnalysisStatus, name="ai_analysis_status")
PRIORITY_TYPE = Enum(Priority, name="complaint_priority")
STATUS_TYPE = Enum(ComplaintStatus, name="complaint_status")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    default_department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id"))
    is_active: Mapped[bool] = mapped_column(server_default=true())
    sort_order: Mapped[int] = mapped_column(server_default=text("0"))


class Complaint(Timestamps, Base):
    __tablename__ = "complaints"
    __table_args__ = (
        ForeignKeyConstraint(["service_area_id", "organization_id"], ["service_areas.id", "service_areas.organization_id"]),
        ForeignKeyConstraint(["assigned_department_id", "organization_id"], ["departments.id", "departments.organization_id"]),
        UniqueConstraint("citizen_id", "idempotency_key", name="uq_complaints_citizen_idempotency"),
        CheckConstraint("(organization_id IS NULL) = (service_area_id IS NULL)", name="ck_complaints_routing"),
        CheckConstraint("assigned_department_id IS NULL OR organization_id IS NOT NULL", name="ck_complaints_department_routing"),
        CheckConstraint("assigned_staff_id IS NULL OR assigned_department_id IS NOT NULL", name="ck_complaints_staff_department"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_complaints_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_complaints_longitude"),
        CheckConstraint("(idempotency_key IS NULL) = (submission_digest IS NULL)", name="ck_complaints_idempotency"),
        Index("ix_complaints_citizen_created", "citizen_id", text("created_at DESC")),
        Index("ix_complaints_scope_status", "organization_id", "service_area_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    public_reference: Mapped[str] = mapped_column(String(30), unique=True)
    citizen_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    organization_id: Mapped[UUID | None] = mapped_column(ForeignKey("organizations.id"))
    service_area_id: Mapped[UUID | None] = mapped_column()
    category_id: Mapped[UUID | None] = mapped_column(ForeignKey("categories.id"))
    category_confirmed: Mapped[bool] = mapped_column(server_default=text("false"))
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    location_label: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[ComplaintStatus] = mapped_column(STATUS_TYPE, server_default=ComplaintStatus.SUBMITTED.value)
    ai_analysis_status: Mapped[AnalysisStatus] = mapped_column(ANALYSIS_TYPE, server_default=AnalysisStatus.SKIPPED.value)
    confirmed_priority: Mapped[Priority | None] = mapped_column(PRIORITY_TYPE)
    priority_override_reason: Mapped[str | None] = mapped_column(Text)
    assigned_department_id: Mapped[UUID | None] = mapped_column()
    assigned_staff_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    visibility: Mapped[ComplaintVisibility] = mapped_column(
        Enum(ComplaintVisibility, name="complaint_visibility"), server_default=ComplaintVisibility.PRIVATE.value
    )
    approved_public_summary: Mapped[str | None] = mapped_column(String(120))
    public_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    public_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    resolution_description: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    submission_digest: Mapped[str | None] = mapped_column(String(64))


class ComplaintUpdate(Base):
    __tablename__ = "complaint_updates"
    __table_args__ = (Index("ix_complaint_updates_complaint_created", "complaint_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    complaint_id: Mapped[UUID] = mapped_column(ForeignKey("complaints.id"))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    old_status: Mapped[ComplaintStatus | None] = mapped_column(STATUS_TYPE)
    new_status: Mapped[ComplaintStatus | None] = mapped_column(STATUS_TYPE)
    reason: Mapped[str] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    visibility: Mapped[UpdateVisibility] = mapped_column(Enum(UpdateVisibility, name="complaint_update_visibility"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ComplaintAssignment(Base):
    __tablename__ = "complaint_assignments"
    __table_args__ = (
        Index("uq_complaint_assignments_open", "complaint_id", unique=True, postgresql_where=text("unassigned_at IS NULL")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    complaint_id: Mapped[UUID] = mapped_column(ForeignKey("complaints.id"))
    department_id: Mapped[UUID] = mapped_column(ForeignKey("departments.id"))
    assigned_staff_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    assigned_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    unassigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
