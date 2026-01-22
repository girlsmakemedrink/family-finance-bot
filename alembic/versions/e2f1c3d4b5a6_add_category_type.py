"""Add category_type to categories.

Revision ID: e2f1c3d4b5a6
Revises: d9e8f7a6b5c4
Create Date: 2026-01-19 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2f1c3d4b5a6'
down_revision: Union[str, None] = 'd9e8f7a6b5c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add category_type column and update unique constraint."""
    category_type_enum = sa.Enum('expense', 'income', name='category_type_enum')
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_unique = {
        constraint.get('name')
        for constraint in inspector.get_unique_constraints('categories')
        if constraint.get('name')
    }
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'category_type',
                category_type_enum,
                server_default='expense',
                nullable=False
            )
        )
        if 'uq_family_category_name' in existing_unique:
            batch_op.drop_constraint('uq_family_category_name', type_='unique')
        batch_op.create_unique_constraint(
            'uq_family_category_name_type',
            ['family_id', 'name', 'category_type']
        )


def downgrade() -> None:
    """Remove category_type column and restore unique constraint."""
    category_type_enum = sa.Enum('expense', 'income', name='category_type_enum')
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.drop_constraint('uq_family_category_name_type', type_='unique')
        batch_op.create_unique_constraint(
            'uq_family_category_name',
            ['family_id', 'name']
        )
        batch_op.drop_column('category_type')
    category_type_enum.drop(op.get_bind(), checkfirst=True)

