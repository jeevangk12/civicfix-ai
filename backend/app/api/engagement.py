from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.complaints import Citizen, Pagination, _page
from app.api.deps import CurrentUser, Database
from app.api.responses import success
from app.db.complaint_models import Complaint, ComplaintStatus
from app.db.engagement_models import Feedback, Notification
from app.repositories.complaints import paginated
from app.schemas.auth import DataResponse
from app.schemas.complaints import PageResponse, UtcTimestamp

router = APIRouter(tags=["notifications and feedback"])


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    type: str
    title: str
    body: str
    resource_type: str | None
    resource_id: UUID | None
    read_at: UtcTimestamp | None
    created_at: UtcTimestamp


class UnreadCount(BaseModel):
    count: int


class MarkedCount(BaseModel):
    updated: int


class FeedbackInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rating: Annotated[int, Field(strict=True, ge=1, le=5)]
    comment: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None


class FeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    rating: int
    comment: str | None
    created_at: UtcTimestamp


@router.get("/notifications")
def list_notifications(
    request: Request, db: Database, current: CurrentUser, params: Pagination,
) -> PageResponse[NotificationRead]:
    rows, total = paginated(
        db, select(Notification).where(Notification.recipient_id == current.user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc()), params,
    )
    return _page(request, [NotificationRead.model_validate(row) for row in rows], params, total)


@router.get("/notifications/unread-count")
def unread_count(request: Request, db: Database, current: CurrentUser) -> DataResponse[UnreadCount]:
    count = db.scalar(select(func.count()).select_from(Notification).where(
        Notification.recipient_id == current.user.id, Notification.read_at.is_(None),
    ))
    return success(request, UnreadCount(count=count or 0))


@router.get("/notifications/{notification_id}")
def get_notification(
    request: Request, db: Database, current: CurrentUser, notification_id: UUID,
) -> DataResponse[NotificationRead]:
    notification = db.scalar(select(Notification).where(
        Notification.id == notification_id, Notification.recipient_id == current.user.id,
    ))
    if notification is None:
        raise HTTPException(404, "Notification not found.")
    return success(request, NotificationRead.model_validate(notification))


@router.patch("/notifications/{notification_id}/read")
def mark_read(
    request: Request, db: Database, current: CurrentUser, notification_id: UUID,
) -> DataResponse[NotificationRead]:
    row = db.scalar(update(Notification).where(
        Notification.id == notification_id, Notification.recipient_id == current.user.id,
    ).values(read_at=func.coalesce(Notification.read_at, datetime.now(UTC))).returning(Notification))
    if row is None:
        raise HTTPException(404, "Notification not found.")
    db.commit()
    return success(request, NotificationRead.model_validate(row))


@router.patch("/notifications/read-all")
def mark_all_read(request: Request, db: Database, current: CurrentUser) -> DataResponse[MarkedCount]:
    result = db.execute(update(Notification).where(
        Notification.recipient_id == current.user.id, Notification.read_at.is_(None),
    ).values(read_at=datetime.now(UTC)))
    db.commit()
    return success(request, MarkedCount(updated=result.rowcount))


def _owned_report(db: Session, citizen_id: UUID, complaint_id: UUID, *, lock: bool = False) -> Complaint:
    query = select(Complaint).where(Complaint.id == complaint_id, Complaint.citizen_id == citizen_id)
    report = db.scalar(query.with_for_update() if lock else query)
    if report is None:
        raise HTTPException(404, "Report not found.")
    return report


@router.get("/complaints/{complaint_id}/feedback")
def get_feedback(
    request: Request, db: Database, citizen: Citizen, complaint_id: UUID,
) -> DataResponse[FeedbackRead | None]:
    _owned_report(db, citizen.id, complaint_id)
    feedback = db.scalar(select(Feedback).where(Feedback.complaint_id == complaint_id, Feedback.citizen_id == citizen.id))
    return success(request, FeedbackRead.model_validate(feedback) if feedback else None)


@router.post("/complaints/{complaint_id}/feedback", status_code=201)
def submit_feedback(
    request: Request, db: Database, citizen: Citizen, complaint_id: UUID, payload: FeedbackInput,
) -> DataResponse[FeedbackRead]:
    request.app.state.rate_limiter.check(request, "complaint-feedback", 10)
    report = _owned_report(db, citizen.id, complaint_id, lock=True)
    if report.status not in {ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED}:
        raise HTTPException(409, "Feedback opens after the report is resolved.")
    feedback = db.scalar(insert(Feedback).values(
        complaint_id=report.id, citizen_id=citizen.id, rating=payload.rating, comment=payload.comment or None,
    ).on_conflict_do_nothing(constraint="uq_feedback_complaint_citizen").returning(Feedback))
    if feedback is None:
        raise HTTPException(409, "You already submitted feedback for this report.")
    db.commit()
    return success(request, FeedbackRead.model_validate(feedback))
