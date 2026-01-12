"""Expense management handlers with improved architecture."""

import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import IntEnum
from typing import Optional, List, Dict, Tuple

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
# CSV export removed - imports commented out
# from bot.utils.export import generate_csv, generate_csv_filename
from bot.utils.formatters import (
    format_amount,
    format_category_summary,
    format_date,
    format_expense,
    format_family_expense,
    format_family_summary,
)
from bot.utils.helpers import end_conversation_silently, end_conversation_and_route, get_user_id, notify_large_expense, notify_expense_to_family
from bot.utils.keyboards import add_navigation_buttons, get_add_another_keyboard, get_home_button

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

class ConversationState(IntEnum):
    """Conversation states for expense flows."""
    # Add expense states
    SELECT_FAMILY = 0
    SELECT_CATEGORY = 1
    ENTER_AMOUNT = 2
    ENTER_DESCRIPTION = 3
    # Create category during expense addition
    CREATE_CATEGORY_NAME = 8
    CREATE_CATEGORY_EMOJI = 9
    # View expenses states
    VIEW_SELECT_FAMILY = 4
    VIEW_SELECT_PERIOD = 5
    # Family expenses states
    FAMILY_VIEW_SELECT_FAMILY = 6
    FAMILY_VIEW_SELECT_PERIOD = 7


class CallbackPattern:
    """Callback data patterns."""
    ADD_EXPENSE = "add_expense"
    MY_EXPENSES = "my_expenses"
    FAMILY_EXPENSES = "family_expenses"
    SELECT_FAMILY_PREFIX = "select_family_"
    SELECT_CATEGORY_PREFIX = "select_category_"
    CREATE_NEW_CATEGORY = "create_new_category"
    NEW_CAT_EMOJI_PREFIX = "new_cat_emoji_"
    SKIP_DESCRIPTION = "skip_description"
    VIEW_FAMILY_PREFIX = "view_family_"
    PERIOD_PREFIX = "period_"
    PAGE_PREV = "page_prev"
    PAGE_NEXT = "page_next"
    PAGE_CURRENT = "page_current"
    MY_EXPORT = "my_export"
    # MY_EXPORT_CSV = "my_export_csv"  # CSV export removed
    MY_EXPORT_GDOCS = "my_export_gdocs"
    MY_DETAILED_REPORT = "my_detailed_report"
    DETAILED_REPORT_TYPE_PREFIX = "dr_type_"
    DETAILED_REPORT_MONTH_PREFIX = "dr_month_"
    DETAILED_REPORT_YEAR_PREFIX = "dr_year_"
    FAMILY_VIEW_PREFIX = "family_view_"
    FAMILY_PERIOD_PREFIX = "family_period_"
    FAMILY_GROUP_USER = "family_group_user"
    FAMILY_GROUP_CATEGORY = "family_group_category"
    FAMILY_GROUP_DEFAULT = "family_group_default"
    FAMILY_PAGE_PREV = "family_page_prev"
    FAMILY_PAGE_NEXT = "family_page_next"
    FAMILY_PAGE_CURRENT = "family_page_current"
    FAMILY_EXPORT = "family_export"
    # FAMILY_EXPORT_CSV = "family_export_csv"  # CSV export removed
    FAMILY_EXPORT_GDOCS = "family_export_gdocs"
    FAMILY_DETAILED_REPORT = "family_detailed_report"
    CREATE_FAMILY = "create_family"
    JOIN_FAMILY = "join_family"
    MY_FAMILIES = "my_families"
    NAV_BACK = "nav_back"
    CANCEL_ADD = "cancel_add_expense"
    CANCEL_VIEW = "cancel_view_expenses"
    CANCEL_FAMILY = "cancel_family_expenses"


class ValidationLimits:
    """Validation limits for inputs."""
    MAX_AMOUNT = Decimal('999999999.99')
    MIN_AMOUNT = Decimal('0')
    MAX_DESCRIPTION_LENGTH = 500
    ITEMS_PER_PAGE = 10


class Emoji:
    """Emoji constants."""
    ERROR = "❌"
    SUCCESS = "✅"
    CHECK = "✅"
    MONEY = "💰"
    FAMILY = "👨‍👩‍👧‍👦"
    CATEGORY = "📂"
    CALENDAR = "📅"
    TODAY = "📆"
    WEEK = "📅"
    MONTH = "🗓"
    ALL = "📚"
    STATS = "📊"
    DESCRIPTION = "📝"
    BACK = "⬅️"
    FORWARD = "➡️"  
    PAGE = "📄"
    EXPORT = "📄"
    REFRESH = "🔄"
    EMPTY = "📭"
    LINK = "🔗"
    PLUS = "➕"
    SKIP = "⏭"
    LOADING = "⏳"
    USER = "👤"
    USER = "👤"
    USERS = "👥"
    REACTION_THUMB = "👍"


class ErrorMessage:
    """Error messages."""
    NOT_REGISTERED = f"{Emoji.ERROR} Вы не зарегистрированы. Используйте команду /start для регистрации."
    NO_FAMILIES = f"{Emoji.ERROR} Вы не состоите ни в одной семье.\n\nСначала создайте семью или присоединитесь к существующей."
    NO_CATEGORIES = f"{Emoji.ERROR} Категории расходов не найдены.\n\nОбратитесь к администратору для настройки категорий."
    FAMILY_NOT_FOUND = f"{Emoji.ERROR} Семья не найдена."
    CATEGORY_NOT_FOUND = f"{Emoji.ERROR} Категория не найдена."
    GENERAL_ERROR = f"{Emoji.ERROR} Произошла ошибка. Пожалуйста, попробуйте позже."
    MISSING_DATA = f"{Emoji.ERROR} Ошибка: отсутствуют данные."
    INVALID_AMOUNT = f"{Emoji.ERROR} Некорректная сумма.\n\nПожалуйста, введите положительное число.\nПримеры: 100, 250.50, 1000,99"
    INVALID_NUMBER = f"{Emoji.ERROR} Пожалуйста, введите числовую сумму."
    DESCRIPTION_TOO_LONG = f"{Emoji.ERROR} Описание слишком длинное. Максимум {ValidationLimits.MAX_DESCRIPTION_LENGTH} символов.\nПожалуйста, введите более короткое описание."
    NO_EXPORT_DATA = f"{Emoji.ERROR} Нет данных для экспорта."
    EXPORT_ERROR = f"{Emoji.ERROR} Ошибка при создании файла."


class Period:
    """Period identifiers and names."""
    TODAY = "today"
    WEEK = "week"
    MONTH = "month"
    ALL = "all"
    
    NAMES = {
        TODAY: "Сегодня",
        WEEK: "За неделю",
        MONTH: "За месяц",
        ALL: "За все время"
    }
    
    @classmethod
    def get_name(cls, period: str) -> str:
        """Get human-readable period name."""
        return cls.NAMES.get(period, "Неизвестный период")


class Grouping:
    """Grouping options for family expenses."""
    DEFAULT = "default"
    BY_USER = "by_user"
    BY_CATEGORY = "by_category"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ExpenseData:
    """Data class for expense creation."""
    family_id: Optional[int] = None
    family_name: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    category_icon: Optional[str] = None
    amount: Optional[Decimal] = None
    description: Optional[str] = None

    @classmethod
    def from_context(cls, context: ContextTypes.DEFAULT_TYPE, prefix: str = "expense") -> 'ExpenseData':
        """Create ExpenseData from context user_data."""
        return cls(
            family_id=context.user_data.get(f'{prefix}_family_id'),
            family_name=context.user_data.get(f'{prefix}_family_name'),
            category_id=context.user_data.get(f'{prefix}_category_id'),
            category_name=context.user_data.get(f'{prefix}_category_name'),
            category_icon=context.user_data.get(f'{prefix}_category_icon'),
            amount=context.user_data.get(f'{prefix}_amount'),
            description=context.user_data.get(f'{prefix}_description')
        )

    def save_to_context(self, context: ContextTypes.DEFAULT_TYPE, prefix: str = "expense") -> None:
        """Save expense data to context."""
        if self.family_id is not None:
            context.user_data[f'{prefix}_family_id'] = self.family_id
        if self.family_name is not None:
            context.user_data[f'{prefix}_family_name'] = self.family_name
        if self.category_id is not None:
            context.user_data[f'{prefix}_category_id'] = self.category_id
        if self.category_name is not None:
            context.user_data[f'{prefix}_category_name'] = self.category_name
        if self.category_icon is not None:
            context.user_data[f'{prefix}_category_icon'] = self.category_icon
        if self.amount is not None:
            context.user_data[f'{prefix}_amount'] = self.amount
        if self.description is not None:
            context.user_data[f'{prefix}_description'] = self.description

    def clear_from_context(self, context: ContextTypes.DEFAULT_TYPE, prefix: str = "expense") -> None:
        """Clear expense data from context."""
        context.user_data.pop(f'{prefix}_family_id', None)
        context.user_data.pop(f'{prefix}_family_name', None)
        context.user_data.pop(f'{prefix}_category_id', None)
        context.user_data.pop(f'{prefix}_category_name', None)
        context.user_data.pop(f'{prefix}_category_icon', None)
        context.user_data.pop(f'{prefix}_amount', None)
        context.user_data.pop(f'{prefix}_description', None)


