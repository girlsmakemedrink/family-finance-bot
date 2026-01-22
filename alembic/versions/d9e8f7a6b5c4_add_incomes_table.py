"""Add incomes table.

Revision ID: d9e8f7a6b5c4
Revises: c1d2e3f4g5h6
Create Date: 2026-01-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9e8f7a6b5c4'
down_revision: Union[str, None] = 'c1d2e3f4g5h6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'incomes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_incomes_user_family', 'incomes', ['user_id', 'family_id'], unique=False)
    op.create_index('ix_incomes_family_date', 'incomes', ['family_id', 'date'], unique=False)
    op.create_index('ix_incomes_category', 'incomes', ['category_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_incomes_category', table_name='incomes')
    op.drop_index('ix_incomes_family_date', table_name='incomes')
    op.drop_index('ix_incomes_user_family', table_name='incomes')
    op.drop_table('incomes')

