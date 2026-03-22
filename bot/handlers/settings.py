"""Settings command handler for user preferences."""

import logging
from typing import Dict, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from bot.database import crud, get_db
from bot.utils.constants import (
    CURRENCY_MAPPING,
    DATE_FORMAT_MAPPING,
    HTML_PARSE_MODE,
    TIME_MAPPING,
    TIMEZONE_MAPPING,
)
from bot.utils.keyboards import (
    get_currency_keyboard,
    get_date_format_keyboard,
    get_monthly_summary_time_keyboard,
    get_settings_keyboard,
    get_timezone_keyboard,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================

def _create_settings_text(user) -> str:
    """Create settings display text for user.
    
    Args:
        user: User object from database
        
    Returns:
        Formatted settings text
    """
    text = (
        "⚙️ <b>Настройки</b>\n\n"
        f"💱 <b>Валюта:</b> {user.currency}\n"
        f"🌍 <b>Часовой пояс:</b> {user.timezone}\n"
        f"📅 <b>Формат даты:</b> {user.date_format}\n"
        f"📊 <b>Месячная сводка:</b> "
        f"{'✅ Включена' if user.monthly_summary_enabled else '❌ Выключена'}"
    )
    
    if user.monthly_summary_enabled and user.monthly_summary_time:
        text += f" (1-го числа в {user.monthly_summary_time})"
    
    text += f"\n🔔 <b>Уведомления об операциях:</b> "
    text += "✅ Включены" if user.expense_notifications_enabled else "❌ Выключены"
    
    text += "\n\nВыберите параметр для изменения:"
    
    return text


async def _get_user_or_error(update: Update, message) -> Optional[object]:
    """Get user from database or return None with error message.
    
    Args:
        update: Telegram update object
        message: Message object to reply to
        
    Returns:
        User object or None if not found
    """
    if not update.effective_user:
        return None
    
    telegram_id = update.effective_user.id
    
    async for session in get_db():
        user = await crud.get_user_by_telegram_id(session, telegram_id)
        
        if not user:
            await message.reply_text(
                "❌ Ошибка: пользователь не найден. Используйте /start для регистрации."
            )
            return None
        
        return user


async def _update_user_setting(telegram_id: int, **kwargs) -> bool:
    """Update user settings in database.
    
    Args:
        telegram_id: User's Telegram ID
        **kwargs: Settings to update
        
    Returns:
        True if successful, False otherwise
    """
    async for session in get_db():
        user = await crud.get_user_by_telegram_id(session, telegram_id)
        
        if not user:
            return False
        
        await crud.update_user_settings(session, user.id, **kwargs)
        await session.commit()
        return True


def _get_value_from_mapping(
    callback_data: str,
    mapping: Dict[str, str]
) -> Optional[str]:
    """Get value from mapping by callback data.
    
    Args:
        callback_data: Callback query data
        mapping: Dictionary mapping callback_data to values
        
    Returns:
        Mapped value or None if not found
    """
    return mapping.get(callback_data)


# ============================================================================
# Main Settings Handler
# ============================================================================

async def settings_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle the /settings command.
    
    Shows user settings menu.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    if not update.effective_user:
        return
    
    message = update.message or update.callback_query.message
    if not message:
        return
    
    telegram_id = update.effective_user.id
    
    logger.info(f"User {telegram_id} opened settings")
    
    async for session in get_db():
        user = await crud.get_user_by_telegram_id(session, telegram_id)
        
        if not user:
            await message.reply_text(
                "❌ Ошибка: пользователь не найден. Используйте /start для регистрации."
            )
            return
        
        settings_text = _create_settings_text(user)
        keyboard = get_settings_keyboard()
        
        if update.callback_query:
            await update.callback_query.answer()
            await message.edit_text(
                settings_text,
                parse_mode=HTML_PARSE_MODE,
                reply_markup=keyboard
            )
        else:
            await message.reply_text(
                settings_text,
                parse_mode=HTML_PARSE_MODE,
                reply_markup=keyboard
            )


# ============================================================================
# Currency Settings
# ============================================================================

async def settings_currency_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show currency selection menu.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    if not update.callback_query or not update.callback_query.message:
        return
    
    await update.callback_query.answer()
    
    text = (
        "💱 <b>Выбор валюты</b>\n\n"
        "Выберите валюту для отображения сумм:"
    )
    
    keyboard = get_currency_keyboard()
    
    await update.callback_query.message.edit_text(
        text,
        parse_mode=HTML_PARSE_MODE,
        reply_markup=keyboard
    )


async def currency_selection_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle currency selection.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    if not update.callback_query or not update.effective_user:
        return
    
    callback_data = update.callback_query.data
    currency = _get_value_from_mapping(callback_data, CURRENCY_MAPPING)
    
    if not currency:
        await update.callback_query.answer("❌ Неизвестная валюта")
        return
    
    telegram_id = update.effective_user.id
    success = await _update_user_setting(telegram_id, currency=currency)
    
    if success:
        await update.callback_query.answer(f"✅ Валюта изменена на {currency}")
        await settings_command(update, context)
    else:
        await update.callback_query.answer("❌ Пользователь не найден")


# ============================================================================
# Timezone Settings
# ============================================================================

async def settings_timezone_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show timezone selection menu.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    if not update.callback_query or not update.callback_query.message:
        return
    
    await update.callback_query.answer()
    
    text = (
        "🌍 <b>Выбор часового пояса</b>\n\n"
        "Выберите ваш часовой пояс:"
    )
    
    keyboard = get_timezone_keyboard()
    
    await update.callback_query.message.edit_text(
        text,
        parse_mode=HTML_PARSE_MODE,
        reply_markup=keyboard
    )


async def timezone_selection_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle timezone selection.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    if not update.callback_query or not update.effective_user:
        return
    
    callback_data = update.callback_query.data
    timezone = _get_value_from_mapping(callback_data, TIMEZONE_MAPPING)
    
    if not timezone:
        await update.callback_query.answer("❌ Неизвестный часовой пояс")
        return
    
    telegram_id = update.effective_user.id
    success = await _update_user_setting(telegram_id, timezone=timezone)
    
    if success:
        await update.callback_query.answer("✅ Часовой пояс изменен")
        await settings_command(update, context)
    else:
        await update.callback_query.answer("❌ Пользователь не найден")


# ============================================================================
# Date Format Settings
# ============================================================================

async def settings_date_format_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show date format selection menu.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    if not update.callback_query or not update.callback_query.message:
        return
    
    await update.callback_query.answer()
    
    text = (
        "📅 <b>Выбор формата даты</b>\n\n"
        "Выберите формат отображения дат:"
    )
    
    keyboard = get_date_format_keyboard()
    
    await update.callback_query.message.edit_text(
        text,
        parse_mode=HTML_PARSE_MODE,
        reply_markup=keyboard
    )


async def date_format_selection_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle date format selection.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    if not update.callback_query or not update.effective_user:
        return
    
    callback_data = update.callback_query.data
    date_format = _get_value_from_mapping(callback_data, DATE_FORMAT_MAPPING)
    
    if not date_format:
        await update.callback_query.answer("❌ Неизвестный формат")
        return
    
    telegram_id = update.effective_user.id
    success = await _update_user_setting(telegram_id, date_format=date_format)
    
    if success:
        await update.callback_query.answer("✅ Формат даты изменен")
        await settings_command(update, context)
    else:
        await update.callback_query.answer("❌ Пользователь не найден")


# ============================================================================
# Monthly Summary Settings
# ============================================================================

async def settings_monthly_summary_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show monthly summary settings menu.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    if not update.callback_query or not update.callback_query.message:
        return
    
    await update.callback_query.answer()
    
    text = (
        "📊 <b>Месячная сводка расходов</b>\n\n"
        "1-го числа каждого месяца вы будете получать детальную сводку "
        "по всем расходам за <b>предыдущий месяц</b>.\n\n"
        "Сводка включает:\n"
        "• 💰 Общую сумму расходов\n"
        "• 📊 Разбивку по категориям\n"
        "• 📈 Сравнение с предыдущим месяцем\n"
        "• 🏆 Топ категории расходов\n\n"
        "Выберите время отправки:"
    )
    
    keyboard = get_monthly_summary_time_keyboard()
    
    await update.callback_query.message.edit_text(
        text,
        parse_mode=HTML_PARSE_MODE,
        reply_markup=keyboard
    )


async def monthly_summary_time_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle monthly summary time selection.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    if not update.callback_query or not update.effective_user:
        return
    
    callback_data = update.callback_query.data
    telegram_id = update.effective_user.id
    
    # Handle disable option
    if callback_data == "summary_disable":
        success = await _update_user_setting(
            telegram_id,
            monthly_summary_enabled=False,
            monthly_summary_time=None
        )
        
        if success:
            await update.callback_query.answer("✅ Месячная сводка отключена")
            await settings_command(update, context)
        else:
            await update.callback_query.answer("❌ Пользователь не найден")
        return
    
    # Handle time selection
    time = _get_value_from_mapping(callback_data, TIME_MAPPING)
    
    if not time:
        await update.callback_query.answer("❌ Неизвестное время")
        return
    
    success = await _update_user_setting(
        telegram_id,
        monthly_summary_enabled=True,
        monthly_summary_time=time
    )
    
    if success:
        await update.callback_query.answer(
            f"✅ Месячная сводка включена! Будет приходить 1-го числа в {time}"
        )
        await settings_command(update, context)
    else:
        await update.callback_query.answer("❌ Пользователь не найден")


# ============================================================================
# Expense Notifications Settings
# ============================================================================

async def settings_expense_notifications_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle expense notifications settings callback - toggle the setting.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    if not query or not update.effective_user:
        return
    
    telegram_id = update.effective_user.id
    
    async for session in get_db():
        user = await crud.get_user_by_telegram_id(session, telegram_id)
        
        if not user:
            await query.answer("❌ Пользователь не найден")
            return
        
        # Toggle the setting
        new_value = not user.expense_notifications_enabled
        user.expense_notifications_enabled = new_value
        await session.commit()
        
        if new_value:
            await query.answer("✅ Уведомления об операциях включены")
            logger.info(f"User {telegram_id} enabled operation notifications")
        else:
            await query.answer("❌ Уведомления об операциях отключены")
            logger.info(f"User {telegram_id} disabled operation notifications")
        
        # Refresh settings menu
        await settings_command(update, context)


# ============================================================================
# Handler Registration
# ============================================================================

settings_handler = CommandHandler("settings", settings_command)

settings_callback_handler = CallbackQueryHandler(
    settings_command,
    pattern="^settings$"
)

settings_currency_handler = CallbackQueryHandler(
    settings_currency_callback,
    pattern="^settings_currency$"
)

currency_selection_handler = CallbackQueryHandler(
    currency_selection_callback,
    pattern="^currency_(rub|usd|eur|uah)$"
)

settings_timezone_handler = CallbackQueryHandler(
    settings_timezone_callback,
    pattern="^settings_timezone$"
)

timezone_selection_handler = CallbackQueryHandler(
    timezone_selection_callback,
    pattern="^tz_"
)

settings_date_format_handler = CallbackQueryHandler(
    settings_date_format_callback,
    pattern="^settings_date_format$"
)

date_format_selection_handler = CallbackQueryHandler(
    date_format_selection_callback,
    pattern="^date_format_"
)

settings_monthly_summary_handler = CallbackQueryHandler(
    settings_monthly_summary_callback,
    pattern="^settings_monthly_summary$"
)

monthly_summary_time_handler = CallbackQueryHandler(
    monthly_summary_time_callback,
    pattern="^summary_(time_|disable)"
)

settings_expense_notifications_handler = CallbackQueryHandler(
    settings_expense_notifications_callback,
    pattern="^settings_expense_notifications$"
)
