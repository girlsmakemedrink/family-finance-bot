"""Remove custom category icons - set all to default icon.

Revision ID: c1d2e3f4g5h6
Revises: a1b2c3d4e5f6
Create Date: 2026-01-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4g5h6'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Remove all category icons - set to empty string."""
    # Update all categories to have no icon
    op.execute(
        sa.text("UPDATE categories SET icon = ''")
    )


def downgrade() -> None:
    """No downgrade possible - icons were user-defined and cannot be restored."""
    # Cannot restore original icons as they were user-defined
    pass

