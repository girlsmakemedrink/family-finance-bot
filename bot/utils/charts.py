"""Chart and visualization utilities for statistics display."""

from typing import Dict, List, Optional


def create_text_bar(value: float, max_value: float, length: int = 10) -> str:
    """Create a text-based progress bar.
    
    Args:
        value: Current value
        max_value: Maximum value (100%)
        length: Length of the bar in characters (default: 10)
        
    Returns:
        String with filled and empty blocks representing the percentage
        
    Examples:
        >>> create_text_bar(50, 100, 10)
        '█████░░░░░'
        >>> create_text_bar(75, 100, 10)
        '███████░░░'
    """
    if max_value <= 0:
        return '░' * length
    
    # Calculate percentage
    percentage = min(value / max_value, 1.0)
    
    # Calculate filled blocks
    filled = int(percentage * length)
    empty = length - filled
    
    # Create bar with filled and empty blocks
    bar = '█' * filled + '░' * empty
    
    return bar


def create_category_chart(category_data: List[Dict], max_categories: int = 10) -> str:
    """Create a text chart showing category breakdown with bars.
    
    Args:
        category_data: List of dictionaries with category information:
            [
                {
                    'category_name': str,
                    'category_icon': str,
                    'amount': Decimal,
                    'percentage': float
                },
                ...
            ]
        max_categories: Maximum number of categories to show (default: 10)
        
    Returns:
        Formatted string with category breakdown including text bars
        
    Example output:
        🛒 Продукты - 18,000 ₽ (39.6%)
        █████████░
        
        🚗 Транспорт - 12,000 ₽ (26.4%)
        ██████░░░░
    """
    if not category_data:
        return "📊 Нет данных по категориям"
    
    from bot.utils.formatters import format_amount
    
    lines = []
    
    # Get max amount for bar scaling
    max_amount = max(cat['amount'] for cat in category_data)
    
    # Show top N categories
    for i, cat in enumerate(category_data[:max_categories]):
        name = cat['category_name']
        amount = cat['amount']
        percentage = cat['percentage']
        
        # Format the category line
        lines.append(
            f"• {name} - {format_amount(amount)} ({percentage:.1f}%)"
        )
        
        # Add bar chart
        bar = create_text_bar(float(amount), float(max_amount), length=10)
        lines.append(bar)
        
        # Add empty line between categories (except for the last one)
        if i < len(category_data[:max_categories]) - 1:
            lines.append("")
    
    return "\n".join(lines)


def format_comparison_indicator(change_percent: float) -> str:
    """Format comparison indicator with emoji and text.
    
    Args:
        change_percent: Percentage change (positive for increase, negative for decrease)
        
    Returns:
        Formatted string with indicator
        
    Examples:
        >>> format_comparison_indicator(12.5)
        '📈 +12.5%'
        >>> format_comparison_indicator(-5.3)
        '📉 -5.3%'
        >>> format_comparison_indicator(0)
        '➡️ 0.0%'
    """
    if change_percent > 0:
        emoji = "📈"
        sign = "+"
    elif change_percent < 0:
        emoji = "📉"
        sign = ""
    else:
        emoji = "➡️"
        sign = ""
    
    return f"{emoji} {sign}{change_percent:.1f}%"


def format_statistics_message(
    stats: Dict,
    period_name: str,
    top_day: Optional[tuple] = None,
    comparison: Optional[Dict] = None
) -> str:
    """Format complete statistics message with all data.
    
    Args:
        stats: Statistics dictionary from get_period_statistics
        period_name: Name of the period (e.g., "Ноябрь 2025", "Неделя")
        top_day: Optional tuple (date, amount) for the highest expense day
        comparison: Optional comparison data from compare_periods
        
    Returns:
        Formatted statistics message ready to send
        
    Example output:
        📊 Статистика за Ноябрь 2025
        
        💰 Общая сумма: 45,500 ₽
        📝 Количество расходов: 127
        📉 Средний расход в день: 1,517 ₽
        🔥 Самый дорогой день: 15.11 - 5,600 ₽
        
        📈 Сравнение с прошлым месяцем: +12.5%
        
        📊 По категориям:
        
        🛒 Продукты - 18,000 ₽ (39.6%)
        █████████░
        
        🚗 Транспорт - 12,000 ₽ (26.4%)
        ██████░░░░
    """
    from bot.utils.formatters import format_amount, format_date
    
    lines = [
        f"📊 <b>Статистика за {period_name}</b>",
        ""
    ]
    
    # Main statistics
    lines.append(f"💰 <b>Общая сумма:</b> {format_amount(stats['total'])}")
    lines.append(f"📝 <b>Количество расходов:</b> {stats['count']}")
    
    if stats['avg_per_day'] > 0:
        lines.append(f"📉 <b>Средний расход в день:</b> {format_amount(stats['avg_per_day'])}")
    
    # Top expense day
    if top_day:
        date_obj, amount = top_day
        # Convert date object to string
        if hasattr(date_obj, 'strftime'):
            date_str = format_date(date_obj)
        else:
            date_str = str(date_obj)
        lines.append(f"🔥 <b>Самый дорогой день:</b> {date_str} - {format_amount(amount)}")
    
    # Comparison with previous period
    if comparison and comparison.get('total_change_percent') != 0:
        lines.append("")
        indicator = format_comparison_indicator(comparison['total_change_percent'])
        lines.append(f"<b>Сравнение с предыдущим периодом:</b> {indicator}")
    
    # Category breakdown
    if stats['by_category']:
        lines.append("")
        lines.append("📊 <b>По категориям:</b>")
        lines.append("")
        
        # Use create_category_chart for visual display
        chart = create_category_chart(stats['by_category'], max_categories=5)
        lines.append(chart)
    else:
        lines.append("")
        lines.append("📊 Нет расходов за выбранный период")
    
    return "\n".join(lines)


def format_period_name(period: str, start_date=None, end_date=None) -> str:
    """Format period name for display in statistics.
    
    Args:
        period: Period identifier ('today', 'week', 'month', '3months', 'year', 'all')
        start_date: Optional start date
        end_date: Optional end date
        
    Returns:
        Formatted period name in Russian
        
    Examples:
        >>> format_period_name('today')
        'Сегодня'
        >>> format_period_name('month')
        'Ноябрь 2025'
    """
    from datetime import datetime
    
    if period == "today":
        return "Сегодня"
    elif period == "week":
        return "Эта неделя"
    elif period == "month":
        now = datetime.now()
        months = [
            "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
            "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
        ]
        return f"{months[now.month - 1]} {now.year}"
    elif period == "3months":
        return "Последние 3 месяца"
    elif period == "year":
        now = datetime.now()
        return f"{now.year} год"
    elif period == "all":
        return "Все время"
    else:
        return "Период"

