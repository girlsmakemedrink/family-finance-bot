"""Help command handler with detailed information."""

import logging

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from bot.utils.constants import HTML_PARSE_MODE
from bot.utils.keyboards import get_back_button, get_help_keyboard
from bot.utils.message_utils import MessageHandler as MsgHandler

logger = logging.getLogger(__name__)


# ============================================================================
# Help Text Constants
# ============================================================================

HELP_MAIN_TEXT = (
    "📚 <b>Справка по Family Finance Bot</b>\n\n"
    "🤖 Я помогаю вести учет финансов всей семьи!\n\n"
    "Выберите раздел для получения подробной информации 👇"
)

HELP_FAMILIES_TEXT = (
    "🏠 <b>Управление семьями</b>\n\n"
    
    "<b>📝 Создание семьи:</b>\n"
    "/create_family - Создать новую семью\n"
    "После создания вы автоматически становитесь администратором.\n\n"
    
    "<b>🔗 Присоединение к семье:</b>\n"
    "/join_family - Присоединиться по инвайт-коду\n"
    "Попросите администратора семьи отправить код приглашения.\n\n"
    
    "<b>👨‍👩‍👧‍👦 Управление:</b>\n"
    "/families - Список всех ваших семей\n"
    "/family_info - Информация о текущей семье\n"
    "/invite - Получить код приглашения (для приглашения других)\n"
    "/family_settings - Настройки семьи (только для администраторов)\n\n"
    
    "💡 <b>Совет:</b> Вы можете состоять в нескольких семьях одновременно!"
)

HELP_EXPENSES_TEXT = (
    "💰 <b>Учет финансов</b>\n\n"
    
    "<b>➕ Добавление расходов:</b>\n"
    "/add_expense - Добавить новый расход\n"
    "Укажите сумму, категорию и описание (опционально).\n\n"
    
    "<b>➕ Добавление доходов:</b>\n"
    "/add_income - Добавить новый доход\n"
    "Укажите сумму, категорию и описание (опционально).\n\n"
    
    "<b>📊 Просмотр расходов:</b>\n"
    "/stats - Статистика расходов\n"
    "Доступна личная статистика и статистика всей семьи.\n\n"
    
    "<b>🏷️ Категории:</b>\n"
    "/categories - Управление категориями\n"
    "Категории разделены для расходов и доходов.\n\n"
    
    "<b>🔍 Примеры использования:</b>\n"
    "• Продукты - 2500₽\n"
    "• Транспорт - 500₽ (такси до работы)\n"
    "• Развлечения - 1200₽ (кино)\n\n"
    
    "💡 <b>Совет:</b> Добавляйте описания к расходам для лучшей детализации!"
)

HELP_STATS_TEXT = (
    "📊 <b>Аналитика и статистика</b>\n\n"
    
    "<b>📈 Статистика:</b>\n"
    "/stats - Подробная статистика доходов и расходов\n"
    "Доступна личная и семейная статистика за любой месяц или год.\n\n"
    
    "<b>📉 Что показывает статистика:</b>\n"
    "• Общая сумма доходов и расходов\n"
    "• Баланс (доходы - расходы)\n"
    "• Количество транзакций\n"
    "• Разбивка по категориям\n"
    "• Процентное соотношение\n"
    "• Средние расходы в день\n"
    "• Графики и диаграммы\n\n"
    
    "<b>👥 Семейная аналитика:</b>\n"
    "• Кто сколько потратил\n"
    "• Самые популярные категории\n"
    "• Динамика расходов\n\n"
    
    "💡 <b>Совет:</b> Регулярно проверяйте статистику для контроля бюджета!"
)

HELP_SETTINGS_TEXT = (
    "⚙️ <b>Настройки</b>\n\n"
    
    "<b>👤 Личные настройки:</b>\n"
    "/settings - Ваши персональные настройки\n\n"
    
    "<b>Доступные опции:</b>\n"
    "💱 <b>Валюта</b> - Выбор валюты отображения (₽, $, €, ₴)\n"
    "🌍 <b>Часовой пояс</b> - Корректное отображение времени\n"
    "📅 <b>Формат даты</b> - DD.MM.YYYY или MM/DD/YYYY\n"
    "🔔 <b>Ежедневная сводка</b> - Получение сводки расходов\n\n"
    
    "<b>👨‍👩‍👧 Настройки семьи:</b>\n"
    "/family_settings - Настройки семьи (только для админов)\n\n"
    
    "<b>Что может администратор:</b>\n"
    "• Изменить название семьи\n"
    "• Сгенерировать новый инвайт-код\n"
    "• Управлять участниками\n"
    "• Удалить семью\n\n"
    
    "💡 <b>Совет:</b> Настройте ежедневную сводку, чтобы быть в курсе расходов!"
)


# ============================================================================
# Helper Functions
# ============================================================================

async def _show_help_section(
    update: Update,
    text: str,
    back_pattern: str = "help"
) -> None:
    """Show help section with back button.
    
    Args:
        update: Telegram update object
        text: Help text to display
        back_pattern: Pattern for back button
    """
    if not update.callback_query or not update.callback_query.message:
        return
    
    await update.callback_query.answer()
    
    keyboard = get_back_button(back_pattern)
    
    await update.callback_query.message.edit_text(
        text,
        parse_mode=HTML_PARSE_MODE,
        reply_markup=keyboard
    )


# ============================================================================
# Main Help Handler
# ============================================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle the /help command.
    
    Shows detailed help information with quick access buttons.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    if not update.effective_user:
        return
    
    logger.info(f"User {update.effective_user.id} requested help")
    
    keyboard = get_help_keyboard()
    
    await MsgHandler.send_or_edit(update, HELP_MAIN_TEXT, reply_markup=keyboard)


# ============================================================================
# Help Section Handlers
# ============================================================================

async def help_families_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show help about family management.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    await _show_help_section(update, HELP_FAMILIES_TEXT)


async def help_expenses_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show help about expense tracking.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    await _show_help_section(update, HELP_EXPENSES_TEXT)


async def help_stats_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show help about statistics and analytics.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    await _show_help_section(update, HELP_STATS_TEXT)


async def help_settings_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show help about settings.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    await _show_help_section(update, HELP_SETTINGS_TEXT)


# ============================================================================
# Handler Registration
# ============================================================================

help_handler = CommandHandler("help", help_command)
help_callback_handler = CallbackQueryHandler(help_command, pattern="^help$")

help_families_handler = CallbackQueryHandler(
    help_families_callback,
    pattern="^help_families$"
)

help_expenses_handler = CallbackQueryHandler(
    help_expenses_callback,
    pattern="^help_expenses$"
)

help_stats_handler = CallbackQueryHandler(
    help_stats_callback,
    pattern="^help_stats$"
)

help_settings_handler = CallbackQueryHandler(
    help_settings_callback,
    pattern="^help_settings$"
)
