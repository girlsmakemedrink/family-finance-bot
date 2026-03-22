"""Search functionality with improved architecture."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import IntEnum
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.database import crud, get_db
from bot.utils.constants import HTML_PARSE_MODE
from bot.utils.formatters import format_amount, format_expense
from bot.utils.helpers import (
    answer_query_safely as shared_answer_query_safely,
    end_conversation_silently,
    end_conversation_and_route,
    extract_id_from_callback as shared_extract_id_from_callback,
    get_user_id,
    handle_db_operation as shared_handle_db_operation,
)
from bot.utils.keyboards import get_home_button

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

class ConversationState(IntEnum):
    """Conversation states for search flow."""
    SELECT_FAMILY = 0
    SELECT_TYPE = 1
    ENTER_QUERY = 2


class CallbackPattern:
    """Callback data patterns."""
    SEARCH = "search"
    SEARCH_FAMILY_PREFIX = "search_family_"
    SEARCH_TYPE_PREFIX = "search_type_"
    SEARCH_CAT_PREFIX = "search_cat_"
    CANCEL = "cancel"
    CREATE_FAMILY = "create_family"
    JOIN_FAMILY = "join_family"
    START = "start"


MAIN_NAV_PATTERN_SEARCH_FLOW = (
    "^(start|categories|settings|help|add_expense|add_income|my_expenses|"
    "family_expenses|my_families|create_family|join_family|family_settings|"
    "stats_start|quick_expense)$"
)


class SearchType:
    """Search type identifiers."""
    DESCRIPTION = "description"
    AMOUNT = "amount"
    DATE = "date"
    CATEGORY = "category"


class Emoji:
    """Emoji constants."""
    SEARCH = "🔍"
    FAMILY = "👨‍👩‍👧‍👦"
    ERROR = "❌"
    PLUS = "➕"
    LINK = "🔗"
    NOTE = "📝"
    MONEY = "💰"
    CALENDAR = "📅"
    CATEGORY = "📂"
    EMPTY = "📭"
    USER = "👤"
    HOME = "🏠"


class ErrorMessage:
    """Error messages."""
    GENERAL = f"{Emoji.ERROR} Произошла ошибка. Попробуйте позже."
    NO_FAMILIES = f"{Emoji.ERROR} <b>У вас нет семей</b>\n\nСоздайте семью или присоединитесь к существующей, чтобы начать искать расходы."
    FAMILY_NOT_FOUND = f"{Emoji.ERROR} Семья не найдена."
    NO_CATEGORIES = f"{Emoji.ERROR} Категории не найдены."
    UNKNOWN_SEARCH_TYPE = f"{Emoji.ERROR} Неизвестный тип поиска."
    INVALID_AMOUNT_FORMAT = f"{Emoji.ERROR} Неверный формат суммы. Используйте формат: <code>100-500</code>"
    INVALID_AMOUNT = f"{Emoji.ERROR} Неверный формат суммы."
    INVALID_DATE_FORMAT = f"{Emoji.ERROR} Неверный формат даты. Используйте формат: <code>ДД.ММ.ГГГГ</code>"
    SEARCH_ERROR = f"{Emoji.ERROR} Произошла ошибка при поиске."


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class SearchData:
    """Data class for search context."""
    family_id: Optional[int] = None
    family_name: Optional[str] = None
    search_type: Optional[str] = None
    category_id: Optional[int] = None

    @classmethod
    def from_context(cls, context: ContextTypes.DEFAULT_TYPE) -> 'SearchData':
        """Create SearchData from context user_data."""
        return cls(
            family_id=context.user_data.get('search_family_id'),
            family_name=context.user_data.get('search_family_name'),
            search_type=context.user_data.get('search_type'),
            category_id=context.user_data.get('search_category_id')
        )

    def save_to_context(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Save search data to context."""
        if self.family_id is not None:
            context.user_data['search_family_id'] = self.family_id
        if self.family_name is not None:
            context.user_data['search_family_name'] = self.family_name
        if self.search_type is not None:
            context.user_data['search_type'] = self.search_type
        if self.category_id is not None:
            context.user_data['search_category_id'] = self.category_id

    def clear_from_context(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Clear search data from context."""
        context.user_data.pop('search_family_id', None)
        context.user_data.pop('search_family_name', None)
        context.user_data.pop('search_type', None)
        context.user_data.pop('search_category_id', None)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def answer_query_safely(query) -> None:
    """Answer callback query safely."""
    await shared_answer_query_safely(query)


async def send_or_edit_message(
    update: Update,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: str = HTML_PARSE_MODE
) -> None:
    """Send new message or edit existing one."""
    # In real Telegram updates, message and callback_query are mutually exclusive.
    # Prioritizing message branch improves compatibility with unit-test mocks.
    if update.message:
        await update.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
        return

    query = update.callback_query
    if query:
        await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=reply_markup)


def extract_id_from_callback(callback_data: str) -> int:
    """Extract numeric ID from callback data."""
    return shared_extract_id_from_callback(callback_data)


async def handle_db_operation(operation, error_message: str):
    """Handle database operations with error handling."""
    return await shared_handle_db_operation(operation, error_message)


# ============================================================================
# MESSAGE BUILDERS
# ============================================================================

class MessageBuilder:
    """Builder class for creating formatted messages."""
    
    @staticmethod
    def build_family_selection_message() -> str:
        """Build message for family selection."""
        return f"{Emoji.SEARCH} <b>Поиск расходов</b>\n\nВыберите семью для поиска:"
    
    @staticmethod
    def build_type_selection_message(family_name: str) -> str:
        """Build message for search type selection."""
        return (
            f"{Emoji.SEARCH} <b>Поиск расходов</b>\n"
            f"{Emoji.FAMILY} Семья: <b>{family_name}</b>\n\n"
            "Выберите тип поиска:"
        )
    
    @staticmethod
    def build_description_prompt(family_name: str) -> str:
        """Build prompt for description search."""
        return (
            f"{Emoji.SEARCH} <b>Поиск по описанию</b>\n"
            f"{Emoji.FAMILY} Семья: <b>{family_name}</b>\n\n"
            "Введите текст для поиска в описании расходов:"
        )
    
    @staticmethod
    def build_amount_prompt(family_name: str) -> str:
        """Build prompt for amount search."""
        return (
            f"{Emoji.MONEY} <b>Поиск по сумме</b>\n"
            f"{Emoji.FAMILY} Семья: <b>{family_name}</b>\n\n"
            "Введите диапазон сумм в формате:\n"
            "<code>мин-макс</code> (например: <code>100-500</code>)\n"
            "или просто сумму для точного поиска."
        )
    
    @staticmethod
    def build_date_prompt(family_name: str) -> str:
        """Build prompt for date search."""
        return (
            f"{Emoji.CALENDAR} <b>Поиск по дате</b>\n"
            f"{Emoji.FAMILY} Семья: <b>{family_name}</b>\n\n"
            "Введите дату или период:\n"
            "• <code>ДД.ММ.ГГГГ</code> - конкретная дата\n"
            "• <code>ДД.ММ-ДД.ММ</code> - период\n"
            "Пример: <code>01.01.2024</code> или <code>01.01-31.01</code>"
        )
    
    @staticmethod
    def build_category_prompt(family_name: str) -> str:
        """Build prompt for category selection."""
        return (
            f"{Emoji.CATEGORY} <b>Поиск по категории</b>\n"
            f"{Emoji.FAMILY} Семья: <b>{family_name}</b>\n\n"
            "Выберите категорию:"
        )
    
    @staticmethod
    def build_results_message(family_name: str, expenses: list) -> str:
        """Build search results message."""
        if not expenses:
            return (
                f"{Emoji.SEARCH} <b>Результаты поиска</b>\n"
                f"{Emoji.FAMILY} Семья: <b>{family_name}</b>\n\n"
                f"{Emoji.EMPTY} Расходы не найдены."
            )
        
        message = (
            f"{Emoji.SEARCH} <b>Результаты поиска</b>\n"
            f"{Emoji.FAMILY} Семья: <b>{family_name}</b>\n"
            f"{Emoji.NOTE} Найдено: <b>{len(expenses)}</b>\n\n"
        )
        
        for expense in expenses[:10]:
            message += format_expense(expense) + "\n"
            message += f"{Emoji.USER} {expense.user.name}\n\n"
        
        if len(expenses) > 10:
            message += f"\n... и еще {len(expenses) - 10} расходов\n"
        
        total = sum(exp.amount for exp in expenses)
        message += f"\n{Emoji.MONEY} <b>Итого:</b> {format_amount(total)}"
        
        return message


# ============================================================================
# KEYBOARD BUILDERS
# ============================================================================

class KeyboardBuilder:
    """Builder class for creating keyboards."""

    @staticmethod
    def _as_markup(buttons: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
        """Wrap button matrix into Telegram inline keyboard markup."""
        return InlineKeyboardMarkup(buttons)

    @staticmethod
    def _with_cancel_button(buttons: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
        """Append cancel button and wrap keyboard markup."""
        buttons.append([InlineKeyboardButton(f"{Emoji.ERROR} Отменить", callback_data=CallbackPattern.CANCEL)])
        return KeyboardBuilder._as_markup(buttons)

    @staticmethod
    def build_no_families_keyboard() -> InlineKeyboardMarkup:
        """Build keyboard when user has no families."""
        return KeyboardBuilder._as_markup([
            [InlineKeyboardButton(f"{Emoji.PLUS} Создать семью", callback_data=CallbackPattern.CREATE_FAMILY)],
            [InlineKeyboardButton(f"{Emoji.LINK} Присоединиться к семье", callback_data=CallbackPattern.JOIN_FAMILY)]
        ])
    
    @staticmethod
    def build_family_selection_keyboard(families: list) -> InlineKeyboardMarkup:
        """Build keyboard for family selection."""
        keyboard = [
            [InlineKeyboardButton(
                f"{Emoji.FAMILY} {family.family.name}",
                callback_data=f"{CallbackPattern.SEARCH_FAMILY_PREFIX}{family.family.id}"
            )]
            for family in families
        ]
        return KeyboardBuilder._with_cancel_button(keyboard)
    
    @staticmethod
    def build_type_selection_keyboard() -> InlineKeyboardMarkup:
        """Build keyboard for search type selection."""
        return KeyboardBuilder._as_markup([
            [InlineKeyboardButton(f"{Emoji.NOTE} По описанию", callback_data=f"{CallbackPattern.SEARCH_TYPE_PREFIX}{SearchType.DESCRIPTION}")],
            [InlineKeyboardButton(f"{Emoji.MONEY} По сумме", callback_data=f"{CallbackPattern.SEARCH_TYPE_PREFIX}{SearchType.AMOUNT}")],
            [InlineKeyboardButton(f"{Emoji.CALENDAR} По дате", callback_data=f"{CallbackPattern.SEARCH_TYPE_PREFIX}{SearchType.DATE}")],
            [InlineKeyboardButton(f"{Emoji.CATEGORY} По категории", callback_data=f"{CallbackPattern.SEARCH_TYPE_PREFIX}{SearchType.CATEGORY}")],
            [InlineKeyboardButton(f"{Emoji.ERROR} Отменить", callback_data=CallbackPattern.CANCEL)]
        ])
    
    @staticmethod
    def build_cancel_keyboard() -> InlineKeyboardMarkup:
        """Build keyboard with only cancel button."""
        return KeyboardBuilder._as_markup([
            [InlineKeyboardButton(f"{Emoji.ERROR} Отменить", callback_data=CallbackPattern.CANCEL)]
        ])
    
    @staticmethod
    def build_category_selection_keyboard(categories: list) -> InlineKeyboardMarkup:
        """Build keyboard for category selection."""
        keyboard = [
            [InlineKeyboardButton(
                category.name,
                callback_data=f"{CallbackPattern.SEARCH_CAT_PREFIX}{category.id}"
            )]
            for category in categories
        ]
        return KeyboardBuilder._with_cancel_button(keyboard)
    
    @staticmethod
    def build_results_keyboard() -> InlineKeyboardMarkup:
        """Build keyboard for search results."""
        return KeyboardBuilder._as_markup([
            [InlineKeyboardButton(f"{Emoji.SEARCH} Новый поиск", callback_data=CallbackPattern.SEARCH)],
            [InlineKeyboardButton(f"{Emoji.HOME} Главное меню", callback_data=CallbackPattern.START)]
        ])


# ============================================================================
# HANDLERS
# ============================================================================

async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start search process."""
    query = update.callback_query
    await answer_query_safely(query)
    
    user_id = await get_user_id(update, context)
    if not user_id:
        return ConversationHandler.END
    
    async def get_families(session):
        return await crud.get_user_families(session, user_id)
    
    families = await handle_db_operation(get_families, "Error in search_start")
    
    if families is None:
        keyboard = get_home_button()
        await send_or_edit_message(update, ErrorMessage.GENERAL, reply_markup=keyboard)
        return ConversationHandler.END
    
    if not families:
        message = ErrorMessage.NO_FAMILIES
        keyboard = KeyboardBuilder.build_no_families_keyboard()
        await send_or_edit_message(update, message, reply_markup=keyboard)
        return ConversationHandler.END
    
    if len(families) == 1:
        search_data = SearchData(
            family_id=families[0].family.id,
            family_name=families[0].family.name
        )
        search_data.save_to_context(context)
        return await show_search_type_selection(update, context)
    
    message = MessageBuilder.build_family_selection_message()
    keyboard = KeyboardBuilder.build_family_selection_keyboard(families)
    await send_or_edit_message(update, message, reply_markup=keyboard)
    
    return ConversationState.SELECT_FAMILY


async def search_family_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle family selection for search."""
    query = update.callback_query
    await query.answer()
    
    family_id = extract_id_from_callback(query.data)
    
    async def get_family(session):
        return await crud.get_family_by_id(session, family_id)
    
    family = await handle_db_operation(get_family, f"Error getting family {family_id}")
    
    if not family:
        keyboard = get_home_button()
        await query.edit_message_text(ErrorMessage.FAMILY_NOT_FOUND, reply_markup=keyboard)
        return ConversationHandler.END
    
    search_data = SearchData(family_id=family_id, family_name=family.name)
    search_data.save_to_context(context)
    
    return await show_search_type_selection(update, context)


async def show_search_type_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show search type selection."""
    search_data = SearchData.from_context(context)
    
    message = MessageBuilder.build_type_selection_message(search_data.family_name)
    keyboard = KeyboardBuilder.build_type_selection_keyboard()
    await send_or_edit_message(update, message, reply_markup=keyboard)
    
    return ConversationState.SELECT_TYPE


async def search_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle search type selection."""
    query = update.callback_query
    await query.answer()
    
    search_type = query.data.split('_')[-1]
    search_data = SearchData.from_context(context)
    search_data.search_type = search_type
    search_data.save_to_context(context)
    
    if search_type == SearchType.DESCRIPTION:
        message = MessageBuilder.build_description_prompt(search_data.family_name)
    elif search_type == SearchType.AMOUNT:
        message = MessageBuilder.build_amount_prompt(search_data.family_name)
    elif search_type == SearchType.DATE:
        message = MessageBuilder.build_date_prompt(search_data.family_name)
    elif search_type == SearchType.CATEGORY:
        return await show_category_selection_for_search(update, context)
    else:
        keyboard = get_home_button()
        await query.edit_message_text(ErrorMessage.UNKNOWN_SEARCH_TYPE, reply_markup=keyboard)
        return ConversationHandler.END
    
    keyboard = KeyboardBuilder.build_cancel_keyboard()
    await query.edit_message_text(message, parse_mode=HTML_PARSE_MODE, reply_markup=keyboard)
    
    return ConversationState.ENTER_QUERY


async def show_category_selection_for_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show category selection for search."""
    query = update.callback_query
    search_data = SearchData.from_context(context)
    
    async def get_categories(session):
        return await crud.get_available_categories(session, search_data.family_id)
    
    categories = await handle_db_operation(get_categories, "Error showing categories for search")
    
    if not categories:
        keyboard = get_home_button()
        await query.edit_message_text(ErrorMessage.NO_CATEGORIES, reply_markup=keyboard)
        return ConversationHandler.END
    
    message = MessageBuilder.build_category_prompt(search_data.family_name)
    keyboard = KeyboardBuilder.build_category_selection_keyboard(categories)
    await query.edit_message_text(message, parse_mode=HTML_PARSE_MODE, reply_markup=keyboard)
    
    return ConversationState.ENTER_QUERY


async def search_query_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle search query input."""
    query_text = None
    is_callback = False
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        is_callback = True
        if query.data.startswith(CallbackPattern.SEARCH_CAT_PREFIX):
            category_id = extract_id_from_callback(query.data)
            search_data = SearchData.from_context(context)
            search_data.category_id = category_id
            search_data.save_to_context(context)
    else:
        query_text = update.message.text.strip()
    
    search_data = SearchData.from_context(context)
    
    async def perform_search(session):
        search_params = {
            'session': session,
            'entity_id': search_data.family_id,
            'is_family': True
        }
        
        if search_data.search_type == SearchType.DESCRIPTION:
            search_params['query'] = query_text
        
        elif search_data.search_type == SearchType.AMOUNT:
            if '-' in query_text:
                parts = query_text.split('-')
                try:
                    search_params['min_amount'] = Decimal(parts[0].strip())
                    search_params['max_amount'] = Decimal(parts[1].strip())
                except (InvalidOperation, ValueError):
                    return None, ErrorMessage.INVALID_AMOUNT_FORMAT
            else:
                try:
                    amount = Decimal(query_text)
                    search_params['min_amount'] = amount
                    search_params['max_amount'] = amount
                except (InvalidOperation, ValueError):
                    return None, ErrorMessage.INVALID_AMOUNT
        
        elif search_data.search_type == SearchType.DATE:
            try:
                if '-' in query_text and '.' in query_text:
                    parts = query_text.split('-')
                    date_from_str = parts[0].strip()
                    date_to_str = parts[1].strip()
                    current_year = datetime.now().year
                    date_from = datetime.strptime(f"{date_from_str}.{current_year}", "%d.%m.%Y")
                    date_to = datetime.strptime(f"{date_to_str}.{current_year}", "%d.%m.%Y")
                    search_params['date_from'] = date_from
                    search_params['date_to'] = date_to + timedelta(days=1)
                else:
                    date = datetime.strptime(query_text, "%d.%m.%Y")
                    search_params['date_from'] = date
                    search_params['date_to'] = date + timedelta(days=1)
            except ValueError:
                return None, ErrorMessage.INVALID_DATE_FORMAT
        
        elif search_data.search_type == SearchType.CATEGORY:
            search_params['category_id'] = search_data.category_id
        
        expenses = await crud.search_expenses(**search_params)
        return expenses, None
    
    result = await handle_db_operation(perform_search, "Error performing search")
    
    keyboard = get_home_button()
    if result is None:
        error_msg = ErrorMessage.SEARCH_ERROR
        if is_callback:
            await update.callback_query.edit_message_text(error_msg, parse_mode=HTML_PARSE_MODE, reply_markup=keyboard)
        else:
            await update.message.reply_text(error_msg, parse_mode=HTML_PARSE_MODE, reply_markup=keyboard)
        return ConversationHandler.END
    
    expenses, error_msg = result
    
    if error_msg:
        if is_callback:
            await update.callback_query.edit_message_text(error_msg, parse_mode=HTML_PARSE_MODE, reply_markup=keyboard)
        else:
            await update.message.reply_text(error_msg, parse_mode=HTML_PARSE_MODE, reply_markup=keyboard)
        return ConversationHandler.END
    
    message = MessageBuilder.build_results_message(search_data.family_name, expenses)
    keyboard = KeyboardBuilder.build_results_keyboard()
    
    if is_callback:
        await update.callback_query.edit_message_text(message, parse_mode=HTML_PARSE_MODE, reply_markup=keyboard)
    else:
        await update.message.reply_text(message, parse_mode=HTML_PARSE_MODE, reply_markup=keyboard)
    
    return ConversationHandler.END


async def cancel_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel search."""
    return await end_conversation_silently(update, context)


# ============================================================================
# CONVERSATION HANDLER
# ============================================================================

search_handler = ConversationHandler(
    entry_points=[
        CommandHandler('search', search_start),
        CallbackQueryHandler(search_start, pattern=f'^{CallbackPattern.SEARCH}$')
    ],
    states={
        ConversationState.SELECT_FAMILY: [
            CallbackQueryHandler(search_family_selected, pattern=f'^{CallbackPattern.SEARCH_FAMILY_PREFIX}\\d+$')
        ],
        ConversationState.SELECT_TYPE: [
            CallbackQueryHandler(search_type_selected, pattern=f'^{CallbackPattern.SEARCH_TYPE_PREFIX}(description|amount|date|category)$')
        ],
        ConversationState.ENTER_QUERY: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, search_query_received),
            CallbackQueryHandler(search_query_received, pattern=f'^{CallbackPattern.SEARCH_CAT_PREFIX}\\d+$')
        ],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_search, pattern=f'^{CallbackPattern.CANCEL}$'),
        CommandHandler('cancel', cancel_search),
        CallbackQueryHandler(end_conversation_silently, pattern="^nav_back$"),
        # Main navigation fallbacks - end conversation and route to new section
        CallbackQueryHandler(end_conversation_and_route, pattern=MAIN_NAV_PATTERN_SEARCH_FLOW)
    ],
    allow_reentry=True,
    name="search_conversation",
    persistent=False,
    per_chat=True,
    per_user=True,
    per_message=False  # False because handler uses MessageHandler and CommandHandler
)
