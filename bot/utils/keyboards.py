"""Keyboard utilities for the bot.

This module contains functions for generating inline keyboards
used throughout the bot.
"""

from typing import List, Optional, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.utils.navigation import NavigationManager


def build_inline_keyboard(
    buttons: List[List[Tuple[str, str]]],
    max_columns: int = 2
) -> InlineKeyboardMarkup:
    """Build an inline keyboard from a list of button data.
    
    Args:
        buttons: List of rows, where each row is a list of (text, callback_data) tuples
        max_columns: Maximum number of columns per row (default: 2)
        
    Returns:
        InlineKeyboardMarkup object
    """
    keyboard = []
    
    for row in buttons:
        keyboard_row = [
            InlineKeyboardButton(text, callback_data=callback_data)
            for text, callback_data in row
        ]
        keyboard.append(keyboard_row)
    
    return InlineKeyboardMarkup(keyboard)


def add_navigation_buttons(
    keyboard: List[List[InlineKeyboardButton]],
    context,
    current_state: Optional[str] = None,
    show_back: bool = True,
    show_home: bool = True
) -> List[List[InlineKeyboardButton]]:
    """Add navigation buttons to existing keyboard.
    
    Args:
        keyboard: Existing keyboard buttons
        context: Telegram context object
        current_state: Current state identifier (to push to history)
        show_back: Whether to show "Back" button
        show_home: Whether to show "Home" button
        
    Returns:
        Updated keyboard with navigation buttons
    """
    nav_buttons = []
    
    # Push current state if provided
    if current_state:
        NavigationManager.push_state(context, current_state)
    
    # Check if there's a previous state
    has_previous = NavigationManager.get_previous_state(context) is not None
    
    # Add "Back" button if requested and there's a previous state
    if show_back and has_previous:
        nav_buttons.append(
            InlineKeyboardButton("◀️ Назад", callback_data="nav_back")
        )
    
    # Add "Home" button if requested
    if show_home:
        nav_buttons.append(
            InlineKeyboardButton("🏠 Главное меню", callback_data="start")
        )
    
    # Add navigation buttons as a separate row
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    return keyboard


def get_main_menu_keyboard(has_families: bool = False) -> InlineKeyboardMarkup:
    """Get main menu keyboard.
    
    Args:
        has_families: Whether user has families
        
    Returns:
        InlineKeyboardMarkup with main menu buttons
    """
    if not has_families:
        buttons = [
            [("👨‍👩‍👧 Создать семью", "create_family")],
            [("🔗 Присоединиться к семье", "join_family")],
            [("❓ Помощь", "help")]
        ]
    else:
        buttons = [
            [("➕ Добавить расход", "add_expense"), ("➕ Добавить доход", "add_income")],
            [("📊 Статистика", "stats_start"), ("🏷️ Категории", "categories")],
            [("🕘 Мои последние операции", "recent_ops")],
            [("👨‍👩‍👧‍👦 Мои семьи", "my_families"), ("➕ Создать семью", "create_family")],
            [("🔗 Присоединиться", "join_family"), ("⚙️ Настройки", "settings")],
            [("❓ Помощь", "help")]
        ]
    
    return build_inline_keyboard(buttons)


def get_back_button(callback_data: str = "back", add_home: bool = True) -> InlineKeyboardMarkup:
    """Get keyboard with a single back button.
    
    Args:
        callback_data: Callback data for the back button
        add_home: Whether to add "Home" button (default: True)
        
    Returns:
        InlineKeyboardMarkup with back button
    """
    buttons = [[("◀️ Назад", callback_data)]]
    
    if add_home:
        buttons.append([("🏠 Главное меню", "start")])
    
    return build_inline_keyboard(buttons)


def get_cancel_button(callback_data: str = "cancel", add_home: bool = True) -> InlineKeyboardMarkup:
    """Get keyboard with a single cancel button.
    
    Args:
        callback_data: Callback data for the cancel button
        add_home: Whether to add "Home" button (default: True)
        
    Returns:
        InlineKeyboardMarkup with cancel button
    """
    buttons = [[("❌ Отмена", callback_data)]]
    
    if add_home:
        buttons.append([("🏠 Главное меню", "start")])
    
    return build_inline_keyboard(buttons)


