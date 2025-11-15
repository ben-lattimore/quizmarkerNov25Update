"""make_organization_id_required

Revision ID: 8241f34114f8
Revises: af9207cf2cda
Create Date: 2025-11-15 19:46:46.881288

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8241f34114f8'
down_revision: Union[str, Sequence[str], None] = 'af9207cf2cda'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Make organization_id NOT NULL for quiz and student tables."""
    # Make organization_id NOT NULL for quiz table
    # Note: Data migration must be run before this to ensure all quizzes have organization_id
    op.alter_column('quiz', 'organization_id',
                    existing_type=sa.Integer(),
                    nullable=False)

    # Make organization_id NOT NULL for student table
    # Note: Data migration must be run before this to ensure all students have organization_id
    op.alter_column('student', 'organization_id',
                    existing_type=sa.Integer(),
                    nullable=False)

    # Note: We keep user.default_organization_id as nullable since it's just a default preference


def downgrade() -> None:
    """Downgrade schema - Make organization_id nullable again."""
    # Make organization_id nullable for student table
    op.alter_column('student', 'organization_id',
                    existing_type=sa.Integer(),
                    nullable=True)

    # Make organization_id nullable for quiz table
    op.alter_column('quiz', 'organization_id',
                    existing_type=sa.Integer(),
                    nullable=True)
