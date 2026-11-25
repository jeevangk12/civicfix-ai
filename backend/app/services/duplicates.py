import re
from datetime import UTC, datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from uuid import UUID

from sqlalchemy import or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.complaint_models import Complaint, ComplaintStatus, UpdateVisibility
from app.db.intelligence_models import DuplicateStatus, DuplicateSuggestion
from app.db.models import User
from app.repositories.complaints import scoped_complaints
from app.schemas.auth import StaffScope
from app.services import notifications
from app.services.access import find_staff_scope
from app.services.complaints import ComplaintConflict, ComplaintNotFound, _record_update

_TERMS = re.compile(r"[^\W_]{3,}", re.UNICODE)


def _terms(complaint: Complaint) -> set[str]:
    return set(_TERMS.findall(f"{complaint.title} {complaint.description}".casefold()))


def _distance(a: Complaint, b: Complaint) -> float:
    lat_a, lat_b = radians(float(a.latitude)), radians(float(b.latitude))
    lng_delta = radians(float(b.longitude - a.longitude))
    haversine = sin((lat_b - lat_a) / 2) ** 2 + cos(lat_a) * cos(lat_b) * sin(lng_delta / 2) ** 2
    return 2 * 6_371_000 * asin(sqrt(min(1.0, haversine)))


def detect(db: Session, source: Complaint, settings: Settings) -> None:
    if source.organization_id is None or source.service_area_id is None:
        return
    latitude, longitude = float(source.latitude), float(source.longitude)
    radius = settings.duplicate_radius_meters
    lat_window = radius / 110_000
    lng_window = min(180, lat_window / max(cos(radians(latitude)), 0.000001))
    candidates = select(Complaint).where(
        Complaint.organization_id == source.organization_id,
        Complaint.service_area_id == source.service_area_id,
        tuple_(Complaint.created_at, Complaint.id) < tuple_(source.created_at, source.id),
        Complaint.created_at >= source.created_at - timedelta(days=settings.duplicate_window_days),
        Complaint.status.not_in((ComplaintStatus.REJECTED, ComplaintStatus.CLOSED)),
        Complaint.latitude.between(latitude - lat_window, latitude + lat_window),
        Complaint.longitude.between(longitude - lng_window, longitude + lng_window),
    )
    if source.category_id is not None:
        candidates = candidates.where(or_(Complaint.category_id == source.category_id, Complaint.category_id.is_(None)))
    terms = _terms(source)
    matches = []
    for candidate in db.scalars(candidates.order_by(Complaint.created_at.desc()).limit(150)):
        candidate_terms = _terms(candidate)
        union = terms | candidate_terms
        similarity = len(terms & candidate_terms) / len(union) if union else 0
        distance = _distance(source, candidate)
        if distance <= radius and similarity >= settings.duplicate_similarity_threshold:
            matches.append((similarity, distance, candidate.id))
    for similarity, distance, candidate_id in sorted(matches, key=lambda item: (-item[0], item[1], item[2]))[:10]:
        db.execute(insert(DuplicateSuggestion).values(
            complaint_id=source.id, candidate_complaint_id=candidate_id, similarity_score=round(similarity, 4),
            distance_meters=round(distance, 2), detection_method="title-description-jaccard-distance-v1",
        ).on_conflict_do_nothing())


def _scope(db: Session, staff: User, complaint_id: UUID, *, lock: bool = False) -> tuple[Complaint, StaffScope]:
    scope = find_staff_scope(db, staff.id)
    query = scoped_complaints(scope).where(Complaint.id == complaint_id)
    complaint = db.scalar(query.with_for_update() if lock else query)
    if complaint is None or scope is None:
        raise ComplaintNotFound("Resource not found.")
    return complaint, scope


def list_suggestions(db: Session, staff: User, complaint_id: UUID):
    _, scope = _scope(db, staff, complaint_id)
    visible_ids = scoped_complaints(scope).with_only_columns(Complaint.id).correlate(None)
    return db.execute(
        select(DuplicateSuggestion, Complaint)
        .join(Complaint, Complaint.id == DuplicateSuggestion.candidate_complaint_id)
        .where(DuplicateSuggestion.complaint_id == complaint_id, Complaint.id.in_(visible_ids))
        .order_by(DuplicateSuggestion.similarity_score.desc(), DuplicateSuggestion.distance_meters, DuplicateSuggestion.id)
    ).all()


def review_suggestion(
    db: Session, staff: User, complaint_id: UUID, duplicate_id: UUID, decision: DuplicateStatus, reason: str
) -> tuple[DuplicateSuggestion, Complaint]:
    source, scope = _scope(db, staff, complaint_id, lock=True)
    suggestion = db.scalar(
        select(DuplicateSuggestion)
        .where(DuplicateSuggestion.id == duplicate_id, DuplicateSuggestion.complaint_id == source.id)
        .with_for_update()
    )
    if suggestion is None:
        raise ComplaintNotFound("Resource not found.")
    candidate = db.scalar(scoped_complaints(scope).where(Complaint.id == suggestion.candidate_complaint_id))
    if candidate is None:
        raise ComplaintNotFound("Resource not found.")
    if suggestion.review_status != DuplicateStatus.PENDING:
        raise ComplaintConflict("This suggestion has already been reviewed.")

    now = datetime.now(UTC)
    suggestion.review_status = decision
    suggestion.reviewed_by = staff.id
    suggestion.reviewed_at = now
    confirmed = decision == DuplicateStatus.CONFIRMED_DUPLICATE
    _record_update(
        db, source, staff, action="DUPLICATE_CONFIRMED" if confirmed else "DUPLICATE_DISMISSED",
        reason=reason,
        message=(
            f"Staff confirmed that another report describes the same issue. "
            f"The primary tracking reference is {candidate.public_reference}."
        ) if confirmed else None,
        now=now, visibility=UpdateVisibility.PUBLIC if confirmed else UpdateVisibility.INTERNAL,
        metadata={"suggestion_id": str(suggestion.id), "candidate_id": str(candidate.id)},
    )
    if confirmed:
        notifications.duplicate_confirmed(db, source, now)
    db.commit()
    return suggestion, candidate
