"""Category management handlers with improved architecture."""

import logging
from dataclasses import dataclass
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
from bot.utils.helpers import end_conversation_silently, end_conversation_and_route, get_user_id, safe_edit_message
from bot.utils.keyboards import add_navigation_buttons, get_home_button

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

class ConversationState(IntEnum):
    """Conversation states for category management."""
    # Add category states
    ADD_SELECT_FAMILY = 0
    ADD_SELECT_TYPE = 1
    ADD_ENTER_NAME = 2
    ADD_CONFIRM = 3
    # Edit category states
    EDIT_SELECT_FAMILY = 4
    EDIT_SELECT_TYPE = 5
    EDIT_SELECT_CATEGORY = 6
    EDIT_ENTER_NAME = 7
    # Delete category states
    DELETE_SELECT_FAMILY = 8
    DELETE_SELECT_TYPE = 9
    DELETE_SELECT_CATEGORY = 10
    DELETE_CONFIRM = 11
    DELETE_SELECT_TARGET = 12


class CallbackPattern:
    """Callback data patterns."""
    CATEGORIES = "categories"
    CAT_SHOW_PREFIX = "cat_show_"
    CAT_ADD_PREFIX = "cat_add_"
    CAT_ADD_CONFIRM = "cat_add_confirm"
    CAT_ADD_CANCEL = "cat_add_cancel"
    CAT_EDIT_PREFIX = "cat_edit_"
    CAT_EDIT_CANCEL = "cat_edit_cancel"
    CAT_DELETE_PREFIX = "cat_delete_"
    CAT_DELETE_CANCEL = "cat_delete_cancel"
    EDITCAT_PREFIX = "editcat_"
    DELCAT_PREFIX = "delcat_"
    MOVETARGET_PREFIX = "movetarget_"
    DELETE_CONFIRM = "delete_confirm"
    DELETE_WITH_EXPENSES = "delete_with_expenses"
    CAT_TYPE_EXPENSE = "cat_type_expense"
    CAT_TYPE_INCOME = "cat_type_income"
    NAV_BACK = "nav_back"


class ValidationLimits:
    """Validation limits for category inputs."""
    MIN_NAME_LENGTH = 2
    MAX_NAME_LENGTH = 50


class Emoji:
    """Common emojis for UI elements."""
    ERROR = "❌"
    SUCCESS = "✅"
    WARNING = "⚠️"
    PLUS = "➕"
    EDIT = "✏️"
    DELETE = "🗑️"
    FAMILY = "👨‍👩‍👧‍👦"
    TAG = "🏷️"
    STAR = "⭐"
    PIN = "📌"
    NOTE = "📝"


class ErrorMessage:
    """Error messages."""
    NOT_REGISTERED = f"{Emoji.ERROR} Вы не зарегистрированы. Используйте команду /start для регистрации."
    NO_FAMILIES = f"{Emoji.ERROR} У вас нет семей.\n\nСоздайте семью или присоединитесь к существующей, чтобы управлять категориями."
    NO_CATEGORIES_EDIT = f"{Emoji.ERROR} У вас нет категорий для редактирования."
    NO_CATEGORIES_DELETE = f"{Emoji.ERROR} У вас нет категорий для удаления."
    CATEGORY_NOT_FOUND = f"{Emoji.ERROR} Категория не найдена."
    NAME_TOO_SHORT = f"{Emoji.ERROR} Название слишком короткое. Введите минимум {ValidationLimits.MIN_NAME_LENGTH} символа:"
    NAME_TOO_LONG = f"{Emoji.ERROR} Название слишком длинное. Максимум {ValidationLimits.MAX_NAME_LENGTH} символов:"
    NAME_EXISTS = f"{Emoji.ERROR} Категория с названием '{{name}}' уже существует.\nВведите другое название:"
    GENERAL_ERROR = f"{Emoji.ERROR} Произошла ошибка. Попробуйте позже."
    CREATE_ERROR = f"{Emoji.ERROR} Произошла ошибка при создании категории. Попробуйте позже."
    UPDATE_ERROR = f"{Emoji.ERROR} Произошла ошибка при обновлении категории."
    DELETE_ERROR = f"{Emoji.ERROR} Произошла ошибка при удалении категории."


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class CategoryData:
    """Data class for category management."""
    family_id: Optional[int] = None
    category_id: Optional[int] = None
    name: Optional[str] = None
    icon: Optional[str] = None
    target_category_id: Optional[int] = None
    category_type: Optional[CategoryTypeEnum] = None

    @classmethod
    def from_context(cls, context: ContextTypes.DEFAULT_TYPE, prefix: str) -> 'CategoryData':
        """Create CategoryData from context user_data."""
        return cls(
            family_id=context.user_data.get(f'{prefix}_family_id'),
            category_id=context.user_data.get(f'{prefix}_id'),
            name=context.user_data.get(f'{prefix}_name'),
            icon=context.user_data.get(f'{prefix}_icon'),
            target_category_id=context.user_data.get(f'{prefix}_target_cat_id'),
            category_type=context.user_data.get(f'{prefix}_category_type')
        )

    def save_to_context(self, context: ContextTypes.DEFAULT_TYPE, prefix: str) -> None:
        """Save category data to context."""
        if self.family_id is not None:
            context.user_data[f'{prefix}_family_id'] = self.family_id
        if self.category_id is not None:
            context.user_data[f'{prefix}_id'] = self.category_id
        if self.name is not None:
            context.user_data[f'{prefix}_name'] = self.name
        if self.icon is not None:
            context.user_data[f'{prefix}_icon'] = self.icon
        if self.target_category_id is not None:
            context.user_data[f'{prefix}_target_cat_id'] = self.target_category_id
        if self.category_type is not None:
            context.user_data[f'{prefix}_category_type'] = self.category_type

    def clear_from_context(self, context: ContextTypes.DEFAULT_TYPE, prefix: str) -> None:
        """Clear category data from context."""
        context.user_data.pop(f'{prefix}_family_id', None)
        context.user_data.pop(f'{prefix}_id', None)
        context.user_data.pop(f'{prefix}_name', None)
        context.user_data.pop(f'{prefix}_icon', None)
        context.user_data.pop(f'{prefix}_target_cat_id', None)
        context.user_data.pop(f'{prefix}_category_type', None)


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
    """Send new message or edit existing one."""
    query = update.callback_query
    if query:
        await safe_edit_message(query, text, reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        if update.message:
            await update.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)


