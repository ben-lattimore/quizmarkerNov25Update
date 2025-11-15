"""add_organization_id_to_existing_tables

Revision ID: af9207cf2cda
Revises: 9d8ff683a34b
Create Date: 2025-11-15 19:44:55.168121

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'af9207cf2cda'
down_revision: Union[str, Sequence[str], None] = '9d8ff683a34b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add organization_id columns to existing tables."""
    # Add default_organization_id to user table
    op.add_column('user', sa.Column('default_organization_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_user_default_organization', 'user', 'organization', ['default_organization_id'], ['id'])

    # Add organization_id to quiz table
    op.add_column('quiz', sa.Column('organization_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_quiz_organization', 'quiz', 'organization', ['organization_id'], ['id'])

    # Add organization_id to student table
    op.add_column('student', sa.Column('organization_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_student_organization', 'student', 'organization', ['organization_id'], ['id'])

    # Add uploaded_files to quiz_submission table
    op.add_column('quiz_submission', sa.Column('uploaded_files', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema - Remove organization_id columns from existing tables."""
    # Remove uploaded_files from quiz_submission table
    op.drop_column('quiz_submission', 'uploaded_files')

    # Remove organization_id from student table
    op.drop_constraint('fk_student_organization', 'student', type_='foreignkey')
    op.drop_column('student', 'organization_id')

    # Remove organization_id from quiz table
    op.drop_constraint('fk_quiz_organization', 'quiz', type_='foreignkey')
    op.drop_column('quiz', 'organization_id')

    # Remove default_organization_id from user table
    op.drop_constraint('fk_user_default_organization', 'user', type_='foreignkey')
    op.drop_column('user', 'default_organization_id')
