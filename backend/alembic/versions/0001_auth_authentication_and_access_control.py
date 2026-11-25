"""authentication and access control

Revision ID: 0001_auth
Revises: None
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_auth'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'organizations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=180), nullable=False),
        sa.Column('organization_type', sa.String(length=80), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_organizations')),
    )
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('full_name', sa.String(length=120), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('role', sa.Enum('CITIZEN', 'STAFF', 'ADMIN', name='user_role'), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
        sa.UniqueConstraint('email', name=op.f('uq_users_email')),
    )
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=True),
        sa.Column('organization_id', sa.Uuid(), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('entity_type', sa.String(length=80), nullable=False),
        sa.Column('entity_id', sa.Uuid(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_hash', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_audit_logs_actor_id_users')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_audit_logs_organization_id_organizations')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_logs')),
    )
    op.create_table(
        'departments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('code', sa.String(length=60), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_departments_organization_id_organizations')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_departments')),
        sa.UniqueConstraint('id', 'organization_id', name='uq_departments_id_organization'),
        sa.UniqueConstraint('organization_id', 'code', name='uq_departments_organization_code'),
    )
    op.create_table(
        'refresh_sessions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('family_id', sa.Uuid(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('replaced_by_session_id', sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(['replaced_by_session_id'], ['refresh_sessions.id'], name=op.f('fk_refresh_sessions_replaced_by_session_id_refresh_sessions')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_refresh_sessions_user_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_refresh_sessions')),
        sa.UniqueConstraint('token_hash', name=op.f('uq_refresh_sessions_token_hash')),
    )
    op.create_index('ix_refresh_sessions_user_family', 'refresh_sessions', ['user_id', 'family_id'], unique=False)
    op.create_table(
        'service_areas',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('boundary_geojson', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_service_areas_organization_id_organizations')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_service_areas')),
        sa.UniqueConstraint('id', 'organization_id', name='uq_service_areas_id_organization'),
    )
    op.create_table(
        'staff_profiles',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('staff_title', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_staff_profiles_organization_id_organizations')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_staff_profiles_user_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_staff_profiles')),
        sa.UniqueConstraint('id', 'organization_id', name='uq_staff_profiles_id_organization'),
        sa.UniqueConstraint('user_id', name=op.f('uq_staff_profiles_user_id')),
    )
    op.create_table(
        'staff_department_memberships',
        sa.Column('staff_profile_id', sa.Uuid(), nullable=False),
        sa.Column('department_id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['department_id', 'organization_id'], ['departments.id', 'departments.organization_id'], name=op.f('fk_staff_department_memberships_department_id_departments')),
        sa.ForeignKeyConstraint(['staff_profile_id', 'organization_id'], ['staff_profiles.id', 'staff_profiles.organization_id'], name=op.f('fk_staff_department_memberships_staff_profile_id_staff_profiles')),
        sa.PrimaryKeyConstraint('staff_profile_id', 'department_id', name=op.f('pk_staff_department_memberships')),
    )
    op.create_table(
        'staff_service_area_memberships',
        sa.Column('staff_profile_id', sa.Uuid(), nullable=False),
        sa.Column('service_area_id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['service_area_id', 'organization_id'], ['service_areas.id', 'service_areas.organization_id'], name=op.f('fk_staff_service_area_memberships_service_area_id_service_areas')),
        sa.ForeignKeyConstraint(['staff_profile_id', 'organization_id'], ['staff_profiles.id', 'staff_profiles.organization_id'], name=op.f('fk_staff_service_area_memberships_staff_profile_id_staff_profiles')),
        sa.PrimaryKeyConstraint('staff_profile_id', 'service_area_id', name=op.f('pk_staff_service_area_memberships')),
    )


def downgrade() -> None:
    op.drop_table('staff_service_area_memberships')
    op.drop_table('staff_department_memberships')
    op.drop_table('staff_profiles')
    op.drop_table('service_areas')
    op.drop_index('ix_refresh_sessions_user_family', table_name='refresh_sessions')
    op.drop_table('refresh_sessions')
    op.drop_table('departments')
    op.drop_table('audit_logs')
    op.drop_table('users')
    sa.Enum(name='user_role').drop(op.get_bind())
    op.drop_table('organizations')
