"""Statistics handlers with improved architecture."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Optional, List, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)

from bot.database import crud, get_db
from bot.utils.formatters import format_amount, format_date
from bot.utils.charts import create_category_chart
from bot.utils.helpers import end_conversation_silently, end_conversation_and_route, get_user_id
from bot.utils.keyboards import add_navigation_buttons, get_back_button, get_home_button

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

class ConversationState(IntEnum):
    """Conversation states for statistics flow."""
    SELECT_TYPE = 0
    SELECT_FAMILY = 1
    SELECT_PERIOD_TYPE = 2
    SELECT_PERIOD = 3
    VIEW_STATS = 4


class CallbackPattern:
    """Callback data patterns."""
    STATS_START = "stats_start"
    STATS_TYPE_PERSONAL = "stats_type_personal"
    STATS_TYPE_FAMILY = "stats_type_family"
    STATS_FAMILY_PREFIX = "stats_family_"
    STATS_PERIOD_TYPE_MONTH = "stats_period_type_month"
    STATS_PERIOD_TYPE_YEAR = "stats_period_type_year"
    STATS_MONTH_PREFIX = "stats_month_"
    STATS_YEAR_PREFIX = "stats_year_"
    STATS_DETAILED_REPORT = "stats_detailed_report"
    STATS_EXPORT_HTML = "stats_export_html"
    STATS_BACK_TO_PERIOD_TYPE = "stats_back_to_period_type"
    STATS_BACK_TO_PERIOD = "stats_back_to_period"
    STATS_BACK = "stats_back"
    STATS_CANCEL = "stats_cancel"
    NAV_BACK = "nav_back"


class StatsType:
    """Statistics type identifiers."""
    PERSONAL = "personal"
    FAMILY = "family"


class PeriodType:
    """Period type identifiers."""
    MONTH = "month"
    YEAR = "year"


class Emoji:
    """Emoji constants."""
    STATS = "📊"
    CALENDAR = "📅"
    FAMILY = "👨‍👩‍👧‍👦"
    USER = "👤"
    USERS = "👥"
    MONEY = "💰"
    NOTE = "📝"
    LOADING = "⏳"
    ERROR = "❌"
    BACK = "◀️"
    WAVE = "👋"
    EXPORT = "📥"
    DASH = "—"
    DOCUMENT = "📄"


class ErrorMessage:
    """Error messages."""
    NOT_REGISTERED = f"{Emoji.ERROR} Вы не зарегистрированы. Используйте команду /start для регистрации."
    NO_FAMILIES = f"{Emoji.ERROR} У вас нет семей. Создайте семью командой /create_family или присоединитесь к существующей через /join_family."
    FAMILY_NOT_FOUND = f"{Emoji.ERROR} Семья не найдена."
    NO_PERIODS = f"{Emoji.ERROR} Нет доступных периодов с операциями."
    STATS_ERROR = f"{Emoji.ERROR} Произошла ошибка при загрузке статистики. Попробуйте позже."


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class StatsData:
    """Data class for statistics context."""
    stats_type: Optional[str] = None
    family_id: Optional[int] = None
    family_name: Optional[str] = None
    period_type: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    @classmethod
    def from_context(cls, context: ContextTypes.DEFAULT_TYPE) -> 'StatsData':
        """Create StatsData from context user_data."""
        return cls(
            stats_type=context.user_data.get('stats_type'),
            family_id=context.user_data.get('stats_family_id'),
            family_name=context.user_data.get('stats_family_name'),
            period_type=context.user_data.get('stats_period_type'),
            year=context.user_data.get('stats_year'),
            month=context.user_data.get('stats_month'),
            start_date=context.user_data.get('stats_start_date'),
            end_date=context.user_data.get('stats_end_date')
        )

    def save_to_context(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Save statistics data to context."""
        if self.stats_type is not None:
            context.user_data['stats_type'] = self.stats_type
        if self.family_id is not None:
            context.user_data['stats_family_id'] = self.family_id
        if self.family_name is not None:
            context.user_data['stats_family_name'] = self.family_name
        if self.period_type is not None:
            context.user_data['stats_period_type'] = self.period_type
        if self.year is not None:
            context.user_data['stats_year'] = self.year
        if self.month is not None:
            context.user_data['stats_month'] = self.month
        if self.start_date is not None:
            context.user_data['stats_start_date'] = self.start_date
        if self.end_date is not None:
            context.user_data['stats_end_date'] = self.end_date

    def clear_from_context(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Clear statistics data from context."""
        context.user_data.pop('stats_type', None)
        context.user_data.pop('stats_family_id', None)
        context.user_data.pop('stats_family_name', None)
        context.user_data.pop('stats_period_type', None)
        context.user_data.pop('stats_year', None)
        context.user_data.pop('stats_month', None)
        context.user_data.pop('stats_start_date', None)
        context.user_data.pop('stats_end_date', None)


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


def calculate_date_range(year: int, month: Optional[int] = None) -> Tuple[datetime, datetime]:
    """Calculate date range for given year and optional month.
    
    Args:
        year: Year
        month: Optional month (1-12)
        
    Returns:
        Tuple of (start_date, end_date)
    """
    if month:
        start_date = datetime(year, month, 1, 0, 0, 0)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, 0, 0, 0) - timedelta(seconds=1)
        else:
            end_date = datetime(year, month + 1, 1, 0, 0, 0) - timedelta(seconds=1)
    else:
        start_date = datetime(year, 1, 1, 0, 0, 0)
        end_date = datetime(year, 12, 31, 23, 59, 59)
    
    return start_date, end_date


def format_period_name(year: int, month: Optional[int] = None) -> str:
    """Format period name for display.
    
    Args:
        year: Year
        month: Optional month (1-12)
        
    Returns:
        Formatted period name
    """
    if month:
        month_names = {
            1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
            5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
            9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
        }
        return f"{month_names[month]} {year}"
    else:
        return f"{year} год"


def extract_id_from_callback(callback_data: str) -> int:
    """Extract numeric ID from callback data."""
    return int(callback_data.split('_')[-1])


async def handle_db_operation(operation, error_message: str):
    """Handle database operations with error handling.
    
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
# MESSAGE FORMATTERS
# ============================================================================

def format_basic_statistics_message(stats: dict, period_name: str, stats_type: str, family_name: str) -> str:
    """Format basic statistics message.
    
    Args:
        stats: Statistics data from get_period_statistics
        period_name: Name of the period
        stats_type: Type of statistics (personal/family)
        family_name: Name of the family
        
    Returns:
        Formatted message
    """
    type_text = "Личная статистика" if stats_type == StatsType.PERSONAL else "Статистика семьи"
    
    income_total = stats.get('income_total', 0)
    expense_total = stats.get('expense_total', 0)
    balance = stats.get('balance', 0)
    
    lines = [
        f"{Emoji.STATS} <b>{type_text}</b>",
        f"{Emoji.FAMILY} Семья: {family_name}",
        f"{Emoji.CALENDAR} Период: {period_name}",
        "",
        f"💹 <b>Общая сумма доходов:</b> {format_amount(income_total)}",
        f"{Emoji.MONEY} <b>Общая сумма расходов:</b> {format_amount(expense_total)}",
        f"🧮 <b>Баланс:</b> {format_amount(balance)}",
        ""
    ]
    
    if income_total == 0 and expense_total == 0:
        lines.append("✨ За выбранный период операций не было!")
        return "\n".join(lines)
    
    income_by_category = stats.get('income_by_category', [])
    if income_by_category:
        lines.append("<b>Доходы по категориям:</b>")
        lines.append("")
        lines.append(create_category_chart(income_by_category, max_categories=5))
        lines.append("")
    
    expense_by_category = stats.get('expense_by_category', [])
    if expense_by_category:
        lines.append("<b>Расходы по категориям:</b>")
        lines.append("")
        lines.append(create_category_chart(expense_by_category, max_categories=5))
    
    return "\n".join(lines)


def format_detailed_statistics_message(
    stats: dict,
    income_stats: dict,
    period_name: str,
    stats_type: str,
    family_name: str
) -> str:
    """Format detailed statistics message with individual transactions.
    
    Args:
        stats: Statistics data from get_detailed_statistics
        period_name: Name of the period
        stats_type: Type of statistics (personal/family)
        family_name: Name of the family
        
    Returns:
        Formatted message
    """
    from decimal import Decimal
    from collections import defaultdict
    
    type_text = "Детализированная личная статистика" if stats_type == StatsType.PERSONAL else "Детализированная статистика семьи"
    income_total = income_stats.get('total', Decimal('0')) if income_stats else Decimal('0')
    expense_total = stats.get('total', Decimal('0')) if stats else Decimal('0')
    
    lines = [
        f"{Emoji.DOCUMENT} <b>{type_text}</b>",
        f"{Emoji.FAMILY} Семья: {family_name}",
        f"{Emoji.CALENDAR} Период: {period_name}",
        "",
        f"💹 <b>Общая сумма доходов:</b> {format_amount(income_total)}",
        f"{Emoji.MONEY} <b>Общая сумма расходов:</b> {format_amount(expense_total)}",
        ""
    ]

    def append_section(section_title: str, section_stats: dict, is_income: bool) -> None:
        if not section_stats or section_stats.get('total', Decimal('0')) == 0:
            lines.append(f"✨ За выбранный период {'доходов' if is_income else 'расходов'} не было!")
            lines.append("")
            return
        if section_stats.get('by_category'):
            lines.append(f"<b>{section_title}</b>")
            lines.append("")
            for cat_data in section_stats['by_category']:
                cat_name = cat_data['category_name']
                amount = cat_data['amount']
                percentage = cat_data['percentage']
                expenses = cat_data.get('expenses', [])

                lines.append(f"• <b>{cat_name}</b>")
                lines.append(f"   {format_amount(amount)} ({percentage:.1f}%)")
                lines.append("")

                if expenses:
                    has_users = expenses and 'user_id' in expenses[0] and 'user_name' in expenses[0]
                    if stats_type == StatsType.FAMILY and has_users:
                        user_expenses = defaultdict(list)
                        user_totals = defaultdict(lambda: Decimal('0'))

                        for expense in expenses:
                            user_id = expense['user_id']
                            user_name = expense['user_name']
                            user_expenses[user_id].append(expense)
                            user_totals[user_id] += expense['amount']
                            if 'user_name' not in user_expenses[user_id][0]:
                                user_expenses[user_id][0]['stored_user_name'] = user_name

                        for _, user_expense_list in user_expenses.items():
                            user_name = user_expense_list[0]['user_name']
                            user_total = user_totals[user_expense_list[0]['user_id']]
                            lines.append(f"   👤 <b>{user_name}:</b> {format_amount(user_total)}")

                            for expense in user_expense_list[:10]:
                                date_str = format_date(expense['date'])
                                amount_str = format_amount(expense['amount'])
                                desc = expense['description'] or "—"
                                description = desc[:40] + "..." if len(desc) > 40 else desc
                                lines.append(f"      • {date_str}: {amount_str}")
                                lines.append(f"        {description}")

                            if len(user_expense_list) > 10:
                                lines.append(f"      <i>... и еще {len(user_expense_list) - 10} операций</i>")
                            lines.append("")
                    else:
                        lines.append("   <i>Детализация:</i>")
                        for expense in expenses[:20]:
                            date_str = format_date(expense['date'])
                            amount_str = format_amount(expense['amount'])
                            desc = expense['description'] or ("Без описания" if not is_income else "—")
                            description = desc[:40] + "..." if len(desc) > 40 else desc
                            lines.append(f"   • {date_str}: {amount_str}")
                            lines.append(f"     {description}")
                            lines.append("")
                        if len(expenses) > 20:
                            lines.append(f"   <i>... и еще {len(expenses) - 20} операций</i>")
                            lines.append("")

    append_section("Доходы по категориям:", income_stats, is_income=True)
    append_section("Расходы по категориям:", stats, is_income=False)

    return "\n".join(lines)


# ============================================================================
# KEYBOARD BUILDERS
# ============================================================================

class KeyboardBuilder:
    """Builder class for creating keyboards."""
    
    @staticmethod
    def build_type_selection_keyboard(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
        """Build keyboard for statistics type selection."""
        keyboard = [
            [InlineKeyboardButton(f"{Emoji.USER} Моя статистика", callback_data=CallbackPattern.STATS_TYPE_PERSONAL)],
            [InlineKeyboardButton(f"{Emoji.USERS} Статистика семьи", callback_data=CallbackPattern.STATS_TYPE_FAMILY)]
        ]
        keyboard = add_navigation_buttons(keyboard, context, current_state="statistics")
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_family_selection_keyboard(families: list, context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
        """Build keyboard for family selection."""
        keyboard = [
            [InlineKeyboardButton(
                f"{Emoji.FAMILY} {family.name}",
                callback_data=f"{CallbackPattern.STATS_FAMILY_PREFIX}{family.id}"
            )]
            for family in families
        ]
        keyboard = add_navigation_buttons(keyboard, context, current_state="stats_select_family")
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_period_type_keyboard(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
        """Build keyboard for period type selection."""
        keyboard = [
            [InlineKeyboardButton(f"{Emoji.CALENDAR} По месяцам", callback_data=CallbackPattern.STATS_PERIOD_TYPE_MONTH)],
            [InlineKeyboardButton(f"{Emoji.CALENDAR} По годам", callback_data=CallbackPattern.STATS_PERIOD_TYPE_YEAR)]
        ]
        keyboard = add_navigation_buttons(keyboard, context, current_state="stats_select_period_type")
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_month_selection_keyboard(months: List[Tuple[int, int]], context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
        """Build keyboard for month selection."""
        month_names = {
            1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
            5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
            9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
        }
        
        keyboard = []
        # Show last 12 months, most recent first
        for year, month in reversed(months[-12:]):
            month_name = f"{month_names[month]} {year}"
            callback_data = f"{CallbackPattern.STATS_MONTH_PREFIX}{year}_{month}"
            keyboard.append([InlineKeyboardButton(month_name, callback_data=callback_data)])
        
        keyboard = add_navigation_buttons(keyboard, context, current_state="stats_select_month")
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_year_selection_keyboard(years: List[int], context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
        """Build keyboard for year selection."""
        keyboard = []
        # Show most recent years first
        for year in reversed(years):
            callback_data = f"{CallbackPattern.STATS_YEAR_PREFIX}{year}"
            keyboard.append([InlineKeyboardButton(str(year), callback_data=callback_data)])
        
        keyboard = add_navigation_buttons(keyboard, context, current_state="stats_select_year")
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_stats_view_keyboard(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
        """Build keyboard for statistics view."""
        keyboard = [
            [
                InlineKeyboardButton(f"{Emoji.EXPORT} HTML отчет", callback_data=CallbackPattern.STATS_EXPORT_HTML),
                InlineKeyboardButton(f"{Emoji.DOCUMENT} Детализация", callback_data=CallbackPattern.STATS_DETAILED_REPORT)
            ]
        ]
        keyboard = add_navigation_buttons(keyboard, context, current_state="stats_view")
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_detailed_view_keyboard(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
        """Build keyboard for detailed statistics view."""
        keyboard = [
            [InlineKeyboardButton(f"{Emoji.BACK} К обычной статистике", callback_data=CallbackPattern.STATS_BACK_TO_PERIOD)]
        ]
        keyboard = add_navigation_buttons(keyboard, context, current_state="stats_detailed_view", show_back=False)
        return InlineKeyboardMarkup(keyboard)


# ============================================================================
# HANDLERS
# ============================================================================

async def stats_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the statistics viewing process.
    
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
        message_text = ErrorMessage.NOT_REGISTERED
        keyboard = get_home_button()
        if query:
            try:
                await query.message.edit_text(message_text, reply_markup=keyboard)
            except BadRequest as e:
                if "no text in the message" in str(e).lower():
                    await query.message.reply_text(message_text, reply_markup=keyboard)
                else:
                    raise
        else:
            await update.message.reply_text(message_text)
        return ConversationHandler.END
    
    message_text = f"{Emoji.STATS} <b>Статистика финансов</b>\n\nВыберите тип статистики:"
    keyboard = KeyboardBuilder.build_type_selection_keyboard(context)
    
    if query:
        try:
            await query.message.edit_text(message_text, reply_markup=keyboard, parse_mode='HTML')
        except BadRequest as e:
            # Handle case when message has no text (e.g., media message with caption)
            if "no text in the message" in str(e).lower():
                await query.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')
            else:
                raise
    else:
        await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode='HTML')
    
    return ConversationState.SELECT_TYPE


async def stats_select_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle statistics type selection.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        Next conversation state
    """
    query = update.callback_query
    await query.answer()
    
    stats_type = query.data.split("_")[-1]
    
    stats_data = StatsData(stats_type=stats_type)
    stats_data.save_to_context(context)
    
    user_id = await get_user_id(update, context)
    
    async def get_families(session):
        return await crud.get_user_families(session, user_id)
    
    families = await handle_db_operation(get_families, "Error getting families for stats")
    
    if not families:
        keyboard = get_home_button()
        await query.edit_message_text(ErrorMessage.NO_FAMILIES, reply_markup=keyboard)
        return ConversationHandler.END
    
    # If only one family, skip family selection
    if len(families) == 1:
        stats_data.family_id = families[0].id
        stats_data.family_name = families[0].name
        stats_data.save_to_context(context)
        return await stats_show_period_type_selection(query, context)
    
    # Show family selection
    message_text = f"{Emoji.FAMILY} Выберите семью для просмотра статистики:"
    keyboard = KeyboardBuilder.build_family_selection_keyboard(families, context)
    await query.edit_message_text(message_text, reply_markup=keyboard)
    
    return ConversationState.SELECT_FAMILY


async def stats_select_family(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle family selection.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        Next conversation state
    """
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
    
    stats_data = StatsData.from_context(context)
    stats_data.family_id = family_id
    stats_data.family_name = family.name
    stats_data.save_to_context(context)
    
    return await stats_show_period_type_selection(query, context)


async def stats_show_period_type_selection(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show period type selection keyboard.
    
    Args:
        query: Callback query object
        context: Telegram context object
        
    Returns:
        Next conversation state
    """
    message_text = f"{Emoji.CALENDAR} Выберите тип периода для статистики:"
    keyboard = KeyboardBuilder.build_period_type_keyboard(context)
    await query.edit_message_text(message_text, reply_markup=keyboard)
    
    return ConversationState.SELECT_PERIOD_TYPE


async def stats_select_period_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle period type selection (month/year).
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        Next conversation state
    """
    query = update.callback_query
    await query.answer()
    
    period_type = PeriodType.MONTH if "month" in query.data else PeriodType.YEAR
    
    stats_data = StatsData.from_context(context)
    stats_data.period_type = period_type
    stats_data.save_to_context(context)
    
    user_id = await get_user_id(update, context)
    is_family = (stats_data.stats_type == StatsType.FAMILY)
    entity_id = stats_data.family_id if is_family else user_id
    
    # Get available periods
    async def get_periods(session):
        return await crud.get_available_periods(session, entity_id, is_family=is_family)
    
    periods_data = await handle_db_operation(get_periods, "Error getting available periods")
    
    if not periods_data:
        keyboard = get_home_button()
        await query.edit_message_text(ErrorMessage.STATS_ERROR, reply_markup=keyboard)
        return ConversationHandler.END
    
    if period_type == PeriodType.MONTH:
        months = periods_data['months']
        if not months:
            keyboard = get_home_button()
            await query.edit_message_text(ErrorMessage.NO_PERIODS, reply_markup=keyboard)
            return ConversationHandler.END
        
        message_text = f"{Emoji.CALENDAR} Выберите месяц для просмотра статистики:"
        keyboard = KeyboardBuilder.build_month_selection_keyboard(months, context)
        await query.edit_message_text(message_text, reply_markup=keyboard)
    else:
        years = periods_data['years']
        if not years:
            keyboard = get_home_button()
            await query.edit_message_text(ErrorMessage.NO_PERIODS, reply_markup=keyboard)
            return ConversationHandler.END
        
        message_text = f"{Emoji.CALENDAR} Выберите год для просмотра статистики:"
        keyboard = KeyboardBuilder.build_year_selection_keyboard(years, context)
        await query.edit_message_text(message_text, reply_markup=keyboard)
    
    return ConversationState.SELECT_PERIOD


async def stats_select_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle month selection and display statistics.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        Next conversation state
    """
    query = update.callback_query
    await query.answer()
    
    # Parse year_month from callback data
    year_month = query.data.replace(CallbackPattern.STATS_MONTH_PREFIX, "")
    year, month = map(int, year_month.split('_'))
    
    stats_data = StatsData.from_context(context)
    stats_data.year = year
    stats_data.month = month
    
    # Calculate date range
    start_date, end_date = calculate_date_range(year, month)
    stats_data.start_date = start_date
    stats_data.end_date = end_date
    stats_data.save_to_context(context)
    
    return await show_basic_statistics(query, context)


async def stats_select_year(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle year selection and display statistics.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        Next conversation state
    """
    query = update.callback_query
    await query.answer()
    
    # Parse year from callback data
    year = int(query.data.replace(CallbackPattern.STATS_YEAR_PREFIX, ""))
    
    stats_data = StatsData.from_context(context)
    stats_data.year = year
    stats_data.month = None
    # Explicitly clear month from context (for yearly reports)
    context.user_data.pop('stats_month', None)
    
    # Calculate date range
    start_date, end_date = calculate_date_range(year)
    stats_data.start_date = start_date
    stats_data.end_date = end_date
    stats_data.save_to_context(context)
    
    return await show_basic_statistics(query, context)


async def show_basic_statistics(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show basic statistics.
    
    Args:
        query: Callback query object
        context: Telegram context object
        
    Returns:
        Next conversation state
    """
    stats_data = StatsData.from_context(context)
    user_id = context.user_data.get('user_id')
    
    await query.edit_message_text(f"{Emoji.LOADING} Загрузка статистики...")
    
    is_family = (stats_data.stats_type == StatsType.FAMILY)
    entity_id = stats_data.family_id if is_family else user_id
    
    async def get_statistics(session):
        return await crud.get_period_financial_statistics(
            session, entity_id,
            stats_data.start_date, stats_data.end_date,
            is_family=is_family
        )
    
    stats = await handle_db_operation(get_statistics, "Error getting statistics")
    
    if stats is None:
        keyboard = get_home_button()
        await query.edit_message_text(ErrorMessage.STATS_ERROR, reply_markup=keyboard)
        return ConversationHandler.END
    
    period_name = format_period_name(stats_data.year, stats_data.month)
    message_text = format_basic_statistics_message(
        stats, period_name, stats_data.stats_type, stats_data.family_name
    )
    
    keyboard = KeyboardBuilder.build_stats_view_keyboard(context)
    await query.edit_message_text(message_text, reply_markup=keyboard, parse_mode='HTML')
    
    return ConversationState.VIEW_STATS


async def stats_show_detailed_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show detailed statistics report.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        Next conversation state
    """
    query = update.callback_query
    await query.answer()
    
    stats_data = StatsData.from_context(context)
    user_id = context.user_data.get('user_id')
    
    await query.edit_message_text(f"{Emoji.LOADING} Генерирую детализированный отчет...")
    
    is_family = (stats_data.stats_type == StatsType.FAMILY)
    entity_id = stats_data.family_id if is_family else user_id
    
    async def get_statistics(session):
        return await crud.get_detailed_statistics(
            session, entity_id,
            stats_data.start_date, stats_data.end_date,
            is_family=is_family
        )
    
    async def get_income_statistics(session):
        return await crud.get_period_income_statistics(
            session,
            entity_id,
            stats_data.start_date,
            stats_data.end_date,
            is_family=is_family
        )
    
    stats = await handle_db_operation(get_statistics, "Error getting detailed statistics")
    income_stats = await handle_db_operation(get_income_statistics, "Error getting income statistics")
    
    if stats is None:
        keyboard = get_home_button()
        await query.edit_message_text(ErrorMessage.STATS_ERROR, reply_markup=keyboard)
        return ConversationHandler.END
    
    period_name = format_period_name(stats_data.year, stats_data.month)
    message_text = format_detailed_statistics_message(
        stats, income_stats, period_name, stats_data.stats_type, stats_data.family_name
    )
    
    # Check message length and split if necessary
    MAX_MESSAGE_LENGTH = 4096
    if len(message_text) > MAX_MESSAGE_LENGTH:
        # Split message into parts
        parts = []
        current_part = ""
        
        for line in message_text.split('\n'):
            if len(current_part) + len(line) + 1 > MAX_MESSAGE_LENGTH:
                if current_part:
                    parts.append(current_part)
                current_part = line + '\n'
            else:
                current_part += line + '\n'
        
        if current_part:
            parts.append(current_part)
        
        # Send first part with edit
        await query.edit_message_text(parts[0].strip(), parse_mode='HTML')
        
        # Send remaining parts as new messages
        for part in parts[1:]:
            await query.message.reply_text(part.strip(), parse_mode='HTML')
        
        # Send final message with keyboard
        keyboard = KeyboardBuilder.build_detailed_view_keyboard(context)
        await query.message.reply_text(
            "Для возврата к обычной статистике используйте кнопку ниже:",
            reply_markup=keyboard
        )
    else:
        keyboard = KeyboardBuilder.build_detailed_view_keyboard(context)
        await query.edit_message_text(message_text, reply_markup=keyboard, parse_mode='HTML')
    
    return ConversationState.VIEW_STATS


async def stats_back_to_period(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Return to basic statistics view.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        Next conversation state
    """
    query = update.callback_query
    await query.answer()
    
    return await show_basic_statistics(query, context)


async def stats_export_html_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle HTML report export from statistics view.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        Next conversation state
    """
    from bot.utils.html_report_export import export_monthly_report, generate_report_filename
    
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(f"{Emoji.LOADING} Создаю HTML отчет...")
    
    stats_data = StatsData.from_context(context)
    user_id = context.user_data.get('user_id')
    
    if not user_id:
        await query.edit_message_text(ErrorMessage.MISSING_DATA)
        return ConversationState.VIEW_STATS
    
    is_family = (stats_data.stats_type == StatsType.FAMILY)
    entity_id = stats_data.family_id if is_family else user_id
    
    async def get_statistics(session):
        return await crud.get_period_financial_statistics(
            session, entity_id,
            stats_data.start_date, stats_data.end_date,
            is_family=is_family
        )
    
    stats = await handle_db_operation(get_statistics, "Error getting statistics for HTML export")
    
    income_total = stats.get('income_total', 0) if stats else 0
    expense_total = stats.get('expense_total', 0) if stats else 0
    if not stats or (income_total == 0 and expense_total == 0):
        await query.edit_message_text(
            f"{Emoji.ERROR} Нет данных для экспорта за выбранный период.\n\n"
            "Возвращаюсь к статистике..."
        )
        return await show_basic_statistics(query, context)
    
    # Format period name
    period_name = format_period_name(stats_data.year, stats_data.month)
    family_name = stats_data.family_name if is_family else "Личные финансы"
    
    try:
        html_file = await export_monthly_report(family_name, period_name, stats)
        filename = generate_report_filename(family_name, period_name, is_personal=not is_family)
        
        # Keyboard with navigation buttons
        keyboard = get_back_button("stats_start")
        
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=html_file,
            filename=filename,
            caption=(
                f"✅ <b>HTML отчет создан!</b>\n\n"
                f"{Emoji.FAMILY if is_family else Emoji.USER} {family_name}\n"
                f"{Emoji.CALENDAR} Период: {period_name}\n\n"
                f"{Emoji.DOCUMENT} Откройте файл в браузере для просмотра"
            ),
            parse_mode='HTML',
            reply_markup=keyboard
        )
        
        # Return to statistics view
        return await show_basic_statistics(query, context)
        
    except Exception as e:
        logger.error(f"Error creating HTML report: {e}", exc_info=True)
        await query.edit_message_text(
            f"{Emoji.ERROR} <b>Ошибка при создании отчета</b>\n\n"
            f"Попробуйте позже. Возвращаюсь к статистике..."
        )
        return await show_basic_statistics(query, context)


async def stats_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the statistics viewing process.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        End conversation state
    """
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(f"{Emoji.WAVE} Просмотр статистики отменен.")
    
    stats_data = StatsData()
    stats_data.clear_from_context(context)
    
    return ConversationHandler.END


# ============================================================================
# CONVERSATION HANDLER
# ============================================================================

stats_handler = ConversationHandler(
    entry_points=[
        CommandHandler("stats", stats_start),
        CallbackQueryHandler(stats_start, pattern=f"^{CallbackPattern.STATS_START}$")
    ],
    states={
        ConversationState.SELECT_TYPE: [
            CallbackQueryHandler(stats_select_type, pattern="^stats_type_(personal|family)$"),
            CallbackQueryHandler(stats_cancel, pattern=f"^{CallbackPattern.STATS_CANCEL}$")
        ],
        ConversationState.SELECT_FAMILY: [
            CallbackQueryHandler(stats_select_family, pattern=f"^{CallbackPattern.STATS_FAMILY_PREFIX}\\d+$"),
            CallbackQueryHandler(stats_cancel, pattern=f"^{CallbackPattern.STATS_CANCEL}$")
        ],
        ConversationState.SELECT_PERIOD_TYPE: [
            CallbackQueryHandler(stats_select_period_type, pattern="^stats_period_type_(month|year)$"),
            CallbackQueryHandler(stats_cancel, pattern=f"^{CallbackPattern.STATS_CANCEL}$")
        ],
        ConversationState.SELECT_PERIOD: [
            CallbackQueryHandler(stats_select_month, pattern=f"^{CallbackPattern.STATS_MONTH_PREFIX}\\d+_\\d+$"),
            CallbackQueryHandler(stats_select_year, pattern=f"^{CallbackPattern.STATS_YEAR_PREFIX}\\d+$"),
            CallbackQueryHandler(stats_cancel, pattern=f"^{CallbackPattern.STATS_CANCEL}$")
        ],
        ConversationState.VIEW_STATS: [
            CallbackQueryHandler(stats_export_html_handler, pattern=f"^{CallbackPattern.STATS_EXPORT_HTML}$"),
            CallbackQueryHandler(stats_show_detailed_report, pattern=f"^{CallbackPattern.STATS_DETAILED_REPORT}$"),
            CallbackQueryHandler(stats_back_to_period, pattern=f"^{CallbackPattern.STATS_BACK_TO_PERIOD}$"),
            CallbackQueryHandler(stats_cancel, pattern=f"^{CallbackPattern.STATS_CANCEL}$")
        ]
    },
    fallbacks=[
        CallbackQueryHandler(stats_cancel, pattern=f"^{CallbackPattern.STATS_CANCEL}$"),
        CallbackQueryHandler(end_conversation_silently, pattern=f"^{CallbackPattern.NAV_BACK}$"),
        # Main navigation fallbacks - end conversation and route to new section
        CallbackQueryHandler(end_conversation_and_route, pattern="^(start|categories|settings|help|add_expense|add_income|quick_expense|search|my_families|create_family|join_family|family_settings)$")
    ],
    allow_reentry=True,
    name="stats_conversation",
    persistent=False,
    per_chat=True,
    per_user=True,
    per_message=False  # False because handler uses CommandHandler in entry_points
)
