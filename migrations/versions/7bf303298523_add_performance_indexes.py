"""add_performance_indexes

Revision ID: 7bf303298523
Revises: 8241f34114f8
Create Date: 2025-11-15 19:47:41.384919

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7bf303298523'
down_revision: Union[str, Sequence[str], None] = '8241f34114f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add performance indexes for faster queries."""
    # Quiz table indexes
    op.create_index('idx_quiz_user_created', 'quiz', ['user_id', sa.text('created_at DESC')])
    op.create_index('idx_quiz_organization', 'quiz', ['organization_id'])
    op.create_index('idx_quiz_standard', 'quiz', ['standard_id'])

    # Quiz submission indexes
    op.create_index('idx_submission_student', 'quiz_submission', ['student_id'])
    op.create_index('idx_submission_quiz', 'quiz_submission', ['quiz_id'])

    # Quiz question indexes
    op.create_index('idx_question_submission', 'quiz_question', ['quiz_submission_id'])

    # Organization member indexes
    op.create_index('idx_org_member_org', 'organization_member', ['organization_id'])
    op.create_index('idx_org_member_user', 'organization_member', ['user_id'])

    # API usage log indexes (timestamp already indexed in table creation, add organization composite)
    op.create_index('idx_api_usage_org_time', 'api_usage_log', ['organization_id', sa.text('timestamp DESC')])

    # Student organization index
    op.create_index('idx_student_organization', 'student', ['organization_id'])


def downgrade() -> None:
    """Downgrade schema - Remove performance indexes."""
    # Remove student organization index
    op.drop_index('idx_student_organization', table_name='student')

    # Remove API usage log indexes
    op.drop_index('idx_api_usage_org_time', table_name='api_usage_log')

    # Remove organization member indexes
    op.drop_index('idx_org_member_user', table_name='organization_member')
    op.drop_index('idx_org_member_org', table_name='organization_member')

    # Remove quiz question indexes
    op.drop_index('idx_question_submission', table_name='quiz_question')

    # Remove quiz submission indexes
    op.drop_index('idx_submission_quiz', table_name='quiz_submission')
    op.drop_index('idx_submission_student', table_name='quiz_submission')

    # Remove quiz table indexes
    op.drop_index('idx_quiz_standard', table_name='quiz')
    op.drop_index('idx_quiz_organization', table_name='quiz')
    op.drop_index('idx_quiz_user_created', table_name='quiz')
