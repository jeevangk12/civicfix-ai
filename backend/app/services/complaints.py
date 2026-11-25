from datetime import UTC, datetime
from hashlib import sha256
from secrets import token_hex
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.complaint_models import (
    AnalysisStatus,
    Category, Complaint, ComplaintAssignment, ComplaintStatus, ComplaintUpdate, UpdateVisibility,
)
from app.db.models import AuditLog, Role, User
from app.repositories.complaints import eligible_staff, scoped_complaints
from app.schemas.auth import StaffScope
from app.schemas.complaints import AssignmentInput, CategoryInput, ComplaintInput, PriorityInput, ReviewInput, StatusInput, UpdateInput
from app.services import notifications
from app.services.access import find_staff_scope
from app.services.complaint_routing import find_intake_area

S = ComplaintStatus
ALLOWED_TRANSITIONS = {
    S.SUBMITTED: {S.UNDER_REVIEW, S.REJECTED},
    S.UNDER_REVIEW: {S.ASSIGNED, S.REJECTED},
    S.ASSIGNED: {S.IN_PROGRESS, S.UNDER_REVIEW},
    S.IN_PROGRESS: {S.RESOLVED, S.ASSIGNED},
    S.RESOLVED: {S.CLOSED, S.IN_PROGRESS},
    S.CLOSED: set(),
    S.REJECTED: set(),
}


class ComplaintNotFound(Exception):
    pass


class ComplaintConflict(Exception):
    pass


class InvalidComplaintValue(Exception):
    pass


class ComplaintUnavailable(Exception):
    pass


def _record_update(
    db: Session, complaint: Complaint, actor: User, *, action: str, reason: str,
    message: str | None, now: datetime, visibility: UpdateVisibility = UpdateVisibility.PUBLIC,
    old_status: ComplaintStatus | None = None, new_status: ComplaintStatus | None = None,
    metadata: dict | None = None,
) -> ComplaintUpdate:
    complaint.updated_at = now
    entry = ComplaintUpdate(
        complaint_id=complaint.id, actor_id=actor.id, reason=reason, message=message,
        old_status=old_status, new_status=new_status, visibility=visibility, created_at=now,
    )
    db.add(entry)
    db.add(AuditLog(
        actor_id=actor.id, organization_id=complaint.organization_id, action=action, entity_type="complaint",
        entity_id=complaint.id, created_at=now,
        event_metadata={
            "old_status": old_status, "new_status": new_status, "visibility": visibility,
            "department_id": str(complaint.assigned_department_id) if complaint.assigned_department_id else None,
            "assigned_staff_id": str(complaint.assigned_staff_id) if complaint.assigned_staff_id else None,
            **(metadata or {}),
        },
    ))
    notifications.status_changed(db, complaint, old_status, new_status, now)
    return entry


def _existing_submission(db: Session, citizen: User, key: str | None, digest: str | None) -> Complaint | None:
    if key is None:
        return None
    complaint = db.scalar(
        select(Complaint).where(Complaint.citizen_id == citizen.id, Complaint.idempotency_key == key)
    )
    if complaint is not None and complaint.submission_digest != digest:
        raise ComplaintConflict("This idempotency key is already in use for a different submission.")
    return complaint


def submit(
    db: Session, citizen: User, payload: ComplaintInput, idempotency_key: str | None, *, analyze: bool = False
) -> tuple[Complaint, bool]:
    digest = sha256(payload.model_dump_json().encode()).hexdigest() if idempotency_key is not None else None
    existing = _existing_submission(db, citizen, idempotency_key, digest)
    if existing is not None:
        return existing, False
    if payload.category_id is not None:
        category = db.get(Category, payload.category_id)
        if category is None or not category.is_active:
            raise InvalidComplaintValue("Select an active complaint category.")

    area = find_intake_area(db, payload.longitude, payload.latitude)
    now = datetime.now(UTC)
    for _ in range(5):
        result = db.scalar(
            insert(Complaint).values(
                **payload.model_dump(), citizen_id=citizen.id,
                public_reference=f"CF-{now.year}-{token_hex(3).upper()}",
                idempotency_key=idempotency_key, submission_digest=digest,
                organization_id=area.organization_id if area else None,
                service_area_id=area.id if area else None,
                ai_analysis_status=AnalysisStatus.PENDING if analyze else AnalysisStatus.SKIPPED,
                created_at=now, updated_at=now,
            ).on_conflict_do_nothing().returning(Complaint)
        )
        if result is not None:
            _record_update(
                db, result, citizen, action="COMPLAINT_SUBMITTED", reason="Complaint submitted.",
                message=None, now=now, new_status=S.SUBMITTED,
            )
            db.commit()
            return result, True
        existing = _existing_submission(db, citizen, idempotency_key, digest)
        if existing is not None:
            return existing, False
    raise ComplaintUnavailable("A tracking reference could not be created. Retry the submission.")


def _locked_complaint(db: Session, staff: User, complaint_id: UUID) -> tuple[Complaint, StaffScope]:
    scope = find_staff_scope(db, staff.id)
    complaint = db.scalar(scoped_complaints(scope).where(Complaint.id == complaint_id).with_for_update())
    if complaint is None or scope is None:
        raise ComplaintNotFound("Resource not found.")
    return complaint, scope


