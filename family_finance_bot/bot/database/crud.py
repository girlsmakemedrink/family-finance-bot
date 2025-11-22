"""CRUD operations for database models.

This module contains functions for Create, Read, Update, Delete operations
on database models.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import Category, Expense, ExpenseTemplate, Family, FamilyMember, User

logger = logging.getLogger(__name__)


# ============================================================================
# User CRUD operations
# ============================================================================

async def get_user_by_telegram_id(
    session: AsyncSession,
    telegram_id: int
) -> Optional[User]:
    """Get user by Telegram ID.
    
    Args:
        session: Database session
        telegram_id: Telegram user ID
        
    Returns:
        User object or None if not found
    """
    try:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            logger.info(f"Found user: {user.name} (telegram_id={telegram_id})")
        else:
            logger.info(f"User not found (telegram_id={telegram_id})")
            
        return user
    except Exception as e:
        logger.error(f"Error getting user by telegram_id {telegram_id}: {e}")
        raise


async def create_user(
    session: AsyncSession,
    telegram_id: int,
    name: str,
    username: Optional[str] = None
) -> User:
    """Create a new user.
    
    Args:
        session: Database session
        telegram_id: Telegram user ID
        name: User's name (first_name + last_name)
        username: Telegram username (optional)
        
    Returns:
        Created User object
    """
    try:
        user = User(
            telegram_id=telegram_id,
            name=name,
            username=username
        )
        session.add(user)
        await session.flush()
        
        logger.info(
            f"Created new user: {user.name} "
            f"(id={user.id}, telegram_id={telegram_id})"
        )
        
        return user
    except Exception as e:
        logger.error(f"Error creating user (telegram_id={telegram_id}): {e}")
        raise


async def get_user_by_id(
    session: AsyncSession,
    user_id: int
) -> Optional[User]:
    """Get user by internal ID.
    
    Args:
        session: Database session
        user_id: Internal user ID
        
    Returns:
        User object or None if not found
    """
    try:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Error getting user by id {user_id}: {e}")
        raise


async def update_user_settings(
    session: AsyncSession,
    user_id: int,
    **settings
) -> Optional[User]:
    """Update user settings.
    
    Args:
        session: Database session
        user_id: User ID
        **settings: Settings to update (currency, timezone, date_format, 
                   daily_summary_enabled, daily_summary_time)
        
    Returns:
        Updated User object or None if not found
    """
    try:
        user = await get_user_by_id(session, user_id)
        
        if not user:
            logger.warning(f"User {user_id} not found for settings update")
            return None
        
        # Update allowed settings
        allowed_fields = {
            'currency', 'timezone', 'date_format',
            'monthly_summary_enabled', 'monthly_summary_time'
        }
        
        for key, value in settings.items():
            if key in allowed_fields:
                setattr(user, key, value)
        
        await session.flush()
        
        logger.info(f"Updated settings for user {user_id}: {settings}")
        
        return user
    except Exception as e:
        logger.error(f"Error updating settings for user {user_id}: {e}")
        raise


# ============================================================================
# Family CRUD operations
# ============================================================================

async def get_user_families(
    session: AsyncSession,
    user_id: int
) -> List[Family]:
    """Get all families that user belongs to.
    
    Args:
        session: Database session
        user_id: Internal user ID
        
    Returns:
        List of Family objects
    """
    try:
        result = await session.execute(
            select(Family)
            .join(FamilyMember)
            .where(FamilyMember.user_id == user_id)
            .order_by(Family.created_at.desc())
        )
        families = result.scalars().all()
        
        logger.info(f"Found {len(families)} families for user_id={user_id}")
        
        return list(families)
    except Exception as e:
        logger.error(f"Error getting families for user_id {user_id}: {e}")
        raise


async def create_family(
    session: AsyncSession,
    name: str
) -> Family:
    """Create a new family.
    
    Args:
        session: Database session
        name: Family name
        
    Returns:
        Created Family object
    """
    try:
        family = Family(name=name)
        session.add(family)
        await session.flush()
        
        logger.info(
            f"Created new family: {family.name} "
            f"(id={family.id}, invite_code={family.invite_code})"
        )
        
        return family
    except Exception as e:
        logger.error(f"Error creating family '{name}': {e}")
        raise


async def get_family_by_invite_code(
    session: AsyncSession,
    invite_code: str
) -> Optional[Family]:
    """Get family by invite code.
    
    Args:
        session: Database session
        invite_code: Family invite code
        
    Returns:
        Family object or None if not found
    """
    try:
        result = await session.execute(
            select(Family).where(Family.invite_code == invite_code)
        )
        family = result.scalar_one_or_none()
        
        if family:
            logger.info(f"Found family by invite code: {family.name}")
        else:
            logger.info(f"Family not found (invite_code={invite_code})")
            
        return family
    except Exception as e:
        logger.error(f"Error getting family by invite_code {invite_code}: {e}")
        raise


async def get_family_by_id(
    session: AsyncSession,
    family_id: int
) -> Optional[Family]:
    """Get family by ID.
    
    Args:
        session: Database session
        family_id: Family ID
        
    Returns:
        Family object or None if not found
    """
    try:
        result = await session.execute(
            select(Family).where(Family.id == family_id)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Error getting family by id {family_id}: {e}")
        raise


async def update_family_settings(
    session: AsyncSession,
    family_id: int,
    **settings
) -> Optional[Family]:
    """Update family settings.
    
    Args:
        session: Database session
        family_id: Family ID
        **settings: Settings to update (name, etc.)
        
    Returns:
        Updated Family object or None if not found
    """
    try:
        family = await get_family_by_id(session, family_id)
        
        if not family:
            logger.warning(f"Family {family_id} not found for settings update")
            return None
        
        # Update allowed settings
        allowed_fields = {'name'}
        
        for key, value in settings.items():
            if key in allowed_fields:
                setattr(family, key, value)
        
        await session.flush()
        
        logger.info(f"Updated settings for family {family_id}: {settings}")
        
        return family
    except Exception as e:
        logger.error(f"Error updating settings for family {family_id}: {e}")
        raise


async def regenerate_invite_code(
    session: AsyncSession,
    family_id: int
) -> Optional[str]:
    """Regenerate invite code for a family.
    
    Args:
        session: Database session
        family_id: Family ID
        
    Returns:
        New invite code or None if family not found
    """
    try:
        from .models import generate_invite_code
        
        family = await get_family_by_id(session, family_id)
        
        if not family:
            logger.warning(f"Family {family_id} not found for invite code regeneration")
            return None
        
        # Generate new unique invite code
        new_code = generate_invite_code()
        
        # Make sure it's unique
        while await get_family_by_invite_code(session, new_code):
            new_code = generate_invite_code()
        
        family.invite_code = new_code
        await session.flush()
        
        logger.info(f"Regenerated invite code for family {family_id}: {new_code}")
        
        return new_code
    except Exception as e:
        logger.error(f"Error regenerating invite code for family {family_id}: {e}")
        raise


# ============================================================================
# FamilyMember CRUD operations
# ============================================================================

async def add_family_member(
    session: AsyncSession,
    user_id: int,
    family_id: int,
    role: str = "member"
) -> FamilyMember:
    """Add user to family.
    
    Args:
        session: Database session
        user_id: User ID
        family_id: Family ID
        role: Member role ("admin" or "member")
        
    Returns:
        Created FamilyMember object
    """
    try:
        from .models import RoleEnum
        
        role_enum = RoleEnum.ADMIN if role == "admin" else RoleEnum.MEMBER
        
        member = FamilyMember(
            user_id=user_id,
            family_id=family_id,
            role=role_enum
        )
        session.add(member)
        await session.flush()
        
        logger.info(
            f"Added user {user_id} to family {family_id} as {role_enum.value}"
        )
        
        return member
    except Exception as e:
        logger.error(
            f"Error adding user {user_id} to family {family_id}: {e}"
        )
        raise


async def get_family_member(
    session: AsyncSession,
    user_id: int,
    family_id: int
) -> Optional[FamilyMember]:
    """Get family member record.
    
    Args:
        session: Database session
        user_id: User ID
        family_id: Family ID
        
    Returns:
        FamilyMember object or None if not found
    """
    try:
        result = await session.execute(
            select(FamilyMember)
            .where(FamilyMember.user_id == user_id)
            .where(FamilyMember.family_id == family_id)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(
            f"Error getting family member "
            f"(user_id={user_id}, family_id={family_id}): {e}"
        )
        raise


async def is_user_in_family(
    session: AsyncSession,
    user_id: int,
    family_id: int
) -> bool:
    """Check if user is member of family.
    
    Args:
        session: Database session
        user_id: User ID
        family_id: Family ID
        
    Returns:
        True if user is in family, False otherwise
    """
    member = await get_family_member(session, user_id, family_id)
    return member is not None


async def get_family_members(
    session: AsyncSession,
    family_id: int
) -> List[tuple[User, FamilyMember]]:
    """Get all members of a family with their user data.
    
    Args:
        session: Database session
        family_id: Family ID
        
    Returns:
        List of tuples (User, FamilyMember) for each member
    """
    try:
        result = await session.execute(
            select(User, FamilyMember)
            .join(FamilyMember, User.id == FamilyMember.user_id)
            .where(FamilyMember.family_id == family_id)
            .order_by(FamilyMember.role.desc(), User.name)
        )
        members = result.all()
        
        logger.info(f"Found {len(members)} members for family_id={family_id}")
        
        return list(members)
    except Exception as e:
        logger.error(f"Error getting family members for family_id {family_id}: {e}")
        raise


async def remove_family_member(
    session: AsyncSession,
    user_id: int,
    family_id: int
) -> bool:
    """Remove user from family.
    
    Args:
        session: Database session
        user_id: User ID
        family_id: Family ID
        
    Returns:
        True if removed, False if member not found
    """
    try:
        member = await get_family_member(session, user_id, family_id)
        
        if not member:
            logger.warning(
                f"Family member not found (user_id={user_id}, family_id={family_id})"
            )
            return False
        
        await session.delete(member)
        await session.flush()
        
        logger.info(f"Removed user {user_id} from family {family_id}")
        
        return True
    except Exception as e:
        logger.error(
            f"Error removing user {user_id} from family {family_id}: {e}"
        )
        raise


async def is_family_admin(
    session: AsyncSession,
    user_id: int,
    family_id: int
) -> bool:
    """Check if user is admin of a family.
    
    Args:
        session: Database session
        user_id: User ID
        family_id: Family ID
        
    Returns:
        True if user is admin, False otherwise
    """
    try:
        from .models import RoleEnum
        
        member = await get_family_member(session, user_id, family_id)
        
        if not member:
            return False
        
        return member.role == RoleEnum.ADMIN
    except Exception as e:
        logger.error(
            f"Error checking admin status for user {user_id} "
            f"in family {family_id}: {e}"
        )
        raise


# ============================================================================
# Category CRUD operations
# ============================================================================

async def get_default_categories(
    session: AsyncSession
) -> List[Category]:
    """Get all default categories.
    
    Args:
        session: Database session
        
    Returns:
        List of default Category objects
    """
    try:
        result = await session.execute(
            select(Category)
            .where(Category.is_default == True)
            .order_by(Category.id)
        )
        categories = result.scalars().all()
        
        logger.info(f"Found {len(categories)} default categories")
        
        return list(categories)
    except Exception as e:
        logger.error(f"Error getting default categories: {e}")
        raise


async def get_category_by_id(
    session: AsyncSession,
    category_id: int
) -> Optional[Category]:
    """Get category by ID.
    
    Args:
        session: Database session
        category_id: Category ID
        
    Returns:
        Category object or None if not found
    """
    try:
        result = await session.execute(
            select(Category).where(Category.id == category_id)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Error getting category by id {category_id}: {e}")
        raise


async def get_all_categories(
    session: AsyncSession
) -> List[Category]:
    """Get all categories (both default and custom).
    
    Args:
        session: Database session
        
    Returns:
        List of all Category objects
    """
    try:
        result = await session.execute(
            select(Category).order_by(Category.is_default.desc(), Category.id)
        )
        categories = result.scalars().all()
        
        logger.info(f"Found {len(categories)} categories")
        
        return list(categories)
    except Exception as e:
        logger.error(f"Error getting all categories: {e}")
        raise


async def get_family_categories(
    session: AsyncSession,
    family_id: int
) -> List[Category]:
    """Get all categories available for a family (default + family-specific).
    
    Args:
        session: Database session
        family_id: Family ID
        
    Returns:
        List of Category objects (default categories + family's custom categories)
    """
    try:
        result = await session.execute(
            select(Category)
            .where(
                (Category.is_default == True) | 
                (Category.family_id == family_id)
            )
            .order_by(Category.is_default.desc(), Category.name)
        )
        categories = result.scalars().all()
        
        logger.info(
            f"Found {len(categories)} categories for family_id={family_id}"
        )
        
        return list(categories)
    except Exception as e:
        logger.error(f"Error getting categories for family_id {family_id}: {e}")
        raise


async def get_family_custom_categories(
    session: AsyncSession,
    family_id: int
) -> List[Category]:
    """Get only custom categories created by a family.
    
    Args:
        session: Database session
        family_id: Family ID
        
    Returns:
        List of custom Category objects for the family
    """
    try:
        result = await session.execute(
            select(Category)
            .where(Category.family_id == family_id)
            .order_by(Category.name)
        )
        categories = result.scalars().all()
        
        logger.info(
            f"Found {len(categories)} custom categories for family_id={family_id}"
        )
        
        return list(categories)
    except Exception as e:
        logger.error(
            f"Error getting custom categories for family_id {family_id}: {e}"
        )
        raise


async def create_category(
    session: AsyncSession,
    name: str,
    icon: str,
    family_id: Optional[int] = None
) -> Category:
    """Create a new category.
    
    Args:
        session: Database session
        name: Category name
        icon: Category icon (emoji)
        family_id: Family ID (None for default categories)
        
    Returns:
        Created Category object
    """
    try:
        category = Category(
            name=name,
            icon=icon,
            is_default=family_id is None,
            family_id=family_id
        )
        session.add(category)
        await session.flush()
        
        logger.info(
            f"Created category: {category.name} "
            f"(id={category.id}, family_id={family_id})"
        )
        
        return category
    except Exception as e:
        logger.error(f"Error creating category '{name}': {e}")
        raise


async def update_category(
    session: AsyncSession,
    category_id: int,
    name: Optional[str] = None,
    icon: Optional[str] = None
) -> Optional[Category]:
    """Update an existing category.
    
    Args:
        session: Database session
        category_id: Category ID
        name: New category name (optional)
        icon: New category icon (optional)
        
    Returns:
        Updated Category object or None if not found
    """
    try:
        category = await get_category_by_id(session, category_id)
        
        if not category:
            logger.warning(f"Category {category_id} not found for update")
            return None
        
        if name is not None:
            category.name = name
        
        if icon is not None:
            category.icon = icon
        
        await session.flush()
        
        logger.info(
            f"Updated category {category_id}: name={name}, icon={icon}"
        )
        
        return category
    except Exception as e:
        logger.error(f"Error updating category {category_id}: {e}")
        raise


async def delete_category(
    session: AsyncSession,
    category_id: int
) -> bool:
    """Delete a category.
    
    Args:
        session: Database session
        category_id: Category ID
        
    Returns:
        True if deleted, False if not found
    """
    try:
        category = await get_category_by_id(session, category_id)
        
        if not category:
            logger.warning(f"Category {category_id} not found for deletion")
            return False
        
        await session.delete(category)
        await session.flush()
        
        logger.info(f"Deleted category {category_id}")
        
        return True
    except Exception as e:
        logger.error(f"Error deleting category {category_id}: {e}")
        raise


async def move_expenses_to_category(
    session: AsyncSession,
    old_category_id: int,
    new_category_id: int
) -> int:
    """Move all expenses from one category to another.
    
    Args:
        session: Database session
        old_category_id: Source category ID
        new_category_id: Target category ID
        
    Returns:
        Number of expenses moved
    """
    try:
        from sqlalchemy import update as sql_update
        
        # Update all expenses with old category to new category
        result = await session.execute(
            sql_update(Expense)
            .where(Expense.category_id == old_category_id)
            .values(category_id=new_category_id)
        )
        
        count = result.rowcount
        await session.flush()
        
        logger.info(
            f"Moved {count} expenses from category {old_category_id} "
            f"to category {new_category_id}"
        )
        
        return count
    except Exception as e:
        logger.error(
            f"Error moving expenses from category {old_category_id} "
            f"to {new_category_id}: {e}"
        )
        raise


async def count_category_expenses(
    session: AsyncSession,
    category_id: int
) -> int:
    """Count number of expenses in a category.
    
    Args:
        session: Database session
        category_id: Category ID
        
    Returns:
        Number of expenses in the category
    """
    try:
        from sqlalchemy import func
        
        result = await session.execute(
            select(func.count(Expense.id))
            .where(Expense.category_id == category_id)
        )
        count = result.scalar()
        
        logger.info(f"Category {category_id} has {count} expenses")
        
        return count or 0
    except Exception as e:
        logger.error(f"Error counting expenses for category {category_id}: {e}")
        raise


async def category_name_exists(
    session: AsyncSession,
    name: str,
    family_id: Optional[int] = None,
    exclude_category_id: Optional[int] = None
) -> bool:
    """Check if category name already exists for a family.
    
    Args:
        session: Database session
        name: Category name to check
        family_id: Family ID (None for default categories)
        exclude_category_id: Category ID to exclude from check (for updates)
        
    Returns:
        True if name exists, False otherwise
    """
    try:
        query = select(Category).where(
            Category.name == name,
            Category.family_id == family_id
        )
        
        if exclude_category_id is not None:
            query = query.where(Category.id != exclude_category_id)
        
        result = await session.execute(query)
        existing = result.scalar_one_or_none()
        
        return existing is not None
    except Exception as e:
        logger.error(f"Error checking category name existence: {e}")
        raise


# ============================================================================
# Expense CRUD operations
# ============================================================================

async def create_expense(
    session: AsyncSession,
    user_id: int,
    family_id: int,
    category_id: int,
    amount: float,
    description: Optional[str] = None
) -> Expense:
    """Create a new expense.
    
    Args:
        session: Database session
        user_id: User ID who created the expense
        family_id: Family ID
        category_id: Category ID
        amount: Expense amount
        description: Optional description
        
    Returns:
        Created Expense object
    """
    try:
        expense = Expense(
            user_id=user_id,
            family_id=family_id,
            category_id=category_id,
            amount=Decimal(str(amount)),
            description=description
        )
        session.add(expense)
        await session.flush()
        
        logger.info(
            f"Created expense: {expense.amount} "
            f"(user_id={user_id}, family_id={family_id})"
        )
        
        return expense
    except Exception as e:
        logger.error(f"Error creating expense: {e}")
        raise


async def get_family_expenses(
    session: AsyncSession,
    family_id: int,
    limit: Optional[int] = None
) -> List[Expense]:
    """Get expenses for a family.
    
    Args:
        session: Database session
        family_id: Family ID
        limit: Optional limit for number of expenses
        
    Returns:
        List of Expense objects
    """
    try:
        query = (
            select(Expense)
            .where(Expense.family_id == family_id)
            .order_by(Expense.date.desc())
        )
        
        if limit:
            query = query.limit(limit)
        
        result = await session.execute(query)
        expenses = result.scalars().all()
        
        logger.info(f"Found {len(expenses)} expenses for family_id={family_id}")
        
        return list(expenses)
    except Exception as e:
        logger.error(f"Error getting expenses for family_id {family_id}: {e}")
        raise


async def get_user_expenses(
    session: AsyncSession,
    user_id: int,
    family_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 10,
    offset: int = 0
) -> List[Expense]:
    """Get expenses for a user in a specific family with optional date filtering.
    
    Args:
        session: Database session
        user_id: User ID
        family_id: Family ID
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering
        limit: Maximum number of expenses to return (default: 10)
        offset: Number of expenses to skip (default: 0)
        
    Returns:
        List of Expense objects with related category and user data loaded
    """
    try:
        query = (
            select(Expense)
            .options(
                selectinload(Expense.category),
                selectinload(Expense.user)
            )
            .where(Expense.user_id == user_id)
            .where(Expense.family_id == family_id)
        )
        
        if start_date:
            query = query.where(Expense.date >= start_date)
        
        if end_date:
            query = query.where(Expense.date <= end_date)
        
        query = query.order_by(Expense.date.desc())
        
        # Apply limit and offset
        query = query.limit(limit).offset(offset)
        
        result = await session.execute(query)
        expenses = result.scalars().all()
        
        logger.info(
            f"Found {len(expenses)} expenses for user_id={user_id}, "
            f"family_id={family_id} (offset={offset}, limit={limit})"
        )
        
        return list(expenses)
    except Exception as e:
        logger.error(
            f"Error getting expenses for user_id {user_id}, "
            f"family_id {family_id}: {e}"
        )
        raise


async def get_user_expenses_summary(
    session: AsyncSession,
    user_id: int,
    family_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> dict:
    """Get summary of user expenses with total and breakdown by categories.
    
    Args:
        session: Database session
        user_id: User ID
        family_id: Family ID
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering
        
    Returns:
        Dictionary with summary data:
        {
            'total': Decimal,  # Total amount
            'count': int,  # Number of expenses
            'by_category': [  # List of category breakdowns
                {
                    'category_id': int,
                    'category_name': str,
                    'category_icon': str,
                    'amount': Decimal,
                    'count': int
                },
                ...
            ]
        }
    """
    try:
        from sqlalchemy import func
        
        # Build base query
        query = (
            select(
                Category.id,
                Category.name,
                Category.icon,
                func.sum(Expense.amount).label('total_amount'),
                func.count(Expense.id).label('expense_count')
            )
            .join(Category, Expense.category_id == Category.id)
            .where(Expense.user_id == user_id)
            .where(Expense.family_id == family_id)
        )
        
        # Apply date filters
        if start_date:
            query = query.where(Expense.date >= start_date)
        
        if end_date:
            query = query.where(Expense.date <= end_date)
        
        # Group by category
        query = query.group_by(Category.id, Category.name, Category.icon)
        query = query.order_by(func.sum(Expense.amount).desc())
        
        result = await session.execute(query)
        rows = result.all()
        
        # Calculate totals
        total_amount = Decimal('0')
        total_count = 0
        by_category = []
        
        for row in rows:
            category_total = Decimal(str(row.total_amount))
            category_count = row.expense_count
            
            total_amount += category_total
            total_count += category_count
            
            by_category.append({
                'category_id': row.id,
                'category_name': row.name,
                'category_icon': row.icon,
                'amount': category_total,
                'count': category_count
            })
        
        summary = {
            'total': total_amount,
            'count': total_count,
            'by_category': by_category
        }
        
        logger.info(
            f"Generated expenses summary for user_id={user_id}, "
            f"family_id={family_id}: total={total_amount}, count={total_count}"
        )
        
        return summary
        
    except Exception as e:
        logger.error(
            f"Error getting expenses summary for user_id {user_id}, "
            f"family_id {family_id}: {e}"
        )
        raise


async def get_user_expenses_detailed_monthly_report(
    session: AsyncSession,
    user_id: int,
    family_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> dict:
    """Get detailed expenses report for monthly summary with expenses breakdown by category.
    
    Args:
        session: Database session
        user_id: User ID
        family_id: Family ID
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering
        
    Returns:
        Dictionary with detailed report data:
        {
            'total': Decimal,  # Total amount
            'count': int,  # Number of expenses
            'by_category': [  # List of category breakdowns with detailed expenses
                {
                    'category_id': int,
                    'category_name': str,
                    'category_icon': str,
                    'amount': Decimal,
                    'percentage': float,
                    'count': int,
                    'expenses': [  # List of individual expenses in this category
                        {
                            'amount': Decimal,
                            'description': str,
                            'date': datetime
                        },
                        ...
                    ]
                },
                ...
            ]
        }
    """
    try:
        from sqlalchemy import func
        
        # First, get category totals
        category_query = (
            select(
                Category.id,
                Category.name,
                Category.icon,
                func.sum(Expense.amount).label('total_amount'),
                func.count(Expense.id).label('expense_count')
            )
            .join(Category, Expense.category_id == Category.id)
            .where(Expense.user_id == user_id)
            .where(Expense.family_id == family_id)
        )
        
        # Apply date filters
        if start_date:
            category_query = category_query.where(Expense.date >= start_date)
        
        if end_date:
            category_query = category_query.where(Expense.date <= end_date)
        
        # Group by category
        category_query = category_query.group_by(Category.id, Category.name, Category.icon)
        category_query = category_query.order_by(func.sum(Expense.amount).desc())
        
        result = await session.execute(category_query)
        category_rows = result.all()
        
        # Calculate total amount
        total_amount = Decimal('0')
        total_count = 0
        by_category = []
        
        for row in category_rows:
            category_total = Decimal(str(row.total_amount))
            category_count = row.expense_count
            
            total_amount += category_total
            total_count += category_count
        
        # Now get detailed expenses for each category
        for row in category_rows:
            category_id = row.id
            category_total = Decimal(str(row.total_amount))
            category_count = row.expense_count
            
            # Calculate percentage
            percentage = float(category_total / total_amount * 100) if total_amount > 0 else 0
            
            # Get all expenses for this category
            expenses_query = (
                select(Expense)
                .where(Expense.user_id == user_id)
                .where(Expense.family_id == family_id)
                .where(Expense.category_id == category_id)
            )
            
            if start_date:
                expenses_query = expenses_query.where(Expense.date >= start_date)
            
            if end_date:
                expenses_query = expenses_query.where(Expense.date <= end_date)
            
            expenses_query = expenses_query.order_by(Expense.date.desc())
            
            expenses_result = await session.execute(expenses_query)
            expenses = expenses_result.scalars().all()
            
            # Format expenses
            expenses_list = []
            for expense in expenses:
                expenses_list.append({
                    'amount': expense.amount,
                    'description': expense.description or "Без описания",
                    'date': expense.date
                })
            
            by_category.append({
                'category_id': category_id,
                'category_name': row.name,
                'category_icon': row.icon,
                'amount': category_total,
                'percentage': percentage,
                'count': category_count,
                'expenses': expenses_list
            })
        
        summary = {
            'total': total_amount,
            'count': total_count,
            'by_category': by_category
        }
        
        logger.info(
            f"Generated detailed monthly report for user_id={user_id}, "
            f"family_id={family_id}: total={total_amount}, count={total_count}, "
            f"categories={len(by_category)}"
        )
        
        return summary
        
    except Exception as e:
        logger.error(
            f"Error getting detailed monthly report for user_id {user_id}, "
            f"family_id {family_id}: {e}"
        )
        raise


async def get_family_expenses_detailed_report(
    session: AsyncSession,
    family_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> dict:
    """Get detailed expenses report for family with expenses breakdown by category.
    
    Args:
        session: Database session
        family_id: Family ID
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering
        
    Returns:
        Dictionary with detailed report data:
        {
            'total': Decimal,  # Total amount
            'count': int,  # Number of expenses
            'by_category': [  # List of category breakdowns with detailed expenses
                {
                    'category_id': int,
                    'category_name': str,
                    'category_icon': str,
                    'amount': Decimal,
                    'percentage': float,
                    'count': int,
                    'expenses': [  # List of individual expenses in this category
                        {
                            'amount': Decimal,
                            'description': str,
                            'date': datetime
                        },
                        ...
                    ]
                },
                ...
            ]
        }
    """
    try:
        from sqlalchemy import func
        
        # First, get category totals
        category_query = (
            select(
                Category.id,
                Category.name,
                Category.icon,
                func.sum(Expense.amount).label('total_amount'),
                func.count(Expense.id).label('expense_count')
            )
            .join(Category, Expense.category_id == Category.id)
            .where(Expense.family_id == family_id)
        )
        
        # Apply date filters
        if start_date:
            category_query = category_query.where(Expense.date >= start_date)
        
        if end_date:
            category_query = category_query.where(Expense.date <= end_date)
        
        # Group by category
        category_query = category_query.group_by(Category.id, Category.name, Category.icon)
        category_query = category_query.order_by(func.sum(Expense.amount).desc())
        
        result = await session.execute(category_query)
        category_rows = result.all()
        
        # Calculate total amount
        total_amount = Decimal('0')
        total_count = 0
        by_category = []
        
        for row in category_rows:
            category_total = Decimal(str(row.total_amount))
            category_count = row.expense_count
            
            total_amount += category_total
            total_count += category_count
        
        # Now get detailed expenses for each category
        for row in category_rows:
            category_id = row.id
            category_total = Decimal(str(row.total_amount))
            category_count = row.expense_count
            
            # Calculate percentage
            percentage = float(category_total / total_amount * 100) if total_amount > 0 else 0
            
            # Get all expenses for this category
            expenses_query = (
                select(Expense)
                .where(Expense.family_id == family_id)
                .where(Expense.category_id == category_id)
            )
            
            if start_date:
                expenses_query = expenses_query.where(Expense.date >= start_date)
            
            if end_date:
                expenses_query = expenses_query.where(Expense.date <= end_date)
            
            expenses_query = expenses_query.order_by(Expense.date.desc())
            
            expenses_result = await session.execute(expenses_query)
            expenses = expenses_result.scalars().all()
            
            # Format expenses
            expenses_list = []
            for expense in expenses:
                expenses_list.append({
                    'amount': expense.amount,
                    'description': expense.description or "Без описания",
                    'date': expense.date
                })
            
            by_category.append({
                'category_id': category_id,
                'category_name': row.name,
                'category_icon': row.icon,
                'amount': category_total,
                'percentage': percentage,
                'count': category_count,
                'expenses': expenses_list
            })
        
        summary = {
            'total': total_amount,
            'count': total_count,
            'by_category': by_category
        }
        
        logger.info(
            f"Generated detailed family report for family_id={family_id}: "
            f"total={total_amount}, count={total_count}, categories={len(by_category)}"
        )
        
        return summary
        
    except Exception as e:
        logger.error(
            f"Error getting detailed family report for family_id {family_id}: {e}"
        )
        raise


async def get_family_expenses_with_users(
    session: AsyncSession,
    family_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 10,
    offset: int = 0
) -> List[Expense]:
    """Get expenses for a family with user and category data loaded.
    
    Args:
        session: Database session
        family_id: Family ID
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering
        limit: Maximum number of expenses to return (default: 10)
        offset: Number of expenses to skip (default: 0)
        
    Returns:
        List of Expense objects with related category and user data loaded
    """
    try:
        query = (
            select(Expense)
            .options(
                selectinload(Expense.category),
                selectinload(Expense.user)
            )
            .where(Expense.family_id == family_id)
        )
        
        if start_date:
            query = query.where(Expense.date >= start_date)
        
        if end_date:
            query = query.where(Expense.date <= end_date)
        
        query = query.order_by(Expense.date.desc())
        
        # Apply limit and offset
        query = query.limit(limit).offset(offset)
        
        result = await session.execute(query)
        expenses = result.scalars().all()
        
        logger.info(
            f"Found {len(expenses)} expenses for family_id={family_id} "
            f"(offset={offset}, limit={limit})"
        )
        
        return list(expenses)
    except Exception as e:
        logger.error(
            f"Error getting expenses for family_id {family_id}: {e}"
        )
        raise


async def get_family_expenses_summary(
    session: AsyncSession,
    family_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> dict:
    """Get summary of family expenses with total and breakdown.
    
    Args:
        session: Database session
        family_id: Family ID
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering
        
    Returns:
        Dictionary with summary data:
        {
            'total': Decimal,  # Total amount
            'count': int,  # Number of expenses
            'by_category': [  # List of category breakdowns
                {
                    'category_id': int,
                    'category_name': str,
                    'category_icon': str,
                    'amount': Decimal,
                    'count': int
                },
                ...
            ],
            'by_user': [  # List of user contributions
                {
                    'user_id': int,
                    'user_name': str,
                    'amount': Decimal,
                    'count': int
                },
                ...
            ]
        }
    """
    try:
        from sqlalchemy import func
        
        # Build query for category breakdown
        category_query = (
            select(
                Category.id,
                Category.name,
                Category.icon,
                func.sum(Expense.amount).label('total_amount'),
                func.count(Expense.id).label('expense_count')
            )
            .join(Category, Expense.category_id == Category.id)
            .where(Expense.family_id == family_id)
        )
        
        # Apply date filters
        if start_date:
            category_query = category_query.where(Expense.date >= start_date)
        
        if end_date:
            category_query = category_query.where(Expense.date <= end_date)
        
        # Group by category
        category_query = category_query.group_by(Category.id, Category.name, Category.icon)
        category_query = category_query.order_by(func.sum(Expense.amount).desc())
        
        result = await session.execute(category_query)
        category_rows = result.all()
        
        # Build query for user breakdown
        user_query = (
            select(
                User.id,
                User.name,
                func.sum(Expense.amount).label('total_amount'),
                func.count(Expense.id).label('expense_count')
            )
            .join(User, Expense.user_id == User.id)
            .where(Expense.family_id == family_id)
        )
        
        # Apply date filters
        if start_date:
            user_query = user_query.where(Expense.date >= start_date)
        
        if end_date:
            user_query = user_query.where(Expense.date <= end_date)
        
        # Group by user
        user_query = user_query.group_by(User.id, User.name)
        user_query = user_query.order_by(func.sum(Expense.amount).desc())
        
        result = await session.execute(user_query)
        user_rows = result.all()
        
        # Calculate totals
        total_amount = Decimal('0')
        total_count = 0
        by_category = []
        by_user = []
        
        for row in category_rows:
            category_total = Decimal(str(row.total_amount))
            category_count = row.expense_count
            
            total_amount += category_total
            total_count += category_count
            
            by_category.append({
                'category_id': row.id,
                'category_name': row.name,
                'category_icon': row.icon,
                'amount': category_total,
                'count': category_count
            })
        
        for row in user_rows:
            user_total = Decimal(str(row.total_amount))
            user_count = row.expense_count
            
            by_user.append({
                'user_id': row.id,
                'user_name': row.name,
                'amount': user_total,
                'count': user_count
            })
        
        summary = {
            'total': total_amount,
            'count': total_count,
            'by_category': by_category,
            'by_user': by_user
        }
        
        logger.info(
            f"Generated family expenses summary for family_id={family_id}: "
            f"total={total_amount}, count={total_count}"
        )
        
        return summary
        
    except Exception as e:
        logger.error(
            f"Error getting family expenses summary for family_id {family_id}: {e}"
        )
        raise


async def get_family_expenses_by_user(
    session: AsyncSession,
    family_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> dict:
    """Get family expenses grouped by user.
    
    Args:
        session: Database session
        family_id: Family ID
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering
        
    Returns:
        Dictionary mapping user_id to user data with expenses:
        {
            user_id: {
                'name': str,
                'amount': Decimal,
                'expenses': [Expense, ...]
            },
            ...
        }
    """
    try:
        # Get all expenses for the family
        query = (
            select(Expense)
            .options(
                selectinload(Expense.category),
                selectinload(Expense.user)
            )
            .where(Expense.family_id == family_id)
        )
        
        if start_date:
            query = query.where(Expense.date >= start_date)
        
        if end_date:
            query = query.where(Expense.date <= end_date)
        
        query = query.order_by(Expense.date.desc())
        
        result = await session.execute(query)
        expenses = result.scalars().all()
        
        # Group by user
        by_user = {}
        for expense in expenses:
            user_id = expense.user_id
            if user_id not in by_user:
                by_user[user_id] = {
                    'name': expense.user.name,
                    'amount': Decimal('0'),
                    'expenses': []
                }
            
            by_user[user_id]['amount'] += expense.amount
            by_user[user_id]['expenses'].append(expense)
        
        logger.info(
            f"Grouped family expenses by user for family_id={family_id}: "
            f"{len(by_user)} users"
        )
        
        return by_user
        
    except Exception as e:
        logger.error(
            f"Error getting family expenses by user for family_id {family_id}: {e}"
        )
        raise


async def get_family_expenses_by_category(
    session: AsyncSession,
    family_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> dict:
    """Get family expenses grouped by category.
    
    Args:
        session: Database session
        family_id: Family ID
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering
        
    Returns:
        Dictionary mapping category_id to category data with expenses:
        {
            category_id: {
                'name': str,
                'icon': str,
                'amount': Decimal,
                'expenses': [Expense, ...]
            },
            ...
        }
    """
    try:
        # Get all expenses for the family
        query = (
            select(Expense)
            .options(
                selectinload(Expense.category),
                selectinload(Expense.user)
            )
            .where(Expense.family_id == family_id)
        )
        
        if start_date:
            query = query.where(Expense.date >= start_date)
        
        if end_date:
            query = query.where(Expense.date <= end_date)
        
        query = query.order_by(Expense.date.desc())
        
        result = await session.execute(query)
        expenses = result.scalars().all()
        
        # Group by category
        by_category = {}
        for expense in expenses:
            category_id = expense.category_id
            if category_id not in by_category:
                by_category[category_id] = {
                    'name': expense.category.name,
                    'icon': expense.category.icon,
                    'amount': Decimal('0'),
                    'expenses': []
                }
            
            by_category[category_id]['amount'] += expense.amount
            by_category[category_id]['expenses'].append(expense)
        
        logger.info(
            f"Grouped family expenses by category for family_id={family_id}: "
            f"{len(by_category)} categories"
        )
        
        return by_category
        
    except Exception as e:
        logger.error(
            f"Error getting family expenses by category for family_id {family_id}: {e}"
        )
        raise


def calculate_date_range(period: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Calculate date range for a given period.
    
    Args:
        period: Period identifier ('today', 'week', 'month', 'all')
        
    Returns:
        Tuple of (start_date, end_date). Returns (None, None) for 'all' period.
        
    Examples:
        >>> start, end = calculate_date_range('today')
        >>> start.hour
        0
        >>> end.hour
        23
    """
    from datetime import timedelta
    
    now = datetime.now()
    
    if period == "today":
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        return (start_of_day, end_of_day)
    
    elif period == "week":
        # Start from Monday of current week
        start_of_week = now - timedelta(days=now.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_week = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        return (start_of_week, end_of_week)
    
    elif period == "month":
        # Start from first day of current month
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_of_month = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        return (start_of_month, end_of_month)
    
    else:  # 'all'
        return (None, None)


# ============================================================================
# Statistics CRUD operations
# ============================================================================

async def get_period_statistics(
    session: AsyncSession,
    entity_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    is_family: bool = False
) -> dict:
    """Get detailed statistics for a period.
    
    Args:
        session: Database session
        entity_id: User ID or Family ID
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering
        is_family: If True, get statistics for family; if False, for user
        
    Returns:
        Dictionary with detailed statistics:
        {
            'total': Decimal,
            'count': int,
            'avg_per_day': Decimal,
            'by_category': [
                {
                    'category_id': int,
                    'category_name': str,
                    'category_icon': str,
                    'amount': Decimal,
                    'count': int,
                    'percentage': float
                },
                ...
            ]
        }
    """
    try:
        from sqlalchemy import func
        
        # Build base query
        query = (
            select(
                Category.id,
                Category.name,
                Category.icon,
                func.sum(Expense.amount).label('total_amount'),
                func.count(Expense.id).label('expense_count')
            )
            .join(Category, Expense.category_id == Category.id)
        )
        
        # Apply entity filter (user or family)
        if is_family:
            query = query.where(Expense.family_id == entity_id)
        else:
            query = query.where(Expense.user_id == entity_id)
        
        # Apply date filters
        if start_date:
            query = query.where(Expense.date >= start_date)
        
        if end_date:
            query = query.where(Expense.date <= end_date)
        
        # Group by category
        query = query.group_by(Category.id, Category.name, Category.icon)
        query = query.order_by(func.sum(Expense.amount).desc())
        
        result = await session.execute(query)
        rows = result.all()
        
        # Calculate totals
        total_amount = Decimal('0')
        total_count = 0
        by_category = []
        
        for row in rows:
            category_total = Decimal(str(row.total_amount))
            category_count = row.expense_count
            
            total_amount += category_total
            total_count += category_count
            
            by_category.append({
                'category_id': row.id,
                'category_name': row.name,
                'category_icon': row.icon,
                'amount': category_total,
                'count': category_count,
                'percentage': 0.0  # Will be calculated later
            })
        
        # Calculate percentages
        for cat_data in by_category:
            if total_amount > 0:
                cat_data['percentage'] = float((cat_data['amount'] / total_amount) * 100)
        
        # Calculate average per day
        avg_per_day = Decimal('0')
        if start_date and end_date:
            days = (end_date - start_date).days + 1
            if days > 0:
                avg_per_day = total_amount / days
        
        statistics = {
            'total': total_amount,
            'count': total_count,
            'avg_per_day': avg_per_day,
            'by_category': by_category
        }
        
        entity_type = "family" if is_family else "user"
        logger.info(
            f"Generated period statistics for {entity_type} {entity_id}: "
            f"total={total_amount}, count={total_count}, avg_per_day={avg_per_day}"
        )
        
        return statistics
        
    except Exception as e:
        entity_type = "family" if is_family else "user"
        logger.error(
            f"Error getting period statistics for {entity_type} {entity_id}: {e}"
        )
        raise


async def get_daily_expenses(
    session: AsyncSession,
    entity_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    is_family: bool = False
) -> List[tuple[datetime, Decimal]]:
    """Get daily expenses aggregated by date.
    
    Args:
        session: Database session
        entity_id: User ID or Family ID
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering
        is_family: If True, get expenses for family; if False, for user
        
    Returns:
        List of tuples (date, total_amount) sorted by date
    """
    try:
        from sqlalchemy import func
        
        # Build query to group by date
        query = (
            select(
                func.date(Expense.date).label('expense_date'),
                func.sum(Expense.amount).label('total_amount')
            )
        )
        
        # Apply entity filter
        if is_family:
            query = query.where(Expense.family_id == entity_id)
        else:
            query = query.where(Expense.user_id == entity_id)
        
        # Apply date filters
        if start_date:
            query = query.where(Expense.date >= start_date)
        
        if end_date:
            query = query.where(Expense.date <= end_date)
        
        # Group by date and order
        query = query.group_by(func.date(Expense.date))
        query = query.order_by(func.date(Expense.date))
        
        result = await session.execute(query)
        rows = result.all()
        
        # Convert to list of tuples
        daily_expenses = [
            (row.expense_date, Decimal(str(row.total_amount)))
            for row in rows
        ]
        
        entity_type = "family" if is_family else "user"
        logger.info(
            f"Found {len(daily_expenses)} days with expenses for {entity_type} {entity_id}"
        )
        
        return daily_expenses
        
    except Exception as e:
        entity_type = "family" if is_family else "user"
        logger.error(
            f"Error getting daily expenses for {entity_type} {entity_id}: {e}"
        )
        raise


async def get_top_expense_day(
    session: AsyncSession,
    entity_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    is_family: bool = False
) -> Optional[tuple[datetime, Decimal]]:
    """Get the day with highest expenses.
    
    Args:
        session: Database session
        entity_id: User ID or Family ID
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering
        is_family: If True, get for family; if False, for user
        
    Returns:
        Tuple of (date, total_amount) for the highest expense day, or None if no expenses
    """
    try:
        from sqlalchemy import func
        
        # Build query to group by date
        query = (
            select(
                func.date(Expense.date).label('expense_date'),
                func.sum(Expense.amount).label('total_amount')
            )
        )
        
        # Apply entity filter
        if is_family:
            query = query.where(Expense.family_id == entity_id)
        else:
            query = query.where(Expense.user_id == entity_id)
        
        # Apply date filters
        if start_date:
            query = query.where(Expense.date >= start_date)
        
        if end_date:
            query = query.where(Expense.date <= end_date)
        
        # Group by date, order by amount descending, limit to 1
        query = query.group_by(func.date(Expense.date))
        query = query.order_by(func.sum(Expense.amount).desc())
        query = query.limit(1)
        
        result = await session.execute(query)
        row = result.first()
        
        if row:
            top_day = (row.expense_date, Decimal(str(row.total_amount)))
            entity_type = "family" if is_family else "user"
            logger.info(
                f"Found top expense day for {entity_type} {entity_id}: "
                f"{top_day[0]} - {top_day[1]}"
            )
            return top_day
        
        return None
        
    except Exception as e:
        entity_type = "family" if is_family else "user"
        logger.error(
            f"Error getting top expense day for {entity_type} {entity_id}: {e}"
        )
        raise


def compare_periods(current_data: dict, previous_data: dict) -> dict:
    """Compare statistics between two periods.
    
    Args:
        current_data: Statistics for current period (from get_period_statistics)
        previous_data: Statistics for previous period (from get_period_statistics)
        
    Returns:
        Dictionary with comparison data:
        {
            'total_change': Decimal,
            'total_change_percent': float,
            'count_change': int,
            'count_change_percent': float
        }
    """
    try:
        current_total = current_data.get('total', Decimal('0'))
        previous_total = previous_data.get('total', Decimal('0'))
        current_count = current_data.get('count', 0)
        previous_count = previous_data.get('count', 0)
        
        # Calculate changes
        total_change = current_total - previous_total
        count_change = current_count - previous_count
        
        # Calculate percentage changes
        if previous_total > 0:
            total_change_percent = float((total_change / previous_total) * 100)
        else:
            total_change_percent = 0.0 if current_total == 0 else 100.0
        
        if previous_count > 0:
            count_change_percent = float((count_change / previous_count) * 100)
        else:
            count_change_percent = 0.0 if current_count == 0 else 100.0
        
        comparison = {
            'total_change': total_change,
            'total_change_percent': total_change_percent,
            'count_change': count_change,
            'count_change_percent': count_change_percent
        }
        
        logger.info(
            f"Period comparison: total_change={total_change} ({total_change_percent:.1f}%), "
            f"count_change={count_change} ({count_change_percent:.1f}%)"
        )
        
        return comparison
        
    except Exception as e:
        logger.error(f"Error comparing periods: {e}")
        raise


async def get_category_details(
    session: AsyncSession,
    entity_id: int,
    category_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    is_family: bool = False
) -> dict:
    """Get detailed information about expenses in a specific category.
    
    Args:
        session: Database session
        entity_id: User ID or Family ID
        category_id: Category ID to get details for
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering
        is_family: If True, get for family; if False, for user
        
    Returns:
        Dictionary with category details:
        {
            'category': Category object,
            'total': Decimal,
            'count': int,
            'expenses': List[Expense]
        }
    """
    try:
        # Get category info
        category = await get_category_by_id(session, category_id)
        if not category:
            raise ValueError(f"Category {category_id} not found")
        
        # Build query for expenses
        query = (
            select(Expense)
            .options(
                selectinload(Expense.category),
                selectinload(Expense.user)
            )
            .where(Expense.category_id == category_id)
        )
        
        # Apply entity filter
        if is_family:
            query = query.where(Expense.family_id == entity_id)
        else:
            query = query.where(Expense.user_id == entity_id)
        
        # Apply date filters
        if start_date:
            query = query.where(Expense.date >= start_date)
        
        if end_date:
            query = query.where(Expense.date <= end_date)
        
        # Order by date descending
        query = query.order_by(Expense.date.desc())
        
        result = await session.execute(query)
        expenses = result.scalars().all()
        
        # Calculate totals
        total_amount = sum(expense.amount for expense in expenses)
        
        details = {
            'category': category,
            'total': total_amount,
            'count': len(expenses),
            'expenses': list(expenses)
        }
        
        entity_type = "family" if is_family else "user"
        logger.info(
            f"Got category details for {entity_type} {entity_id}, "
            f"category {category_id}: {len(expenses)} expenses, total={total_amount}"
        )
        
        return details
        
    except Exception as e:
        entity_type = "family" if is_family else "user"
        logger.error(
            f"Error getting category details for {entity_type} {entity_id}, "
            f"category {category_id}: {e}"
        )
        raise


# ============================================================================
# Search and Filter operations
# ============================================================================

async def search_expenses(
    session: AsyncSession,
    entity_id: int,
    is_family: bool = False,
    query: Optional[str] = None,
    category_id: Optional[int] = None,
    min_amount: Optional[Decimal] = None,
    max_amount: Optional[Decimal] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List[Expense]:
    """Search expenses with multiple filters.
    
    Args:
        session: Database session
        entity_id: User ID or Family ID
        is_family: If True, search in family expenses; if False, in user expenses
        query: Text search query for description
        category_id: Filter by category
        min_amount: Minimum amount filter
        max_amount: Maximum amount filter
        date_from: Start date filter
        date_to: End date filter
        
    Returns:
        List of matching Expense objects
    """
    try:
        # Build base query
        stmt = (
            select(Expense)
            .options(
                selectinload(Expense.category),
                selectinload(Expense.user)
            )
        )
        
        # Apply entity filter
        if is_family:
            stmt = stmt.where(Expense.family_id == entity_id)
        else:
            stmt = stmt.where(Expense.user_id == entity_id)
        
        # Apply filters
        if query:
            # Search in description (case-insensitive)
            stmt = stmt.where(Expense.description.ilike(f"%{query}%"))
        
        if category_id:
            stmt = stmt.where(Expense.category_id == category_id)
        
        if min_amount is not None:
            stmt = stmt.where(Expense.amount >= min_amount)
        
        if max_amount is not None:
            stmt = stmt.where(Expense.amount <= max_amount)
        
        if date_from:
            stmt = stmt.where(Expense.date >= date_from)
        
        if date_to:
            stmt = stmt.where(Expense.date <= date_to)
        
        # Order by date descending
        stmt = stmt.order_by(Expense.date.desc())
        
        result = await session.execute(stmt)
        expenses = list(result.scalars().all())
        
        entity_type = "family" if is_family else "user"
        logger.info(
            f"Search expenses for {entity_type} {entity_id}: "
            f"found {len(expenses)} results"
        )
        
        return expenses
        
    except Exception as e:
        entity_type = "family" if is_family else "user"
        logger.error(f"Error searching expenses for {entity_type} {entity_id}: {e}")
        raise


# ============================================================================
# Expense Template CRUD operations
# ============================================================================

async def create_expense_template(
    session: AsyncSession,
    user_id: int,
    family_id: int,
    name: str,
    category_id: int,
    amount: Decimal,
    description: Optional[str] = None
) -> ExpenseTemplate:
    """Create a new expense template.
    
    Args:
        session: Database session
        user_id: User ID who creates the template
        family_id: Family ID
        name: Template name
        category_id: Category ID
        amount: Default amount
        description: Optional description
        
    Returns:
        Created ExpenseTemplate object
    """
    try:
        template = ExpenseTemplate(
            user_id=user_id,
            family_id=family_id,
            name=name,
            category_id=category_id,
            amount=amount,
            description=description
        )
        session.add(template)
        await session.flush()
        
        logger.info(
            f"Created expense template: {template.name} "
            f"(id={template.id}, user_id={user_id}, family_id={family_id})"
        )
        
        return template
        
    except Exception as e:
        logger.error(
            f"Error creating expense template for user {user_id}, "
            f"family {family_id}: {e}"
        )
        raise


async def get_user_expense_templates(
    session: AsyncSession,
    user_id: int,
    family_id: int
) -> List[ExpenseTemplate]:
    """Get all expense templates for a user in a family.
    
    Args:
        session: Database session
        user_id: User ID
        family_id: Family ID
        
    Returns:
        List of ExpenseTemplate objects
    """
    try:
        result = await session.execute(
            select(ExpenseTemplate)
            .options(selectinload(ExpenseTemplate.category))
            .where(
                ExpenseTemplate.user_id == user_id,
                ExpenseTemplate.family_id == family_id
            )
            .order_by(ExpenseTemplate.name)
        )
        templates = list(result.scalars().all())
        
        logger.info(
            f"Found {len(templates)} expense templates for "
            f"user {user_id} in family {family_id}"
        )
        
        return templates
        
    except Exception as e:
        logger.error(
            f"Error getting expense templates for user {user_id}, "
            f"family {family_id}: {e}"
        )
        raise


async def get_expense_template_by_id(
    session: AsyncSession,
    template_id: int
) -> Optional[ExpenseTemplate]:
    """Get expense template by ID.
    
    Args:
        session: Database session
        template_id: Template ID
        
    Returns:
        ExpenseTemplate object or None
    """
    try:
        result = await session.execute(
            select(ExpenseTemplate)
            .options(selectinload(ExpenseTemplate.category))
            .where(ExpenseTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        
        if template:
            logger.info(f"Found expense template: {template.name} (id={template_id})")
        else:
            logger.info(f"Expense template not found (id={template_id})")
        
        return template
        
    except Exception as e:
        logger.error(f"Error getting expense template by id {template_id}: {e}")
        raise


async def delete_expense_template(
    session: AsyncSession,
    template_id: int
) -> bool:
    """Delete an expense template.
    
    Args:
        session: Database session
        template_id: Template ID to delete
        
    Returns:
        True if deleted, False if not found
    """
    try:
        template = await get_expense_template_by_id(session, template_id)
        
        if not template:
            logger.warning(f"Cannot delete template {template_id}: not found")
            return False
        
        await session.delete(template)
        await session.flush()
        
        logger.info(f"Deleted expense template: {template.name} (id={template_id})")
        
        return True
        
    except Exception as e:
        logger.error(f"Error deleting expense template {template_id}: {e}")
        raise


# ============================================================================
# Period Statistics Helper Functions
# ============================================================================

async def get_available_periods(
    session: AsyncSession,
    entity_id: int,
    is_family: bool = False
) -> Dict[str, List[Tuple[int, int]]]:
    """Get available months and years that have expenses.
    
    Args:
        session: Database session
        entity_id: User ID or Family ID
        is_family: If True, get periods for family; if False, for user
        
    Returns:
        Dictionary with 'months' (list of (year, month) tuples) and 'years' (list of years)
    """
    try:
        from sqlalchemy import func, extract
        
        # Build base query
        base_query = select(Expense.date)
        
        # Apply entity filter
        if is_family:
            base_query = base_query.where(Expense.family_id == entity_id)
        else:
            base_query = base_query.where(Expense.user_id == entity_id)
        
        # Get unique year-month combinations
        query_months = (
            select(
                extract('year', Expense.date).label('year'),
                extract('month', Expense.date).label('month')
            )
            .where(
                Expense.family_id == entity_id if is_family else Expense.user_id == entity_id
            )
            .group_by('year', 'month')
            .order_by('year', 'month')
        )
        
        result = await session.execute(query_months)
        month_rows = result.all()
        months = [(int(row.year), int(row.month)) for row in month_rows]
        
        # Get unique years
        query_years = (
            select(extract('year', Expense.date).label('year'))
            .where(
                Expense.family_id == entity_id if is_family else Expense.user_id == entity_id
            )
            .group_by('year')
            .order_by('year')
        )
        
        result = await session.execute(query_years)
        year_rows = result.scalars().all()
        years = [int(year) for year in year_rows]
        
        entity_type = "family" if is_family else "user"
        logger.info(
            f"Found {len(months)} months and {len(years)} years with expenses "
            f"for {entity_type} {entity_id}"
        )
        
        return {
            'months': months,
            'years': years
        }
        
    except Exception as e:
        entity_type = "family" if is_family else "user"
        logger.error(
            f"Error getting available periods for {entity_type} {entity_id}: {e}"
        )
        raise


async def get_detailed_statistics(
    session: AsyncSession,
    entity_id: int,
    start_date: datetime,
    end_date: datetime,
    is_family: bool = False
) -> dict:
    """Get detailed statistics with all expenses for each category.
    
    Args:
        session: Database session
        entity_id: User ID or Family ID
        start_date: Start date for filtering
        end_date: End date for filtering
        is_family: If True, get statistics for family; if False, for user
        
    Returns:
        Dictionary with detailed statistics including individual expenses:
        {
            'total': Decimal,
            'count': int,
            'by_category': [
                {
                    'category_id': int,
                    'category_name': str,
                    'category_icon': str,
                    'amount': Decimal,
                    'count': int,
                    'percentage': float,
                    'expenses': [
                        {
                            'id': int,
                            'amount': Decimal,
                            'description': str,
                            'date': datetime,
                            'user_id': int,
                            'user_name': str
                        },
                        ...
                    ]
                },
                ...
            ]
        }
    """
    try:
        from sqlalchemy import func
        
        # First, get category totals
        query_totals = (
            select(
                Category.id,
                Category.name,
                Category.icon,
                func.sum(Expense.amount).label('total_amount'),
                func.count(Expense.id).label('expense_count')
            )
            .join(Category, Expense.category_id == Category.id)
        )
        
        # Apply entity filter
        if is_family:
            query_totals = query_totals.where(Expense.family_id == entity_id)
        else:
            query_totals = query_totals.where(Expense.user_id == entity_id)
        
        # Apply date filters
        query_totals = query_totals.where(
            Expense.date >= start_date,
            Expense.date <= end_date
        )
        
        # Group by category
        query_totals = query_totals.group_by(Category.id, Category.name, Category.icon)
        query_totals = query_totals.order_by(func.sum(Expense.amount).desc())
        
        result = await session.execute(query_totals)
        category_rows = result.all()
        
        # Calculate totals
        total_amount = Decimal('0')
        total_count = 0
        by_category = []
        
        for cat_row in category_rows:
            category_total = Decimal(str(cat_row.total_amount))
            category_count = cat_row.expense_count
            
            total_amount += category_total
            total_count += category_count
            
            # Get detailed expenses for this category
            query_expenses = (
                select(Expense, User)
                .join(User, Expense.user_id == User.id)
                .where(Expense.category_id == cat_row.id)
            )
            
            # Apply entity filter
            if is_family:
                query_expenses = query_expenses.where(Expense.family_id == entity_id)
            else:
                query_expenses = query_expenses.where(Expense.user_id == entity_id)
            
            # Apply date filters
            query_expenses = query_expenses.where(
                Expense.date >= start_date,
                Expense.date <= end_date
            )
            
            # Order by date descending
            query_expenses = query_expenses.order_by(Expense.date.desc())
            
            result_expenses = await session.execute(query_expenses)
            expense_rows = result_expenses.all()
            
            expenses = []
            for exp, user in expense_rows:
                expenses.append({
                    'id': exp.id,
                    'amount': exp.amount,
                    'description': exp.description,
                    'date': exp.date,
                    'user_id': user.id,
                    'user_name': user.name or user.username or f"User {user.id}"
                })
            
            by_category.append({
                'category_id': cat_row.id,
                'category_name': cat_row.name,
                'category_icon': cat_row.icon,
                'amount': category_total,
                'count': category_count,
                'percentage': 0.0,  # Will be calculated later
                'expenses': expenses
            })
        
        # Calculate percentages
        for cat_data in by_category:
            if total_amount > 0:
                cat_data['percentage'] = float((cat_data['amount'] / total_amount) * 100)
        
        statistics = {
            'total': total_amount,
            'count': total_count,
            'by_category': by_category
        }
        
        entity_type = "family" if is_family else "user"
        logger.info(
            f"Generated detailed statistics for {entity_type} {entity_id}: "
            f"total={total_amount}, count={total_count}"
        )
        
        return statistics
        
    except Exception as e:
        entity_type = "family" if is_family else "user"
        logger.error(
            f"Error getting detailed statistics for {entity_type} {entity_id}: {e}"
        )
        raise

