from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.api.access import StaffUser
from app.api.deps import Database
from app.api.responses import success
from app.db.complaint_models import AnalysisStatus, Category, Complaint, Priority
from app.db.intelligence_models import Analysis, DuplicateStatus, DuplicateSuggestion
from app.db.models import Department
from app.repositories.complaints import visible_complaint
from app.schemas.auth import DataResponse
from app.schemas.complaints import ProgressText, UtcTimestamp
from app.services import complaints, duplicates

router = APIRouter(prefix="/authority", tags=["complaint intelligence"])


class RecommendationRead(BaseModel):
    status: AnalysisStatus
    summary: str | None = None
    category: str | None = None
    priority: Priority | None = None
    priority_reason: str | None = None
    department: str | None = None
    confidence: float | None = None
    needs_human_review: bool = True


class DuplicateRead(BaseModel):
    id: UUID
    candidate_id: UUID
    public_reference: str
    title: str
    similarity_score: float
    distance_meters: float
    review_status: DuplicateStatus
    reviewed_by: UUID | None
    reviewed_at: UtcTimestamp | None


class DuplicateReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal[DuplicateStatus.CONFIRMED_DUPLICATE, DuplicateStatus.NOT_DUPLICATE]
    reason: ProgressText


def _duplicate_data(item: DuplicateSuggestion, candidate: Complaint) -> DuplicateRead:
    return DuplicateRead(
        id=item.id, candidate_id=candidate.id, public_reference=candidate.public_reference, title=candidate.title,
        similarity_score=float(item.similarity_score), distance_meters=float(item.distance_meters),
        review_status=item.review_status, reviewed_by=item.reviewed_by, reviewed_at=item.reviewed_at,
    )


@router.get("/complaints/{complaint_id}/analysis")
def recommendation(
    request: Request, db: Database, staff: StaffUser, complaint_id: UUID
) -> DataResponse[RecommendationRead]:
    case = visible_complaint(db, staff, complaint_id)
    if case is None:
        raise complaints.ComplaintNotFound("Resource not found.")
    analysis = db.scalar(select(Analysis).where(Analysis.complaint_id == complaint_id))
    if analysis is None or analysis.status != AnalysisStatus.SUCCEEDED:
        return success(request, RecommendationRead(status=case.ai_analysis_status))
    category = db.get(Category, analysis.suggested_category_id) if analysis.suggested_category_id else None
    department = db.get(Department, analysis.suggested_department_id) if analysis.suggested_department_id else None
    return success(request, RecommendationRead(
        status=analysis.status, summary=analysis.summary, category=category.name if category else None,
        priority=analysis.suggested_priority, priority_reason=analysis.priority_reason,
        department=department.name if department else None,
        confidence=float(analysis.confidence) if analysis.confidence is not None else None,
        needs_human_review=analysis.needs_human_review,
    ))


@router.get("/complaints/{complaint_id}/duplicates")
def duplicate_suggestions(
    request: Request, db: Database, staff: StaffUser, complaint_id: UUID
) -> DataResponse[list[DuplicateRead]]:
    return success(request, [_duplicate_data(row, case) for row, case in duplicates.list_suggestions(db, staff, complaint_id)])


@router.post("/duplicates/{duplicate_id}/review")
def review_duplicate(
    request: Request, db: Database, staff: StaffUser, duplicate_id: UUID, payload: DuplicateReview
) -> DataResponse[DuplicateRead]:
    complaint_id = db.scalar(select(DuplicateSuggestion.complaint_id).where(DuplicateSuggestion.id == duplicate_id))
    if complaint_id is None:
        raise complaints.ComplaintNotFound("Resource not found.")
    item, candidate = duplicates.review_suggestion(db, staff, complaint_id, duplicate_id, payload.decision, payload.reason)
    return success(request, _duplicate_data(item, candidate))
