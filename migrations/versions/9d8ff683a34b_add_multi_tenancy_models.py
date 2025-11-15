"""add_multi_tenancy_models

Revision ID: 9d8ff683a34b
Revises: 859374994632
Create Date: 2025-11-15 19:41:58.895088

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d8ff683a34b'
down_revision: Union[str, Sequence[str], None] = '859374994632'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add multi-tenancy tables."""
    # Create Organization table
    op.create_table(
        'organization',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('plan', sa.String(length=50), nullable=True),
        sa.Column('max_quizzes_per_month', sa.Integer(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create OrganizationMember table
    op.create_table(
        'organization_member',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=True),
        sa.Column('joined_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'user_id', name='unique_org_member')
    )

    # Create APIUsageLog table
    op.create_table(
        'api_usage_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('endpoint', sa.String(length=200), nullable=False),
        sa.Column('method', sa.String(length=10), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('openai_tokens_used', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Add index on timestamp for faster queries
    op.create_index('ix_api_usage_log_timestamp', 'api_usage_log', ['timestamp'])


def downgrade() -> None:
    """Downgrade schema - Remove multi-tenancy tables."""
    # Drop index first
    op.drop_index('ix_api_usage_log_timestamp', table_name='api_usage_log')

    # Drop tables in reverse order (to handle foreign keys)
    op.drop_table('api_usage_log')
    op.drop_table('organization_member')
    op.drop_table('organization')
