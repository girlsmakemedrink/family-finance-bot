"""Add expense_notifications_enabled field to users table

Revision ID: a1b2c3d4e5f6
Revises: 817723caa981
Create Date: 2024-12-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '817723caa981'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add expense_notifications_enabled column to users table."""
    op.add_column(
        'users',
        sa.Column(
            'expense_notifications_enabled',
            sa.Boolean(),
            nullable=False,
            server_default=sa.sql.expression.true()
        )
    )


def downgrade() -> None:
    """Remove expense_notifications_enabled column from users table."""
    op.drop_column('users', 'expense_notifications_enabled')