@dataclass
class ViewData:
    """Data class for viewing expenses."""
    family_id: Optional[int] = None
    family_name: Optional[str] = None
    period: str = Period.ALL
    page: int = 0
    grouping: str = Grouping.DEFAULT

    @classmethod
    def from_context(cls, context: ContextTypes.DEFAULT_TYPE, prefix: str = "view") -> 'ViewData':
        """Create ViewData from context user_data."""
        return cls(
            family_id=context.user_data.get(f'{prefix}_family_id'),
            family_name=context.user_data.get(f'{prefix}_family_name', 'Unknown'),
            period=context.user_data.get(f'{prefix}_period', Period.ALL),
            page=context.user_data.get(f'{prefix}_page', 0),
            grouping=context.user_data.get(f'{prefix}_grouping', Grouping.DEFAULT)
        )

    def save_to_context(self, context: ContextTypes.DEFAULT_TYPE, prefix: str = "view") -> None:
        """Save view data to context."""
        if self.family_id is not None:
            context.user_data[f'{prefix}_family_id'] = self.family_id
        if self.family_name is not None:
            context.user_data[f'{prefix}_family_name'] = self.family_name
        context.user_data[f'{prefix}_period'] = self.period
        context.user_data[f'{prefix}_page'] = self.page
        context.user_data[f'{prefix}_grouping'] = self.grouping

    def clear_from_context(self, context: ContextTypes.DEFAULT_TYPE, prefix: str = "view") -> None:
        """Clear view data from context."""
        context.user_data.pop(f'{prefix}_family_id', None)
        context.user_data.pop(f'{prefix}_family_name', None)
        context.user_data.pop(f'{prefix}_period', None)
        context.user_data.pop(f'{prefix}_page', None)
        context.user_data.pop(f'{prefix}_grouping', None)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def answer_query_safely(query) -> None:
    """Answer callback query safely, ignoring errors."""
    if query:
        try:
            await query.answer()
        except Exception as e:
            logger.debug(f"Failed to answer query: {e}")


async def send_or_edit_message(
    update: Update,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: str = "HTML"
) -> None:
    """Send new message or edit existing one based on update type."""
    query = update.callback_query
    if query:
        await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)


async def set_reaction_safely(message, emoji: str) -> None:
    """Set reaction on message safely, ignoring errors."""
    try:
        await message.set_reaction(emoji)
    except Exception as e:
        logger.debug(f"Could not set reaction: {e}")


def validate_amount(amount_str: str) -> Optional[Decimal]:
    """
    Validate and parse amount string.
    
    Args:
        amount_str: Amount string to validate
        
    Returns:
        Decimal amount if valid, None otherwise
    """
    try:
        amount_str = amount_str.replace(',', '.')
        
        if not re.match(r'^\d+(\.\d{1,2})?$', amount_str):
            return None
        
        amount = Decimal(amount_str)
        
        if amount <= ValidationLimits.MIN_AMOUNT or amount > ValidationLimits.MAX_AMOUNT:
            return None
        
        return amount
    except (InvalidOperation, ValueError):
        return None


def extract_id_from_callback(callback_data: str) -> int:
    """Extract numeric ID from callback data."""
    return int(callback_data.split('_')[-1])


async def handle_db_operation(operation, error_message: str):
    """
    Handle database operations with error handling.
    
    Args:
        operation: Async function to execute
        error_message: Error message to log on failure
        
    Returns:
        Result of operation or None on error
    """
    result = None
    async for session in get_db():
        try:
            result = await operation(session)
            # Ensure objects are loaded before session closes
            if result and hasattr(result, '__iter__') and not isinstance(result, (str, bytes, dict)):
                # Force load all objects and their attributes
                result_list = list(result)
                for obj in result_list:
                    if hasattr(obj, '__dict__'):
                        for key in obj.__dict__.keys():
                            getattr(obj, key, None)
                result = result_list
        except Exception as e:
            logger.error(f"{error_message}: {e}", exc_info=True)
            result = None
        finally:
            break
    return result


# ============================================================================
# MESSAGE BUILDERS
# ============================================================================

class MessageBuilder:
    """Builder class for creating formatted messages."""
    
    @staticmethod
    def build_no_families_message(title: str) -> str:
        """Build message when user has no families."""
        return (
            f"{title}\n\n"
            f"{ErrorMessage.NO_FAMILIES}"
        )
    
    @staticmethod
    def build_family_selection_message(title: str, prompt: str) -> str:
        """Build message for family selection."""
        return f"{title}\n\n{prompt}"
    
    @staticmethod
    def build_category_selection_message(family_name: str) -> str:
        """Build message for category selection."""
        return (
            f"{Emoji.MONEY} <b>Добавление расхода</b>\n"
            f"{Emoji.FAMILY} Семья: <b>{family_name}</b>\n\n"
            f"{Emoji.CATEGORY} Выберите категорию расхода:"
        )
    
    @staticmethod
    def build_amount_input_message(family_name: str, category_icon: str, category_name: str) -> str:
        """Build message for amount input."""
        return (
            f"{Emoji.MONEY} <b>Добавление расхода</b>\n"
            f"{Emoji.FAMILY} Семья: <b>{family_name}</b>\n"
            f"{Emoji.CATEGORY} Категория: {category_icon} <b>{category_name}</b>\n\n"
            f"{Emoji.MONEY} Введите сумму расхода:\n\n"
            "💡 <b>Примеры:</b>\n"
            "• 100\n"
            "• 250.50\n"
            "• 1000,99\n\n"
            "⚡ <b>Можно сразу добавить описание:</b>\n"
            "• 100 продукты в магазине\n"
            "• 250.50 оплата за интернет\n"
            "• 1000 подарок маме\n\n"
            "Для отмены используйте команду /cancel"
        )
    
    @staticmethod
    def build_description_input_message(expense_data: ExpenseData) -> str:
        """Build message for description input."""
        return (
            f"{Emoji.MONEY} <b>Добавление расхода</b>\n"
            f"{Emoji.FAMILY} Семья: <b>{expense_data.family_name}</b>\n"
            f"{Emoji.CATEGORY} Категория: {expense_data.category_icon} <b>{expense_data.category_name}</b>\n"
            f"{Emoji.MONEY} Сумма: <b>{format_amount(expense_data.amount)}</b>\n\n"
            f"{Emoji.DESCRIPTION} Введите описание расхода (опционально):\n\n"
            "💡 <b>Примеры:</b>\n"
            "• Продукты в Пятёрочке\n"
            "• Оплата за интернет\n"
            "• Подарок маме\n\n"
            "Или нажмите кнопку «Пропустить», чтобы сохранить без описания."
        )
    
    @staticmethod
    def build_expense_created_message(expense_data: ExpenseData, expense, user) -> str:
        """Build message after expense creation."""
        date_str = expense.date.strftime('%d.%m.%Y %H:%M')
        message = (
            f"{Emoji.SUCCESS} <b>Расход успешно добавлен!</b>\n\n"
            f"{Emoji.FAMILY} <b>Семья:</b> {expense_data.family_name}\n"
            f"{Emoji.CATEGORY} <b>Категория:</b> {expense_data.category_icon} {expense_data.category_name}\n"
            f"{Emoji.MONEY} <b>Сумма:</b> {format_amount(expense.amount)}\n"
        )
        
        if expense_data.description:
            message += f"{Emoji.DESCRIPTION} <b>Описание:</b> {expense_data.description}\n"
        
        message += (
            f"{Emoji.CALENDAR} <b>Дата:</b> {date_str}\n"
            f"{Emoji.USER} <b>Добавил:</b> {user.name}\n\n"
            "🎉 Расход зафиксирован!"
        )
        
        return message
    
    @staticmethod
    def build_period_selection_message(family_name: str, title: str) -> str:
        """Build message for period selection."""
        return (
            f"{title}\n"
            f"{Emoji.FAMILY} Семья: <b>{family_name}</b>\n\n"
            f"{Emoji.CALENDAR} Выберите период для просмотра:"
        )
    
    @staticmethod
    def build_no_expenses_message(title: str, family_name: str, period_name: str, prompt: str) -> str:
        """Build message when no expenses found."""
        return (
            f"{title}\n"
            f"{Emoji.FAMILY} Семья: <b>{family_name}</b>\n"
            f"{Emoji.CALENDAR} Период: <b>{period_name}</b>\n\n"
            f"{Emoji.EMPTY} <b>Расходов не найдено</b>\n\n"
            f"{prompt}"
        )


# ============================================================================
# KEYBOARD BUILDERS
# ============================================================================