def _check_transition(complaint: Complaint, target: ComplaintStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[complaint.status]:
        raise ComplaintConflict(f"Cannot move a complaint from {complaint.status} to {target}.")


def _close_assignment(db: Session, complaint_id: UUID, now: datetime) -> None:
    db.execute(
        update(ComplaintAssignment)
        .where(ComplaintAssignment.complaint_id == complaint_id, ComplaintAssignment.unassigned_at.is_(None))
        .values(unassigned_at=now)
    )


def assign(db: Session, staff: User, complaint_id: UUID, payload: AssignmentInput) -> Complaint:
    complaint, scope = _locked_complaint(db, staff, complaint_id)
    if complaint.status != S.ASSIGNED:
        _check_transition(complaint, S.ASSIGNED)
    if payload.department_id not in scope.department_ids:
        raise InvalidComplaintValue("Select a department within your active scope.")
    if payload.assigned_staff_id is not None:
        assignee = db.get(User, payload.assigned_staff_id)
        candidate = (
            find_staff_scope(db, assignee.id, scope.organization_id)
            if assignee is not None and assignee.is_active and assignee.role == Role.STAFF else None
        )
        if (
            candidate is None
            or payload.department_id not in candidate.department_ids
            or complaint.service_area_id not in candidate.service_area_ids
        ):
            raise InvalidComplaintValue("Select an active staff member in the department and service area.")

    now = datetime.now(UTC)
    previous = complaint.status
    _close_assignment(db, complaint.id, now)
    complaint.status = S.ASSIGNED
    complaint.assigned_department_id = payload.department_id
    complaint.assigned_staff_id = payload.assigned_staff_id
    db.add(ComplaintAssignment(
        complaint_id=complaint.id, department_id=payload.department_id, assigned_staff_id=payload.assigned_staff_id,
        assigned_by=staff.id, assigned_at=now, reason=payload.reason,
    ))
    _record_update(
        db, complaint, staff, action="COMPLAINT_ASSIGNED", reason=payload.reason, message=payload.public_message,
        now=now, old_status=previous, new_status=S.ASSIGNED,
    )
    recipients = (
        [payload.assigned_staff_id] if payload.assigned_staff_id is not None else
        [user.id for _, user in db.execute(eligible_staff([payload.department_id], complaint.service_area_id))]
    )
    for recipient in recipients:
        notifications.assigned(db, complaint, recipient, now)
    db.commit()
    return complaint


def change_status(db: Session, staff: User, complaint_id: UUID, payload: StatusInput) -> Complaint:
    complaint, _ = _locked_complaint(db, staff, complaint_id)
    previous, target = complaint.status, payload.status
    _check_transition(complaint, target)
    if target == S.ASSIGNED and previous == S.UNDER_REVIEW:
        raise ComplaintConflict("Create an assignment to move this complaint to ASSIGNED.")

    now = datetime.now(UTC)
    complaint.status = target
    if target == S.RESOLVED:
        complaint.resolved_at = now
        complaint.resolution_description = payload.resolution_description
    if previous == S.RESOLVED and target == S.IN_PROGRESS:
        complaint.resolved_at = None
        complaint.resolution_description = None
    if target == S.CLOSED:
        complaint.closed_at = now
    if target in {S.CLOSED, S.REJECTED, S.UNDER_REVIEW}:
        _close_assignment(db, complaint.id, now)
    if target == S.UNDER_REVIEW:
        complaint.assigned_staff_id = None
    _record_update(
        db, complaint, staff, action="COMPLAINT_REVIEWED" if target == S.UNDER_REVIEW else "COMPLAINT_STATUS_CHANGED",
        reason=payload.reason, message=payload.public_message, now=now, old_status=previous, new_status=target,
    )
    db.commit()
    return complaint


def review(db: Session, staff: User, complaint_id: UUID, payload: ReviewInput) -> Complaint:
    return change_status(db, staff, complaint_id, StatusInput(status=S.UNDER_REVIEW, **payload.model_dump()))


def confirm_priority(db: Session, staff: User, complaint_id: UUID, payload: PriorityInput) -> Complaint:
    complaint, _ = _locked_complaint(db, staff, complaint_id)
    old = complaint.confirmed_priority
    complaint.confirmed_priority = payload.priority
    complaint.priority_override_reason = payload.reason
    _record_update(
        db, complaint, staff, action="COMPLAINT_PRIORITY_CHANGED", reason=payload.reason,
        message=None, now=datetime.now(UTC), visibility=UpdateVisibility.INTERNAL,
        metadata={"old_priority": old, "new_priority": payload.priority},
    )
    db.commit()
    return complaint


def confirm_category(db: Session, staff: User, complaint_id: UUID, payload: CategoryInput) -> Complaint:
    complaint, _ = _locked_complaint(db, staff, complaint_id)
    category = db.get(Category, payload.category_id)
    if category is None or not category.is_active:
        raise InvalidComplaintValue("Select an active complaint category.")
    old = complaint.category_id
    complaint.category_id = category.id
    complaint.category_confirmed = True
    _record_update(
        db, complaint, staff, action="COMPLAINT_CATEGORY_CHANGED", reason=payload.reason,
        message=None, now=datetime.now(UTC), visibility=UpdateVisibility.INTERNAL,
        metadata={"old_category_id": str(old) if old else None, "new_category_id": str(category.id)},
    )
    db.commit()
    return complaint


def add_update(db: Session, staff: User, complaint_id: UUID, payload: UpdateInput) -> ComplaintUpdate:
    complaint, _ = _locked_complaint(db, staff, complaint_id)
    message = payload.message
    entry = _record_update(
        db, complaint, staff, action="COMPLAINT_NOTE_ADDED", reason=message, message=message,
        visibility=payload.visibility, now=datetime.now(UTC),
    )
    db.commit()
    return entry
