from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, ForeignKeyConstraint, Index, Numeric, String, Text
from sqlalchemy import func, text, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.complaint_models import ANALYSIS_TYPE, PRIORITY_TYPE, AnalysisStatus, Priority
from app.db.models import Base


class DuplicateStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED_DUPLICATE = "CONFIRMED_DUPLICATE"
    NOT_DUPLICATE = "NOT_DUPLICATE"


class Analysis(Base):
    __tablename__ = "ai_analyses"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    complaint_id: Mapped[UUID] = mapped_column(ForeignKey("complaints.id"), unique=True)
    provider: Mapped[str] = mapped_column(String(40))
    model_name: Mapped[str] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(40))
    status: Mapped[AnalysisStatus] = mapped_column(ANALYSIS_TYPE)
    suggested_category_id: Mapped[UUID | None] = mapped_column(ForeignKey("categories.id"))
    suggested_priority: Mapped[Priority | None] = mapped_column(PRIORITY_TYPE)
    suggested_department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id"))
    summary: Mapped[str | None] = mapped_column(Text)
    priority_reason: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    needs_human_review: Mapped[bool] = mapped_column(server_default=true())
    safety_flags: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    sanitized_error_code: Mapped[str | None] = mapped_column(String(80))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DuplicateSuggestion(Base):
    __tablename__ = "complaint_duplicates"
    __table_args__ = (
        CheckConstraint("complaint_id <> candidate_complaint_id", name="ck_complaint_duplicate_distinct"),
        Index(
            "uq_complaint_duplicate_pair",
            text("least(complaint_id, candidate_complaint_id)"),
            text("greatest(complaint_id, candidate_complaint_id)"),
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    complaint_id: Mapped[UUID] = mapped_column(ForeignKey("complaints.id"), index=True)
    candidate_complaint_id: Mapped[UUID] = mapped_column(ForeignKey("complaints.id"))
    similarity_score: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    distance_meters: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    detection_method: Mapped[str] = mapped_column(String(80))
    review_status: Mapped[DuplicateStatus] = mapped_column(
        Enum(DuplicateStatus, name="duplicate_review_status"), server_default=DuplicateStatus.PENDING.value,
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CategoryDepartmentMapping(Base):
    __tablename__ = "category_department_mappings"
    __table_args__ = (
        ForeignKeyConstraint(["department_id", "organization_id"], ["departments.id", "departments.organization_id"]),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    category_id: Mapped[UUID] = mapped_column(ForeignKey("categories.id"), primary_key=True)
    department_id: Mapped[UUID] = mapped_column()