def validate_category_name(name: str) -> tuple[Optional[str], Optional[str]]:
    """
    Validate category name.
    
    Args:
        name: Category name
        
    Returns:
        Tuple of (validated_name, error_message)
    """
    name = name.strip()
    
    if len(name) < ValidationLimits.MIN_NAME_LENGTH:
        return None, ErrorMessage.NAME_TOO_SHORT
    
    if len(name) > ValidationLimits.MAX_NAME_LENGTH:
        return None, ErrorMessage.NAME_TOO_LONG
    
    return name, None


def extract_id_from_callback(callback_data: str, index: int = -1) -> int:
    """Extract numeric ID from callback data."""
    return int(callback_data.split('_')[index])


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
                # Access all lazy-loaded attributes to load them into memory
                for obj in result_list:
                    if hasattr(obj, '__dict__'):
                        # Trigger loading of all attributes by accessing them
                        for key in obj.__dict__.keys():
                            getattr(obj, key, None)
                result = result_list
            # Log result info
            result_info = f"type: {type(result)}"
            if result and hasattr(result, '__len__'):
                result_info += f", count: {len(result)}"
            logger.info(f"handle_db_operation result {result_info}")
        except Exception as e:
            logger.error(f"{error_message}: {e}", exc_info=True)
            result = None
        finally:
            break
    
    # Return after the session context is closed
    return_info = f"type: {type(result)}"
    if result and hasattr(result, '__len__'):
        return_info += f", count: {len(result)}"
    logger.info(f"handle_db_operation returning: {return_info}")
    return result


# ============================================================================
# MESSAGE BUILDERS
# ============================================================================

class MessageBuilder:
    """Builder class for creating formatted messages."""
    
    @staticmethod
    def build_family_selection_message() -> str:
        """Build message for family selection."""
        return (
            f"{Emoji.TAG} <b>Управление категориями</b>\n\n"
            "Выберите семью для управления категориями:"
        )
    
    @staticmethod
    def build_categories_list_message(
        family_name: str,
        expense_default: List,
        expense_custom: List,
        income_default: List,
        income_custom: List
    ) -> str:
        """Build message showing categories by type."""
        message = f"{Emoji.TAG} <b>Категории семьи '{family_name}'</b>\n\n"
        
        message += "<b>💸 Расходы:</b>\n"
        if expense_default:
            message += f"{Emoji.PIN} Стандартные:\n"
            for cat in expense_default:
                message += f"• {cat.name}\n"
        if expense_custom:
            message += f"{Emoji.STAR} Ваши:\n"
            for cat in expense_custom:
                message += f"• {cat.name}\n"
        if not expense_default and not expense_custom:
            message += "• Нет категорий расходов\n"
        message += "\n"
        
        message += "<b>💹 Доходы:</b>\n"
        if income_default:
            message += f"{Emoji.PIN} Стандартные:\n"
            for cat in income_default:
                message += f"• {cat.name}\n"
        if income_custom:
            message += f"{Emoji.STAR} Ваши:\n"
            for cat in income_custom:
                message += f"• {cat.name}\n"
        if not income_default and not income_custom:
            message += "• Нет категорий доходов\n"
        message += "\n"
        
        message += "Выберите действие:"
        return message
    
    @staticmethod
    def build_add_category_name_prompt(category_type: CategoryTypeEnum) -> str:
        """Build prompt for category name input."""
        type_label = "расходов" if category_type == CategoryTypeEnum.EXPENSE else "доходов"
        return (
            f"{Emoji.PLUS} <b>Добавление категории {type_label}</b>\n\n"
            "Введите название категории (например: 'Рестораны', 'Такси', 'Спорт'):"
        )
    
    @staticmethod
    def build_add_category_confirmation(name: str, category_type: CategoryTypeEnum) -> str:
        """Build confirmation message for category creation."""
        type_label = "расходов" if category_type == CategoryTypeEnum.EXPENSE else "доходов"
        return (
            f"{Emoji.NOTE} <b>Подтверждение</b>\n\n"
            f"Категория {type_label}: <b>{name}</b>\n\n"
            "Создать категорию?"
        )
    
    @staticmethod
    def build_category_created_message(name: str, category_type: CategoryTypeEnum) -> str:
        """Build success message after category creation."""
        type_label = "расходов" if category_type == CategoryTypeEnum.EXPENSE else "доходов"
        return (
            f"{Emoji.SUCCESS} <b>Категория создана!</b>\n\n"
            f"{type_label.capitalize()}: <b>{name}</b>\n\n"
            "Теперь вы можете использовать эту категорию при добавлении операций."
        )
    
    @staticmethod
    def build_edit_category_list_prompt() -> str:
        """Build prompt for category selection (editing)."""
        return (
            f"{Emoji.EDIT} <b>Редактирование категории</b>\n\n"
            f"{Emoji.WARNING} Можно изменить любую категорию, включая стандартные.\n\n"
            "Выберите категорию для редактирования:"
        )
    
    @staticmethod
    def build_edit_enter_name_prompt(name: str) -> str:
        """Build prompt for entering new category name."""
        return (
            f"{Emoji.EDIT} <b>Редактирование: {name}</b>\n\n"
            "Введите новое название категории:"
        )
    
    @staticmethod
    def build_category_updated_message(name: str) -> str:
        """Build success message after category update."""
        return f"{Emoji.SUCCESS} Название категории изменено на:\n<b>{name}</b>"
    
    @staticmethod
    def build_delete_category_list_prompt() -> str:
        """Build prompt for category selection (deletion)."""
        return (
            f"{Emoji.DELETE} <b>Удаление категории</b>\n\n"
            f"{Emoji.WARNING} <b>Внимание!</b> Можно удалить любую категорию, включая стандартные.\n\n"
            "Выберите категорию для удаления:"
        )
    
    @staticmethod
    def build_delete_with_expenses_prompt(name: str, expense_count: int, income_count: int) -> str:
        """Build message when category has transactions."""
        total_count = expense_count + income_count
        return (
            f"{Emoji.WARNING} <b>Внимание!</b>\n\n"
            f"В категории '{name}' есть {total_count} операци(й).\n"
            f"Расходы: {expense_count}, доходы: {income_count}\n\n"
            "Что вы хотите сделать?"
        )
    
    @staticmethod
    def build_delete_confirm_no_expenses(name: str) -> str:
        """Build confirmation message for deletion (no transactions)."""
        return (
            f"{Emoji.DELETE} <b>Удаление категории</b>\n\n"
            f"Вы уверены, что хотите удалить категорию?\n\n"
            f"<b>{name}</b>\n\n"
            "В этой категории нет операций."
        )
    
    @staticmethod
    def build_delete_confirm_with_move(
        from_name: str,
        to_name: str,
        expense_count: int,
        income_count: int
    ) -> str:
        """Build confirmation message for deletion with transaction move."""
        total_count = expense_count + income_count
        return (
            f"{Emoji.DELETE} <b>Подтверждение удаления</b>\n\n"
            f"Удалить: <b>{from_name}</b>\n"
            f"Переместить {total_count} операци(й) в: <b>{to_name}</b>\n"
            f"Расходы: {expense_count}, доходы: {income_count}\n\n"
            "Подтвердите удаление:"
        )
    
    @staticmethod
    def build_category_deleted_message(
        name: str,
        moved_expense_count: int = 0,
        moved_income_count: int = 0,
        deleted_expense_count: int = 0,
        deleted_income_count: int = 0,
        target_name: str = ""
    ) -> str:
        """Build success message after category deletion."""
        message = f"{Emoji.SUCCESS} <b>Категория удалена!</b>\n\n{name}"
        
        moved_total = moved_expense_count + moved_income_count
        deleted_total = deleted_expense_count + deleted_income_count
        
        if moved_total > 0:
            message += (
                f"\n\nПеремещено в {target_name}: {moved_total} операци(й)"
                f"\nРасходы: {moved_expense_count}, доходы: {moved_income_count}"
            )
        elif deleted_total > 0:
            message += (
                f"\n\nУдалено: {deleted_total} операци(й)"
                f"\nРасходы: {deleted_expense_count}, доходы: {deleted_income_count}"
            )
        
        return message
    
    @staticmethod
    def build_delete_confirm_with_expenses(name: str, expense_count: int, income_count: int) -> str:
        """Build confirmation message for deletion with transactions."""
        total_count = expense_count + income_count
        return (
            f"{Emoji.DELETE} <b>Подтверждение удаления</b>\n\n"
            f"Удалить категорию <b>{name}</b>\n"
            f"вместе со всеми {total_count} операци(й)?\n"
            f"Расходы: {expense_count}, доходы: {income_count}\n\n"
            f"{Emoji.WARNING} <b>Это действие нельзя отменить!</b>"
        )

    @staticmethod
    def build_category_type_prompt(action_label: str) -> str:
        """Build prompt for category type selection."""
        return (
            f"{Emoji.TAG} <b>{action_label}</b>\n\n"
            "Выберите тип категорий:"
        )


