from datetime import UTC
from typing import Annotated, TypeVar
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request, Response
from sqlalchemy import select

from app.api.access import StaffUser
from app.api.deps import CurrentUser, Database, require_role
from app.api.responses import success
from app.db.complaint_models import Category, Complaint, ComplaintStatus, ComplaintVisibility
from app.db.models import Department, Role, User
from app.repositories.complaints import eligible_staff, paginated, scoped_complaints, updates_for, visible_complaint
from app.schemas.auth import DataResponse
from app.schemas.complaints import (
    AssignmentInput, AssignmentOption, CategoryInput, CategorySummary, CitizenProgress, ComplaintDetail,
    ComplaintInput, ComplaintSummary,
    PageMeta, PageParams, PageResponse, PublicComplaint, ReviewInput, StaffComplaintDetail, StaffProgress,
    PriorityInput, StatusInput, UpdateInput,
)
from app.services import complaints, intake
from app.services.access import find_staff_scope

router = APIRouter(prefix="/complaints", tags=["complaints"])
authority_router = APIRouter(prefix="/authority/complaints", tags=["authority complaints"])
public_router = APIRouter(prefix="/public", tags=["public complaints"])
Citizen = Annotated[User, Depends(require_role(Role.CITIZEN))]
Pagination = Annotated[PageParams, Query()]
Item = TypeVar("Item")


def _page(request: Request, data: list[Item], params: PageParams, total: int) -> PageResponse[Item]:
    return PageResponse(
        data=data,
        meta=PageMeta(page=params.page, page_size=params.page_size, total=total, request_id=request.state.request_id),
    )


@router.post("", status_code=201, responses={200: {"description": "Existing idempotent submission"}})
def submit(
    request: Request, response: Response, payload: ComplaintInput, db: Database, citizen: Citizen, tasks: BackgroundTasks,
    idempotency_key: Annotated[str | None, Header(min_length=1, max_length=128, pattern=r"^[!-~]+$")] = None,
) -> DataResponse[ComplaintDetail]:
    request.app.state.rate_limiter.check(request, "complaint-submission", 10)
    gemini = request.app.state.gemini
    complaint, created = complaints.submit(db, citizen, payload, idempotency_key, analyze=gemini is not None)
    if created:
        tasks.add_task(
            intake.process, request.app.state.database_engine, request.app.state.settings, complaint.id, gemini
        )
    else:
        response.status_code = 200
    return success(request, ComplaintDetail.model_validate(complaint))


@router.get("/mine")
def mine(request: Request, db: Database, citizen: Citizen, params: Pagination) -> PageResponse[ComplaintSummary]:
    statement = (
        select(Complaint).where(Complaint.citizen_id == citizen.id)
        .order_by(Complaint.created_at.desc(), Complaint.id)
    )
    rows, total = paginated(db, statement, params)
    return _page(request, [ComplaintSummary.model_validate(row) for row in rows], params, total)


def _require_visible(db: Database, current: CurrentUser, complaint_id: UUID) -> Complaint:
    complaint = visible_complaint(db, current.user, complaint_id)
    if complaint is None:
        raise complaints.ComplaintNotFound("Resource not found.")
    return complaint


@router.get("/{complaint_id}")
def detail(
    request: Request, current: CurrentUser, complaint: Annotated[Complaint, Depends(_require_visible)]
) -> DataResponse[ComplaintDetail | StaffComplaintDetail]:
    schema = ComplaintDetail if current.user.role == Role.CITIZEN else StaffComplaintDetail
    return success(request, schema.model_validate(complaint))


@router.get("/{complaint_id}/updates")
def history(
    request: Request, db: Database, current: CurrentUser, params: Pagination,
    complaint: Annotated[Complaint, Depends(_require_visible)],
) -> PageResponse[CitizenProgress | StaffProgress]:
    citizen_view = current.user.role == Role.CITIZEN
    rows, total = paginated(db, updates_for(complaint.id, citizen_view), params)
    schema = CitizenProgress if citizen_view else StaffProgress
    return _page(request, [schema.model_validate(row) for row in rows], params, total)


class AuthorityFilters(PageParams):
    status: ComplaintStatus | None = None
    category_id: UUID | None = None


@authority_router.get("")
def staff_queue(
    request: Request, db: Database, staff: StaffUser, params: Annotated[AuthorityFilters, Query()]
) -> PageResponse[ComplaintSummary]:
    statement = scoped_complaints(find_staff_scope(db, staff.id))
    if params.status is not None:
        statement = statement.where(Complaint.status == params.status)
    if params.category_id is not None:
        statement = statement.where(Complaint.category_id == params.category_id)
    rows, total = paginated(db, statement.order_by(Complaint.created_at.desc(), Complaint.id), params)
    return _page(request, [ComplaintSummary.model_validate(row) for row in rows], params, total)


