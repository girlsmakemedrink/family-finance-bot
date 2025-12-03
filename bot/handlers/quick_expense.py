"""Quick expense templates handler with improved architecture."""

import logging
from dataclasses import dataclass
from datetime import datetime
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

from bot.database import crud, get_db
from bot.utils.formatters import format_amount
from bot.utils.helpers import end_conversation_silently, end_conversation_and_route, get_user_id
from bot.utils.keyboards import get_home_button

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

class ConversationState(IntEnum):
    """Conversation states for quick expense flow."""
    SELECT_FAMILY = 0
    SELECT_ACTION = 1
    SELECT_TEMPLATE = 2
    CREATE_SELECT_CATEGORY = 3
    CREATE_ENTER_AMOUNT = 4
    CREATE_ENTER_NAME = 5
    CREATE_ENTER_DESCRIPTION = 6


class CallbackPattern:
    """Callback data patterns for button handlers."""
    QUICK_EXPENSE = "quick_expense"
    FAMILY_PREFIX = "qe_family_"
    USE_TEMPLATE_PREFIX = "qe_use_"
    CREATE_TEMPLATE = "qe_create"
    DELETE_MENU = "qe_delete_menu"
    DELETE_TEMPLATE_PREFIX = "qe_del_"
    CATEGORY_PREFIX = "qe_cat_"
    SKIP_DESCRIPTION = "qe_skip_desc"
    CANCEL = "cancel"
    ADD_EXPENSE = "add_expense"
    START = "start"


class ValidationLimits:
    """Validation limits for user inputs."""
    MAX_AMOUNT = Decimal('999999999.99')
    MIN_AMOUNT = Decimal('0')
    MAX_NAME_LENGTH = 100
    MAX_DESCRIPTION_LENGTH = 500


class Emoji:
    """Emojis used in messages."""
    ERROR = "❌"
    SUCCESS = "✅"
    QUICK = "⚡"
    FAMILY = "👨‍👩‍👧‍👦"
    MONEY = "💰"
    NOTE = "📝"
    PLUS = "➕"
    DELETE = "🗑"
    SKIP = "⏭"
    HOME = "🏠"
    LINK = "🔗"
    SPEECH = "💬"


