"""Database models for the Family Finance Bot."""

import enum
import secrets
import string
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class RoleEnum(enum.Enum):
    """Enum for family member roles."""
    ADMIN = "admin"
    MEMBER = "member"


class CategoryTypeEnum(enum.Enum):
    """Enum for category type."""
    EXPENSE = "expense"
    INCOME = "income"


def generate_invite_code(length: int = 8) -> str:
    """Generate a random invite code for family.
    
    Args:
        length: Length of the invite code (default: 8)
        
    Returns:
        Random alphanumeric invite code
    """
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


class User(Base):
    """User model representing a Telegram user."""
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # User settings
    currency: Mapped[str] = mapped_column(String(3), default="₽", nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Moscow", nullable=False)
    date_format: Mapped[str] = mapped_column(String(20), default="DD.MM.YYYY", nullable=False)
    monthly_summary_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    monthly_summary_time: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)  # Format: HH:MM (when to send on 1st day)
    last_monthly_summary_sent: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # Date when last monthly summary was sent
    expense_notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # Receive notifications when family members add expenses
    
    # Relationships
    family_memberships: Mapped[list["FamilyMember"]] = relationship(
        "FamilyMember", 
        back_populates="user",
        cascade="all, delete-orphan"
    )
    expenses: Mapped[list["Expense"]] = relationship(
        "Expense",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    incomes: Mapped[list["Income"]] = relationship(
        "Income",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, name={self.name})>"


class Family(Base):
    """Family model representing a group of users."""
    
    __tablename__ = "families"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    invite_code: Mapped[str] = mapped_column(
        String(16), 
        unique=True, 
        index=True,
        nullable=False,
        default=generate_invite_code
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    members: Mapped[list["FamilyMember"]] = relationship(
        "FamilyMember",
        back_populates="family",
        cascade="all, delete-orphan"
    )
    expenses: Mapped[list["Expense"]] = relationship(
        "Expense",
        back_populates="family",
        cascade="all, delete-orphan"
    )
    incomes: Mapped[list["Income"]] = relationship(
        "Income",
        back_populates="family",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Family(id={self.id}, name={self.name}, invite_code={self.invite_code})>"


class FamilyMember(Base):
    """Association table for users and families with roles."""
    
    __tablename__ = "family_members"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    family_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False
    )
    role: Mapped[RoleEnum] = mapped_column(
        Enum(RoleEnum),
        default=RoleEnum.MEMBER,
        nullable=False
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="family_memberships")
    family: Mapped["Family"] = relationship("Family", back_populates="members")
    
    # Unique constraint for user_id + family_id combination
    __table_args__ = (
        UniqueConstraint('user_id', 'family_id', name='uq_user_family'),
        Index('ix_family_members_user_family', 'user_id', 'family_id'),
    )
    
    def __repr__(self) -> str:
        return f"<FamilyMember(user_id={self.user_id}, family_id={self.family_id}, role={self.role.value})>"


class Category(Base):
    """Category model for expense categorization."""
    
    __tablename__ = "categories"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    icon: Mapped[str] = mapped_column(String(10), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    category_type: Mapped[CategoryTypeEnum] = mapped_column(
        Enum(
            CategoryTypeEnum,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            native_enum=False
        ),
        default=CategoryTypeEnum.EXPENSE,
        nullable=False
    )
    family_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("families.id", ondelete="CASCADE"),
        nullable=True
    )
    
    # Relationships
    expenses: Mapped[list["Expense"]] = relationship(
        "Expense",
        back_populates="category"
    )
    incomes: Mapped[list["Income"]] = relationship(
        "Income",
        back_populates="category"
    )
    family: Mapped[Optional["Family"]] = relationship(
        "Family",
        backref="custom_categories"
    )
    
    # Unique constraint for family_id + name combination
    __table_args__ = (
        UniqueConstraint('family_id', 'name', 'category_type', name='uq_family_category_name_type'),
        Index('ix_categories_family', 'family_id'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<Category(id={self.id}, name={self.name}, icon={self.icon}, "
            f"type={self.category_type.value}, is_default={self.is_default}, "
            f"family_id={self.family_id})>"
        )


class Expense(Base):
    """Expense model for tracking family expenses."""
    
    __tablename__ = "expenses"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    family_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False
    )
    category_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    receipt_photo_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="expenses")
    family: Mapped["Family"] = relationship("Family", back_populates="expenses")
    category: Mapped["Category"] = relationship("Category", back_populates="expenses")
    
    # Indexes for better query performance
    __table_args__ = (
        Index('ix_expenses_user_family', 'user_id', 'family_id'),
        Index('ix_expenses_family_date', 'family_id', 'date'),
        Index('ix_expenses_category', 'category_id'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<Expense(id={self.id}, user_id={self.user_id}, "
            f"family_id={self.family_id}, amount={self.amount})>"
        )


class Income(Base):
    """Income model for tracking family income."""

    __tablename__ = "incomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    family_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False
    )
    category_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="incomes")
    family: Mapped["Family"] = relationship("Family", back_populates="incomes")
    category: Mapped["Category"] = relationship("Category", back_populates="incomes")

    # Indexes for better query performance
    __table_args__ = (
        Index('ix_incomes_user_family', 'user_id', 'family_id'),
        Index('ix_incomes_family_date', 'family_id', 'date'),
        Index('ix_incomes_category', 'category_id'),
    )

    def __repr__(self) -> str:
        return (
            f"<Income(id={self.id}, user_id={self.user_id}, "
            f"family_id={self.family_id}, amount={self.amount})>"
        )


class ExpenseTemplate(Base):
    """Template model for quick expense entry."""
    
    __tablename__ = "expense_templates"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    family_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User")
    family: Mapped["Family"] = relationship("Family")
    category: Mapped["Category"] = relationship("Category")
    
    # Indexes for better query performance
    __table_args__ = (
        Index('ix_expense_templates_user_family', 'user_id', 'family_id'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<ExpenseTemplate(id={self.id}, name={self.name}, "
            f"user_id={self.user_id}, amount={self.amount})>"
        )
