"""Tests for database models and CRUD operations."""

import pytest
from decimal import Decimal
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User, Family, FamilyMember, Category, Expense, RoleEnum, generate_invite_code
from bot.database import crud


class TestModels:
    """Test database models."""
    
    @pytest.mark.asyncio
    async def test_user_creation(self, test_session: AsyncSession):
        """Test creating a user."""
        user = User(
            telegram_id=987654321,
            name="New User",
            username="newuser"
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)
        
        assert user.id is not None
        assert user.telegram_id == 987654321
        assert user.name == "New User"
        assert user.username == "newuser"
        assert user.currency == "₽"
        assert user.timezone == "Europe/Moscow"
        assert user.created_at is not None
    
    @pytest.mark.asyncio
    async def test_family_creation(self, test_session: AsyncSession):
        """Test creating a family."""
        family = Family(name="My Family")
        test_session.add(family)
        await test_session.commit()
        await test_session.refresh(family)
        
        assert family.id is not None
        assert family.name == "My Family"
        assert family.invite_code is not None
        assert len(family.invite_code) == 8
        assert family.created_at is not None
    
    @pytest.mark.asyncio
    async def test_invite_code_uniqueness(self, test_session: AsyncSession):
        """Test that invite codes are unique."""
        codes = set()
        for i in range(100):
            code = generate_invite_code()
            codes.add(code)
        
        # All codes should be unique
        assert len(codes) == 100
        
        # All codes should be uppercase alphanumeric
        for code in codes:
            assert code.isalnum()
            assert code.isupper()
    
    @pytest.mark.asyncio
    async def test_family_member_relationship(
        self,
        test_session: AsyncSession,
        test_user: User,
        test_family: Family
    ):
        """Test family member relationships."""
        member = FamilyMember(
            user_id=test_user.id,
            family_id=test_family.id,
            role=RoleEnum.MEMBER
        )
        test_session.add(member)
        await test_session.commit()
        await test_session.refresh(member)
        
        assert member.id is not None
        assert member.user_id == test_user.id
        assert member.family_id == test_family.id
        assert member.role == RoleEnum.MEMBER
        
        # Test relationships
        await test_session.refresh(member, ["user", "family"])
        assert member.user.telegram_id == test_user.telegram_id
        assert member.family.name == test_family.name
    
    @pytest.mark.asyncio
    async def test_expense_creation(
        self,
        test_session: AsyncSession,
        test_user: User,
        test_family: Family,
        test_category: Category
    ):
        """Test creating an expense."""
        expense = Expense(
            user_id=test_user.id,
            family_id=test_family.id,
            category_id=test_category.id,
            amount=Decimal("250.75"),
            description="Groceries"
        )
        test_session.add(expense)
        await test_session.commit()
        await test_session.refresh(expense)
        
        assert expense.id is not None
        assert expense.amount == Decimal("250.75")
        assert expense.description == "Groceries"
        assert expense.created_at is not None
        assert expense.date is not None
    
    @pytest.mark.asyncio
    async def test_category_relationships(
        self,
        test_session: AsyncSession,
        test_family: Family
    ):
        """Test category with family relationship."""
        # Default category (no family)
        default_cat = Category(
            name="Default Category",
            icon="📦",
            is_default=True
        )
        test_session.add(default_cat)
        
        # Family-specific category
        custom_cat = Category(
            name="Custom Category",
            icon="🎯",
            is_default=False,
            family_id=test_family.id
        )
        test_session.add(custom_cat)
        await test_session.commit()
        
        await test_session.refresh(default_cat)
        await test_session.refresh(custom_cat)
        
        assert default_cat.family_id is None
        assert custom_cat.family_id == test_family.id


