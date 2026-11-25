from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.complaint_models import Complaint, ComplaintStatus
from app.db.engagement_models import Notification

S = ComplaintStatus
_MILESTONES = {
    S.SUBMITTED: ("COMPLAINT_SUBMITTED", "Report received"),
    S.RESOLVED: ("COMPLAINT_RESOLVED", "Report resolved"),
    S.REJECTED: ("COMPLAINT_REJECTED", "Report rejected"),
}
_STATUS_LABELS = {
    S.SUBMITTED: "Submitted", S.UNDER_REVIEW: "Under review", S.ASSIGNED: "Assigned",
    S.IN_PROGRESS: "In progress", S.RESOLVED: "Resolved", S.CLOSED: "Closed", S.REJECTED: "Rejected",
}


def _add(
    db: Session, complaint: Complaint, recipient_id: UUID, kind: str, title: str, body: str, now: datetime,
) -> None:
    db.add(Notification(
        recipient_id=recipient_id, type=kind, title=title, body=body,
        resource_type="complaint", resource_id=complaint.id, created_at=now,
    ))


def status_changed(
    db: Session, complaint: Complaint, old: ComplaintStatus | None, new: ComplaintStatus | None, now: datetime,
) -> None:
    if new is None or new == old:
        return
    kind, title = _MILESTONES.get(new, ("COMPLAINT_STATUS_CHANGED", "Report status updated"))
    _add(
        db, complaint, complaint.citizen_id, kind, title,
        f"{complaint.public_reference} is now {_STATUS_LABELS[new].lower()}. Open the report to see its progress.",
        now,
    )


def assigned(db: Session, complaint: Complaint, recipient_id: UUID, now: datetime) -> None:
    _add(
        db, complaint, recipient_id, "COMPLAINT_ASSIGNED", "Complaint assigned",
        f"{complaint.public_reference} was assigned to you or your department.", now,
    )


def duplicate_confirmed(db: Session, complaint: Complaint, now: datetime) -> None:
    _add(
        db, complaint, complaint.citizen_id, "DUPLICATE_CONFIRMED", "Related report confirmed",
        f"Staff linked {complaint.public_reference} to another report about the same issue. Open the report for details.",
        now,
    )