@authority_router.post("/{complaint_id}/review")
def review(
    request: Request, db: Database, staff: StaffUser, complaint_id: UUID, payload: ReviewInput
) -> DataResponse[StaffComplaintDetail]:
    return success(request, StaffComplaintDetail.model_validate(complaints.review(db, staff, complaint_id, payload)))


@authority_router.get("/{complaint_id}/assignment-options")
def assignment_options(
    request: Request, db: Database, staff: StaffUser, complaint_id: UUID
) -> DataResponse[list[AssignmentOption]]:
    scope = find_staff_scope(db, staff.id)
    current = db.scalar(scoped_complaints(scope).where(Complaint.id == complaint_id))
    if current is None or scope is None:
        raise complaints.ComplaintNotFound("Resource not found.")
    departments = db.scalars(
        select(Department).where(Department.id.in_(scope.department_ids)).order_by(Department.name, Department.id)
    ).all()
    staff_by_department = {department.id: [] for department in departments}
    eligible = db.execute(eligible_staff(scope.department_ids, current.service_area_id))
    for department_id, user in eligible:
        staff_by_department[department_id].append(AssignmentOption.Person(id=user.id, name=user.full_name))
    return success(request, [
        AssignmentOption(id=department.id, name=department.name, staff=staff_by_department[department.id])
        for department in departments
    ])


@authority_router.patch("/{complaint_id}/priority")
def confirm_priority(
    request: Request, db: Database, staff: StaffUser, complaint_id: UUID, payload: PriorityInput
) -> DataResponse[StaffComplaintDetail]:
    case = complaints.confirm_priority(db, staff, complaint_id, payload)
    return success(request, StaffComplaintDetail.model_validate(case))


@authority_router.patch("/{complaint_id}/category")
def confirm_category(
    request: Request, db: Database, staff: StaffUser, complaint_id: UUID, payload: CategoryInput
) -> DataResponse[StaffComplaintDetail]:
    case = complaints.confirm_category(db, staff, complaint_id, payload)
    return success(request, StaffComplaintDetail.model_validate(case))


@authority_router.post("/{complaint_id}/assignments", status_code=201)
def assign(
    request: Request, db: Database, staff: StaffUser, complaint_id: UUID, payload: AssignmentInput
) -> DataResponse[StaffComplaintDetail]:
    return success(request, StaffComplaintDetail.model_validate(complaints.assign(db, staff, complaint_id, payload)))


@authority_router.post("/{complaint_id}/status")
def change_status(
    request: Request, db: Database, staff: StaffUser, complaint_id: UUID, payload: StatusInput
) -> DataResponse[StaffComplaintDetail]:
    complaint = complaints.change_status(db, staff, complaint_id, payload)
    return success(request, StaffComplaintDetail.model_validate(complaint))


@authority_router.post("/{complaint_id}/updates", status_code=201)
def post_update(
    request: Request, db: Database, staff: StaffUser, complaint_id: UUID, payload: UpdateInput
) -> DataResponse[StaffProgress]:
    return success(request, StaffProgress.model_validate(complaints.add_update(db, staff, complaint_id, payload)))


@public_router.get("/complaints/{public_reference}")
def public_detail(request: Request, db: Database, public_reference: str) -> DataResponse[PublicComplaint]:
    complaint = db.scalar(
        select(Complaint).where(
            Complaint.public_reference == public_reference,
            Complaint.visibility.in_((ComplaintVisibility.PUBLIC, ComplaintVisibility.APPROXIMATE)),
            Complaint.approved_public_summary.is_not(None),
        )
    )
    if complaint is None or not (complaint.approved_public_summary or "").strip():
        raise complaints.ComplaintNotFound("Resource not found.")
    category = db.get(Category, complaint.category_id) if complaint.category_id is not None else None
    return success(request, PublicComplaint(
        public_reference=complaint.public_reference,
        title=complaint.approved_public_summary,
        category=CategorySummary.model_validate(category) if category is not None else None,
        status=complaint.status,
        created_on=complaint.created_at.astimezone(UTC).date(),
        updated_on=complaint.updated_at.astimezone(UTC).date(),
    ))


@public_router.get("/categories")
def categories(request: Request, db: Database, params: Pagination) -> PageResponse[CategorySummary]:
    rows, total = paginated(db, select(Category).where(Category.is_active).order_by(Category.sort_order, Category.code), params)
    return _page(request, [CategorySummary.model_validate(row) for row in rows], params, total)
