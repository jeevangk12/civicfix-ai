"""Add recipient notifications and citizen feedback."""

import sqlalchemy as sa
from alembic import op

revision = "0005_engagement"
down_revision = "0004_authority"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("recipient_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(60), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("body", sa.String(500), nullable=False),
        sa.Column("resource_type", sa.String(60)),
        sa.Column("resource_id", sa.Uuid()),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_notifications_recipient_read_created", "notifications",
        ["recipient_id", "read_at", sa.text("created_at DESC")],
    )
    op.create_table(
        "feedback",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("complaint_id", sa.Uuid(), sa.ForeignKey("complaints.id"), nullable=False),
        sa.Column("citizen_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("comment", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("complaint_id", "citizen_id", name="uq_feedback_complaint_citizen"),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_feedback_rating"),
    )


def downgrade() -> None:
    op.drop_table("feedback")
    op.drop_index("ix_notifications_recipient_read_created", table_name="notifications")
    op.drop_table("notifications")
