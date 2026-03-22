"""Database connection and initialization."""

from typing import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config.settings import settings

from .models import Base, Category, CategoryTypeEnum


class DatabaseManager:
    """Manages database connections and sessions."""
    
    def __init__(self) -> None:
        """Initialize the database manager."""
        self.engine: AsyncEngine | None = None
        self.session_factory: async_sessionmaker[AsyncSession] | None = None
    
    def init_engine(self) -> None:
        """Initialize the database engine."""
        # Convert sync database URL to async if needed
        db_url = settings.DATABASE_URL
        
        if settings.is_sqlite and not db_url.startswith("sqlite+aiosqlite"):
            db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://")
        elif settings.is_postgresql and not db_url.startswith("postgresql+asyncpg"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
        
        self.engine = create_async_engine(
            db_url,
            echo=settings.DEBUG,
            future=True,
        )
        
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    
    async def create_tables(self) -> None:
        """Create all database tables."""
        if not self.engine:
            self.init_engine()
        
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def drop_tables(self) -> None:
        """Drop all database tables (use with caution)."""
        if not self.engine:
            self.init_engine()
        
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session.
        
        Yields:
            AsyncSession: Database session for queries.
        """
        if not self.session_factory:
            self.init_engine()
        
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def close(self) -> None:
        """Close the database engine."""
        if self.engine:
            await self.engine.dispose()


# Global database manager instance
db_manager = DatabaseManager()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database sessions.
    
    Usage:
        async with get_db() as session:
            # use session
            
    Yields:
        AsyncSession: Database session
    """
    async for session in db_manager.get_session():
        yield session


async def init_database() -> None:
    """Initialize database: create tables and add default categories.
    
    This function should be called on application startup.
    """
    # Initialize engine
    db_manager.init_engine()
    
    # Create all tables
    await db_manager.create_tables()
    
    # Add default categories
    await create_default_categories()


async def create_default_categories() -> None:
    """Create default categories if they don't exist.
    
    Default categories:
    - Продукты 🛒
    - Транспорт 🚗
    - Развлечения 🎮
    - Здоровье 💊
    - Одежда 👕
    - Прочее 📦
    """
    expense_categories = [
        {"name": "Продукты", "icon": "🛒"},
        {"name": "Транспорт", "icon": "🚗"},
        {"name": "Развлечения", "icon": "🎮"},
        {"name": "Здоровье", "icon": "💊"},
        {"name": "Одежда", "icon": "👕"},
        {"name": "Прочее", "icon": "📦"},
    ]
    income_categories = [
        {"name": "Зарплата", "icon": "💼"},
        {"name": "Премия", "icon": "🏆"},
        {"name": "Подарки", "icon": "🎁"},
        {"name": "Кэшбэк", "icon": "💳"},
        {"name": "Прочее", "icon": "📦"},
    ]
    
    async for session in db_manager.get_session():
        result = await session.execute(
            select(Category).where(Category.is_default == True)
        )
        existing = result.scalars().all()
        existing_types = {cat.category_type for cat in existing}
        
        if CategoryTypeEnum.EXPENSE not in existing_types:
            for cat_data in expense_categories:
                category = Category(
                    name=cat_data["name"],
                    icon=cat_data["icon"],
                    is_default=True,
                    category_type=CategoryTypeEnum.EXPENSE
                )
                session.add(category)
        
        if CategoryTypeEnum.INCOME not in existing_types:
            for cat_data in income_categories:
                category = Category(
                    name=cat_data["name"],
                    icon=cat_data["icon"],
                    is_default=True,
                    category_type=CategoryTypeEnum.INCOME
                )
                session.add(category)
        
        await session.commit()


async def reset_database() -> None:
    """Reset database: drop all tables and recreate them.
    
    WARNING: This will delete all data! Use only for development/testing.
    """
    db_manager.init_engine()
    await db_manager.drop_tables()
    await db_manager.create_tables()
    await create_default_categories()

