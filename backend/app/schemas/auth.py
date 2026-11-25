from typing import Annotated, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.db.models import Role

FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
NewPassword = Annotated[str, Field(min_length=12, max_length=128)]
T = TypeVar("T")


class RequestMeta(BaseModel):
    request_id: str


class DataResponse(BaseModel, Generic[T]):
    data: T
    meta: RequestMeta


class AccountInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: FullName
    email: Annotated[EmailStr, Field(max_length=255)]
    password: NewPassword


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Annotated[EmailStr, Field(max_length=255)]
    password: Annotated[str, Field(min_length=1, max_length=128)]


class StaffInput(AccountInput):
    organization_id: UUID
    department_ids: set[UUID] = Field(min_length=1, max_length=100)
    service_area_ids: set[UUID] = Field(min_length=1, max_length=100)
    staff_title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)] | None = None


class UserDetails(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: EmailStr
    role: Role
    is_active: bool


class AccessToken(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class StaffScope(BaseModel):
    organization_id: UUID
    department_ids: list[UUID]
    service_area_ids: list[UUID]


class ProvisionedStaff(BaseModel):
    user: UserDetails
    scope: StaffScope
