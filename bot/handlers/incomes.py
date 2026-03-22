"""Income management handlers."""

import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import IntEnum
from typing import Optional, List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.database import CategoryTypeEnum, crud, get_db
from bot.utils.formatters import format_amount
from bot.utils.helpers import (
    answer_query_safely as shared_answer_query_safely,
    end_conversation_silently,
    end_conversation_and_route,
    extract_id_from_callback as shared_extract_id_from_callback,
    get_user_id,
    handle_db_operation as shared_handle_db_operation,
    notify_income_to_family,
)
from bot.utils.keyboards import add_navigation_buttons, get_home_button, get_add_another_income_keyboard

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

class ConversationState(IntEnum):
    """Conversation states for income flows."""
    SELECT_FAMILY = 0
    SELECT_CATEGORY = 1
    ENTER_AMOUNT = 2
    ENTER_DESCRIPTION = 3


class CallbackPattern:
    """Callback data patterns."""
    ADD_INCOME = "add_income"
    SELECT_FAMILY_PREFIX = "income_family_"
    SELECT_CATEGORY_PREFIX = "income_category_"
    SKIP_DESCRIPTION = "income_skip_description"
    CANCEL_ADD = "cancel_add_income"
    NAV_BACK = "nav_back"


MAIN_NAV_PATTERN_ADD_INCOME_FLOW = (
    "^(start|categories|settings|help|add_expense|add_income|family_expenses|"
    "my_expenses|my_families|create_family|join_family|family_settings|"
    "stats_start|quick_expense|search)$"
)


class ValidationLimits:
    """Validation limits for inputs."""
    MAX_AMOUNT = Decimal('999999999.99')
    MIN_AMOUNT = Decimal('0')
    MAX_DESCRIPTION_LENGTH = 500


class Emoji:
    """Emoji constants."""
    ERROR = "❌"
    SUCCESS = "✅"
    MONEY = "💰"
    FAMILY = "👨‍👩‍👧‍👦"
    CATEGORY = "📂"
    CALENDAR = "📅"
    DESCRIPTION = "📝"
    SKIP = "⏭"
    USER = "👤"


class ErrorMessage:
    """Error messages."""
    NOT_REGISTERED = f"{Emoji.ERROR} Вы не зарегистрированы. Используйте команду /start для регистрации."
    NO_FAMILIES = f"{Emoji.ERROR} Вы не состоите ни в одной семье.\n\nСначала создайте семью или присоединитесь к существующей."
    NO_CATEGORIES = f"{Emoji.ERROR} Категории не найдены.\n\nОбратитесь к администратору для настройки категорий."
    FAMILY_NOT_FOUND = f"{Emoji.ERROR} Семья не найдена."
    CATEGORY_NOT_FOUND = f"{Emoji.ERROR} Категория не найдена."
    GENERAL_ERROR = f"{Emoji.ERROR} Произошла ошибка. Пожалуйста, попробуйте позже."
    MISSING_DATA = f"{Emoji.ERROR} Ошибка: отсутствуют данные."
    INVALID_AMOUNT = f"{Emoji.ERROR} Некорректная сумма.\n\nПожалуйста, введите положительное число.\nПримеры: 100, 250.50, 1000,99"
    INVALID_NUMBER = f"{Emoji.ERROR} Пожалуйста, введите числовую сумму."
    DESCRIPTION_TOO_LONG = f"{Emoji.ERROR} Описание слишком длинное. Максимум {ValidationLimits.MAX_DESCRIPTION_LENGTH} символов.\nПожалуйста, введите более короткое описание."


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class IncomeData:
    """Data class for income creation."""
    family_id: Optional[int] = None
    family_name: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    amount: Optional[Decimal] = None
    description: Optional[str] = None

    @classmethod
    def from_context(cls, context: ContextTypes.DEFAULT_TYPE, prefix: str = "income") -> "IncomeData":
        """Create IncomeData from context user_data."""
        return cls(
            family_id=context.user_data.get(f'{prefix}_family_id'),
            family_name=context.user_data.get(f'{prefix}_family_name'),
            category_id=context.user_data.get(f'{prefix}_category_id'),
            category_name=context.user_data.get(f'{prefix}_category_name'),
            amount=context.user_data.get(f'{prefix}_amount'),
            description=context.user_data.get(f'{prefix}_description')
        )

    def save_to_context(self, context: ContextTypes.DEFAULT_TYPE, prefix: str = "income") -> None:
        """Save income data to context."""
        if self.family_id is not None:
            context.user_data[f'{prefix}_family_id'] = self.family_id
        if self.family_name is not None:
            context.user_data[f'{prefix}_family_name'] = self.family_name
        if self.category_id is not None:
            context.user_data[f'{prefix}_category_id'] = self.category_id
        if self.category_name is not None:
            context.user_data[f'{prefix}_category_name'] = self.category_name
        if self.amount is not None:
            context.user_data[f'{prefix}_amount'] = self.amount
        if self.description is not None:
            context.user_data[f'{prefix}_description'] = self.description

    def clear_from_context(self, context: ContextTypes.DEFAULT_TYPE, prefix: str = "income") -> None:
        """Clear income data from context."""
        context.user_data.pop(f'{prefix}_family_id', None)
        context.user_data.pop(f'{prefix}_family_name', None)
        context.user_data.pop(f'{prefix}_category_id', None)
        context.user_data.pop(f'{prefix}_category_name', None)
        context.user_data.pop(f'{prefix}_amount', None)
        context.user_data.pop(f'{prefix}_description', None)


