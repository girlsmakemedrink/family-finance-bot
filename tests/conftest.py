"""Pytest configuration and fixtures."""

import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from bot.database.models import Base, User, Family, FamilyMember, Category, Expense
from bot.database import init_database
from config.settings import settings


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings for testing."""
    monkeypatch.setenv("BOT_TOKEN", "test_token_123456789:ABCdefGHIjklMNOpqrsTUVwxyz")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("DEBUG", "True")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")


@pytest_asyncio.fixture
async def test_engine(mock_settings) -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine with in-memory SQLite."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def test_user(test_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        telegram_id=123456789,
        name="Test User",
        username="testuser"
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_family(test_session: AsyncSession) -> Family:
    """Create a test family."""
    family = Family(
        name="Test Family",
        invite_code="TESTCODE"
    )
    test_session.add(family)
    await test_session.commit()
    await test_session.refresh(family)
    return family


@pytest_asyncio.fixture
async def test_category(test_session: AsyncSession) -> Category:
    """Create a test category."""
    category = Category(
        name="Test Category",
        icon="🧪",
        is_default=True
    )
    test_session.add(category)
    await test_session.commit()
    await test_session.refresh(category)
    return category


@pytest_asyncio.fixture
async def test_family_member(
    test_session: AsyncSession,
    test_user: User,
    test_family: Family
) -> FamilyMember:
    """Create a test family member."""
    from bot.database.models import RoleEnum
    
    member = FamilyMember(
        user_id=test_user.id,
        family_id=test_family.id,
        role=RoleEnum.ADMIN
    )
    test_session.add(member)
    await test_session.commit()
    await test_session.refresh(member)
    return member


@pytest_asyncio.fixture
async def test_expense(
    test_session: AsyncSession,
    test_user: User,
    test_family: Family,
    test_category: Category
) -> Expense:
    """Create a test expense."""
    from decimal import Decimal
    
    expense = Expense(
        user_id=test_user.id,
        family_id=test_family.id,
        category_id=test_category.id,
        amount=Decimal("100.50"),
        description="Test expense"
    )
    test_session.add(expense)
    await test_session.commit()
    await test_session.refresh(expense)
    return expense


@pytest.fixture
def mock_telegram_update():
    """Create a mock Telegram Update object."""
    update = MagicMock()
    update.effective_user.id = 123456789
    update.effective_user.first_name = "Test"
    update.effective_user.last_name = "User"
    update.effective_user.username = "testuser"
    update.effective_chat.id = 123456789
    update.message = MagicMock()
    update.message.text = "/start"
    update.callback_query = None
    return update


@pytest.fixture
def mock_telegram_context():
    """Create a mock Telegram Context object."""
    context = MagicMock()
    context.bot = AsyncMock()
    context.user_data = {}
    context.chat_data = {}
    context.bot_data = {}
    return context

