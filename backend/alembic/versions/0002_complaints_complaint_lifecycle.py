"""complaint lifecycle

Revision ID: 0002_complaints
Revises: 0001_auth
"""
from uuid import NAMESPACE_URL, uuid5

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0002_complaints'
down_revision = '0001_auth'
branch_labels = None
depends_on = None


complaint_status = postgresql.ENUM(
    "SUBMITTED", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED", "REJECTED",
    name="complaint_status", create_type=False,
)

CATEGORY_NAMES = (
    ("ROAD_DAMAGE", "Road damage / pothole"),
    ("GARBAGE", "Garbage accumulation / waste collection"),
    ("STREETLIGHT", "Streetlight failure"),
    ("WATER_LEAKAGE", "Water leakage / water supply"),
    ("DRAINAGE", "Drainage / sewage / blocked drain"),
    ("FOOTPATH", "Footpath / pedestrian infrastructure"),
    ("PUBLIC_PROPERTY", "Public property damage"),
    ("TRAFFIC_SIGNAL", "Traffic signal / road signage"),
    ("TREE_OBSTRUCTION", "Tree obstruction / fallen tree"),
    ("OTHER", "Other / needs review"),
)


def upgrade() -> None:
    complaint_status.create(op.get_bind(), checkfirst=False)
    op.create_table(
        'categories',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('code', sa.String(length=60), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('default_department_id', sa.Uuid(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.ForeignKeyConstraint(['default_department_id'], ['departments.id'], name=op.f('fk_categories_default_department_id_departments')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_categories')),
        sa.UniqueConstraint('code', name=op.f('uq_categories_code')),
    )

    categories = sa.table(
        "categories",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("sort_order", sa.Integer()),
    )
    op.bulk_insert(
        categories,
        [
            {"id": uuid5(NAMESPACE_URL, f"civicfix-ai:category:{code}"), "code": code, "name": name, "sort_order": order}
            for order, (code, name) in enumerate(CATEGORY_NAMES)
        ],
    )
    op.create_table(
        'complaints',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('public_reference', sa.String(length=30), nullable=False),
        sa.Column('citizen_id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=True),
        sa.Column('service_area_id', sa.Uuid(), nullable=True),
        sa.Column('category_id', sa.Uuid(), nullable=True),
        sa.Column('title', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('latitude', sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column('longitude', sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column('location_label', sa.String(length=255), nullable=True),
        sa.Column('status', complaint_status, server_default='SUBMITTED', nullable=False),
        sa.Column('assigned_department_id', sa.Uuid(), nullable=True),
        sa.Column('assigned_staff_id', sa.Uuid(), nullable=True),
        sa.Column('visibility', sa.Enum('PRIVATE', 'APPROXIMATE', 'PUBLIC', name='complaint_visibility'), server_default='PRIVATE', nullable=False),
        sa.Column('approved_public_summary', sa.String(length=120), nullable=True),
        sa.Column('resolution_description', sa.Text(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('idempotency_key', sa.String(length=128), nullable=True),
        sa.Column('submission_digest', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('(idempotency_key IS NULL) = (submission_digest IS NULL)', name='ck_complaints_idempotency'),
        sa.CheckConstraint('(organization_id IS NULL) = (service_area_id IS NULL)', name='ck_complaints_routing'),
        sa.CheckConstraint('assigned_department_id IS NULL OR organization_id IS NOT NULL', name='ck_complaints_department_routing'),
        sa.CheckConstraint('assigned_staff_id IS NULL OR assigned_department_id IS NOT NULL', name='ck_complaints_staff_department'),
        sa.CheckConstraint('latitude BETWEEN -90 AND 90', name='ck_complaints_latitude'),
        sa.CheckConstraint('longitude BETWEEN -180 AND 180', name='ck_complaints_longitude'),
        sa.ForeignKeyConstraint(['assigned_department_id', 'organization_id'], ['departments.id', 'departments.organization_id'], name=op.f('fk_complaints_assigned_department_id_departments')),
        sa.ForeignKeyConstraint(['assigned_staff_id'], ['users.id'], name=op.f('fk_complaints_assigned_staff_id_users')),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], name=op.f('fk_complaints_category_id_categories')),
        sa.ForeignKeyConstraint(['citizen_id'], ['users.id'], name=op.f('fk_complaints_citizen_id_users')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_complaints_organization_id_organizations')),
        sa.ForeignKeyConstraint(['service_area_id', 'organization_id'], ['service_areas.id', 'service_areas.organization_id'], name=op.f('fk_complaints_service_area_id_service_areas')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_complaints')),
        sa.UniqueConstraint('citizen_id', 'idempotency_key', name='uq_complaints_citizen_idempotency'),
        sa.UniqueConstraint('public_reference', name=op.f('uq_complaints_public_reference')),
    )
    op.create_index('ix_complaints_citizen_created', 'complaints', ['citizen_id', sa.literal_column('created_at DESC')], unique=False)
    op.create_index('ix_complaints_scope_status', 'complaints', ['organization_id', 'service_area_id', 'status'], unique=False)
    op.create_table(
        'complaint_assignments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('complaint_id', sa.Uuid(), nullable=False),
        sa.Column('department_id', sa.Uuid(), nullable=False),
        sa.Column('assigned_staff_id', sa.Uuid(), nullable=True),
        sa.Column('assigned_by', sa.Uuid(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('unassigned_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], name=op.f('fk_complaint_assignments_assigned_by_users')),
        sa.ForeignKeyConstraint(['assigned_staff_id'], ['users.id'], name=op.f('fk_complaint_assignments_assigned_staff_id_users')),
        sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id'], name=op.f('fk_complaint_assignments_complaint_id_complaints')),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], name=op.f('fk_complaint_assignments_department_id_departments')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_complaint_assignments')),
    )
    op.create_index('uq_complaint_assignments_open', 'complaint_assignments', ['complaint_id'], unique=True, postgresql_where=sa.text('unassigned_at IS NULL'))
    op.create_table(
        'complaint_updates',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('complaint_id', sa.Uuid(), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=False),
        sa.Column('old_status', complaint_status, nullable=True),
        sa.Column('new_status', complaint_status, nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('visibility', sa.Enum('PUBLIC', 'INTERNAL', name='complaint_update_visibility'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_complaint_updates_actor_id_users')),
        sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id'], name=op.f('fk_complaint_updates_complaint_id_complaints')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_complaint_updates')),
    )
    op.create_index('ix_complaint_updates_complaint_created', 'complaint_updates', ['complaint_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_complaint_updates_complaint_created', table_name='complaint_updates')
    op.drop_table('complaint_updates')
    op.drop_index('uq_complaint_assignments_open', table_name='complaint_assignments', postgresql_where=sa.text('unassigned_at IS NULL'))
    op.drop_table('complaint_assignments')
    op.drop_index('ix_complaints_scope_status', table_name='complaints')
    op.drop_index('ix_complaints_citizen_created', table_name='complaints')
    op.drop_table('complaints')
    op.drop_table('categories')
    postgresql.ENUM(name="complaint_update_visibility").drop(op.get_bind(), checkfirst=False)
    postgresql.ENUM(name="complaint_visibility").drop(op.get_bind(), checkfirst=False)
    complaint_status.drop(op.get_bind(), checkfirst=False)
