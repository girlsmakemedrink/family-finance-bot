"""add_advanced_features

Revision ID: b55b48c34d4a
Revises: 575af1005a43
Create Date: 2025-11-16 00:15:51.719488

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b55b48c34d4a'
down_revision: Union[str, None] = '575af1005a43'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add receipt_photo_id to expenses table
    op.add_column('expenses', sa.Column('receipt_photo_id', sa.String(length=255), nullable=True))
    
    # Add large_expense_threshold to users table
    op.add_column('users', sa.Column('large_expense_threshold', sa.Numeric(precision=12, scale=2), nullable=True))
    
    # Create expense_templates table
    op.create_table(
        'expense_templates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['family_id'], ['families.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_expense_templates_user_family', 'expense_templates', ['user_id', 'family_id'], unique=False)


def downgrade() -> None:
    # Drop expense_templates table
    op.drop_index('ix_expense_templates_user_family', table_name='expense_templates')
    op.drop_table('expense_templates')
    
    # Drop columns from users and expenses
    op.drop_column('users', 'large_expense_threshold')
    op.drop_column('expenses', 'receipt_photo_id')

