from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, SmallInteger, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base, Timestamps


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_recipient_read_created", "recipient_id", "read_at", text("created_at DESC")),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    recipient_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(String(500))
    resource_type: Mapped[str | None] = mapped_column(String(60))
    resource_id: Mapped[UUID | None] = mapped_column()
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Feedback(Timestamps, Base):
    __tablename__ = "feedback"
    __table_args__ = (
        UniqueConstraint("complaint_id", "citizen_id", name="uq_feedback_complaint_citizen"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_feedback_rating"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    complaint_id: Mapped[UUID] = mapped_column(ForeignKey("complaints.id"))
    citizen_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    rating: Mapped[int] = mapped_column(SmallInteger)
    comment: Mapped[str | None] = mapped_column(String(1000))