class ErrorMessage:
    """Error messages."""
    GENERAL = f"{Emoji.ERROR} Произошла ошибка. Попробуйте позже."
    NO_FAMILIES = f"{Emoji.ERROR} <b>У вас нет семей</b>\n\nСоздайте семью или присоединитесь к существующей."
    FAMILY_NOT_FOUND = f"{Emoji.ERROR} Семья не найдена."
    NO_CATEGORIES = f"{Emoji.ERROR} Категории не найдены."
    TEMPLATE_NOT_FOUND = f"{Emoji.ERROR} Шаблон не найден."
    CREATE_EXPENSE_FAILED = f"{Emoji.ERROR} Ошибка при создании расхода."
    CREATE_TEMPLATE_FAILED = f"{Emoji.ERROR} Ошибка при создании шаблона."
    DELETE_TEMPLATE_FAILED = f"{Emoji.ERROR} Ошибка при удалении шаблона."
    NO_TEMPLATES_TO_DELETE = f"{Emoji.ERROR} У вас нет шаблонов для удаления."
    INVALID_AMOUNT = f"{Emoji.ERROR} Неверная сумма. Введите положительное число до {ValidationLimits.MAX_AMOUNT}:"
    INVALID_NUMBER_FORMAT = f"{Emoji.ERROR} Неверный формат. Введите число (например: 100 или 100.50):"
    INVALID_NAME_LENGTH = f"{Emoji.ERROR} Название должно быть от 1 до {ValidationLimits.MAX_NAME_LENGTH} символов. Попробуйте еще раз:"
    INVALID_DESCRIPTION_LENGTH = f"{Emoji.ERROR} Описание слишком длинное (максимум {ValidationLimits.MAX_DESCRIPTION_LENGTH} символов). Попробуйте еще раз:"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class TemplateData:
    """Data class for template creation."""
    family_id: int
    family_name: str
    category_id: Optional[int] = None
    amount: Optional[Decimal] = None
    name: Optional[str] = None
    description: Optional[str] = None

    @classmethod
    def from_context(cls, context: ContextTypes.DEFAULT_TYPE) -> 'TemplateData':
        """Create TemplateData from context user_data."""
        return cls(
            family_id=context.user_data.get('qe_family_id'),
            family_name=context.user_data.get('qe_family_name', 'Unknown'),
            category_id=context.user_data.get('qe_category_id'),
            amount=context.user_data.get('qe_amount'),
            name=context.user_data.get('qe_name'),
            description=context.user_data.get('qe_description')
        )

    def save_to_context(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Save template data to context."""
        context.user_data['qe_family_id'] = self.family_id
        context.user_data['qe_family_name'] = self.family_name
        if self.category_id is not None:
            context.user_data['qe_category_id'] = self.category_id
        if self.amount is not None:
            context.user_data['qe_amount'] = self.amount
        if self.name is not None:
            context.user_data['qe_name'] = self.name
        if self.description is not None:
            context.user_data['qe_description'] = self.description


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


def create_keyboard(buttons: List[List[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    """Create inline keyboard markup from button list."""
    return InlineKeyboardMarkup(buttons)


def create_cancel_button() -> InlineKeyboardButton:
    """Create cancel button."""
    return InlineKeyboardButton(f"{Emoji.ERROR} Отменить", callback_data=CallbackPattern.CANCEL)


def create_navigation_keyboard() -> List[List[InlineKeyboardButton]]:
    """Create standard navigation keyboard."""
    return [
        [InlineKeyboardButton(f"{Emoji.QUICK} К списку шаблонов", callback_data=CallbackPattern.QUICK_EXPENSE)],
        [InlineKeyboardButton(f"{Emoji.HOME} Главное меню", callback_data=CallbackPattern.START)]
    ]


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
            logger.error(f"{error_message}: {e}")
            result = None
        finally:
            break
    return result


def validate_amount(amount_str: str) -> tuple[Optional[Decimal], Optional[str]]:
    """
    Validate amount input.
    
    Args:
        amount_str: String representation of amount
        
    Returns:
        Tuple of (validated_amount, error_message)
    """
    amount_str = amount_str.strip().replace(',', '.')
    
    try:
        amount = Decimal(amount_str)
        if amount <= ValidationLimits.MIN_AMOUNT or amount > ValidationLimits.MAX_AMOUNT:
            return None, ErrorMessage.INVALID_AMOUNT
        return amount, None
    except (InvalidOperation, ValueError):
        return None, ErrorMessage.INVALID_NUMBER_FORMAT


def validate_name(name: str) -> tuple[Optional[str], Optional[str]]:
    """
    Validate template name.
    
    Args:
        name: Template name
        
    Returns:
        Tuple of (validated_name, error_message)
    """
    name = name.strip()
    if not name or len(name) > ValidationLimits.MAX_NAME_LENGTH:
        return None, ErrorMessage.INVALID_NAME_LENGTH
    return name, None


def validate_description(description: str) -> tuple[Optional[str], Optional[str]]:
    """
    Validate description.
    
    Args:
        description: Description text
        
    Returns:
        Tuple of (validated_description, error_message)
    """
    description = description.strip()
    if len(description) > ValidationLimits.MAX_DESCRIPTION_LENGTH:
        return None, ErrorMessage.INVALID_DESCRIPTION_LENGTH
    return description, None


def extract_id_from_callback(callback_data: str) -> int:
    """Extract numeric ID from callback data."""
    return int(callback_data.split('_')[-1])


# ============================================================================
# MESSAGE BUILDERS
# ============================================================================

class MessageBuilder:
    """Builder class for creating formatted messages."""
    
    @staticmethod
    def build_family_selection_message() -> str:
        """Build message for family selection."""
        return (
            f"{Emoji.QUICK} <b>Быстрые расходы</b>\n\n"
            "Выберите семью:"
        )
    
    @staticmethod
    def build_template_menu_message(family_name: str, templates: List) -> str:
        """Build message for template menu."""
        message = (
            f"{Emoji.QUICK} <b>Быстрые расходы</b>\n"
            f"{Emoji.FAMILY} Семья: <b>{family_name}</b>\n\n"
        )
        
        if templates:
            message += "Ваши шаблоны:\n\n"
            for template in templates:
                message += (
                    f"{template.category.icon} <b>{template.name}</b>\n"
                    f"{Emoji.MONEY} {format_amount(template.amount)}\n\n"
                )
        else:
            message += "У вас пока нет шаблонов.\n"
        
        return message
    
    @staticmethod
    def build_expense_created_message(template, expense) -> str:
        """Build message for expense creation confirmation."""
        message = (
            f"{Emoji.SUCCESS} <b>Расход добавлен!</b>\n\n"
            f"{template.category.icon} <b>{template.category.name}</b>\n"
            f"{Emoji.MONEY} Сумма: <b>{format_amount(expense.amount)}</b>\n"
        )
        
        if expense.description:
            message += f"{Emoji.NOTE} Описание: {expense.description}\n"
        
        return message
    
    @staticmethod
    def build_category_selection_message(family_name: str) -> str:
        """Build message for category selection."""
        return (
            f"{Emoji.PLUS} <b>Создание шаблона</b>\n"
            f"{Emoji.FAMILY} Семья: <b>{family_name}</b>\n\n"
            "Выберите категорию:"
        )
    
    @staticmethod
    def build_amount_input_message(family_name: str) -> str:
        """Build message for amount input."""
        return (
            f"{Emoji.PLUS} <b>Создание шаблона</b>\n"
            f"{Emoji.FAMILY} Семья: <b>{family_name}</b>\n\n"
            "Введите сумму расхода:"
        )
    
    @staticmethod
    def build_name_input_message(family_name: str, amount: Decimal) -> str:
        """Build message for name input."""
        return (
            f"{Emoji.PLUS} <b>Создание шаблона</b>\n"
            f"{Emoji.FAMILY} Семья: <b>{family_name}</b>\n"
            f"{Emoji.MONEY} Сумма: <b>{format_amount(amount)}</b>\n\n"
            "Введите название шаблона (например: 'Обед в кафе'):"
        )
    
    @staticmethod
    def build_description_input_message(family_name: str, name: str, amount: Decimal) -> str:
        """Build message for description input."""
        return (
            f"{Emoji.PLUS} <b>Создание шаблона</b>\n"
            f"{Emoji.FAMILY} Семья: <b>{family_name}</b>\n"
            f"{Emoji.NOTE} Название: <b>{name}</b>\n"
            f"{Emoji.MONEY} Сумма: <b>{format_amount(amount)}</b>\n\n"
            "Введите описание (необязательно) или нажмите Пропустить:"
        )
    
    @staticmethod
    def build_template_created_message(template) -> str:
        """Build message for template creation confirmation."""
        message = (
            f"{Emoji.SUCCESS} <b>Шаблон создан!</b>\n\n"
            f"{Emoji.NOTE} {template.name}\n"
            f"{template.category.icon} {template.category.name}\n"
            f"{Emoji.MONEY} {format_amount(template.amount)}\n"
        )
        
        if template.description:
            message += f"\n{Emoji.SPEECH} {template.description}\n"
        
        return message
    
    @staticmethod
    def build_delete_menu_message(family_name: str) -> str:
        """Build message for template deletion menu."""
        return (
            f"{Emoji.DELETE} <b>Удаление шаблона</b>\n"
            f"{Emoji.FAMILY} Семья: <b>{family_name}</b>\n\n"
            "Выберите шаблон для удаления:"
        )


# ============================================================================
# KEYBOARD BUILDERS
# ============================================================================

class KeyboardBuilder:
    """Builder class for creating keyboards."""
    
    @staticmethod
    def build_no_families_keyboard() -> InlineKeyboardMarkup:
        """Build keyboard for no families state."""
        buttons = [
            [InlineKeyboardButton(f"{Emoji.PLUS} Создать семью", callback_data="create_family")],
            [InlineKeyboardButton(f"{Emoji.LINK} Присоединиться", callback_data="join_family")]
        ]
        return create_keyboard(buttons)
    
    @staticmethod
    def build_family_selection_keyboard(families: List) -> InlineKeyboardMarkup:
        """Build keyboard for family selection."""
        buttons = [
            [InlineKeyboardButton(
                f"{Emoji.FAMILY} {family.family.name}",
                callback_data=f"{CallbackPattern.FAMILY_PREFIX}{family.family.id}"
            )]
            for family in families
        ]
        buttons.append([create_cancel_button()])
        return create_keyboard(buttons)
    
    @staticmethod
    def build_template_menu_keyboard(templates: List) -> InlineKeyboardMarkup:
        """Build keyboard for template menu."""
        buttons = []
        
        for template in templates:
            buttons.append([
                InlineKeyboardButton(
                    f"{Emoji.SUCCESS} {template.category.icon} {template.name}",
                    callback_data=f"{CallbackPattern.USE_TEMPLATE_PREFIX}{template.id}"
                )
            ])
        
        if templates:
            buttons.append([
                InlineKeyboardButton(
                    f"{Emoji.DELETE} Удалить шаблон",
                    callback_data=CallbackPattern.DELETE_MENU
                )
            ])
        
        buttons.extend([
            [InlineKeyboardButton(f"{Emoji.PLUS} Создать шаблон", callback_data=CallbackPattern.CREATE_TEMPLATE)],
            [create_cancel_button()]
        ])
        
        return create_keyboard(buttons)
    
    @staticmethod
    def build_category_selection_keyboard(categories: List) -> InlineKeyboardMarkup:
        """Build keyboard for category selection."""
        buttons = [
            [InlineKeyboardButton(
                f"{category.icon} {category.name}",
                callback_data=f"{CallbackPattern.CATEGORY_PREFIX}{category.id}"
            )]
            for category in categories
        ]
        buttons.append([create_cancel_button()])
        return create_keyboard(buttons)
    
    @staticmethod
    def build_description_input_keyboard() -> InlineKeyboardMarkup:
        """Build keyboard for description input."""
        buttons = [
            [InlineKeyboardButton(f"{Emoji.SKIP} Пропустить", callback_data=CallbackPattern.SKIP_DESCRIPTION)],
            [create_cancel_button()]
        ]
        return create_keyboard(buttons)
    
    @staticmethod
    def build_expense_created_keyboard(template_id: int) -> InlineKeyboardMarkup:
        """Build keyboard after expense creation."""
        buttons = [
            [InlineKeyboardButton(
                f"{Emoji.PLUS} Использовать шаблон",
                callback_data=f"{CallbackPattern.USE_TEMPLATE_PREFIX}{template_id}"
            )],
            *create_navigation_keyboard()
        ]
        return create_keyboard(buttons)
    
    @staticmethod
    def build_template_created_keyboard(template_id: int) -> InlineKeyboardMarkup:
        """Build keyboard after template creation."""
        buttons = [
            [InlineKeyboardButton(
                f"{Emoji.PLUS} Использовать шаблон",
                callback_data=f"{CallbackPattern.USE_TEMPLATE_PREFIX}{template_id}"
            )],
            *create_navigation_keyboard()
        ]
        return create_keyboard(buttons)
    
    @staticmethod
    def build_delete_menu_keyboard(templates: List) -> InlineKeyboardMarkup:
        """Build keyboard for template deletion."""
        buttons = [
            [InlineKeyboardButton(
                f"{Emoji.DELETE} {template.category.icon} {template.name}",
                callback_data=f"{CallbackPattern.DELETE_TEMPLATE_PREFIX}{template.id}"
            )]
            for template in templates
        ]
        buttons.append([create_cancel_button()])
        return create_keyboard(buttons)
    
    @staticmethod
    def build_simple_cancel_keyboard() -> InlineKeyboardMarkup:
        """Build simple keyboard with only cancel button."""
        return create_keyboard([[create_cancel_button()]])


# ============================================================================
# HANDLERS
# ============================================================================

async def quick_expense_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Start quick expense process.
    
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
        return ConversationHandler.END
    
    async def get_families(session):
        return await crud.get_user_families(session, user_id)
    
    families = await handle_db_operation(get_families, "Error in quick_expense_start")
    
    if families is None:
        keyboard = get_home_button()
        await send_or_edit_message(update, ErrorMessage.GENERAL, reply_markup=keyboard)
        return ConversationHandler.END
    
    if not families:
        await send_or_edit_message(
            update,
            ErrorMessage.NO_FAMILIES,
            reply_markup=KeyboardBuilder.build_no_families_keyboard()
        )
        return ConversationHandler.END
    
    # If user has only one family, skip selection
    if len(families) == 1:
        family_member = families[0]
        template_data = TemplateData(
            family_id=family_member.family.id,
            family_name=family_member.family.name
        )
        template_data.save_to_context(context)
        return await show_quick_expense_menu(update, context)
    
    # Show family selection
    message = MessageBuilder.build_family_selection_message()
    keyboard = KeyboardBuilder.build_family_selection_keyboard(families)
    await send_or_edit_message(update, message, reply_markup=keyboard)
    
    return ConversationState.SELECT_FAMILY


async def qe_family_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle family selection.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        Next conversation state
    """
    query = update.callback_query
    await answer_query_safely(query)
    
    family_id = extract_id_from_callback(query.data)
    
    async def get_family(session):
        return await crud.get_family_by_id(session, family_id)
    
    family = await handle_db_operation(get_family, f"Error getting family {family_id}")
    
    if not family:
        await query.edit_message_text(ErrorMessage.FAMILY_NOT_FOUND)
        return ConversationHandler.END
    
    template_data = TemplateData(family_id=family_id, family_name=family.name)
    template_data.save_to_context(context)
    
    return await show_quick_expense_menu(update, context)


async def show_quick_expense_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Show quick expense menu.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        Next conversation state
    """
    template_data = TemplateData.from_context(context)
    user_id = await get_user_id(update, context)
    
    async def get_templates(session):
        return await crud.get_user_expense_templates(session, user_id, template_data.family_id)
    
    templates = await handle_db_operation(get_templates, "Error showing quick expense menu")
    
    if templates is None:
        keyboard = get_home_button()
        await send_or_edit_message(update, ErrorMessage.GENERAL, reply_markup=keyboard)
        return ConversationHandler.END
    
    message = MessageBuilder.build_template_menu_message(template_data.family_name, templates)
    keyboard = KeyboardBuilder.build_template_menu_keyboard(templates)
    await send_or_edit_message(update, message, reply_markup=keyboard)
    
    return ConversationState.SELECT_ACTION


async def qe_use_template(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Use a template to create expense.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        End conversation state
    """
    query = update.callback_query
    await query.answer(f"{Emoji.MONEY} Добавляю расход...")
    
    template_id = extract_id_from_callback(query.data)
    user_id = await get_user_id(update, context)
    
    async def create_expense_from_template(session):
        template = await crud.get_expense_template_by_id(session, template_id)
        if not template:
            return None, None
        
        expense = await crud.create_expense(
            session,
            user_id=user_id,
            family_id=template.family_id,
            category_id=template.category_id,
            amount=template.amount,
            description=template.description,
            date=datetime.now()
        )
        await session.commit()
        return template, expense
    
    result = await handle_db_operation(create_expense_from_template, f"Error using template {template_id}")
    
    if result is None or result[0] is None:
        await query.edit_message_text(ErrorMessage.TEMPLATE_NOT_FOUND)
        return ConversationHandler.END
    
    template, expense = result
    
    message = MessageBuilder.build_expense_created_message(template, expense)
    keyboard = KeyboardBuilder.build_expense_created_keyboard(template_id)
    await query.edit_message_text(message, parse_mode="HTML", reply_markup=keyboard)
    
    logger.info(f"Created expense from template {template_id} for user {user_id}")
    
    return ConversationHandler.END


async def qe_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Start template creation.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        Next conversation state
    """
    query = update.callback_query
    await answer_query_safely(query)
    
    template_data = TemplateData.from_context(context)
    
    async def get_categories(session):
        return await crud.get_available_categories(session, template_data.family_id)
    
    categories = await handle_db_operation(get_categories, "Error starting template creation")
    
    if not categories:
        await query.edit_message_text(ErrorMessage.NO_CATEGORIES)
        return ConversationHandler.END
    
    message = MessageBuilder.build_category_selection_message(template_data.family_name)
    keyboard = KeyboardBuilder.build_category_selection_keyboard(categories)
    await query.edit_message_text(message, parse_mode="HTML", reply_markup=keyboard)
    
    return ConversationState.CREATE_SELECT_CATEGORY


async def qe_category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle category selection for template.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        Next conversation state
    """
    query = update.callback_query
    await answer_query_safely(query)
    
    category_id = extract_id_from_callback(query.data)
    template_data = TemplateData.from_context(context)
    template_data.category_id = category_id
    template_data.save_to_context(context)
    
    message = MessageBuilder.build_amount_input_message(template_data.family_name)
    keyboard = KeyboardBuilder.build_simple_cancel_keyboard()
    await query.edit_message_text(message, parse_mode="HTML", reply_markup=keyboard)
    
    return ConversationState.CREATE_ENTER_AMOUNT


async def qe_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle amount input for template.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        Next conversation state
    """
    amount, error_message = validate_amount(update.message.text)
    
    if error_message:
        await update.message.reply_text(error_message)
        return ConversationState.CREATE_ENTER_AMOUNT
    
    template_data = TemplateData.from_context(context)
    template_data.amount = amount
    template_data.save_to_context(context)
    
    message = MessageBuilder.build_name_input_message(template_data.family_name, amount)
    keyboard = KeyboardBuilder.build_simple_cancel_keyboard()
    await update.message.reply_text(message, parse_mode="HTML", reply_markup=keyboard)
    
    return ConversationState.CREATE_ENTER_NAME


async def qe_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle name input for template.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        Next conversation state
    """
    name, error_message = validate_name(update.message.text)
    
    if error_message:
        await update.message.reply_text(error_message)
        return ConversationState.CREATE_ENTER_NAME
    
    template_data = TemplateData.from_context(context)
    template_data.name = name
    template_data.save_to_context(context)
    
    message = MessageBuilder.build_description_input_message(
        template_data.family_name,
        name,
        template_data.amount
    )
    keyboard = KeyboardBuilder.build_description_input_keyboard()
    await update.message.reply_text(message, parse_mode="HTML", reply_markup=keyboard)
    
    return ConversationState.CREATE_ENTER_DESCRIPTION


async def qe_description_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle description input for template.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        End conversation state
    """
    description = None
    
    if update.message:
        description, error_message = validate_description(update.message.text)
        if error_message:
            await update.message.reply_text(error_message)
            return ConversationState.CREATE_ENTER_DESCRIPTION
    elif update.callback_query:
        await answer_query_safely(update.callback_query)
        description = None  # Skip description
    
    template_data = TemplateData.from_context(context)
    user_id = await get_user_id(update, context)
    
    async def create_template(session):
        template = await crud.create_expense_template(
            session,
            user_id=user_id,
            family_id=template_data.family_id,
            name=template_data.name,
            category_id=template_data.category_id,
            amount=template_data.amount,
            description=description
        )
        await session.commit()
        return template
    
    template = await handle_db_operation(create_template, "Error creating template")
    
    if template is None:
        error_msg = ErrorMessage.CREATE_TEMPLATE_FAILED
        if update.message:
            await update.message.reply_text(error_msg)
        else:
            await update.callback_query.edit_message_text(error_msg)
        return ConversationHandler.END
    
    message = MessageBuilder.build_template_created_message(template)
    keyboard = KeyboardBuilder.build_template_created_keyboard(template.id)
    
    if update.message:
        await update.message.reply_text(message, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.callback_query.edit_message_text(message, parse_mode="HTML", reply_markup=keyboard)
    
    logger.info(f"Created template '{template_data.name}' for user {user_id}")
    
    return ConversationHandler.END


async def qe_delete_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Show template deletion menu.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        State to select template for deletion
    """
    query = update.callback_query
    await answer_query_safely(query)
    
    template_data = TemplateData.from_context(context)
    user_id = await get_user_id(update, context)
    
    async def get_templates(session):
        return await crud.get_user_expense_templates(session, user_id, template_data.family_id)
    
    templates = await handle_db_operation(get_templates, "Error showing delete menu")
    
    if not templates:
        await query.edit_message_text(ErrorMessage.NO_TEMPLATES_TO_DELETE)
        return ConversationHandler.END
    
    message = MessageBuilder.build_delete_menu_message(template_data.family_name)
    keyboard = KeyboardBuilder.build_delete_menu_keyboard(templates)
    await query.edit_message_text(message, parse_mode="HTML", reply_markup=keyboard)
    
    return ConversationState.SELECT_TEMPLATE


async def qe_delete_template(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Delete a template.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        End conversation state
    """
    query = update.callback_query
    await answer_query_safely(query)
    
    template_id = extract_id_from_callback(query.data)
    
    async def delete_template(session):
        deleted = await crud.delete_expense_template(session, template_id)
        if deleted:
            await session.commit()
        return deleted
    
    deleted = await handle_db_operation(delete_template, f"Error deleting template {template_id}")
    
    message = f"{Emoji.SUCCESS} Шаблон удален!" if deleted else ErrorMessage.TEMPLATE_NOT_FOUND
    keyboard = create_keyboard(create_navigation_keyboard())
    await query.edit_message_text(message, reply_markup=keyboard)
    
    return ConversationHandler.END


async def cancel_quick_expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Cancel quick expense.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        End conversation state
    """
    return await end_conversation_silently(update, context)


# ============================================================================
# CONVERSATION HANDLER
# ============================================================================

quick_expense_handler = ConversationHandler(
    entry_points=[
        CommandHandler('quick_expense', quick_expense_start),
        CallbackQueryHandler(quick_expense_start, pattern=f'^{CallbackPattern.QUICK_EXPENSE}$')
    ],
    states={
        ConversationState.SELECT_FAMILY: [
            CallbackQueryHandler(qe_family_selected, pattern=f'^{CallbackPattern.FAMILY_PREFIX}\\d+$')
        ],
        ConversationState.SELECT_ACTION: [
            CallbackQueryHandler(qe_use_template, pattern=f'^{CallbackPattern.USE_TEMPLATE_PREFIX}\\d+$'),
            CallbackQueryHandler(qe_create_start, pattern=f'^{CallbackPattern.CREATE_TEMPLATE}$'),
            CallbackQueryHandler(qe_delete_menu, pattern=f'^{CallbackPattern.DELETE_MENU}$')
        ],
        ConversationState.SELECT_TEMPLATE: [
            CallbackQueryHandler(qe_delete_template, pattern=f'^{CallbackPattern.DELETE_TEMPLATE_PREFIX}\\d+$')
        ],
        ConversationState.CREATE_SELECT_CATEGORY: [
            CallbackQueryHandler(qe_category_selected, pattern=f'^{CallbackPattern.CATEGORY_PREFIX}\\d+$')
        ],
        ConversationState.CREATE_ENTER_AMOUNT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, qe_amount_received)
        ],
        ConversationState.CREATE_ENTER_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, qe_name_received)
        ],
        ConversationState.CREATE_ENTER_DESCRIPTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, qe_description_received),
            CallbackQueryHandler(qe_description_received, pattern=f'^{CallbackPattern.SKIP_DESCRIPTION}$')
        ],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_quick_expense, pattern=f'^{CallbackPattern.CANCEL}$'),
        CommandHandler('cancel', cancel_quick_expense),
        CallbackQueryHandler(end_conversation_silently, pattern="^nav_back$"),
        # Main navigation fallbacks - end conversation and route to new section
        CallbackQueryHandler(end_conversation_and_route, pattern="^(start|categories|settings|help|add_expense|my_expenses|family_expenses|my_families|create_family|join_family|family_settings|stats_start|search)$")
    ],
    allow_reentry=True,
    name="quick_expense_conversation",
    persistent=False,
    per_chat=True,
    per_user=True
)
