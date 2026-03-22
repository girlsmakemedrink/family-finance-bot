"""Formatting utilities for displaying data in bot messages."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot.database.models import Expense

MONTH_NAMES_RU = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}


def format_month_year(month: int, year: int) -> str:
    """Return localized month + year string, e.g. 'Январь 2026'."""
    return f"{MONTH_NAMES_RU[month]} {year}"


def format_amount(amount: Decimal | float) -> str:
    """Format amount for display with Russian formatting.
    
    Args:
        amount: Amount to format (Decimal or float)
        
    Returns:
        Formatted amount string with space as thousands separator (e.g., "1 500 ₽")
        
    Examples:
        >>> format_amount(Decimal("1500.00"))
        "1 500 ₽"
        >>> format_amount(1234567.89)
        "1 234 567,89 ₽"
    """
    if isinstance(amount, float):
        amount = Decimal(str(amount))
    
    # Format with comma as thousands separator and dot as decimal
    formatted = f"{amount:,.2f}"
    
    # Replace comma with temporary placeholder
    formatted = formatted.replace(',', '|')
    # Replace dot with comma (Russian decimal separator)
    formatted = formatted.replace('.', ',')
    # Replace placeholder with space (Russian thousands separator)
    formatted = formatted.replace('|', ' ')
    
    return f"{formatted} ₽"


def format_date(date: datetime) -> str:
    """Format date for display.
    
    Args:
        date: Date to format
        
    Returns:
        Formatted date string (e.g., "15.11.2025")
        
    Examples:
        >>> format_date(datetime(2025, 11, 15, 14, 30))
        "15.11.2025"
    """
    return date.strftime('%d.%m.%Y')


def format_datetime(date: datetime) -> str:
    """Format datetime for display.
    
    Args:
        date: Datetime to format
        
    Returns:
        Formatted datetime string (e.g., "15.11.2025 14:30")
        
    Examples:
        >>> format_datetime(datetime(2025, 11, 15, 14, 30))
        "15.11.2025 14:30"
    """
    return date.strftime('%d.%m.%Y %H:%M')


def format_expense(expense: "Expense") -> str:
    """Format expense for display in message.
    
    Args:
        expense: Expense object with loaded category relationship
        
    Returns:
        Formatted expense string with category icon, name, amount, date, and description
        
    Example output:
        🍔 Продукты - 1 500 ₽
        📅 15.11.2025
        📝 Покупка продуктов в магазине
    """
    # First line: category icon + name + amount
    lines = [
        f"{expense.category.icon} {expense.category.name} - {format_amount(expense.amount)}"
    ]
    
    # Second line: date
    lines.append(f"📅 {format_date(expense.date)}")
    
    # Third line: description (if exists)
    if expense.description:
        # Truncate long descriptions
        desc = expense.description
        if len(desc) > 100:
            desc = desc[:97] + "..."
        lines.append(f"📝 {desc}")
    
    return "\n".join(lines)


def format_category_summary(category_name: str, amount: Decimal | float) -> str:
    """Format category summary line.
    
    Args:
        category_name: Name of the category
        amount: Total amount for the category
        
    Returns:
        Formatted category summary string
        
    Example:
        >>> format_category_summary("Продукты", Decimal("1500.00"))
        "• Продукты - 1 500 ₽"
    """
    return f"• {category_name} - {format_amount(amount)}"


def truncate_text(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """Truncate text to specified length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length (default: 50)
        suffix: Suffix to add if truncated (default: "...")
        
    Returns:
        Truncated text
        
    Examples:
        >>> truncate_text("Very long text that needs truncating", 20)
        "Very long text th..."
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def format_family_expense(expense: "Expense") -> str:
    """Format expense for family view with user information.
    
    Args:
        expense: Expense object with loaded category and user relationships
        
    Returns:
        Formatted expense string with user icon, category, amount, date, and description
        
    Example output:
        👤 Иван
        🍔 Продукты - 1 500 ₽
        📅 15.11.2025
        📝 Покупка продуктов в магазине
    """
    # First line: user name
    lines = [f"👤 {expense.user.name}"]
    
    # Second line: category icon + name + amount
    lines.append(
        f"{expense.category.icon} {expense.category.name} - {format_amount(expense.amount)}"
    )
    
    # Third line: date
    lines.append(f"📅 {format_date(expense.date)}")
    
    # Fourth line: description (if exists)
    if expense.description:
        # Truncate long descriptions
        desc = expense.description
        if len(desc) > 100:
            desc = desc[:97] + "..."
        lines.append(f"📝 {desc}")
    
    return "\n".join(lines)


def format_user_contribution(user_name: str, amount: Decimal | float, total: Decimal | float) -> str:
    """Format user contribution with percentage.
    
    Args:
        user_name: Name of the user
        amount: User's total contribution
        total: Total amount for the family
        
    Returns:
        Formatted contribution string with percentage
        
    Example:
        >>> format_user_contribution("Иван", Decimal("1500.00"), Decimal("3000.00"))
        "👤 Иван - 1 500 ₽ (50.0%)"
    """
    if isinstance(amount, float):
        amount = Decimal(str(amount))
    if isinstance(total, float):
        total = Decimal(str(total))
    
    # Calculate percentage
    if total > 0:
        percentage = (amount / total) * 100
    else:
        percentage = Decimal('0')
    
    return f"👤 {user_name} - {format_amount(amount)} ({percentage:.1f}%)"


def format_family_summary(summary_data: dict) -> str:
    """Format family expenses summary.
    
    Args:
        summary_data: Dictionary with summary data containing:
            - total: Total amount
            - count: Number of expenses
            - by_category: List of category breakdowns (top 3 will be shown)
            - by_user: List of user contributions
            
    Returns:
        Formatted summary string
        
    Example output:
        💰 Всего за период: 10 500 ₽
        📝 Количество расходов: 15
        
        👥 По участникам:
        👤 Иван - 6 000 ₽ (57.1%)
        👤 Мария - 4 500 ₽ (42.9%)
        
        📊 Топ-3 категории:
        🍔 Продукты - 5 000 ₽
        🚗 Транспорт - 3 000 ₽
        🏠 Квартира - 2 500 ₽
    """
    total = summary_data['total']
    count = summary_data['count']
    by_user = summary_data.get('by_user', [])
    by_category = summary_data.get('by_category', [])
    
    lines = [
        f"💰 <b>Всего за период:</b> {format_amount(total)}",
        f"📝 <b>Количество расходов:</b> {count}",
        ""
    ]
    
    # Add user contributions
    if by_user:
        lines.append("👥 <b>По участникам:</b>")
        for user_data in by_user:
            user_name = user_data['user_name']
            amount = user_data['amount']
            lines.append(format_user_contribution(user_name, amount, total))
        lines.append("")
    
    # Add top 3 categories
    if by_category:
        lines.append("📊 <b>Топ-3 категории:</b>")
        for cat_data in by_category[:3]:  # Only top 3
            cat_name = cat_data['category_name']
            cat_icon = cat_data['category_icon']
            amount = cat_data['amount']
            lines.append(format_category_summary(cat_name, cat_icon, amount))
    
    return "\n".join(lines)