# ============================================================================
# KEYBOARD BUILDERS
# ============================================================================

class KeyboardBuilder:
    """Builder class for creating keyboards."""
    
    @staticmethod
    def build_family_selection_keyboard(families: List, context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
        """Build keyboard for family selection."""
        keyboard = [
            [InlineKeyboardButton(
                f"{Emoji.FAMILY} {family.name}",
                callback_data=f"{CallbackPattern.CAT_SHOW_PREFIX}{family.id}"
            )]
            for family in families
        ]
        keyboard = add_navigation_buttons(keyboard, context, current_state="categories")
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_category_management_keyboard(family_id: int, has_custom: bool, has_any: bool, context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
        """Build keyboard for category management."""
        keyboard = [
            [InlineKeyboardButton(f"{Emoji.PLUS} Добавить категорию", callback_data=f"{CallbackPattern.CAT_ADD_PREFIX}{family_id}")]
        ]
        
        if has_any:
            keyboard.append([InlineKeyboardButton(f"{Emoji.EDIT} Изменить категорию", callback_data=f"{CallbackPattern.CAT_EDIT_PREFIX}{family_id}")])
        
        if has_any:
            keyboard.append([InlineKeyboardButton(f"{Emoji.DELETE} Удалить категорию", callback_data=f"{CallbackPattern.CAT_DELETE_PREFIX}{family_id}")])
        
        keyboard = add_navigation_buttons(keyboard, context, current_state="categories")
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def build_category_type_keyboard(context: ContextTypes.DEFAULT_TYPE, current_state: str) -> InlineKeyboardMarkup:
        """Build keyboard for category type selection."""
        keyboard = [
            [InlineKeyboardButton("💸 Расходы", callback_data=CallbackPattern.CAT_TYPE_EXPENSE)],
            [InlineKeyboardButton("💹 Доходы", callback_data=CallbackPattern.CAT_TYPE_INCOME)],
        ]
        keyboard = add_navigation_buttons(keyboard, context, current_state=current_state)
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_confirmation_keyboard(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
        """Build keyboard for confirmation."""
        keyboard = [
            [
                InlineKeyboardButton(f"{Emoji.SUCCESS} Создать", callback_data=CallbackPattern.CAT_ADD_CONFIRM),
                InlineKeyboardButton(f"{Emoji.ERROR} Отмена", callback_data=CallbackPattern.CAT_ADD_CANCEL)
            ]
        ]
        keyboard = add_navigation_buttons(keyboard, context, show_back=False)
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_category_list_keyboard(categories: List, pattern_prefix: str, context: ContextTypes.DEFAULT_TYPE, state: str) -> InlineKeyboardMarkup:
        """Build keyboard with list of categories."""
        keyboard = [
            [InlineKeyboardButton(
                cat.name,
                callback_data=f"{pattern_prefix}{cat.id}"
            )]
            for cat in categories
        ]
        keyboard = add_navigation_buttons(keyboard, context, current_state=state)
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_delete_confirmation_keyboard(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
        """Build keyboard for delete confirmation."""
        keyboard = [
            [InlineKeyboardButton(f"{Emoji.SUCCESS} Да, удалить", callback_data=CallbackPattern.DELETE_CONFIRM)]
        ]
        keyboard = add_navigation_buttons(keyboard, context)
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_delete_with_expenses_keyboard(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
        """Build keyboard for delete action selection when category has expenses."""
        keyboard = [
            [InlineKeyboardButton(f"📦 Переместить операции в другую категорию", callback_data=CallbackPattern.MOVETARGET_PREFIX + "select")],
            [InlineKeyboardButton(f"{Emoji.DELETE} Удалить категорию вместе с операциями", callback_data=CallbackPattern.DELETE_WITH_EXPENSES)]
        ]
        keyboard = add_navigation_buttons(keyboard, context)
        return InlineKeyboardMarkup(keyboard)


# ============================================================================
# MAIN CATEGORIES COMMAND
# ============================================================================

async def categories_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /categories command - show categories management menu."""
    query = update.callback_query
    await answer_query_safely(query)
    
    user_id = await get_user_id(update, context)
    if not user_id:
        await send_or_edit_message(update, ErrorMessage.NOT_REGISTERED)
        return
    
    async def get_families(session):
        return await crud.get_user_families(session, user_id)
    
    families = await handle_db_operation(get_families, "Error in categories_command")
    
    if not families:
        keyboard = get_home_button()
        await send_or_edit_message(update, ErrorMessage.NO_FAMILIES, reply_markup=keyboard)
        return
    
    # If user has only one family, show categories directly
    if len(families) == 1:
        await show_family_categories_by_id(update, context, families[0].id)
        return
    
    # Multiple families - let user choose
    message = MessageBuilder.build_family_selection_message()
    keyboard = KeyboardBuilder.build_family_selection_keyboard(families, context)
    await send_or_edit_message(update, message, reply_markup=keyboard)


async def show_family_categories_by_id(update: Update, context: ContextTypes.DEFAULT_TYPE, family_id: int) -> None:
    """Show categories for a specific family by ID."""
    async def get_family_and_categories(session):
        family = await crud.get_family_by_id(session, family_id)
        expense_categories = await crud.get_family_categories(
            session,
            family_id,
            category_type=CategoryTypeEnum.EXPENSE
        )
        income_categories = await crud.get_family_categories(
            session,
            family_id,
            category_type=CategoryTypeEnum.INCOME
        )
        return family, expense_categories, income_categories
    
    result = await handle_db_operation(get_family_and_categories, f"Error showing categories for family {family_id}")
    
    if result is None:
        await send_or_edit_message(update, ErrorMessage.GENERAL_ERROR)
        return
    
    family, expense_categories, income_categories = result
    
    # Separate default and custom categories
    expense_default = [c for c in expense_categories if c.is_default]
    expense_custom = [c for c in expense_categories if not c.is_default]
    income_default = [c for c in income_categories if c.is_default]
    income_custom = [c for c in income_categories if not c.is_default]
    
    message = MessageBuilder.build_categories_list_message(
        family.name,
        expense_default,
        expense_custom,
        income_default,
        income_custom
    )
    has_any = bool(expense_categories or income_categories)
    has_custom = bool(expense_custom or income_custom)
    keyboard = KeyboardBuilder.build_category_management_keyboard(family_id, has_custom, has_any, context)
    await send_or_edit_message(update, message, reply_markup=keyboard)


async def show_categories_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback handler for showing family categories."""
    query = update.callback_query
    await query.answer()
    
    family_id = extract_id_from_callback(query.data, index=2)
    await show_family_categories_by_id(update, context, family_id)


# ============================================================================
# ADD CATEGORY CONVERSATION
# ============================================================================

async def add_category_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start add category conversation."""
    query = update.callback_query
    await query.answer()
    
    family_id = extract_id_from_callback(query.data, index=2)
    cat_data = CategoryData(family_id=family_id)
    cat_data.save_to_context(context, "add_cat")
    
    message = MessageBuilder.build_category_type_prompt("Добавление новой категории")
    keyboard = KeyboardBuilder.build_category_type_keyboard(context, current_state="add_category")
    await safe_edit_message(query, message, parse_mode="HTML", reply_markup=keyboard)
    
    return ConversationState.ADD_SELECT_TYPE


async def add_category_select_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle category type selection for add flow."""
    query = update.callback_query
    await query.answer()
    
    selected_type = (
        CategoryTypeEnum.EXPENSE
        if query.data == CallbackPattern.CAT_TYPE_EXPENSE
        else CategoryTypeEnum.INCOME
    )
    
    cat_data = CategoryData.from_context(context, "add_cat")
    cat_data.category_type = selected_type
    cat_data.save_to_context(context, "add_cat")
    
    message = MessageBuilder.build_add_category_name_prompt(selected_type)
    keyboard = add_navigation_buttons([], context, current_state="add_category")
    await safe_edit_message(query, message, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    
    return ConversationState.ADD_ENTER_NAME


async def add_category_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle category name input."""
    name, error_message = validate_category_name(update.message.text)
    
    if error_message:
        keyboard = get_home_button()
        await update.message.reply_text(error_message, reply_markup=keyboard)
        return ConversationState.ADD_ENTER_NAME
    
    cat_data = CategoryData.from_context(context, "add_cat")
    
    # Check if name already exists
    async def check_name_exists(session):
        return await crud.category_name_exists(
            session,
            name,
            cat_data.family_id,
            category_type=cat_data.category_type
        )
    
    exists = await handle_db_operation(check_name_exists, "Error checking category name")
    
    if exists:
        keyboard = get_home_button()
        await update.message.reply_text(ErrorMessage.NAME_EXISTS.format(name=name), reply_markup=keyboard)
        return ConversationState.ADD_ENTER_NAME
    
    cat_data.name = name
    cat_data.icon = ""
    cat_data.save_to_context(context, "add_cat")
    
    message = MessageBuilder.build_add_category_confirmation(name, cat_data.category_type)
    keyboard = KeyboardBuilder.build_confirmation_keyboard(context)
    await update.message.reply_text(message, reply_markup=keyboard, parse_mode="HTML")
    
    return ConversationState.ADD_CONFIRM


async def add_category_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirm and create the category."""
    query = update.callback_query
    await query.answer()
    
    cat_data = CategoryData.from_context(context, "add_cat")
    
    async def create_category(session):
        category = await crud.create_category(
            session,
            name=cat_data.name,
            icon=cat_data.icon,
            family_id=cat_data.family_id,
            category_type=cat_data.category_type
        )
        await session.commit()
        return category
    
    category = await handle_db_operation(create_category, "Error creating category")
    
    keyboard = get_home_button()
    if category is None:
        await safe_edit_message(query, ErrorMessage.CREATE_ERROR, reply_markup=keyboard)
    else:
        message = MessageBuilder.build_category_created_message(cat_data.name, cat_data.category_type)
        await safe_edit_message(query, message, parse_mode="HTML", reply_markup=keyboard)
        logger.info(f"Created category {category.id} for family {cat_data.family_id}")
    
    cat_data.clear_from_context(context, "add_cat")
    return ConversationHandler.END


async def add_category_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel add category conversation."""
    query = update.callback_query
    await query.answer()
    
    keyboard = get_home_button()
    await safe_edit_message(query, f"{Emoji.ERROR} Добавление категории отменено.", reply_markup=keyboard)
    
    cat_data = CategoryData()
    cat_data.clear_from_context(context, "add_cat")
    
    return ConversationHandler.END


# ============================================================================
# EDIT CATEGORY CONVERSATION
# ============================================================================

async def edit_category_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start edit category conversation - show category selection."""
    query = update.callback_query
    await query.answer()
    
    family_id = extract_id_from_callback(query.data, index=2)
    cat_data = CategoryData(family_id=family_id)
    cat_data.save_to_context(context, "edit_cat")

    message = MessageBuilder.build_category_type_prompt("Редактирование категории")
    keyboard = KeyboardBuilder.build_category_type_keyboard(context, current_state="edit_category")
    await safe_edit_message(query, message, reply_markup=keyboard, parse_mode="HTML")
    
    return ConversationState.EDIT_SELECT_TYPE


async def edit_category_select_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle category type selection for editing."""
    query = update.callback_query
    await query.answer()
    
    selected_type = (
        CategoryTypeEnum.EXPENSE
        if query.data == CallbackPattern.CAT_TYPE_EXPENSE
        else CategoryTypeEnum.INCOME
    )
    
    cat_data = CategoryData.from_context(context, "edit_cat")
    cat_data.category_type = selected_type
    cat_data.save_to_context(context, "edit_cat")
    
    async def get_all_categories(session):
        return await crud.get_family_categories(
            session,
            cat_data.family_id,
            category_type=selected_type
        )
    
    categories = await handle_db_operation(get_all_categories, "Error getting categories")
    
    if not categories:
        keyboard = get_home_button()
        await safe_edit_message(query, ErrorMessage.NO_CATEGORIES_EDIT, reply_markup=keyboard)
        return ConversationHandler.END
    
    message = MessageBuilder.build_edit_category_list_prompt()
    keyboard = KeyboardBuilder.build_category_list_keyboard(
        categories,
        CallbackPattern.EDITCAT_PREFIX,
        context,
        "edit_category"
    )
    await safe_edit_message(query, message, reply_markup=keyboard, parse_mode="HTML")
    
    return ConversationState.EDIT_SELECT_CATEGORY


async def edit_category_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle category selection for editing - go directly to name input."""
    query = update.callback_query
    await query.answer()
    
    category_id = extract_id_from_callback(query.data, index=1)
    cat_data = CategoryData.from_context(context, "edit_cat")
    cat_data.category_id = category_id
    cat_data.save_to_context(context, "edit_cat")
    
    async def get_category(session):
        return await crud.get_category_by_id(session, category_id)
    
    category = await handle_db_operation(get_category, f"Error getting category {category_id}")
    
    if not category:
        keyboard = get_home_button()
        await safe_edit_message(query, ErrorMessage.CATEGORY_NOT_FOUND, reply_markup=keyboard)
        return ConversationHandler.END
    
    message = MessageBuilder.build_edit_enter_name_prompt(category.name)
    keyboard = add_navigation_buttons([], context, current_state="edit_category")
    await safe_edit_message(query, message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    
    return ConversationState.EDIT_ENTER_NAME


async def edit_category_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle new category name input."""
    name, error_message = validate_category_name(update.message.text)
    
    if error_message:
        keyboard = get_home_button()
        await update.message.reply_text(error_message, reply_markup=keyboard)
        return ConversationState.EDIT_ENTER_NAME
    
    cat_data = CategoryData.from_context(context, "edit_cat")
    
    async def check_and_update(session):
        exists = await crud.category_name_exists(
            session,
            name,
            cat_data.family_id,
            category_type=cat_data.category_type,
            exclude_category_id=cat_data.category_id
        )
        
        if exists:
            return None, "exists"
        
        category = await crud.update_category(session, cat_data.category_id, name=name)
        await session.commit()
        return category, None
    
    result = await handle_db_operation(check_and_update, "Error updating category name")
    
    keyboard = get_home_button()
    if result is None:
        await update.message.reply_text(ErrorMessage.UPDATE_ERROR, reply_markup=keyboard)
    else:
        category, error = result
        if error == "exists":
            await update.message.reply_text(ErrorMessage.NAME_EXISTS.format(name=name), reply_markup=keyboard)
            return ConversationState.EDIT_ENTER_NAME
        
        message = MessageBuilder.build_category_updated_message(category.name)
        await update.message.reply_text(message, parse_mode="HTML", reply_markup=keyboard)
        logger.info(f"Updated category {cat_data.category_id} name to '{name}'")
    
    cat_data.clear_from_context(context, "edit_cat")
    return ConversationHandler.END


async def edit_category_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel edit category conversation."""
    query = update.callback_query
    await query.answer()
    
    keyboard = get_home_button()
    await safe_edit_message(query, f"{Emoji.ERROR} Редактирование категории отменено.", reply_markup=keyboard)
    
    cat_data = CategoryData()
    cat_data.clear_from_context(context, "edit_cat")
    
    return ConversationHandler.END


# ============================================================================
# DELETE CATEGORY CONVERSATION
# ============================================================================

async def delete_category_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start delete category conversation - show category selection."""
    query = update.callback_query
    await query.answer()
    
    family_id = extract_id_from_callback(query.data, index=2)
    cat_data = CategoryData(family_id=family_id)
    cat_data.save_to_context(context, "delete_cat")

    message = MessageBuilder.build_category_type_prompt("Удаление категории")
    keyboard = KeyboardBuilder.build_category_type_keyboard(context, current_state="delete_category")
    await safe_edit_message(query, message, reply_markup=keyboard, parse_mode="HTML")
    
    return ConversationState.DELETE_SELECT_TYPE


async def delete_category_select_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle category type selection for deletion."""
    query = update.callback_query
    await query.answer()
    
    selected_type = (
        CategoryTypeEnum.EXPENSE
        if query.data == CallbackPattern.CAT_TYPE_EXPENSE
        else CategoryTypeEnum.INCOME
    )
    
    cat_data = CategoryData.from_context(context, "delete_cat")
    cat_data.category_type = selected_type
    cat_data.save_to_context(context, "delete_cat")
    
    async def get_all_categories(session):
        return await crud.get_family_categories(
            session,
            cat_data.family_id,
            category_type=selected_type
        )
    
    categories = await handle_db_operation(get_all_categories, "Error getting categories")
    
    if not categories:
        keyboard = get_home_button()
        await safe_edit_message(query, ErrorMessage.NO_CATEGORIES_DELETE, reply_markup=keyboard)
        return ConversationHandler.END
    
    message = MessageBuilder.build_delete_category_list_prompt()
    keyboard = KeyboardBuilder.build_category_list_keyboard(
        categories,
        CallbackPattern.DELCAT_PREFIX,
        context,
        "delete_category"
    )
    await safe_edit_message(query, message, reply_markup=keyboard, parse_mode="HTML")
    
    return ConversationState.DELETE_SELECT_CATEGORY


async def delete_category_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle category selection for deletion."""
    query = update.callback_query
    await query.answer()
    
    category_id = extract_id_from_callback(query.data, index=1)
    cat_data = CategoryData.from_context(context, "delete_cat")
    cat_data.category_id = category_id
    cat_data.save_to_context(context, "delete_cat")
    
    async def get_category_and_expenses(session):
        category = await crud.get_category_by_id(session, category_id)
        expense_count = await crud.count_category_expenses(session, category_id)
        income_count = await crud.count_category_incomes(session, category_id)
        return category, expense_count, income_count
    
    result = await handle_db_operation(get_category_and_expenses, "Error checking category")
    
    keyboard = get_home_button()
    if result is None:
        await safe_edit_message(query, ErrorMessage.GENERAL_ERROR, reply_markup=keyboard)
        return ConversationHandler.END
    
    category, expense_count, income_count = result
    
    if not category:
        await safe_edit_message(query, ErrorMessage.CATEGORY_NOT_FOUND, reply_markup=keyboard)
        return ConversationHandler.END
    
    # Save counts to context
    context.user_data['delete_cat_expense_count'] = expense_count
    context.user_data['delete_cat_income_count'] = income_count
    
    if expense_count + income_count > 0:
        # Show options: move or delete with expenses
        message = MessageBuilder.build_delete_with_expenses_prompt(
            category.name,
            expense_count,
            income_count
        )
        keyboard = KeyboardBuilder.build_delete_with_expenses_keyboard(context)
        await safe_edit_message(query, message, reply_markup=keyboard, parse_mode="HTML")
        return ConversationState.DELETE_SELECT_TARGET
    else:
        # No expenses, can delete directly
        message = MessageBuilder.build_delete_confirm_no_expenses(category.name)
        keyboard = KeyboardBuilder.build_delete_confirmation_keyboard(context)
        await safe_edit_message(query, message, reply_markup=keyboard, parse_mode="HTML")
        return ConversationState.DELETE_CONFIRM


async def delete_category_choose_move(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show category list for moving expenses."""
    query = update.callback_query
    await query.answer()
    
    cat_data = CategoryData.from_context(context, "delete_cat")
    
    async def get_other_categories(session):
        all_categories = await crud.get_family_categories(
            session,
            cat_data.family_id,
            category_type=cat_data.category_type
        )
        other_categories = [c for c in all_categories if c.id != cat_data.category_id]
        return other_categories
    
    other_categories = await handle_db_operation(get_other_categories, "Error getting categories")
    
    if not other_categories:
        keyboard = get_home_button()
        await safe_edit_message(query, ErrorMessage.GENERAL_ERROR, reply_markup=keyboard)
        return ConversationHandler.END
    
    async def get_category(session):
        return await crud.get_category_by_id(session, cat_data.category_id)
    
    category = await handle_db_operation(get_category, "Error getting category")
    expense_count = context.user_data.get('delete_cat_expense_count', 0)
    income_count = context.user_data.get('delete_cat_income_count', 0)
    total_count = expense_count + income_count
    
    message = (
        f"{Emoji.WARNING} <b>Переместить операции</b>\n\n"
        f"В категории '{category.name}' есть {total_count} операци(й).\n"
        f"Расходы: {expense_count}, доходы: {income_count}\n\n"
        "Выберите категорию, в которую переместить эти операции:"
    )
    keyboard = KeyboardBuilder.build_category_list_keyboard(
        other_categories,
        CallbackPattern.MOVETARGET_PREFIX,
        context,
        "delete_target"
    )
    await safe_edit_message(query, message, reply_markup=keyboard, parse_mode="HTML")
    return ConversationState.DELETE_SELECT_TARGET


async def delete_category_select_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle target category selection for moving expenses."""
    query = update.callback_query
    await query.answer()
    
    target_category_id = extract_id_from_callback(query.data, index=1)
    cat_data = CategoryData.from_context(context, "delete_cat")
    cat_data.target_category_id = target_category_id
    cat_data.save_to_context(context, "delete_cat")
    
    async def get_categories_and_count(session):
        category = await crud.get_category_by_id(session, cat_data.category_id)
        target_category = await crud.get_category_by_id(session, target_category_id)
        expense_count = await crud.count_category_expenses(session, cat_data.category_id)
        income_count = await crud.count_category_incomes(session, cat_data.category_id)
        return category, target_category, expense_count, income_count
    
    result = await handle_db_operation(get_categories_and_count, "Error getting categories")
    
    if result is None:
        keyboard = get_home_button()
        await safe_edit_message(query, ErrorMessage.GENERAL_ERROR, reply_markup=keyboard)
        return ConversationHandler.END
    
    category, target_category, expense_count, income_count = result
    
    message = MessageBuilder.build_delete_confirm_with_move(
        category.name,
        target_category.name,
        expense_count,
        income_count
    )
    keyboard = KeyboardBuilder.build_delete_confirmation_keyboard(context)
    await safe_edit_message(query, message, reply_markup=keyboard, parse_mode="HTML")
    
    return ConversationState.DELETE_CONFIRM


async def delete_category_with_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle deletion of category with all its expenses."""
    query = update.callback_query
    await query.answer()
    
    cat_data = CategoryData.from_context(context, "delete_cat")
    
    async def get_category_and_count(session):
        category = await crud.get_category_by_id(session, cat_data.category_id)
        expense_count = await crud.count_category_expenses(session, cat_data.category_id)
        income_count = await crud.count_category_incomes(session, cat_data.category_id)
        return category, expense_count, income_count
    
    result = await handle_db_operation(get_category_and_count, "Error getting category")
    
    if result is None:
        keyboard = get_home_button()
        await safe_edit_message(query, ErrorMessage.GENERAL_ERROR, reply_markup=keyboard)
        return ConversationHandler.END
    
    category, expense_count, income_count = result
    
    message = MessageBuilder.build_delete_confirm_with_expenses(
        category.name,
        expense_count,
        income_count
    )
    keyboard = KeyboardBuilder.build_delete_confirmation_keyboard(context)
    await safe_edit_message(query, message, reply_markup=keyboard, parse_mode="HTML")
    
    return ConversationState.DELETE_CONFIRM


async def delete_category_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirm and delete the category."""
    query = update.callback_query
    await query.answer()
    
    cat_data = CategoryData.from_context(context, "delete_cat")
    
    async def delete_and_process(session):
        category = await crud.get_category_by_id(session, cat_data.category_id)
        category_name = category.name
        
        moved_expense_count = 0
        moved_income_count = 0
        deleted_expense_count = 0
        deleted_income_count = 0
        target_name = ""
        
        if cat_data.target_category_id:
            # Move expenses to another category
            moved_expense_count = await crud.move_expenses_to_category(
                session,
                cat_data.category_id,
                cat_data.target_category_id
            )
            moved_income_count = await crud.move_incomes_to_category(
                session,
                cat_data.category_id,
                cat_data.target_category_id
            )
            target_category = await crud.get_category_by_id(session, cat_data.target_category_id)
            target_name = target_category.name
        else:
            # Delete all expenses in this category
            deleted_expense_count = await crud.delete_category_expenses(session, cat_data.category_id)
            deleted_income_count = await crud.delete_category_incomes(session, cat_data.category_id)
        
        await crud.delete_category(session, cat_data.category_id)
        await session.commit()
        
        return (
            category_name,
            moved_expense_count,
            moved_income_count,
            deleted_expense_count,
            deleted_income_count,
            target_name
        )
    
    result = await handle_db_operation(delete_and_process, "Error deleting category")
    
    keyboard = get_home_button()
    if result is None:
        await safe_edit_message(query, ErrorMessage.DELETE_ERROR, reply_markup=keyboard)
    else:
        (
            category_name,
            moved_expense_count,
            moved_income_count,
            deleted_expense_count,
            deleted_income_count,
            target_name
        ) = result
        message = MessageBuilder.build_category_deleted_message(
            category_name,
            moved_expense_count,
            moved_income_count,
            deleted_expense_count,
            deleted_income_count,
            target_name
        )
        await safe_edit_message(query, message, parse_mode="HTML", reply_markup=keyboard)
        logger.info(
            f"Deleted category {cat_data.category_id}, moved expenses={moved_expense_count}, "
            f"moved incomes={moved_income_count}, deleted expenses={deleted_expense_count}, "
            f"deleted incomes={deleted_income_count}"
        )
    
    cat_data.clear_from_context(context, "delete_cat")
    context.user_data.pop('delete_cat_expense_count', None)
    context.user_data.pop('delete_cat_income_count', None)
    return ConversationHandler.END


async def delete_category_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel delete category conversation."""
    query = update.callback_query
    await query.answer()
    
    keyboard = get_home_button()
    await safe_edit_message(query, f"{Emoji.ERROR} Удаление категории отменено.", reply_markup=keyboard)
    
    cat_data = CategoryData()
    cat_data.clear_from_context(context, "delete_cat")
    
    return ConversationHandler.END


# ============================================================================
# HANDLER REGISTRATION
# ============================================================================

categories_handler = CommandHandler("categories", categories_command)

show_categories_handler = CallbackQueryHandler(
    show_categories_callback,
    pattern=f"^{CallbackPattern.CAT_SHOW_PREFIX}\\d+$"
)

add_category_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(add_category_start, pattern=f"^{CallbackPattern.CAT_ADD_PREFIX}\\d+$")
    ],
    states={
        ConversationState.ADD_SELECT_TYPE: [
            CallbackQueryHandler(add_category_select_type, pattern=f"^{CallbackPattern.CAT_TYPE_EXPENSE}$"),
            CallbackQueryHandler(add_category_select_type, pattern=f"^{CallbackPattern.CAT_TYPE_INCOME}$")
        ],
        ConversationState.ADD_ENTER_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, add_category_name)
        ],
        ConversationState.ADD_CONFIRM: [
            CallbackQueryHandler(add_category_confirm, pattern=f"^{CallbackPattern.CAT_ADD_CONFIRM}$"),
            CallbackQueryHandler(add_category_cancel, pattern=f"^{CallbackPattern.CAT_ADD_CANCEL}$")
        ]
    },
    fallbacks=[
        CallbackQueryHandler(add_category_cancel, pattern=f"^{CallbackPattern.CAT_ADD_CANCEL}$"),
        CallbackQueryHandler(end_conversation_silently, pattern=f"^{CallbackPattern.NAV_BACK}$"),
        # Main navigation fallbacks - end conversation and route to new section
        CallbackQueryHandler(end_conversation_and_route, pattern="^(start|categories|settings|help|add_expense|add_income|my_expenses|family_expenses|my_families|create_family|join_family|family_settings|stats_start|quick_expense|search)$")
    ],
    name="add_category_conversation",
    allow_reentry=True,
    persistent=False,
    per_chat=True,
    per_user=True,
    per_message=False  # False because handler uses MessageHandler for category name input
)

edit_category_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(edit_category_start, pattern=f"^{CallbackPattern.CAT_EDIT_PREFIX}\\d+$")
    ],
    states={
        ConversationState.EDIT_SELECT_TYPE: [
            CallbackQueryHandler(edit_category_select_type, pattern=f"^{CallbackPattern.CAT_TYPE_EXPENSE}$"),
            CallbackQueryHandler(edit_category_select_type, pattern=f"^{CallbackPattern.CAT_TYPE_INCOME}$")
        ],
        ConversationState.EDIT_SELECT_CATEGORY: [
            CallbackQueryHandler(edit_category_select, pattern=f"^{CallbackPattern.EDITCAT_PREFIX}\\d+$"),
            CallbackQueryHandler(edit_category_cancel, pattern=f"^{CallbackPattern.CAT_EDIT_CANCEL}$")
        ],
        ConversationState.EDIT_ENTER_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, edit_category_name)
        ]
    },
    fallbacks=[
        CallbackQueryHandler(edit_category_cancel, pattern=f"^{CallbackPattern.CAT_EDIT_CANCEL}$"),
        CallbackQueryHandler(end_conversation_silently, pattern=f"^{CallbackPattern.NAV_BACK}$"),
        # Main navigation fallbacks - end conversation and route to new section
        CallbackQueryHandler(end_conversation_and_route, pattern="^(start|categories|settings|help|add_expense|add_income|my_expenses|family_expenses|my_families|create_family|join_family|family_settings|stats_start|quick_expense|search)$")
    ],
    allow_reentry=True,
    name="edit_category_conversation",
    persistent=False,
    per_chat=True,
    per_user=True,
    per_message=False  # False because handler uses MessageHandler for category name input
)

