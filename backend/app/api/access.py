from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import Database, require_role
from app.api.responses import success
from app.db.models import Role, User
from app.schemas.auth import DataResponse, ProvisionedStaff, StaffInput, StaffScope
from app.services import access
from app.services.auth import EmailInUse

router = APIRouter(tags=["access control"])
AdminUser = Annotated[User, Depends(require_role(Role.ADMIN))]
StaffUser = Annotated[User, Depends(require_role(Role.STAFF))]


@router.post("/admin/staff", status_code=201)
def provision_staff(
    request: Request, payload: StaffInput, db: Database, admin: AdminUser
) -> DataResponse[ProvisionedStaff]:
    request.app.state.rate_limiter.check(request, "provision-staff", 20)
    try:
        return success(request, access.provision_staff(db, admin, payload))
    except access.InvalidStaffScope as error:
        raise HTTPException(422, str(error)) from None
    except EmailInUse:
        raise HTTPException(409, "An account already uses this email.") from None


def require_staff_scope(organization_id: UUID, db: Database, staff: StaffUser) -> StaffScope:
    scope = access.find_staff_scope(db, staff.id, organization_id)
    if scope is None:
        raise HTTPException(404, "Resource not found.")
    return scope


@router.get("/authority/scope/{organization_id}")
def staff_scope(
    request: Request, scope: Annotated[StaffScope, Depends(require_staff_scope)]
) -> DataResponse[StaffScope]:
    return success(request, scope)
