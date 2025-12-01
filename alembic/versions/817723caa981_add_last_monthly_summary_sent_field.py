"""add_last_monthly_summary_sent_field

Revision ID: 817723caa981
Revises: b55b48c34d4a
Create Date: 2025-12-01 12:24:32.898918

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '817723caa981'
down_revision: Union[str, None] = 'b55b48c34d4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add last_monthly_summary_sent column to users table
    op.add_column('users', sa.Column('last_monthly_summary_sent', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Remove last_monthly_summary_sent column from users table
    op.drop_column('users', 'last_monthly_summary_sent')

