"""Remove large_expense_threshold field

Revision ID: f1a2b3c4d5e6
Revises: c1d2e3f4g5h6
Create Date: 2026-01-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e2f1c3d4b5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove large_expense_threshold column from users table."""
    op.drop_column('users', 'large_expense_threshold')


def downgrade() -> None:
    """Add large_expense_threshold column back to users table."""
    op.add_column(
        'users',
        sa.Column(
            'large_expense_threshold',
            sa.Numeric(precision=12, scale=2),
            nullable=True
        )
    )