class TestCRUD:
    """Test CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_get_user_by_telegram_id(self, test_session: AsyncSession, test_user: User):
        """Test getting user by telegram_id."""
        user = await crud.get_user_by_telegram_id(test_session, test_user.telegram_id)
        
        assert user is not None
        assert user.id == test_user.id
        assert user.telegram_id == test_user.telegram_id
        assert user.name == test_user.name
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_user(self, test_session: AsyncSession):
        """Test getting a user that doesn't exist."""
        user = await crud.get_user_by_telegram_id(test_session, 999999999)
        assert user is None
    
    @pytest.mark.asyncio
    async def test_create_user(self, test_session: AsyncSession):
        """Test creating a new user."""
        user = await crud.create_user(
            test_session,
            telegram_id=111222333,
            name="Created User",
            username="createduser"
        )
        
        assert user.id is not None
        assert user.telegram_id == 111222333
        assert user.name == "Created User"
        assert user.username == "createduser"
    
    @pytest.mark.asyncio
    async def test_create_family(self, test_session: AsyncSession):
        """Test creating a family."""
        family = await crud.create_family(
            test_session,
            name="CRUD Test Family"
        )
        
        assert family.id is not None
        assert family.name == "CRUD Test Family"
        assert family.invite_code is not None
        assert len(family.invite_code) > 0
    
    @pytest.mark.asyncio
    async def test_get_family_by_invite_code(self, test_session: AsyncSession, test_family: Family):
        """Test getting family by invite code."""
        family = await crud.get_family_by_invite_code(test_session, test_family.invite_code)
        
        assert family is not None
        assert family.id == test_family.id
        assert family.name == test_family.name
    
    @pytest.mark.asyncio
    async def test_add_family_member(
        self,
        test_session: AsyncSession,
        test_user: User,
        test_family: Family
    ):
        """Test adding a member to a family."""
        member = await crud.add_family_member(
            test_session,
            user_id=test_user.id,
            family_id=test_family.id,
            role="admin"
        )
        
        assert member is not None
        assert member.user_id == test_user.id
        assert member.family_id == test_family.id
        assert member.role == RoleEnum.ADMIN
    
    @pytest.mark.asyncio
    async def test_get_user_families(
        self,
        test_session: AsyncSession,
        test_user: User,
        test_family_member: FamilyMember
    ):
        """Test getting all families for a user."""
        families = await crud.get_user_families(test_session, test_user.id)
        
        assert len(families) > 0
        assert any(f.id == test_family_member.family_id for f in families)
    
    @pytest.mark.asyncio
    async def test_create_expense(
        self,
        test_session: AsyncSession,
        test_user: User,
        test_family: Family,
        test_category: Category
    ):
        """Test creating an expense."""
        expense = await crud.create_expense(
            test_session,
            user_id=test_user.id,
            family_id=test_family.id,
            category_id=test_category.id,
            amount=Decimal("99.99"),
            description="Test expense"
        )
        
        assert expense is not None
        assert expense.user_id == test_user.id
        assert expense.family_id == test_family.id
        assert expense.category_id == test_category.id
        assert expense.amount == Decimal("99.99")
        assert expense.description == "Test expense"
    
    @pytest.mark.asyncio
    async def test_get_family_expenses(
        self,
        test_session: AsyncSession,
        test_family: Family,
        test_expense: Expense
    ):
        """Test getting expenses for a family."""
        expenses = await crud.get_family_expenses(
            test_session,
            family_id=test_family.id,
            limit=10
        )
        
        assert len(expenses) > 0
        assert any(e.id == test_expense.id for e in expenses)
    
    @pytest.mark.asyncio
    async def test_update_user_settings(self, test_session: AsyncSession, test_user: User):
        """Test updating user settings."""
        updated_user = await crud.update_user_settings(
            test_session,
            user_id=test_user.id,
            currency="$",
            timezone="America/New_York"
        )
        
        assert updated_user.currency == "$"
        assert updated_user.timezone == "America/New_York"
    
    @pytest.mark.asyncio
    async def test_get_default_categories(self, test_session: AsyncSession):
        """Test getting default categories."""
        # Create some default categories
        categories = [
            Category(name="Food", icon="🍔", is_default=True),
            Category(name="Transport", icon="🚗", is_default=True),
            Category(name="Entertainment", icon="🎮", is_default=True),
        ]
        for cat in categories:
            test_session.add(cat)
        await test_session.commit()
        
        default_cats = await crud.get_default_categories(test_session)
        
        assert len(default_cats) >= 3
        for cat in default_cats:
            assert cat.is_default is True
            assert cat.family_id is None
    
    @pytest.mark.asyncio
    async def test_cascade_delete_family(
        self,
        test_session: AsyncSession,
        test_family: Family,
        test_family_member: FamilyMember,
        test_expense: Expense
    ):
        """Test that deleting a family cascades to members and expenses."""
        family_id = test_family.id
        
        # Delete the family
        await test_session.delete(test_family)
        await test_session.commit()
        
        # Check that related objects are deleted
        result = await test_session.execute(
            select(FamilyMember).where(FamilyMember.family_id == family_id)
        )
        members = result.scalars().all()
        assert len(members) == 0
        
        result = await test_session.execute(
            select(Expense).where(Expense.family_id == family_id)
        )
        expenses = result.scalars().all()
        assert len(expenses) == 0


class TestValidation:
    """Test data validation."""
    
    @pytest.mark.asyncio
    async def test_unique_telegram_id(self, test_session: AsyncSession, test_user: User):
        """Test that telegram_id must be unique."""
        duplicate_user = User(
            telegram_id=test_user.telegram_id,
            name="Duplicate User"
        )
        test_session.add(duplicate_user)
        
        with pytest.raises(Exception):  # SQLAlchemy will raise an IntegrityError
            await test_session.commit()
    
    @pytest.mark.asyncio
    async def test_unique_invite_code(self, test_session: AsyncSession, test_family: Family):
        """Test that invite_code must be unique."""
        duplicate_family = Family(
            name="Duplicate Family",
            invite_code=test_family.invite_code
        )
        test_session.add(duplicate_family)
        
        with pytest.raises(Exception):  # SQLAlchemy will raise an IntegrityError
            await test_session.commit()
    
    @pytest.mark.asyncio
    async def test_unique_user_family_combination(
        self,
        test_session: AsyncSession,
        test_family_member: FamilyMember
    ):
        """Test that user can't join the same family twice."""
        duplicate_member = FamilyMember(
            user_id=test_family_member.user_id,
            family_id=test_family_member.family_id,
            role=RoleEnum.MEMBER
        )
        test_session.add(duplicate_member)
        
        with pytest.raises(Exception):  # SQLAlchemy will raise an IntegrityError
            await test_session.commit()