# ============================================================================
# HELPERS
# ============================================================================

async def answer_query_safely(query) -> None:
    """Answer callback query safely."""
    await shared_answer_query_safely(query)


async def send_or_edit_message(
    update: Update,
    message: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: Optional[str] = "HTML",
) -> None:
    """Send or edit message depending on update type."""
    # In real Telegram updates, message and callback_query are mutually exclusive.
    # Prioritizing message branch improves compatibility with unit-test mocks.
    if update.message:
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode=parse_mode)
        return

    if update.callback_query:
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode=parse_mode)


def extract_id_from_callback(callback_data: str) -> int:
    """Extract numeric ID from callback data."""
    return shared_extract_id_from_callback(callback_data)


def validate_amount(amount_str: str) -> Optional[Decimal]:
    """Validate and parse amount string."""
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


async def handle_db_operation(operation, error_message: str):
    """Handle database operations with error handling."""
    return await shared_handle_db_operation(operation, error_message)


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
            f"{Emoji.MONEY} <b>Добавление дохода</b>\n"
            f"{Emoji.FAMILY} Семья: <b>{family_name}</b>\n\n"
            f"{Emoji.CATEGORY} Выберите категорию дохода:"
        )

    @staticmethod
    def build_amount_input_message(family_name: str, category_name: str) -> str:
        """Build message for amount input."""
        return (
            f"{Emoji.MONEY} <b>Добавление дохода</b>\n"
            f"{Emoji.FAMILY} Семья: <b>{family_name}</b>\n"
            f"{Emoji.CATEGORY} Категория: <b>{category_name}</b>\n\n"
            f"{Emoji.MONEY} Введите сумму дохода:\n\n"
            "💡 <b>Примеры:</b>\n"
            "• 100\n"
            "• 250.50\n"
            "• 1000,99\n\n"
            "⚡ <b>Можно сразу добавить описание:</b>\n"
            "• 100 зарплата\n"
            "• 250.50 кэшбэк\n"
            "• 1000 подарок\n\n"
            "Для отмены используйте команду /cancel"
        )

    @staticmethod
    def build_description_input_message(income_data: IncomeData) -> str:
        """Build message for description input."""
        return (
            f"{Emoji.MONEY} <b>Добавление дохода</b>\n"
            f"{Emoji.FAMILY} Семья: <b>{income_data.family_name}</b>\n"
            f"{Emoji.CATEGORY} Категория: <b>{income_data.category_name}</b>\n"
            f"{Emoji.MONEY} Сумма: <b>{format_amount(income_data.amount)}</b>\n\n"
            f"{Emoji.DESCRIPTION} Введите описание дохода (опционально):\n\n"
            "💡 <b>Примеры:</b>\n"
            "• Зарплата за месяц\n"
            "• Кэшбэк от банка\n"
            "• Премия\n\n"
            "Или нажмите кнопку «Пропустить», чтобы сохранить без описания."
        )

    @staticmethod
    def build_income_created_message(income_data: IncomeData, income, user) -> str:
        """Build message after income creation."""
        date_str = income.date.strftime('%d.%m.%Y %H:%M')
        message = (
            f"{Emoji.SUCCESS} <b>Доход успешно добавлен!</b>\n\n"
            f"{Emoji.FAMILY} <b>Семья:</b> {income_data.family_name}\n"
            f"{Emoji.CATEGORY} <b>Категория:</b> {income_data.category_name}\n"
            f"{Emoji.MONEY} <b>Сумма:</b> {format_amount(income.amount)}\n"
        )
        if income_data.description:
            message += f"{Emoji.DESCRIPTION} <b>Описание:</b> {income_data.description}\n"
        message += (
            f"{Emoji.CALENDAR} <b>Дата:</b> {date_str}\n"
            f"{Emoji.USER} <b>Добавил:</b> {user.name}\n\n"
            "🎉 Доход зафиксирован!"
        )
        return message


