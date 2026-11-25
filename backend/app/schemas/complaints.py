from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Generic, Self
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.db.complaint_models import AnalysisStatus, ComplaintStatus, ComplaintVisibility, Priority, UpdateVisibility
from app.schemas.auth import RequestMeta, T

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
ProgressText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
UtcTimestamp = Annotated[datetime, AfterValidator(lambda value: value.astimezone(UTC))]
CoordinatePrecision = AfterValidator(lambda value: value.quantize(Decimal("0.000001")))


class ComplaintInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=120)]
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=5000)]
    latitude: Annotated[Decimal, Field(ge=-90, le=90), CoordinatePrecision]
    longitude: Annotated[Decimal, Field(ge=-180, le=180), CoordinatePrecision]
    category_id: UUID | None = None
    location_label: ShortText | None = None


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: ProgressText
    public_message: ProgressText | None = None


class AssignmentInput(ReviewInput):
    department_id: UUID
    assigned_staff_id: UUID | None = None


class AssignmentOption(BaseModel):
    class Person(BaseModel):
        id: UUID
        name: str

    id: UUID
    name: str
    staff: list[Person]


class PriorityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    priority: Priority
    reason: ProgressText


class CategoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category_id: UUID
    reason: ProgressText


class StatusInput(ReviewInput):
    status: ComplaintStatus
    resolution_description: ProgressText | None = None

    @model_validator(mode="after")
    def validate_resolution(self) -> Self:
        if (self.status == ComplaintStatus.RESOLVED) != (self.resolution_description is not None):
            raise ValueError("A resolution description is required when resolving a complaint.")
        return self


class UpdateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: ProgressText
    visibility: UpdateVisibility


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1, le=1_000_000)
    page_size: int = Field(default=20, ge=1, le=100)


class PageMeta(RequestMeta, PageParams):
    total: int


class PageResponse(BaseModel, Generic[T]):
    data: list[T]
    meta: PageMeta


class ComplaintSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_reference: str
    title: str
    status: ComplaintStatus
    category_id: UUID | None
    visibility: ComplaintVisibility
    created_at: UtcTimestamp
    updated_at: UtcTimestamp


class ComplaintDetail(ComplaintSummary):
    description: str
    latitude: float
    longitude: float
    location_label: str | None


class StaffComplaintDetail(ComplaintDetail):
    ai_analysis_status: AnalysisStatus
    category_confirmed: bool
    confirmed_priority: Priority | None
    priority_override_reason: str | None
    organization_id: UUID | None
    service_area_id: UUID | None
    assigned_department_id: UUID | None
    assigned_staff_id: UUID | None
    resolution_description: str | None
    resolved_at: UtcTimestamp | None
    closed_at: UtcTimestamp | None


class CitizenProgress(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    old_status: ComplaintStatus | None
    new_status: ComplaintStatus | None
    message: str | None
    created_at: UtcTimestamp


class StaffProgress(CitizenProgress):
    actor_id: UUID
    reason: str
    visibility: UpdateVisibility


class CategorySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str


class PublicComplaint(BaseModel):
    public_reference: str
    title: str
    category: CategorySummary | None
    status: ComplaintStatus
    created_on: date
    updated_on: date
