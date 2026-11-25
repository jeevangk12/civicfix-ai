from logging import getLogger
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from python_multipart.exceptions import MultipartParseError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from app.api.deps import Config, CurrentUser, Database
from app.api.responses import success
from app.db.evidence_models import ComplaintImage, ImageKind
from app.db.models import Role
from app.repositories.complaints import visible_complaint
from app.schemas.auth import DataResponse
from app.schemas.complaints import UtcTimestamp
from app.services.evidence import CloudinaryEvidence, InvalidImage, UploadUnavailable, clean_image

router = APIRouter(tags=["private evidence"])
logger = getLogger(__name__)


class ImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    mime_type: str
    image_kind: ImageKind
    created_at: UtcTimestamp


class BodyTooLarge(MultiPartException):
    pass


async def _limited_stream(request: Request, limit: int):
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise BodyTooLarge("Photo exceeds the configured size limit.")
        yield chunk


async def _read_photo(request: Request, limit: int) -> tuple[bytes, str | None]:
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "multipart/form-data":
        raise HTTPException(415, "Upload one photo as multipart form data.")
    try:
        form = await MultiPartParser(request.headers, _limited_stream(request, limit + 16_384), max_files=1, max_fields=0).parse()
    except BodyTooLarge as error:
        raise HTTPException(413, error.message) from None
    except (MultiPartException, MultipartParseError):
        raise HTTPException(422, "Select one valid photo.") from None
    try:
        file = form.get("file")
        if not isinstance(file, UploadFile):
            raise HTTPException(422, "Select one photo.")
        contents = await file.read(limit + 1)
        if len(contents) > limit:
            raise HTTPException(413, "Photo exceeds the configured size limit.")
        return contents, file.content_type
    finally:
        await form.close()


def _store(
    db: Session, storage: CloudinaryEvidence, complaint_id: UUID, actor_id: UUID, kind: ImageKind,
    contents: bytes, mime_type: str | None, max_images: int,
) -> ImageRead:
    size = db.scalar(select(func.count()).select_from(ComplaintImage).where(ComplaintImage.complaint_id == complaint_id))
    if size >= max_images:
        raise HTTPException(409, "This report already has the maximum number of photos.")
    try:
        photo = clean_image(contents, mime_type)
        image_id = uuid4()
        key = f"civicfix/{complaint_id}/{image_id.hex}"
        url = storage.upload(photo, key)
    except InvalidImage as error:
        raise HTTPException(422, str(error)) from None
    except UploadUnavailable:
        raise HTTPException(503, "Photo storage is temporarily unavailable.") from None
    record = ComplaintImage(
        id=image_id, complaint_id=complaint_id, uploaded_by=actor_id, secure_url=url, cloudinary_public_id=key,
        mime_type="image/jpeg", file_size_bytes=len(photo), image_kind=kind,
    )
    db.add(record)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        try:
            storage.remove(key)
        except UploadUnavailable:
            logger.warning("Could not remove unassociated evidence image %s", image_id)
        raise
    return ImageRead.model_validate(record)


@router.post("/complaints/{complaint_id}/images", status_code=201)
async def add_evidence(
    request: Request, db: Database, config: Config, current: CurrentUser, complaint_id: UUID,
    kind: ImageKind = "REPORT",
) -> DataResponse[ImageRead]:
    user = current.user
    if user.role not in {Role.CITIZEN, Role.STAFF} or (kind == "RESOLUTION" and user.role != Role.STAFF):
        raise HTTPException(403, "This account cannot attach evidence of this kind.")
    request.app.state.rate_limiter.check(request, "complaint-image", 15)
    if await run_in_threadpool(visible_complaint, db, user, complaint_id) is None:
        raise HTTPException(404, "Report not found.")
    photo, content_type = await _read_photo(request, config.max_upload_size_mb * 1024 * 1024)
    if await run_in_threadpool(visible_complaint, db, user, complaint_id, lock=True) is None:
        raise HTTPException(404, "Report not found.")
    record = await run_in_threadpool(
        _store, db, request.app.state.evidence, complaint_id, user.id, kind,
        photo, content_type, config.max_images_per_complaint,
    )
    return success(request, record)