# ============================================================================
# KEYBOARD BUILDERS
# ============================================================================

class KeyboardBuilder:
    """Builder class for creating keyboards."""

    @staticmethod
    def _as_markup(keyboard: List[List[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
        """Wrap button matrix into Telegram inline keyboard markup."""
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def _wrap_with_navigation(
        keyboard: List[List[InlineKeyboardButton]],
        context: ContextTypes.DEFAULT_TYPE,
        *,
        current_state: Optional[str] = None,
    ) -> InlineKeyboardMarkup:
        """Attach navigation controls and wrap keyboard markup."""
        keyboard = add_navigation_buttons(keyboard, context, current_state=current_state)
        return KeyboardBuilder._as_markup(keyboard)

    @staticmethod
    def build_no_families_keyboard(context: ContextTypes.DEFAULT_TYPE, current_state: str) -> InlineKeyboardMarkup:
        """Build keyboard when user has no families."""
        keyboard = [
            [InlineKeyboardButton(f"{Emoji.FAMILY} Создать семью", callback_data="create_family")],
            [InlineKeyboardButton("🔗 Присоединиться к семье", callback_data="join_family")]
        ]
        return KeyboardBuilder._wrap_with_navigation(keyboard, context, current_state=current_state)

    @staticmethod
    def build_family_selection_keyboard(families: List, context: ContextTypes.DEFAULT_TYPE, current_state: str) -> InlineKeyboardMarkup:
        """Build keyboard for family selection."""
        keyboard = [
            [InlineKeyboardButton(family.name, callback_data=f"{CallbackPattern.SELECT_FAMILY_PREFIX}{family.id}")]
            for family in families
        ]
        return KeyboardBuilder._wrap_with_navigation(keyboard, context, current_state=current_state)

    @staticmethod
    def build_category_selection_keyboard(categories: List, context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
        """Build keyboard for category selection (2 per row)."""
        keyboard = []
        row = []
        for category in categories:
            row.append(
                InlineKeyboardButton(
                    category.name,
                    callback_data=f"{CallbackPattern.SELECT_CATEGORY_PREFIX}{category.id}"
                )
            )
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        return KeyboardBuilder._wrap_with_navigation(keyboard, context)

    @staticmethod
    def build_amount_input_keyboard(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
        keyboard = []
        return KeyboardBuilder._wrap_with_navigation(keyboard, context, current_state="enter_income_amount")

    @staticmethod
    def build_description_input_keyboard(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
        keyboard = [[InlineKeyboardButton(f"{Emoji.SKIP} Пропустить", callback_data=CallbackPattern.SKIP_DESCRIPTION)]]
        return KeyboardBuilder._wrap_with_navigation(keyboard, context, current_state="enter_income_description")


# ============================================================================
# HANDLERS
# ============================================================================

async def add_income_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the income adding process."""
    query = update.callback_query
    await answer_query_safely(query)
    
    user_id = await get_user_id(update, context)
    if not user_id:
        keyboard = get_home_button()
        await send_or_edit_message(update, ErrorMessage.NOT_REGISTERED, reply_markup=keyboard)
        return ConversationHandler.END
    
    async def get_families(session):
        return await crud.get_user_families(session, user_id)
    
    families = await handle_db_operation(get_families, "Error starting income adding")
    
    if families is None:
        keyboard = get_home_button()
        await send_or_edit_message(update, ErrorMessage.GENERAL_ERROR, reply_markup=keyboard)
        return ConversationHandler.END
    
    if not families:
        message = MessageBuilder.build_no_families_message("📋 <b>Добавление дохода</b>")
        keyboard = KeyboardBuilder.build_no_families_keyboard(context, "add_income")
        await send_or_edit_message(update, message, reply_markup=keyboard)
        return ConversationHandler.END
    
    if len(families) == 1:
        income_data = IncomeData(family_id=families[0].id, family_name=families[0].name)
        income_data.save_to_context(context)
        return await show_category_selection(update, context)
    
    message = MessageBuilder.build_family_selection_message(
        "👨‍👩‍👧‍👦 <b>Выберите семью</b>",
        "Для какой семьи вы хотите добавить доход?"
    )
    keyboard = KeyboardBuilder.build_family_selection_keyboard(families, context, "add_income")
    await send_or_edit_message(update, message, reply_markup=keyboard)
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
    
    income_data = IncomeData(family_id=family_id, family_name=family.name)
    income_data.save_to_context(context)
    return await show_category_selection(update, context)


async def show_category_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show category selection."""
    income_data = IncomeData.from_context(context)
    
    async def get_categories(session):
        return await crud.get_family_categories(
            session,
            income_data.family_id,
            category_type=CategoryTypeEnum.INCOME
        )
    
    categories = await handle_db_operation(get_categories, "Error showing categories")
    
    if not categories:
        keyboard = get_home_button()
        await send_or_edit_message(update, ErrorMessage.NO_CATEGORIES, reply_markup=keyboard)
        return ConversationHandler.END
    
    message = MessageBuilder.build_category_selection_message(income_data.family_name)
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
    
    income_data = IncomeData.from_context(context)
    income_data.category_id = category_id
    income_data.category_name = category.name
    income_data.save_to_context(context)
    
    message = MessageBuilder.build_amount_input_message(
        income_data.family_name,
        income_data.category_name
    )
    keyboard = KeyboardBuilder.build_amount_input_keyboard(context)
    await query.edit_message_text(message, reply_markup=keyboard, parse_mode="HTML")
    
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
    
    if ' ' in input_text:
        parts = input_text.split(maxsplit=1)
        amount_str = parts[0]
        if len(parts) > 1:
            description = parts[1].strip()
            if description and len(description) > ValidationLimits.MAX_DESCRIPTION_LENGTH:
                keyboard = get_home_button()
                await update.message.reply_text(ErrorMessage.DESCRIPTION_TOO_LONG, reply_markup=keyboard)
                return ConversationState.ENTER_AMOUNT
    
    amount = validate_amount(amount_str)
    if amount is None:
        await update.message.reply_text(ErrorMessage.INVALID_AMOUNT)
        return ConversationState.ENTER_AMOUNT
    
    income_data = IncomeData.from_context(context)
    income_data.amount = amount

    income_data.description = description if description else None
    income_data.save_to_context(context)
    return await _save_income(update, context, income_data)


async def description_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle description input and save income."""
    description = None
    
    if update.callback_query:
        await update.callback_query.answer()
    elif update.message and update.message.text:
        description = update.message.text.strip()
        if len(description) > ValidationLimits.MAX_DESCRIPTION_LENGTH:
            await update.message.reply_text(ErrorMessage.DESCRIPTION_TOO_LONG)
            return ConversationState.ENTER_DESCRIPTION
    
    income_data = IncomeData.from_context(context)
    income_data.description = description
    income_data.save_to_context(context)
    
    return await _save_income(update, context, income_data)


async def _save_income(update: Update, context: ContextTypes.DEFAULT_TYPE, income_data: IncomeData) -> int:
    """Save income to database and show confirmation."""
    user_id = await get_user_id(update, context)
    
    if not all([user_id, income_data.family_id, income_data.category_id, income_data.amount]):
        await send_or_edit_message(update, ErrorMessage.MISSING_DATA, parse_mode=None)
        return ConversationHandler.END
    
    async def create_income_and_notify(session):
        income = await crud.create_income(
            session,
            user_id=user_id,
            family_id=income_data.family_id,
            category_id=income_data.category_id,
            amount=float(income_data.amount),
            description=income_data.description
        )
        await session.commit()
        
        user = await crud.get_user_by_id(session, user_id)
        category = await crud.get_category_by_id(session, income_data.category_id)
        family_members = await crud.get_family_members(session, income_data.family_id)
        
        return income, user, category, family_members
    
    result = await handle_db_operation(create_income_and_notify, "Error creating income")
    
    if result is None:
        error_text = f"{Emoji.ERROR} Произошла ошибка при сохранении дохода. Пожалуйста, попробуйте позже."
        await send_or_edit_message(update, error_text, parse_mode=None)
        return ConversationHandler.END
    
    income, user, category, family_members = result
    
    # Send notifications to family members about the new income
    await notify_income_to_family(None, context.bot, income, family_members)
    income_data.category_name = category.name
    
    message = MessageBuilder.build_income_created_message(income_data, income, user)
    reply_markup = get_add_another_income_keyboard()
    
    await send_or_edit_message(update, message, parse_mode="HTML", reply_markup=reply_markup)
    
    income_data.clear_from_context(context)
    return ConversationHandler.END


async def cancel_add_income(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel income adding process."""
    message = f"{Emoji.ERROR} Добавление дохода отменено."
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(message)
    else:
        await update.message.reply_text(message)
    IncomeData().clear_from_context(context)
    return ConversationHandler.END


# ============================================================================
# HANDLER REGISTRATION
# ============================================================================

add_income_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(add_income_start, pattern=f"^{CallbackPattern.ADD_INCOME}$"),
        CommandHandler("add_income", add_income_start)
    ],
    states={
        ConversationState.SELECT_FAMILY: [
            CallbackQueryHandler(family_selected, pattern=f"^{CallbackPattern.SELECT_FAMILY_PREFIX}\\d+$")
        ],
        ConversationState.SELECT_CATEGORY: [
            CallbackQueryHandler(category_selected, pattern=f"^{CallbackPattern.SELECT_CATEGORY_PREFIX}\\d+$")
        ],
        ConversationState.ENTER_AMOUNT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, amount_received)
        ],
        ConversationState.ENTER_DESCRIPTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, description_received),
            CallbackQueryHandler(description_received, pattern=f"^{CallbackPattern.SKIP_DESCRIPTION}$")
        ]
    },
    fallbacks=[
        CommandHandler("cancel", cancel_add_income),
        CallbackQueryHandler(cancel_add_income, pattern=f"^{CallbackPattern.CANCEL_ADD}$"),
        CallbackQueryHandler(end_conversation_silently, pattern=f"^{CallbackPattern.NAV_BACK}$"),
        CallbackQueryHandler(end_conversation_and_route, pattern=MAIN_NAV_PATTERN_ADD_INCOME_FLOW)
    ],
    name="add_income_conversation",
    persistent=False,
    allow_reentry=True,
    per_chat=True,
    per_user=True,
    per_message=False  # False because handler uses MessageHandler and CommandHandler
)