class KeyboardBuilder:
    """Builder class for creating keyboards."""
    
    @staticmethod
    def build_no_families_keyboard(context: ContextTypes.DEFAULT_TYPE, current_state: str) -> InlineKeyboardMarkup:
        """Build keyboard when user has no families."""
        keyboard = [
            [InlineKeyboardButton(f"{Emoji.FAMILY} Создать семью", callback_data=CallbackPattern.CREATE_FAMILY)],
            [InlineKeyboardButton(f"{Emoji.LINK} Присоединиться к семье", callback_data=CallbackPattern.JOIN_FAMILY)]
        ]
        keyboard = add_navigation_buttons(keyboard, context, current_state=current_state)
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_family_selection_keyboard(families: List, pattern_prefix: str, context: ContextTypes.DEFAULT_TYPE, current_state: str) -> InlineKeyboardMarkup:
        """Build keyboard for family selection."""
        keyboard = [
            [InlineKeyboardButton(family.name, callback_data=f"{pattern_prefix}{family.id}")]
            for family in families
        ]
        keyboard = add_navigation_buttons(keyboard, context, current_state=current_state)
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_category_selection_keyboard(categories: List, context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
        """Build keyboard for category selection (2 per row)."""
        keyboard = []
        row = []
        for category in categories:
            button = InlineKeyboardButton(
                f"{category.icon} {category.name}",
                callback_data=f"{CallbackPattern.SELECT_CATEGORY_PREFIX}{category.id}"
            )
            row.append(button)
            
            if len(row) == 2:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        # Add button to create new category
        keyboard.append([InlineKeyboardButton(
            f"{Emoji.PLUS} Создать новую категорию",
            callback_data=CallbackPattern.CREATE_NEW_CATEGORY
        )])
        
        keyboard = add_navigation_buttons(keyboard, context)
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_amount_input_keyboard(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
        """Build keyboard for amount input."""
        keyboard = []
        keyboard = add_navigation_buttons(keyboard, context, current_state="enter_amount")
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_description_input_keyboard(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
        """Build keyboard for description input."""
        keyboard = [[InlineKeyboardButton(f"{Emoji.SKIP} Пропустить", callback_data=CallbackPattern.SKIP_DESCRIPTION)]]
        keyboard = add_navigation_buttons(keyboard, context, current_state="enter_description")
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_period_selection_keyboard(period_prefix: str, context: ContextTypes.DEFAULT_TYPE, current_state: str) -> InlineKeyboardMarkup:
        """Build keyboard for period selection."""
        keyboard = [
            [InlineKeyboardButton(f"{Emoji.TODAY} Сегодня", callback_data=f"{period_prefix}{Period.TODAY}")],
            [InlineKeyboardButton(f"{Emoji.WEEK} За неделю", callback_data=f"{period_prefix}{Period.WEEK}")],
            [InlineKeyboardButton(f"{Emoji.MONTH} За месяц", callback_data=f"{period_prefix}{Period.MONTH}")],
            [InlineKeyboardButton(f"{Emoji.ALL} За все время", callback_data=f"{period_prefix}{Period.ALL}")]
        ]
        keyboard = add_navigation_buttons(keyboard, context, current_state=current_state)
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_expense_list_keyboard(
        page: int,
        total_count: int,
        has_next: bool,
        is_personal: bool = True
    ) -> InlineKeyboardMarkup:
        """Build keyboard for expense list with pagination."""
        keyboard = []
        per_page = ValidationLimits.ITEMS_PER_PAGE
        
        # Pagination
        if page > 0 or has_next:
            pagination_row = []
            if page > 0:
                prev_pattern = CallbackPattern.PAGE_PREV if is_personal else CallbackPattern.FAMILY_PAGE_PREV
                pagination_row.append(InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data=prev_pattern))
            
            total_pages = (total_count + per_page - 1) // per_page
            page_pattern = CallbackPattern.PAGE_CURRENT if is_personal else CallbackPattern.FAMILY_PAGE_CURRENT
            pagination_row.append(InlineKeyboardButton(f"{Emoji.PAGE} {page + 1}/{total_pages}", callback_data=page_pattern))
            
            if has_next:
                next_pattern = CallbackPattern.PAGE_NEXT if is_personal else CallbackPattern.FAMILY_PAGE_NEXT
                pagination_row.append(InlineKeyboardButton(f"Вперед {Emoji.FORWARD}", callback_data=next_pattern))
            
            if len(pagination_row) > 1:
                keyboard.append(pagination_row)
        
        # Action buttons
        if is_personal:
            keyboard.extend([
                [InlineKeyboardButton(f"{Emoji.MONEY} Добавить расход", callback_data=CallbackPattern.ADD_EXPENSE)],
                [InlineKeyboardButton(f"📊 Детальный отчет", callback_data=CallbackPattern.MY_DETAILED_REPORT)],
                [InlineKeyboardButton(f"{Emoji.REFRESH} Выбрать другой период", callback_data=CallbackPattern.MY_EXPENSES)],
                [InlineKeyboardButton(f"{Emoji.FAMILY} Мои семьи", callback_data=CallbackPattern.MY_FAMILIES)]
            ])
        else:
            keyboard.extend([
                [InlineKeyboardButton(f"📊 Детальный отчет", callback_data=CallbackPattern.FAMILY_DETAILED_REPORT)],
                [InlineKeyboardButton(f"{Emoji.MONEY} Добавить расход", callback_data=CallbackPattern.ADD_EXPENSE)],
                [InlineKeyboardButton(f"{Emoji.REFRESH} Выбрать другой период", callback_data=CallbackPattern.FAMILY_EXPENSES)]
            ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_no_expenses_keyboard(is_personal: bool = True) -> InlineKeyboardMarkup:
        """Build keyboard when no expenses found."""
        if is_personal:
            keyboard = [
                [InlineKeyboardButton(f"{Emoji.MONEY} Добавить расход", callback_data=CallbackPattern.ADD_EXPENSE)],
                [InlineKeyboardButton(f"{Emoji.REFRESH} Выбрать другой период", callback_data=CallbackPattern.MY_EXPENSES)]
            ]
        else:
            keyboard = [
                [InlineKeyboardButton(f"{Emoji.MONEY} Добавить расход", callback_data=CallbackPattern.ADD_EXPENSE)],
                [InlineKeyboardButton(f"{Emoji.REFRESH} Выбрать другой период", callback_data=CallbackPattern.FAMILY_EXPENSES)]
            ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_family_expenses_keyboard(
        page: int,
        total_count: int,
        has_next: bool,
        grouping: str
    ) -> InlineKeyboardMarkup:
        """Build keyboard for family expense list with grouping."""
        keyboard = []
        
        # Grouping buttons
        grouping_row = []
        if grouping != Grouping.BY_USER:
            grouping_row.append(InlineKeyboardButton(f"{Emoji.USERS} По участникам", callback_data=CallbackPattern.FAMILY_GROUP_USER))
        if grouping != Grouping.BY_CATEGORY:
            grouping_row.append(InlineKeyboardButton(f"{Emoji.CATEGORY} По категориям", callback_data=CallbackPattern.FAMILY_GROUP_CATEGORY))
        if grouping != Grouping.DEFAULT:
            grouping_row.append(InlineKeyboardButton("📋 По датам", callback_data=CallbackPattern.FAMILY_GROUP_DEFAULT))
        
        if grouping_row:
            keyboard.append(grouping_row)
        
        # Pagination (only for default view)
        if grouping == Grouping.DEFAULT and (page > 0 or has_next):
            per_page = ValidationLimits.ITEMS_PER_PAGE
            pagination_row = []
            
            if page > 0:
                pagination_row.append(InlineKeyboardButton(f"{Emoji.BACK} Назад", callback_data=CallbackPattern.FAMILY_PAGE_PREV))
            
            total_pages = (total_count + per_page - 1) // per_page
            pagination_row.append(InlineKeyboardButton(f"{Emoji.PAGE} {page + 1}/{total_pages}", callback_data=CallbackPattern.FAMILY_PAGE_CURRENT))
            
            if has_next:
                pagination_row.append(InlineKeyboardButton(f"Вперед {Emoji.FORWARD}", callback_data=CallbackPattern.FAMILY_PAGE_NEXT))
            
            if len(pagination_row) > 1:
                keyboard.append(pagination_row)
        
        # Action buttons
        keyboard.extend([
            [InlineKeyboardButton(f"📊 Детальный отчет", callback_data=CallbackPattern.FAMILY_DETAILED_REPORT)],
            [InlineKeyboardButton(f"{Emoji.MONEY} Добавить расход", callback_data=CallbackPattern.ADD_EXPENSE)],
            [InlineKeyboardButton(f"{Emoji.REFRESH} Выбрать другой период", callback_data=CallbackPattern.FAMILY_EXPENSES)]
        ])
        
        return InlineKeyboardMarkup(keyboard)


# ============================================================================
# ADD EXPENSE HANDLERS
# ============================================================================

async def add_expense_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Start the expense adding process.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        Next conversation state
    """
    query = update.callback_query
    await answer_query_safely(query)
    
    user_id = await get_user_id(update, context)
    if not user_id:
        keyboard = get_home_button()
        await send_or_edit_message(update, ErrorMessage.NOT_REGISTERED, reply_markup=keyboard)
        return ConversationHandler.END
    
    async def get_families(session):
        return await crud.get_user_families(session, user_id)
    
    families = await handle_db_operation(get_families, "Error starting expense adding")
    
    if families is None:
        keyboard = get_home_button()
        await send_or_edit_message(update, ErrorMessage.GENERAL_ERROR, reply_markup=keyboard)
        return ConversationHandler.END
    
    if not families:
        message = MessageBuilder.build_no_families_message("📋 <b>Добавление расхода</b>")
        keyboard = KeyboardBuilder.build_no_families_keyboard(context, "add_expense")
        await send_or_edit_message(update, message, reply_markup=keyboard)
        return ConversationHandler.END
    
    # If user has only one family, skip selection
    if len(families) == 1:
        expense_data = ExpenseData(family_id=families[0].id, family_name=families[0].name)
        expense_data.save_to_context(context)
        logger.info(f"User {user_id} started expense adding for family {families[0].id}")
        return await show_category_selection(update, context)
    
    # Show family selection
    message = MessageBuilder.build_family_selection_message(
        "👨‍👩‍👧‍👦 <b>Выберите семью</b>",
        "Для какой семьи вы хотите добавить расход?"
    )
    keyboard = KeyboardBuilder.build_family_selection_keyboard(
        families,
        CallbackPattern.SELECT_FAMILY_PREFIX,
        context,
        "add_expense"
    )
    await send_or_edit_message(update, message, reply_markup=keyboard)
    
    logger.info(f"User {user_id} started expense adding, selecting family")
    return ConversationState.SELECT_FAMILY


async def family_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle family selection."""
    query = update.callback_query
    await query.answer()
    
    family_id = extract_id_from_callback(query.data)
    
    async def get_family(session):
        return await crud.get_family_by_id(session, family_id)
    
    family = await handle_db_operation(get_family, f"Error selecting family {family_id}")
    
    if not family:
        keyboard = get_home_button()
        await query.edit_message_text(ErrorMessage.FAMILY_NOT_FOUND, reply_markup=keyboard)
        return ConversationHandler.END
    
    expense_data = ExpenseData(family_id=family_id, family_name=family.name)
    expense_data.save_to_context(context)
    
    logger.info(f"User selected family {family_id} for expense")
    return await show_category_selection(update, context)


async def show_category_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show category selection."""
    expense_data = ExpenseData.from_context(context)
    
    async def get_categories(session):
        return await crud.get_family_categories(session, expense_data.family_id)
    
    categories = await handle_db_operation(get_categories, "Error showing categories")
    
    if not categories:
        keyboard = get_home_button()
        await send_or_edit_message(update, ErrorMessage.NO_CATEGORIES, reply_markup=keyboard)
        return ConversationHandler.END
    
    message = MessageBuilder.build_category_selection_message(expense_data.family_name)
    keyboard = KeyboardBuilder.build_category_selection_keyboard(categories, context)
    await send_or_edit_message(update, message, reply_markup=keyboard)
    
    return ConversationState.SELECT_CATEGORY


async def category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle category selection."""
    query = update.callback_query
    await query.answer()
    
    category_id = extract_id_from_callback(query.data)
    
    async def get_category(session):
        return await crud.get_category_by_id(session, category_id)
    
    category = await handle_db_operation(get_category, f"Error selecting category {category_id}")
    
    if not category:
        keyboard = get_home_button()
        await query.edit_message_text(ErrorMessage.CATEGORY_NOT_FOUND, reply_markup=keyboard)
        return ConversationHandler.END
    
    expense_data = ExpenseData.from_context(context)
    expense_data.category_id = category_id
    expense_data.category_name = category.name
    expense_data.category_icon = category.icon
    expense_data.save_to_context(context)
    
    message = MessageBuilder.build_amount_input_message(
        expense_data.family_name,
        category.icon,
        category.name
    )
    keyboard = KeyboardBuilder.build_amount_input_keyboard(context)
    await query.edit_message_text(message, parse_mode="HTML", reply_markup=keyboard)
    
    logger.info(f"User selected category {category_id} ({category.name}) for expense")
    return ConversationState.ENTER_AMOUNT


async def create_category_during_expense_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start creating a new category during expense addition."""
    query = update.callback_query
    await query.answer()
    
    expense_data = ExpenseData.from_context(context)
    
    message = (
        f"{Emoji.PLUS} <b>Создание новой категории</b>\n"
        f"{Emoji.FAMILY} Семья: <b>{expense_data.family_name}</b>\n\n"
        "Введите название новой категории (например: 'Рестораны', 'Такси', 'Спорт'):"
    )
    keyboard = add_navigation_buttons([], context, current_state="create_category_name")
    await query.edit_message_text(message, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    
    logger.info(f"User started creating new category during expense addition for family {expense_data.family_id}")
    return ConversationState.CREATE_CATEGORY_NAME


async def create_category_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle new category name input."""
    if not update.message or not update.message.text:
        keyboard = get_home_button()
        await update.message.reply_text(ErrorMessage.INVALID_NUMBER, reply_markup=keyboard)
        return ConversationState.CREATE_CATEGORY_NAME
    
    name = update.message.text.strip()
    
    # Validate name length
    if len(name) < 2:
        await update.message.reply_text(
            f"{Emoji.ERROR} Название слишком короткое. Введите минимум 2 символа:"
        )
        return ConversationState.CREATE_CATEGORY_NAME
    
    if len(name) > 50:
        await update.message.reply_text(
            f"{Emoji.ERROR} Название слишком длинное. Максимум 50 символов:"
        )
        return ConversationState.CREATE_CATEGORY_NAME
    
    expense_data = ExpenseData.from_context(context)
    
    # Check if category name already exists
    async def check_name_exists(session):
        return await crud.category_name_exists(session, name, expense_data.family_id)
    
    exists = await handle_db_operation(check_name_exists, "Error checking category name")
    
    if exists:
        await update.message.reply_text(
            f"{Emoji.ERROR} Категория с названием '{name}' уже существует.\nВведите другое название:"
        )
        return ConversationState.CREATE_CATEGORY_NAME
    
    # Save name to context
    context.user_data['new_category_name'] = name
    
    # Get common emojis
    from bot.handlers.categories import Emoji as CatEmoji
    emojis = CatEmoji.get_all_common_emojis()
    
    # Build emoji keyboard
    keyboard = []
    row = []
    for i, emoji in enumerate(emojis):
        row.append(InlineKeyboardButton(emoji, callback_data=f"{CallbackPattern.NEW_CAT_EMOJI_PREFIX}{emoji}"))
        if (i + 1) % 5 == 0:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    keyboard = add_navigation_buttons(keyboard, context, current_state="create_category_emoji")
    
    message = (
        f"{Emoji.SUCCESS} Название: <b>{name}</b>\n\n"
        "Теперь выберите иконку для категории из списка ниже "
        "или отправьте свою (любой эмодзи):"
    )
    await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    
    logger.info(f"User entered new category name: {name}")
    return ConversationState.CREATE_CATEGORY_EMOJI


async def create_category_emoji_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle emoji selection for new category."""
    expense_data = ExpenseData.from_context(context)
    category_name = context.user_data.get('new_category_name')
    
    if not category_name:
        keyboard = get_home_button()
        await send_or_edit_message(update, ErrorMessage.MISSING_DATA, reply_markup=keyboard)
        return ConversationHandler.END
    
    # Check if it's a callback (emoji button) or message (custom emoji)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        emoji = query.data.split("_")[-1]
    else:
        emoji = update.message.text.strip()
        
        # Validate emoji
        from bot.handlers.categories import validate_emoji
        if not validate_emoji(emoji):
            await update.message.reply_text(
                f"{Emoji.ERROR} Это не похоже на эмодзи. Попробуйте еще раз или выберите из предложенных:"
            )
            return ConversationState.CREATE_CATEGORY_EMOJI
    
    # Create the new category
    async def create_category(session):
        category = await crud.create_category(
            session,
            name=category_name,
            icon=emoji,
            family_id=expense_data.family_id
        )
        await session.commit()
        return category
    
    category = await handle_db_operation(create_category, "Error creating category")
    
    if category is None:
        error_msg = f"{Emoji.ERROR} Произошла ошибка при создании категории. Попробуйте позже."
        if update.callback_query:
            await update.callback_query.edit_message_text(error_msg)
        else:
            await update.message.reply_text(error_msg)
        return ConversationHandler.END
    
    # Update expense data with the new category
    expense_data.category_id = category.id
    expense_data.category_name = category.name
    expense_data.category_icon = category.icon
    expense_data.save_to_context(context)
    
    # Clear temporary data
    context.user_data.pop('new_category_name', None)
    
    # Show success message and proceed to amount input
    message = MessageBuilder.build_amount_input_message(
        expense_data.family_name,
        category.icon,
        category.name
    )
    keyboard = KeyboardBuilder.build_amount_input_keyboard(context)
    
    success_msg = (
        f"{Emoji.SUCCESS} <b>Категория создана!</b>\n\n"
        f"{emoji} <b>{category_name}</b>\n\n"
        "Теперь продолжим добавление расхода:\n\n"
        f"{message}"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(success_msg, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_text(success_msg, parse_mode="HTML", reply_markup=keyboard)
    
    logger.info(f"Created category {category.id} ({category_name}) during expense addition")
    return ConversationState.ENTER_AMOUNT


async def amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle amount input, optionally with description in the same line."""
    if not update.message or not update.message.text:
        keyboard = get_home_button()
        await update.message.reply_text(ErrorMessage.INVALID_NUMBER, reply_markup=keyboard)
        return ConversationState.ENTER_AMOUNT
    
    input_text = update.message.text.strip()
    description = None
    amount_str = input_text
    
    # Check if input contains space - might be "amount description" format
    if ' ' in input_text:
        parts = input_text.split(maxsplit=1)
        amount_str = parts[0]
        if len(parts) > 1:
            description = parts[1].strip()
            # Validate description length
            if description and len(description) > ValidationLimits.MAX_DESCRIPTION_LENGTH:
                keyboard = get_home_button()
                await update.message.reply_text(ErrorMessage.DESCRIPTION_TOO_LONG, reply_markup=keyboard)
                return ConversationState.ENTER_AMOUNT
    
    amount = validate_amount(amount_str)
    
    if amount is None:
        await update.message.reply_text(ErrorMessage.INVALID_AMOUNT)
        return ConversationState.ENTER_AMOUNT
    
    expense_data = ExpenseData.from_context(context)
    expense_data.amount = amount
    
    # If description was provided in the same line, save expense immediately
    if description:
        expense_data.description = description
        expense_data.save_to_context(context)
        logger.info(f"User entered amount {amount} with description in one line")
        
        # Save expense immediately
        user_id = await get_user_id(update, context)
        
        if not all([user_id, expense_data.family_id, expense_data.category_id, expense_data.amount]):
            await update.message.reply_text(ErrorMessage.MISSING_DATA)
            return ConversationHandler.END
        
        async def create_expense_and_notify(session):
            expense = await crud.create_expense(
                session,
                user_id=user_id,
                family_id=expense_data.family_id,
                category_id=expense_data.category_id,
                amount=float(expense_data.amount),
                description=description
            )
            await session.commit()
            
            user = await crud.get_user_by_id(session, user_id)
            category = await crud.get_category_by_id(session, expense_data.category_id)
            family_members = await crud.get_family_members(session, expense_data.family_id)
            
            # Send notifications about large expenses
            await notify_large_expense(session, context.bot, expense, family_members)
            
            # Send notifications to family members about the new expense
            await notify_expense_to_family(session, context.bot, expense, family_members)
            
            return expense, user, category
        
        result = await handle_db_operation(create_expense_and_notify, "Error creating expense")
        
        if result is None:
            await update.message.reply_text(f"{Emoji.ERROR} Произошла ошибка при сохранении расхода. Пожалуйста, попробуйте позже.")
            return ConversationHandler.END
        
        expense, user, category = result
        
        # Update expense_data with category info
        expense_data.category_name = category.name
        expense_data.category_icon = category.icon
        
        message = MessageBuilder.build_expense_created_message(expense_data, expense, user)
        reply_markup = get_add_another_keyboard()
        
        sent_message = await update.message.reply_text(
            message,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        
        await set_reaction_safely(sent_message, Emoji.REACTION_THUMB)
        
        logger.info(f"Expense created: id={expense.id}, user_id={user_id}, family_id={expense_data.family_id}, amount={expense_data.amount}")
        
        # Clear data
        expense_data.clear_from_context(context)
        
        return ConversationHandler.END
    
    # No description provided - save expense immediately without description
    expense_data.description = None
    expense_data.save_to_context(context)
    logger.info(f"User entered amount {amount} without description")
    
    # Save expense immediately
    user_id = await get_user_id(update, context)
    
    if not all([user_id, expense_data.family_id, expense_data.category_id, expense_data.amount]):
        await update.message.reply_text(ErrorMessage.MISSING_DATA)
        return ConversationHandler.END
    
    async def create_expense_and_notify(session):
        expense = await crud.create_expense(
            session,
            user_id=user_id,
            family_id=expense_data.family_id,
            category_id=expense_data.category_id,
            amount=float(expense_data.amount),
            description=None
        )
        await session.commit()
        
        user = await crud.get_user_by_id(session, user_id)
        category = await crud.get_category_by_id(session, expense_data.category_id)
        family_members = await crud.get_family_members(session, expense_data.family_id)
        
        # Send notifications about large expenses
        await notify_large_expense(session, context.bot, expense, family_members)
        
        # Send notifications to family members about the new expense
        await notify_expense_to_family(session, context.bot, expense, family_members)
        
        return expense, user, category
    
    result = await handle_db_operation(create_expense_and_notify, "Error creating expense")
    
    if result is None:
        await update.message.reply_text(f"{Emoji.ERROR} Произошла ошибка при сохранении расхода. Пожалуйста, попробуйте позже.")
        return ConversationHandler.END
    
    expense, user, category = result
    
    # Update expense_data with category info
    expense_data.category_name = category.name
    expense_data.category_icon = category.icon
    
    message = MessageBuilder.build_expense_created_message(expense_data, expense, user)
    reply_markup = get_add_another_keyboard()
    
    sent_message = await update.message.reply_text(
        message,
        parse_mode="HTML",
        reply_markup=reply_markup
    )
    
    await set_reaction_safely(sent_message, Emoji.REACTION_THUMB)
    
    logger.info(f"Expense created: id={expense.id}, user_id={user_id}, family_id={expense_data.family_id}, amount={expense_data.amount}")
    
    # Clear data
    expense_data.clear_from_context(context)
    
    return ConversationHandler.END


async def description_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle description input and save expense."""
    description = None
    
    if update.callback_query:
        await update.callback_query.answer()
        logger.info("User skipped description")
    elif update.message and update.message.text:
        description = update.message.text.strip()
        
        if len(description) > ValidationLimits.MAX_DESCRIPTION_LENGTH:
            await update.message.reply_text(ErrorMessage.DESCRIPTION_TOO_LONG)
            return ConversationState.ENTER_DESCRIPTION
        
        logger.info(f"User entered description: {description[:50]}...")
    
    # Save expense
    user_id = await get_user_id(update, context)
    expense_data = ExpenseData.from_context(context)
    expense_data.description = description
    
    if not all([user_id, expense_data.family_id, expense_data.category_id, expense_data.amount]):
        error_message = ErrorMessage.MISSING_DATA
        if update.callback_query:
            await update.callback_query.edit_message_text(error_message)
        else:
            await update.message.reply_text(error_message)
        return ConversationHandler.END
    
    async def create_expense_and_notify(session):
        expense = await crud.create_expense(
            session,
            user_id=user_id,
            family_id=expense_data.family_id,
            category_id=expense_data.category_id,
            amount=float(expense_data.amount),
            description=description
        )
        await session.commit()
        
        user = await crud.get_user_by_id(session, user_id)
        category = await crud.get_category_by_id(session, expense_data.category_id)
        family_members = await crud.get_family_members(session, expense_data.family_id)
        
        # Send notifications about large expenses
        await notify_large_expense(session, context.bot, expense, family_members)
        
        # Send notifications to family members about the new expense
        await notify_expense_to_family(session, context.bot, expense, family_members)
        
        return expense, user, category
    
    result = await handle_db_operation(create_expense_and_notify, "Error creating expense")
    
    if result is None:
        error_message = f"{Emoji.ERROR} Произошла ошибка при сохранении расхода. Пожалуйста, попробуйте позже."
        if update.callback_query:
            await update.callback_query.edit_message_text(error_message)
        else:
            await update.message.reply_text(error_message)
        return ConversationHandler.END
    
    expense, user, category = result
    
    # Update expense_data with category info (in case it was loaded from DB)
    expense_data.category_name = category.name
    expense_data.category_icon = category.icon
    
    message = MessageBuilder.build_expense_created_message(expense_data, expense, user)
    reply_markup = get_add_another_keyboard()
    
    if update.callback_query:
        sent_message = await update.callback_query.edit_message_text(
            message,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    else:
        sent_message = await update.message.reply_text(
            message,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    
    await set_reaction_safely(sent_message, Emoji.REACTION_THUMB)
    
    logger.info(f"Expense created: id={expense.id}, user_id={user_id}, family_id={expense_data.family_id}, amount={expense_data.amount}")
    
    # Clear data
    expense_data.clear_from_context(context)
    
    return ConversationHandler.END


async def cancel_add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the expense adding process."""
    message = f"{Emoji.ERROR} Добавление расхода отменено."
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(message)
    elif update.message:
        await update.message.reply_text(message)
    
    expense_data = ExpenseData()
    expense_data.clear_from_context(context)
    
    logger.info(f"User {context.user_data.get('user_id')} cancelled expense adding")
    return ConversationHandler.END


# ============================================================================
# VIEW PERSONAL EXPENSES HANDLERS
# ============================================================================

async def my_expenses_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start viewing personal expenses."""
    query = update.callback_query
    await answer_query_safely(query)
    
    user_id = await get_user_id(update, context)
    if not user_id:
        keyboard = get_home_button()
        await send_or_edit_message(update, ErrorMessage.NOT_REGISTERED, reply_markup=keyboard)
        return ConversationHandler.END
    
    async def get_families(session):
        return await crud.get_user_families(session, user_id)
    
    families = await handle_db_operation(get_families, "Error starting expense viewing")
    
    if families is None:
        keyboard = get_home_button()
        await send_or_edit_message(update, ErrorMessage.GENERAL_ERROR, reply_markup=keyboard)
        return ConversationHandler.END
    
    if not families:
        message = MessageBuilder.build_no_families_message("📊 <b>Мои расходы</b>")
        keyboard = KeyboardBuilder.build_no_families_keyboard(context, "my_expenses")
        await send_or_edit_message(update, message, reply_markup=keyboard)
        return ConversationHandler.END
    
    # If user has only one family, skip selection
    if len(families) == 1:
        view_data = ViewData(family_id=families[0].id, family_name=families[0].name)
        view_data.save_to_context(context)
        logger.info(f"User {user_id} started viewing expenses for family {families[0].id}")
        return await show_period_selection(update, context)
    
    # Show family selection
    message = MessageBuilder.build_family_selection_message(
        "📊 <b>Мои расходы</b>",
        f"{Emoji.FAMILY} Выберите семью для просмотра расходов:"
    )
    keyboard = KeyboardBuilder.build_family_selection_keyboard(
        families,
        CallbackPattern.VIEW_FAMILY_PREFIX,
        context,
        "my_expenses"
    )
    await send_or_edit_message(update, message, reply_markup=keyboard)
    
    logger.info(f"User {user_id} started viewing expenses, selecting family")
    return ConversationState.VIEW_SELECT_FAMILY


async def view_family_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle family selection for viewing expenses."""
    query = update.callback_query
    await query.answer()
    
    family_id = extract_id_from_callback(query.data)
    
    async def get_family(session):
        return await crud.get_family_by_id(session, family_id)
    
    family = await handle_db_operation(get_family, f"Error selecting family for viewing {family_id}")
    
    if not family:
        keyboard = get_home_button()
        await query.edit_message_text(ErrorMessage.FAMILY_NOT_FOUND, reply_markup=keyboard)
        return ConversationHandler.END
    
    view_data = ViewData(family_id=family_id, family_name=family.name)
    view_data.save_to_context(context)
    
    logger.info(f"User selected family {family_id} for viewing expenses")
    return await show_period_selection(update, context)


async def show_period_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show period selection."""
    view_data = ViewData.from_context(context)
    
    message = MessageBuilder.build_period_selection_message(
        view_data.family_name,
        f"{Emoji.STATS} <b>Мои расходы</b>"
    )
    keyboard = KeyboardBuilder.build_period_selection_keyboard(
        CallbackPattern.PERIOD_PREFIX,
        context,
        "select_period"
    )
    await send_or_edit_message(update, message, reply_markup=keyboard)
    
    return ConversationState.VIEW_SELECT_PERIOD


async def period_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle period selection and display expenses."""
    query = update.callback_query
    await query.answer()
    
    period = query.data.split('_')[-1]
    
    view_data = ViewData.from_context(context)
    view_data.period = period
    view_data.page = 0
    view_data.save_to_context(context)
    
    await display_expenses_page(update, context)
    return ConversationHandler.END


async def display_expenses_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display expenses for a specific page with pagination."""
    user_id = await get_user_id(update, context)
    view_data = ViewData.from_context(context)
    
    if not all([user_id, view_data.family_id]):
        keyboard = get_home_button()
        await send_or_edit_message(update, ErrorMessage.MISSING_DATA, reply_markup=keyboard)
        return
    
    start_date, end_date = crud.calculate_date_range(view_data.period)
    period_name = Period.get_name(view_data.period)
    per_page = ValidationLimits.ITEMS_PER_PAGE
    offset = view_data.page * per_page
    
    async def get_expenses_and_summary(session):
        expenses = await crud.get_user_expenses(
            session,
            user_id=user_id,
            family_id=view_data.family_id,
            start_date=start_date,
            end_date=end_date,
            limit=per_page + 1,
            offset=offset
        )
        
        summary = await crud.get_user_expenses_summary(
            session,
            user_id=user_id,
            family_id=view_data.family_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return expenses, summary
    
    result = await handle_db_operation(get_expenses_and_summary, "Error showing expenses")
    
    if result is None:
        error_msg = f"{Emoji.ERROR} Произошла ошибка при загрузке расходов. Пожалуйста, попробуйте позже."
        await send_or_edit_message(update, error_msg)
        return
    
    expenses, summary = result
    
    # Build message
    if summary['count'] == 0:
        message = MessageBuilder.build_no_expenses_message(
            f"{Emoji.STATS} <b>Мои расходы</b>",
            view_data.family_name,
            period_name,
            "За выбранный период у вас нет расходов."
        )
        keyboard = KeyboardBuilder.build_no_expenses_keyboard(is_personal=True)
    else:
        has_next_page = len(expenses) > per_page
        expenses_to_show = expenses[:per_page]
        
        message = (
            f"{Emoji.STATS} <b>Мои расходы</b>\n"
            f"{Emoji.FAMILY} Семья: <b>{view_data.family_name}</b>\n"
            f"{Emoji.CALENDAR} Период: <b>{period_name}</b>\n\n"
        )
        
        for expense in expenses_to_show:
            message += format_expense(expense) + "\n\n"
        
        message += "━━━━━━━━━━━━━━━━━━━\n\n"
        message += f"{Emoji.MONEY} <b>Всего за период:</b> {format_amount(summary['total'])}\n"
        message += f"{Emoji.DESCRIPTION} <b>Количество:</b> {summary['count']}\n\n"
        
        if summary['by_category']:
            message += f"<b>{Emoji.STATS} По категориям:</b>\n"
            for cat in summary['by_category']:
                message += format_category_summary(
                    cat['category_name'],
                    cat['category_icon'],
                    cat['amount']
                ) + "\n"
        
        keyboard = KeyboardBuilder.build_expense_list_keyboard(
            view_data.page,
            summary['count'],
            has_next_page,
            is_personal=True
        )
    
    await send_or_edit_message(update, message, reply_markup=keyboard)
    logger.info(f"Showed page {view_data.page} of expenses to user {user_id} for family {view_data.family_id}, period {view_data.period}")


async def pagination_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle pagination button presses."""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    view_data = ViewData.from_context(context)
    
    if action == CallbackPattern.PAGE_PREV and view_data.page > 0:
        view_data.page -= 1
        view_data.save_to_context(context)
        await display_expenses_page(update, context)
    elif action == CallbackPattern.PAGE_NEXT:
        view_data.page += 1
        view_data.save_to_context(context)
        await display_expenses_page(update, context)
    elif action == CallbackPattern.PAGE_CURRENT:
        pass  # Just ignore - it's a page indicator


# Export handlers moved to statistics section
# async def my_export_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     """Handle export button for personal expenses - start HTML export."""
#     # Redirect directly to HTML export
#     return await my_export_gdocs_handler(update, context)


# CSV export has been removed - only HTML export is now supported
# async def my_export_csv_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     """Handle CSV export for personal expenses."""
#     query = update.callback_query
#     await query.answer("📊 Генерирую CSV файл...")
#     
#     user_id = await get_user_id(update, context)
#     view_data = ViewData.from_context(context)
#     
#     if not all([user_id, view_data.family_id]):
#         await query.answer(ErrorMessage.MISSING_DATA, show_alert=True)
#         return
#     
#     start_date, end_date = crud.calculate_date_range(view_data.period)
#     
#     async def get_all_expenses(session):
#         return await crud.get_user_expenses(
#             session,
#             user_id=user_id,
#             family_id=view_data.family_id,
#             start_date=start_date,
#             end_date=end_date,
#             limit=None,
#             offset=0
#         )
#     
#     expenses = await handle_db_operation(get_all_expenses, "Error exporting personal expenses")
#     
#     if not expenses:
#         await query.answer(ErrorMessage.NO_EXPORT_DATA, show_alert=True)
#         return
#     
#     try:
#         csv_file = generate_csv(expenses, include_user=False)
#         filename = generate_csv_filename(family_name=view_data.family_name, is_personal=True)
#         
#         await context.bot.send_document(
#             chat_id=query.message.chat_id,
#             document=csv_file,
#             filename=filename,
#             caption=f"📊 Экспорт ваших расходов\n{Emoji.FAMILY} Семья: {view_data.family_name}\n{Emoji.DESCRIPTION} Записей: {len(expenses)}"
#         )
#         
#         logger.info(f"Exported {len(expenses)} personal expenses to CSV for user {user_id}")
#     except Exception as e:
#         logger.error(f"Error exporting personal expenses: {e}")
#         await query.answer(ErrorMessage.EXPORT_ERROR, show_alert=True)


# Export handlers moved to statistics section - no longer used from expenses view
# async def my_export_gdocs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle HTML report export for personal expenses."""
    from bot.utils.html_report_export import export_monthly_report, generate_report_filename
    from datetime import datetime
    
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(f"{Emoji.LOADING} Создаю HTML отчет...")
    
    user_id = await get_user_id(update, context)
    view_data = ViewData.from_context(context)
    
    if not all([user_id, view_data.family_id]):
        await query.edit_message_text(ErrorMessage.MISSING_DATA)
        return
    
    start_date, end_date = crud.calculate_date_range(view_data.period)
    
    async def get_statistics(session):
        return await crud.get_period_statistics(
            session, user_id, start_date, end_date, is_family=False
        )
    
    stats = await handle_db_operation(get_statistics, "Error getting statistics for HTML export")
    
    if not stats or stats.get('total', 0) == 0:
        await query.edit_message_text(ErrorMessage.NO_EXPORT_DATA)
        return
    
    # Format period name
    now = datetime.now()
    
    if view_data.period == 'today':
        period_name = f"Сегодня - {now.strftime('%d.%m.%Y')}"
    elif view_data.period == 'week':
        period_name = f"Эта неделя"
    elif view_data.period == 'month':
        month_names = {
            1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
            5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
            9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
        }
        period_name = f"{month_names[now.month]} {now.year}"
    elif view_data.period and view_data.period != 'all' and '-' in view_data.period:
        # Format: "YYYY-MM"
        month_names = {
            1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
            5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
            9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
        }
        year, month = map(int, view_data.period.split('-'))
        period_name = f"{month_names[month]} {year}"
    else:
        period_name = f"Все время"
    
    try:
        html_file = await export_monthly_report(view_data.family_name, period_name, stats)
        filename = generate_report_filename(view_data.family_name, period_name, is_personal=True)
        
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=html_file,
            filename=filename,
            caption=(
                f"{Emoji.CHECK} <b>Отчет успешно создан!</b>\n\n"
                f"{Emoji.FAMILY} Семья: {view_data.family_name}\n"
                f"{Emoji.CALENDAR} Период: {period_name}\n\n"
                f"📊 Откройте файл в браузере для просмотра красиво оформленного отчета"
            ),
            parse_mode='HTML'
        )
        
        await query.edit_message_text(
            f"{Emoji.CHECK} Отчет отправлен! Откройте HTML файл в браузере."
        )
        
        logger.info(f"Exported HTML report for user {user_id}")
    except Exception as e:
        logger.error(f"Error creating HTML report: {e}", exc_info=True)
        await query.edit_message_text(
            f"{Emoji.ERROR} <b>Ошибка при создании отчета</b>\n\n"
            f"Ошибка: {str(e)}\n\n"
            "Используйте CSV экспорт как альтернативу."
        )


async def cancel_view_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the expense viewing process."""
    message = f"{Emoji.ERROR} Просмотр расходов отменен."
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(message)
    elif update.message:
        await update.message.reply_text(message)
    
    view_data = ViewData()
    view_data.clear_from_context(context)
    
    logger.info(f"User {context.user_data.get('user_id')} cancelled expense viewing")
    return ConversationHandler.END


# ============================================================================
# VIEW FAMILY EXPENSES HANDLERS
# ============================================================================

async def family_expenses_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start viewing family expenses."""
    query = update.callback_query
    await answer_query_safely(query)
    
    user_id = await get_user_id(update, context)
    if not user_id:
        keyboard = get_home_button()
        await send_or_edit_message(update, ErrorMessage.NOT_REGISTERED, reply_markup=keyboard)
        return ConversationHandler.END
    
    async def get_families(session):
        return await crud.get_user_families(session, user_id)
    
    families = await handle_db_operation(get_families, "Error starting family expense viewing")
    
    if families is None:
        keyboard = get_home_button()
        await send_or_edit_message(update, ErrorMessage.GENERAL_ERROR, reply_markup=keyboard)
        return ConversationHandler.END
    
    if not families:
        message = MessageBuilder.build_no_families_message("📊 <b>Расходы семьи</b>")
        keyboard = KeyboardBuilder.build_no_families_keyboard(context, "family_expenses")
        await send_or_edit_message(update, message, reply_markup=keyboard)
        return ConversationHandler.END
    
    # If user has only one family, skip selection
    if len(families) == 1:
        view_data = ViewData(family_id=families[0].id, family_name=families[0].name)
        view_data.save_to_context(context, prefix="family_view")
        logger.info(f"User {user_id} started viewing family expenses for family {families[0].id}")
        return await show_family_period_selection(update, context)
    
    # Show family selection
    message = MessageBuilder.build_family_selection_message(
        "📊 <b>Расходы семьи</b>",
        f"{Emoji.FAMILY} Выберите семью для просмотра расходов:"
    )
    keyboard = KeyboardBuilder.build_family_selection_keyboard(
        families,
        CallbackPattern.FAMILY_VIEW_PREFIX,
        context,
        "family_expenses"
    )
    await send_or_edit_message(update, message, reply_markup=keyboard)
    
    logger.info(f"User {user_id} started viewing family expenses, selecting family")
    return ConversationState.FAMILY_VIEW_SELECT_FAMILY


async def family_view_family_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle family selection for viewing family expenses."""
    query = update.callback_query
    await query.answer()
    
    family_id = extract_id_from_callback(query.data)
    
    async def get_family(session):
        return await crud.get_family_by_id(session, family_id)
    
    family = await handle_db_operation(get_family, f"Error selecting family for viewing {family_id}")
    
    if not family:
        keyboard = get_home_button()
        await query.edit_message_text(ErrorMessage.FAMILY_NOT_FOUND, reply_markup=keyboard)
        return ConversationHandler.END
    
    view_data = ViewData(family_id=family_id, family_name=family.name)
    view_data.save_to_context(context, prefix="family_view")
    
    logger.info(f"User selected family {family_id} for viewing family expenses")
    return await show_family_period_selection(update, context)


async def show_family_period_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show period selection for family expenses."""
    view_data = ViewData.from_context(context, prefix="family_view")
    
    message = MessageBuilder.build_period_selection_message(
        view_data.family_name,
        f"{Emoji.STATS} <b>Расходы семьи</b>"
    )
    keyboard = KeyboardBuilder.build_period_selection_keyboard(
        CallbackPattern.FAMILY_PERIOD_PREFIX,
        context,
        "family_select_period"
    )
    await send_or_edit_message(update, message, reply_markup=keyboard)
    
    return ConversationState.FAMILY_VIEW_SELECT_PERIOD


async def family_period_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle period selection and display family expenses."""
    query = update.callback_query
    await query.answer()
    
    period = query.data.split('_')[-1]
    
    view_data = ViewData.from_context(context, prefix="family_view")
    view_data.period = period
    view_data.page = 0
    view_data.grouping = Grouping.DEFAULT
    view_data.save_to_context(context, prefix="family_view")
    
    await display_family_expenses_page(update, context)
    return ConversationHandler.END


async def display_family_expenses_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display family expenses for a specific page with pagination and grouping."""
    view_data = ViewData.from_context(context, prefix="family_view")
    
    if not view_data.family_id:
        keyboard = get_home_button()
        await send_or_edit_message(update, ErrorMessage.MISSING_DATA, reply_markup=keyboard)
        return
    
    start_date, end_date = crud.calculate_date_range(view_data.period)
    period_name = Period.get_name(view_data.period)
    per_page = ValidationLimits.ITEMS_PER_PAGE
    offset = view_data.page * per_page
    
    async def get_expenses_and_summary(session):
        expenses = await crud.get_family_expenses_with_users(
            session,
            family_id=view_data.family_id,
            start_date=start_date,
            end_date=end_date,
            limit=per_page + 1,
            offset=offset
        )
        
        summary = await crud.get_family_expenses_summary(
            session,
            family_id=view_data.family_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # For grouped views
        by_user_data = None
        by_category_data = None
        
        if view_data.grouping == Grouping.BY_USER:
            by_user_data = await crud.get_family_expenses_by_user(
                session,
                family_id=view_data.family_id,
                start_date=start_date,
                end_date=end_date
            )
        elif view_data.grouping == Grouping.BY_CATEGORY:
            by_category_data = await crud.get_family_expenses_by_category(
                session,
                family_id=view_data.family_id,
                start_date=start_date,
                end_date=end_date
            )
        
        return expenses, summary, by_user_data, by_category_data
    
    result = await handle_db_operation(get_expenses_and_summary, "Error showing family expenses")
    
    if result is None:
        error_msg = f"{Emoji.ERROR} Произошла ошибка при загрузке расходов. Пожалуйста, попробуйте позже."
        await send_or_edit_message(update, error_msg)
        return
    
    expenses, summary, by_user_data, by_category_data = result
    
    # Build message header
    message = (
        f"{Emoji.STATS} <b>Расходы семьи</b>\n"
        f"{Emoji.FAMILY} Семья: <b>{view_data.family_name}</b>\n"
        f"{Emoji.CALENDAR} Период: <b>{period_name}</b>\n\n"
    )
    
    if summary['count'] == 0:
        message += (
            f"{Emoji.EMPTY} <b>Расходов не найдено</b>\n\n"
            "За выбранный период у семьи нет расходов."
        )
        keyboard = KeyboardBuilder.build_no_expenses_keyboard(is_personal=False)
    else:
        has_next_page = len(expenses) > per_page
        expenses_to_show = expenses[:per_page]
        
        # Display based on grouping
        if view_data.grouping == Grouping.BY_USER and by_user_data:
            for user_id_key, user_data in by_user_data.items():
                message += f"{Emoji.USER} <b>{user_data['name']}</b> - {format_amount(user_data['amount'])}\n\n"
                for exp in user_data['expenses'][:5]:
                    message += f"  {exp.category.icon} {exp.category.name} - {format_amount(exp.amount)}\n"
                    message += f"  {Emoji.CALENDAR} {format_date(exp.date)}\n\n"
                
                if len(user_data['expenses']) > 5:
                    message += f"  ... и еще {len(user_data['expenses']) - 5} расходов\n\n"
        
        elif view_data.grouping == Grouping.BY_CATEGORY and by_category_data:
            for cat_id, cat_data in by_category_data.items():
                message += f"{cat_data['icon']} <b>{cat_data['name']}</b> - {format_amount(cat_data['amount'])}\n\n"
                for exp in cat_data['expenses'][:5]:
                    message += f"  {Emoji.USER} {exp.user.name} - {format_amount(exp.amount)}\n"
                    message += f"  {Emoji.CALENDAR} {format_date(exp.date)}\n\n"
                
                if len(cat_data['expenses']) > 5:
                    message += f"  ... и еще {len(cat_data['expenses']) - 5} расходов\n\n"
        
        else:  # default grouping
            for expense in expenses_to_show:
                message += format_family_expense(expense) + "\n\n"
        
        message += "━━━━━━━━━━━━━━━━━━━\n\n"
        message += format_family_summary(summary)
        
        keyboard = KeyboardBuilder.build_family_expenses_keyboard(
            view_data.page,
            summary['count'],
            has_next_page,
            view_data.grouping
        )
    
    await send_or_edit_message(update, message, reply_markup=keyboard)
    logger.info(f"Showed family expenses page {view_data.page} for family {view_data.family_id}, period {view_data.period}, grouping {view_data.grouping}")


async def family_grouping_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle grouping button presses."""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    view_data = ViewData.from_context(context, prefix="family_view")
    
    if action == CallbackPattern.FAMILY_GROUP_USER:
        view_data.grouping = Grouping.BY_USER
    elif action == CallbackPattern.FAMILY_GROUP_CATEGORY:
        view_data.grouping = Grouping.BY_CATEGORY
    elif action == CallbackPattern.FAMILY_GROUP_DEFAULT:
        view_data.grouping = Grouping.DEFAULT
    
    view_data.page = 0
    view_data.save_to_context(context, prefix="family_view")
    
    await display_family_expenses_page(update, context)


async def family_pagination_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle pagination button presses for family expenses."""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    view_data = ViewData.from_context(context, prefix="family_view")
    
    if action == CallbackPattern.FAMILY_PAGE_PREV and view_data.page > 0:
        view_data.page -= 1
        view_data.save_to_context(context, prefix="family_view")
        await display_family_expenses_page(update, context)
    elif action == CallbackPattern.FAMILY_PAGE_NEXT:
        view_data.page += 1
        view_data.save_to_context(context, prefix="family_view")
        await display_family_expenses_page(update, context)
    elif action == CallbackPattern.FAMILY_PAGE_CURRENT:
        pass  # Just ignore - it's a page indicator


# Export handlers moved to statistics section
# async def family_export_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     """Handle export button for family expenses - start HTML export."""
#     # Redirect directly to HTML export
#     return await family_export_gdocs_handler(update, context)


# CSV export has been removed - only HTML export is now supported
# async def family_export_csv_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     """Handle CSV export for family expenses."""
#     query = update.callback_query
#     await query.answer("📊 Генерирую CSV файл...")
#     
#     view_data = ViewData.from_context(context, prefix="family_view")
#     
#     if not view_data.family_id:
#         await query.answer(ErrorMessage.MISSING_DATA, show_alert=True)
#         return
#     
#     start_date, end_date = crud.calculate_date_range(view_data.period)
#     
#     async def get_all_expenses(session):
#         return await crud.get_family_expenses_with_users(
#             session,
#             family_id=view_data.family_id,
#             start_date=start_date,
#             end_date=end_date,
#             limit=None,
#             offset=0
#         )
#     
#     expenses = await handle_db_operation(get_all_expenses, "Error exporting family expenses")
#     
#     if not expenses:
#         await query.answer(ErrorMessage.NO_EXPORT_DATA, show_alert=True)
#         return
#     
#     try:
#         csv_file = generate_csv(expenses, include_user=True)
#         filename = generate_csv_filename(family_name=view_data.family_name, is_personal=False)
#         
#         await context.bot.send_document(
#             chat_id=query.message.chat_id,
#             document=csv_file,
#             filename=filename,
#             caption=f"📊 Экспорт семейных расходов\n{Emoji.FAMILY} Семья: {view_data.family_name}\n{Emoji.DESCRIPTION} Записей: {len(expenses)}"
#         )
#         
#         logger.info(f"Exported {len(expenses)} family expenses to CSV for family {view_data.family_id}")
#     except Exception as e:
#         logger.error(f"Error exporting family expenses: {e}")
#         await query.answer(ErrorMessage.EXPORT_ERROR, show_alert=True)


# Export handlers moved to statistics section - no longer used from expenses view  
# async def family_export_gdocs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle HTML report export for family expenses."""
    from bot.utils.html_report_export import export_monthly_report, generate_report_filename
    from datetime import datetime
    
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(f"{Emoji.LOADING} Создаю HTML отчет...")
    
    view_data = ViewData.from_context(context, prefix="family_view")
    
    if not view_data.family_id:
        await query.edit_message_text(ErrorMessage.MISSING_DATA)
        return
    
    start_date, end_date = crud.calculate_date_range(view_data.period)
    
    async def get_statistics(session):
        return await crud.get_period_statistics(
            session, view_data.family_id, start_date, end_date, is_family=True
        )
    
    stats = await handle_db_operation(get_statistics, "Error getting statistics for HTML export")
    
    if not stats or stats.get('total', 0) == 0:
        await query.edit_message_text(ErrorMessage.NO_EXPORT_DATA)
        return
    
    # Format period name
    now = datetime.now()
    
    if view_data.period == 'today':
        period_name = f"Сегодня - {now.strftime('%d.%m.%Y')}"
    elif view_data.period == 'week':
        period_name = f"Эта неделя"
    elif view_data.period == 'month':
        month_names = {
            1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
            5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
            9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
        }
        period_name = f"{month_names[now.month]} {now.year}"
    elif view_data.period and view_data.period != 'all' and '-' in view_data.period:
        # Format: "YYYY-MM"
        month_names = {
            1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
            5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
            9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
        }
        year, month = map(int, view_data.period.split('-'))
        period_name = f"{month_names[month]} {year}"
    else:
        period_name = f"Все время"
    
    try:
        html_file = await export_monthly_report(view_data.family_name, period_name, stats)
        filename = generate_report_filename(view_data.family_name, period_name, is_personal=False)
        
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=html_file,
            filename=filename,
            caption=(
                f"{Emoji.CHECK} <b>Отчет успешно создан!</b>\n\n"
                f"{Emoji.FAMILY} Семья: {view_data.family_name}\n"
                f"{Emoji.CALENDAR} Период: {period_name}\n\n"
                f"📊 Откройте файл в браузере для просмотра красиво оформленного отчета"
            ),
            parse_mode='HTML'
        )
        
        await query.edit_message_text(
            f"{Emoji.CHECK} Отчет отправлен! Откройте HTML файл в браузере."
        )
        
        logger.info(f"Exported HTML report for family {view_data.family_id}")
    except Exception as e:
        logger.error(f"Error creating HTML report: {e}", exc_info=True)
        await query.edit_message_text(
            f"{Emoji.ERROR} <b>Ошибка при создании отчета</b>\n\n"
            f"Ошибка: {str(e)}\n\n"
            "Используйте CSV экспорт как альтернативу."
        )


async def cancel_family_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the family expense viewing process."""
    message = f"{Emoji.ERROR} Просмотр расходов семьи отменен."
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(message)
    elif update.message:
        await update.message.reply_text(message)
    
    view_data = ViewData()
    view_data.clear_from_context(context, prefix="family_view")
    
    logger.info(f"User {context.user_data.get('user_id')} cancelled family expense viewing")
    return ConversationHandler.END


# ============================================================================
# CONVERSATION HANDLERS
# ============================================================================

add_expense_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(add_expense_start, pattern=f"^{CallbackPattern.ADD_EXPENSE}$"),
        CommandHandler("add_expense", add_expense_start)
    ],
    states={
        ConversationState.SELECT_FAMILY: [
            CallbackQueryHandler(family_selected, pattern=f"^{CallbackPattern.SELECT_FAMILY_PREFIX}\\d+$")
        ],
        ConversationState.SELECT_CATEGORY: [
            CallbackQueryHandler(category_selected, pattern=f"^{CallbackPattern.SELECT_CATEGORY_PREFIX}\\d+$"),
            CallbackQueryHandler(create_category_during_expense_start, pattern=f"^{CallbackPattern.CREATE_NEW_CATEGORY}$")
        ],
        ConversationState.CREATE_CATEGORY_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, create_category_name_received)
        ],
        ConversationState.CREATE_CATEGORY_EMOJI: [
            CallbackQueryHandler(create_category_emoji_received, pattern=f"^{CallbackPattern.NEW_CAT_EMOJI_PREFIX}"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, create_category_emoji_received)
        ],
        ConversationState.ENTER_AMOUNT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, amount_received)
        ],
        ConversationState.ENTER_DESCRIPTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, description_received),
            CallbackQueryHandler(description_received, pattern=f"^{CallbackPattern.SKIP_DESCRIPTION}$")
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_add_expense),
        CallbackQueryHandler(cancel_add_expense, pattern=f"^{CallbackPattern.CANCEL_ADD}$"),
        CallbackQueryHandler(end_conversation_silently, pattern=f"^{CallbackPattern.NAV_BACK}$"),
        # Main navigation fallbacks - end conversation and route to new section
        CallbackQueryHandler(end_conversation_and_route, pattern="^(start|categories|settings|help|my_expenses|family_expenses|my_families|create_family|join_family|family_settings|stats_start|quick_expense|search)$")
    ],
    allow_reentry=True,
    name="add_expense_conversation",
    persistent=False,
    per_chat=True,
    per_user=True
)

view_expenses_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(my_expenses_start, pattern=f"^{CallbackPattern.MY_EXPENSES}$"),
        CommandHandler("my_expenses", my_expenses_start)
    ],
    states={
        ConversationState.VIEW_SELECT_FAMILY: [
            CallbackQueryHandler(view_family_selected, pattern=f"^{CallbackPattern.VIEW_FAMILY_PREFIX}\\d+$")
        ],
        ConversationState.VIEW_SELECT_PERIOD: [
            CallbackQueryHandler(period_selected, pattern=f"^{CallbackPattern.PERIOD_PREFIX}(today|week|month|all)$")
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_view_expenses),
        CallbackQueryHandler(cancel_view_expenses, pattern=f"^{CallbackPattern.CANCEL_VIEW}$"),
        CallbackQueryHandler(end_conversation_silently, pattern=f"^{CallbackPattern.NAV_BACK}$"),
        # Main navigation fallbacks - end conversation and route to new section
        CallbackQueryHandler(end_conversation_and_route, pattern="^(start|categories|settings|help|add_expense|family_expenses|my_families|create_family|join_family|family_settings|stats_start|quick_expense|search)$")
    ],
    allow_reentry=True,
    name="view_expenses_conversation",
    persistent=False,
    per_chat=True,
    per_user=True
)

family_expenses_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(family_expenses_start, pattern=f"^{CallbackPattern.FAMILY_EXPENSES}$"),
        CommandHandler("family_expenses", family_expenses_start)
    ],
    states={
        ConversationState.FAMILY_VIEW_SELECT_FAMILY: [
            CallbackQueryHandler(family_view_family_selected, pattern=f"^{CallbackPattern.FAMILY_VIEW_PREFIX}\\d+$")
        ],
        ConversationState.FAMILY_VIEW_SELECT_PERIOD: [
            CallbackQueryHandler(family_period_selected, pattern=f"^{CallbackPattern.FAMILY_PERIOD_PREFIX}(today|week|month|all)$")
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_family_expenses),
        CallbackQueryHandler(cancel_family_expenses, pattern=f"^{CallbackPattern.CANCEL_FAMILY}$"),
        CallbackQueryHandler(end_conversation_silently, pattern=f"^{CallbackPattern.NAV_BACK}$"),
        # Main navigation fallbacks - end conversation and route to new section
        CallbackQueryHandler(end_conversation_and_route, pattern="^(start|categories|settings|help|add_expense|my_expenses|my_families|create_family|join_family|family_settings|stats_start|quick_expense|search)$")
    ],
    allow_reentry=True,
    name="family_expenses_conversation",
    persistent=False,
    per_chat=True,
    per_user=True
)