def get_confirmation_keyboard(
    confirm_callback: str,
    cancel_callback: str = "cancel",
    add_home: bool = True
) -> InlineKeyboardMarkup:
    """Get confirmation keyboard with Yes/No buttons.
    
    Args:
        confirm_callback: Callback data for confirm button
        cancel_callback: Callback data for cancel button
        add_home: Whether to add "Home" button (default: True)
        
    Returns:
        InlineKeyboardMarkup with confirmation buttons
    """
    buttons = [
        [("✅ Да", confirm_callback), ("❌ Нет", cancel_callback)]
    ]
    
    if add_home:
        buttons.append([("🏠 Главное меню", "start")])
    
    return build_inline_keyboard(buttons)


def get_currency_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for currency selection.
    
    Returns:
        InlineKeyboardMarkup with currency options
    """
    buttons = [
        [("₽ Рубль", "currency_rub"), ("$ Доллар", "currency_usd")],
        [("€ Евро", "currency_eur"), ("₴ Гривна", "currency_uah")],
        [("◀️ Назад", "settings")]
    ]
    return build_inline_keyboard(buttons)


def get_timezone_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for timezone selection.
    
    Returns:
        InlineKeyboardMarkup with timezone options
    """
    buttons = [
        [("🇷🇺 Москва (UTC+3)", "tz_europe_moscow")],
        [("🇷🇺 Екатеринбург (UTC+5)", "tz_asia_yekaterinburg")],
        [("🇷🇺 Новосибирск (UTC+7)", "tz_asia_novosibirsk")],
        [("🇷🇺 Владивосток (UTC+10)", "tz_asia_vladivostok")],
        [("🇺🇦 Киев (UTC+2)", "tz_europe_kiev")],
        [("🇰🇿 Алматы (UTC+6)", "tz_asia_almaty")],
        [("◀️ Назад", "settings")]
    ]
    return build_inline_keyboard(buttons)


def get_date_format_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for date format selection.
    
    Returns:
        InlineKeyboardMarkup with date format options
    """
    buttons = [
        [("DD.MM.YYYY (31.12.2024)", "date_format_dmy")],
        [("MM/DD/YYYY (12/31/2024)", "date_format_mdy")],
        [("YYYY-MM-DD (2024-12-31)", "date_format_ymd")],
        [("◀️ Назад", "settings")]
    ]
    return build_inline_keyboard(buttons)


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for settings menu.
    
    Returns:
        InlineKeyboardMarkup with settings options
    """
    buttons = [
        [("💱 Валюта", "settings_currency")],
        [("🌍 Часовой пояс", "settings_timezone")],
        [("📅 Формат даты", "settings_date_format")],
        [("📊 Месячная сводка", "settings_monthly_summary")],
        [("🔔 Уведомления об операциях", "settings_expense_notifications")],
        [("🏠 Главное меню", "start")]
    ]
    return build_inline_keyboard(buttons)


def get_family_settings_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Get keyboard for family settings menu.
    
    Args:
        is_admin: Whether user is admin of the family
        
    Returns:
        InlineKeyboardMarkup with family settings options
    """
    buttons = []
    
    if is_admin:
        buttons.extend([
            [("✏️ Изменить название", "family_rename")],
            [("🔄 Новый инвайт-код", "family_regenerate_code")],
            [("👥 Управление участниками", "family_manage_members")],
            [("🗑️ Удалить семью", "family_delete")]
        ])
    
    buttons.extend([
        [("🚪 Покинуть семью", "family_leave")],
        [("◀️ Назад", "my_families")]
    ])
    
    return build_inline_keyboard(buttons)


def get_pagination_keyboard(
    current_page: int,
    total_pages: int,
    prefix: str = "page"
) -> InlineKeyboardMarkup:
    """Get pagination keyboard.
    
    Args:
        current_page: Current page number (0-indexed)
        total_pages: Total number of pages
        prefix: Prefix for callback data (default: "page")
        
    Returns:
        InlineKeyboardMarkup with pagination buttons
    """
    buttons = []
    
    nav_row = []
    
    if current_page > 0:
        nav_row.append(("◀️ Пред.", f"{prefix}_prev"))
    
    nav_row.append((f"📄 {current_page + 1}/{total_pages}", f"{prefix}_current"))
    
    if current_page < total_pages - 1:
        nav_row.append(("▶️ След.", f"{prefix}_next"))
    
    buttons.append(nav_row)
    
    return build_inline_keyboard(buttons)


def get_help_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for help menu.
    
    Returns:
        InlineKeyboardMarkup with help options
    """
    buttons = [
        [("🏠 Управление семьями", "help_families")],
        [("💰 Учет финансов", "help_expenses")],
        [("📊 Аналитика", "help_stats")],
        [("⚙️ Настройки", "help_settings")],
        [("🏠 Главное меню", "start")]
    ]
    return build_inline_keyboard(buttons)