delete_category_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(delete_category_start, pattern=f"^{CallbackPattern.CAT_DELETE_PREFIX}\\d+$")
    ],
    states={
        ConversationState.DELETE_SELECT_TYPE: [
            CallbackQueryHandler(delete_category_select_type, pattern=f"^{CallbackPattern.CAT_TYPE_EXPENSE}$"),
            CallbackQueryHandler(delete_category_select_type, pattern=f"^{CallbackPattern.CAT_TYPE_INCOME}$")
        ],
        ConversationState.DELETE_SELECT_CATEGORY: [
            CallbackQueryHandler(delete_category_select, pattern=f"^{CallbackPattern.DELCAT_PREFIX}\\d+$"),
            CallbackQueryHandler(delete_category_cancel, pattern=f"^{CallbackPattern.CAT_DELETE_CANCEL}$")
        ],
        ConversationState.DELETE_SELECT_TARGET: [
            CallbackQueryHandler(delete_category_choose_move, pattern=f"^{CallbackPattern.MOVETARGET_PREFIX}select$"),
            CallbackQueryHandler(delete_category_select_target, pattern=f"^{CallbackPattern.MOVETARGET_PREFIX}\\d+$"),
            CallbackQueryHandler(delete_category_with_expenses, pattern=f"^{CallbackPattern.DELETE_WITH_EXPENSES}$"),
            CallbackQueryHandler(delete_category_cancel, pattern=f"^{CallbackPattern.CAT_DELETE_CANCEL}$")
        ],
        ConversationState.DELETE_CONFIRM: [
            CallbackQueryHandler(delete_category_confirm, pattern=f"^{CallbackPattern.DELETE_CONFIRM}$"),
            CallbackQueryHandler(delete_category_cancel, pattern=f"^{CallbackPattern.CAT_DELETE_CANCEL}$")
        ]
    },
    fallbacks=[
        CallbackQueryHandler(delete_category_cancel, pattern=f"^{CallbackPattern.CAT_DELETE_CANCEL}$"),
        CallbackQueryHandler(end_conversation_silently, pattern=f"^{CallbackPattern.NAV_BACK}$"),
        # Main navigation fallbacks - end conversation and route to new section
        CallbackQueryHandler(end_conversation_and_route, pattern="^(start|categories|settings|help|add_expense|add_income|my_expenses|family_expenses|my_families|create_family|join_family|family_settings|stats_start|quick_expense|search)$")
    ],
    allow_reentry=True,
    name="delete_category_conversation",
    persistent=False,
    per_chat=True,
    per_user=True,
    per_message=True  # True because all handlers are CallbackQueryHandler
)

categories_callback_handler = CallbackQueryHandler(
    categories_command,
    pattern=f"^{CallbackPattern.CATEGORIES}$"
)
