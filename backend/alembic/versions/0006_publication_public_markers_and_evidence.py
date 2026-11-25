"""Add separate approved map coordinates and private complaint evidence."""

import sqlalchemy as sa
from alembic import op

revision = "0006_publication"
down_revision = "0005_engagement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("complaints", sa.Column("public_latitude", sa.Numeric(9, 6)))
    op.add_column("complaints", sa.Column("public_longitude", sa.Numeric(9, 6)))
    op.create_table(
        "complaint_images",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("complaint_id", sa.Uuid(), sa.ForeignKey("complaints.id"), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("cloudinary_public_id", sa.String(255), unique=True, nullable=False),
        sa.Column("secure_url", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("image_kind", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_complaint_images_complaint_id", "complaint_images", ["complaint_id"])


def downgrade() -> None:
    op.drop_table("complaint_images")
    op.drop_column("complaints", "public_longitude")
    op.drop_column("complaints", "public_latitude")