def get_add_another_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard with 'Add another expense' button.
    
    Returns:
        InlineKeyboardMarkup with add another button
    """
    buttons = [
        [("➕ Добавить еще расход", "add_expense")],
        [("🏠 Главное меню", "start")]
    ]
    return build_inline_keyboard(buttons)


def get_add_another_income_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard with 'Add another income' button.
    
    Returns:
        InlineKeyboardMarkup with add another income button
    """
    buttons = [
        [("➕ Добавить еще доход", "add_income")],
        [("🏠 Главное меню", "start")]
    ]
    return build_inline_keyboard(buttons)


def get_period_keyboard(prefix: str = "period") -> InlineKeyboardMarkup:
    """Get keyboard for period selection.
    
    Args:
        prefix: Prefix for callback data
        
    Returns:
        InlineKeyboardMarkup with period options
    """
    buttons = [
        [("📅 Сегодня", f"{prefix}_today"), ("📅 Неделя", f"{prefix}_week")],
        [("📅 Месяц", f"{prefix}_month"), ("📅 Всё время", f"{prefix}_all")],
        [("◀️ Назад", "start")]
    ]
    return build_inline_keyboard(buttons)


def get_family_selection_keyboard(
    families: List[Tuple[int, str]],
    callback_prefix: str = "select_family"
) -> InlineKeyboardMarkup:
    """Get keyboard for family selection.
    
    Args:
        families: List of (family_id, family_name) tuples
        callback_prefix: Prefix for callback data
        
    Returns:
        InlineKeyboardMarkup with family options
    """
    buttons = []
    
    for family_id, family_name in families:
        buttons.append([(f"👨‍👩‍👧 {family_name}", f"{callback_prefix}_{family_id}")])
    
    buttons.append([("◀️ Назад", "start")])
    
    return build_inline_keyboard(buttons)


def get_monthly_summary_time_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for monthly summary time selection.
    
    Returns:
        InlineKeyboardMarkup with time options
    """
    buttons = [
        [("🌅 08:00", "summary_time_08"), ("☀️ 10:00", "summary_time_10")],
        [("🌞 12:00", "summary_time_12"), ("🌆 18:00", "summary_time_18")],
        [("❌ Отключить", "summary_disable")],
        [("◀️ Назад", "settings")]
    ]
    return build_inline_keyboard(buttons)


def get_home_button() -> InlineKeyboardMarkup:
    """Get keyboard with a single home button.
    
    Returns:
        InlineKeyboardMarkup with home button
    """
    buttons = [[("🏠 Главное меню", "start")]]
    return build_inline_keyboard(buttons)


def get_my_families_home_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard with "My families" and "Home" buttons."""
    buttons = [
        [("👨‍👩‍👧‍👦 Мои семьи", "my_families")],
        [("🏠 Главное меню", "start")],
    ]
    return build_inline_keyboard(buttons)


def get_expense_notification_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for expense notifications from family members.
    
    Provides quick navigation options when receiving notification
    about a new expense from another family member.
    
    Returns:
        InlineKeyboardMarkup with navigation buttons
    """
    buttons = [
        [("➕ Добавить расход", "add_expense")],
        [("🏠 Главное меню", "start")]
    ]
    return build_inline_keyboard(buttons)


def get_income_notification_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for income notifications from family members.
    
    Provides quick navigation options when receiving notification
    about a new income from another family member.
    
    Returns:
        InlineKeyboardMarkup with navigation buttons
    """
    buttons = [
        [("➕ Добавить доход", "add_income")],
        [("🏠 Главное меню", "start")]
    ]
    return build_inline_keyboard(buttons)

