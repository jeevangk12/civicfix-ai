from datetime import UTC, datetime
from decimal import ROUND_FLOOR, Decimal
from typing import Annotated, Self
from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import func, select

from app.api.access import StaffUser
from app.api.complaints import _page
from app.api.deps import Config, Database
from app.api.responses import success
from app.db.complaint_models import Category, Complaint, ComplaintStatus, ComplaintVisibility, UpdateVisibility
from app.db.models import User
from app.repositories.complaints import paginated
from app.schemas.auth import DataResponse
from app.schemas.complaints import (
    CategorySummary, CoordinatePrecision, PageParams, PageResponse, ProgressText, PublicComplaint,
)
from app.services.complaints import InvalidComplaintValue, _locked_complaint, _record_update
from app.services.gemini import without_identifiers

router = APIRouter(tags=["public map and visibility"])
V = ComplaintVisibility


class VisibilityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    visibility: ComplaintVisibility
    approved_public_summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=120)] | None = None
    public_latitude: Annotated[Decimal, Field(ge=-90, le=90), CoordinatePrecision] | None = None
    public_longitude: Annotated[Decimal, Field(ge=-180, le=180), CoordinatePrecision] | None = None
    reason: ProgressText

    @model_validator(mode="after")
    def validate_public_fields(self) -> Self:
        if (self.visibility != V.PRIVATE) != (self.approved_public_summary is not None):
            raise ValueError("Visible reports require an approved public summary.")
        coordinates = (self.public_latitude, self.public_longitude)
        if self.visibility == V.PUBLIC and None in coordinates:
            raise ValueError("Public markers require an explicitly approved latitude and longitude.")
        if self.visibility != V.PUBLIC and coordinates != (None, None):
            raise ValueError("Only a public marker accepts manually approved coordinates.")
        return self


class VisibilityRead(BaseModel):
    id: UUID
    visibility: ComplaintVisibility
    approved_public_summary: str | None


class PublicMapFilters(PageParams):
    status: ComplaintStatus | None = None
    category_id: UUID | None = None


class MapMarker(PublicComplaint):
    latitude: float
    longitude: float
    location_precision: str


def _cell_center(value: Decimal, grid: Decimal, bound: int) -> Decimal:
    half = grid / 2
    center = (value / grid).to_integral_value(rounding=ROUND_FLOOR) * grid + half
    center = max(-bound + half, min(bound - half, center))
    if center == value:
        return center + grid if center + grid < bound else center - grid
    return center


def _approximate(latitude: Decimal, longitude: Decimal, grid: Decimal) -> tuple[Decimal, Decimal]:
    return _cell_center(latitude, grid, 90), _cell_center(longitude, grid, 180)


@router.patch("/authority/complaints/{complaint_id}/visibility")
def set_visibility(
    request: Request, db: Database, staff: StaffUser, config: Config, complaint_id: UUID, payload: VisibilityInput,
) -> DataResponse[VisibilityRead]:
    complaint, _ = _locked_complaint(db, staff, complaint_id)
    summary = payload.approved_public_summary
    if summary is not None:
        name = db.scalar(select(User.full_name).where(User.id == complaint.citizen_id)) or ""
        if without_identifiers(summary, name) != summary:
            raise InvalidComplaintValue("Remove the reporter name and contact details from the public summary.")
    previous = complaint.visibility
    complaint.visibility = payload.visibility
    complaint.approved_public_summary = summary
    public_coordinates = (payload.public_latitude, payload.public_longitude)
    if payload.visibility == V.APPROXIMATE:
        public_coordinates = _approximate(complaint.latitude, complaint.longitude, config.public_location_grid_degrees)
    complaint.public_latitude, complaint.public_longitude = public_coordinates
    _record_update(
        db, complaint, staff, action="COMPLAINT_VISIBILITY_CHANGED", reason=payload.reason, message=None,
        now=datetime.now(UTC), visibility=UpdateVisibility.INTERNAL,
        metadata={"old_visibility": previous, "new_visibility": complaint.visibility},
    )
    db.commit()
    return success(request, VisibilityRead(id=complaint.id, visibility=complaint.visibility, approved_public_summary=summary))


@router.get("/public/complaints/map")
def public_markers(
    request: Request, db: Database, config: Config, filters: Annotated[PublicMapFilters, Query()],
) -> PageResponse[MapMarker]:
    reports = select(Complaint).where(
        Complaint.visibility.in_((V.PUBLIC, V.APPROXIMATE)),
        func.length(func.btrim(Complaint.approved_public_summary)) > 0,
        Complaint.public_latitude.between(-90, 90), Complaint.public_longitude.between(-180, 180),
    )
    if filters.status is not None:
        reports = reports.where(Complaint.status == filters.status)
    if filters.category_id is not None:
        reports = reports.where(Complaint.category_id == filters.category_id)
    rows, total = paginated(db, reports.order_by(Complaint.updated_at.desc(), Complaint.id), filters)
    categories = {category.id: CategorySummary.model_validate(category) for category in db.scalars(
        select(Category).where(Category.id.in_({row.category_id for row in rows if row.category_id})),
    )}
    markers = []
    for row in rows:
        latitude, longitude = row.public_latitude, row.public_longitude
        if row.visibility == V.APPROXIMATE:
            latitude, longitude = _approximate(row.latitude, row.longitude, config.public_location_grid_degrees)
        markers.append(MapMarker(
            public_reference=row.public_reference, title=row.approved_public_summary, category=categories.get(row.category_id),
            status=row.status, latitude=float(latitude), longitude=float(longitude),
            location_precision="approximate" if row.visibility == V.APPROXIMATE else "approved",
            created_on=row.created_at.astimezone(UTC).date(), updated_on=row.updated_at.astimezone(UTC).date(),
        ))
    return _page(request, markers, filters, total)
