"""Add staff-confirmed priority to complaints."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_authority"
down_revision = "0003_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("complaints", sa.Column("category_confirmed", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("complaints", sa.Column(
        "confirmed_priority", postgresql.ENUM(name="complaint_priority", create_type=False), nullable=True,
    ))
    op.add_column("complaints", sa.Column("priority_override_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("complaints", "priority_override_reason")
    op.drop_column("complaints", "confirmed_priority")
    op.drop_column("complaints", "category_confirmed")
