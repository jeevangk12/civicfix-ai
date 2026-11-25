from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base

ImageKind = Literal["REPORT", "RESOLUTION"]


class ComplaintImage(Base):
    __tablename__ = "complaint_images"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    complaint_id: Mapped[UUID] = mapped_column(ForeignKey("complaints.id"), index=True)
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    cloudinary_public_id: Mapped[str] = mapped_column(String(255), unique=True)
    secure_url: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger)
    image_kind: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
