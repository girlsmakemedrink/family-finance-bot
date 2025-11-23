"""Category management handlers with improved architecture."""

import logging
import re
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

from bot.database import crud, get_db
from bot.utils.helpers import end_conversation_silently, end_conversation_and_route, get_user_id, safe_edit_message
from bot.utils.keyboards import add_navigation_buttons

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

class ConversationState(IntEnum):
    """Conversation states for category management."""
    # Add category states
    ADD_SELECT_FAMILY = 0
    ADD_ENTER_NAME = 1
    ADD_SELECT_EMOJI = 2
    ADD_CONFIRM = 3
    # Edit category states
    EDIT_SELECT_FAMILY = 4
    EDIT_SELECT_CATEGORY = 5
    EDIT_SELECT_ACTION = 6
    EDIT_ENTER_NAME = 7
    EDIT_SELECT_EMOJI = 8
    # Delete category states
    DELETE_SELECT_FAMILY = 9
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
    EMOJI_PREFIX = "emoji_"
    EDITEMOJI_PREFIX = "editemoji_"
    EDIT_NAME = "edit_name"
    EDIT_ICON = "edit_icon"
    MOVETARGET_PREFIX = "movetarget_"
    DELETE_CONFIRM = "delete_confirm"
    DELETE_WITH_EXPENSES = "delete_with_expenses"
    NAV_BACK = "nav_back"


class ValidationLimits:
    """Validation limits for category inputs."""
    MIN_NAME_LENGTH = 2
    MAX_NAME_LENGTH = 50
    MAX_EMOJI_LENGTH = 10


class Emoji:
    """Common emojis for categories."""
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
    PALETTE = "🎨"
    NOTE = "📝"
    
    # Category icons
    FOOD_GROCERIES = ["🍔", "🍕", "🍜", "☕", "🛒"]
    TRANSPORT = ["🚗", "🚌", "⛽", "🚕", "🚙"]
    HOME_UTILITIES = ["🏠", "💡", "🔧", "🛠️", "🔑"]
    CLOTHING = ["👕", "👗", "👠", "🎽", "👔"]
    HEALTH = ["🏥", "💊", "💉", "🩺", "⚕️"]
    ENTERTAINMENT = ["🎮", "🎬", "🎵", "🎨", "📚"]
    TRAVEL = ["✈️", "🏖️", "🏔️", "🗺️", "🎫"]
    FINANCE = ["💰", "💳", "💵", "🏦", "📊"]
    ELECTRONICS = ["📱", "💻", "🖥️", "⌚", "🎧"]
    EDUCATION = ["🎓", "📖", "✏️", "📝", "🎒"]
    
    @classmethod
    def get_all_common_emojis(cls) -> List[str]:
        """Get list of all common category emojis."""
        return (
            cls.FOOD_GROCERIES + cls.TRANSPORT + cls.HOME_UTILITIES +
            cls.CLOTHING + cls.HEALTH + cls.ENTERTAINMENT +
            cls.TRAVEL + cls.FINANCE + cls.ELECTRONICS + cls.EDUCATION
        )


class ErrorMessage:
    """Error messages."""
    NOT_REGISTERED = f"{Emoji.ERROR} Вы не зарегистрированы. Используйте команду /start для регистрации."
    NO_FAMILIES = f"{Emoji.ERROR} У вас нет семей.\n\nСоздайте семью или присоединитесь к существующей, чтобы управлять категориями."
    NO_CUSTOM_CATEGORIES_EDIT = f"{Emoji.ERROR} У вас нет собственных категорий для редактирования."
    NO_CATEGORIES_DELETE = f"{Emoji.ERROR} У вас нет категорий для удаления."
    CATEGORY_NOT_FOUND = f"{Emoji.ERROR} Категория не найдена."
    NAME_TOO_SHORT = f"{Emoji.ERROR} Название слишком короткое. Введите минимум {ValidationLimits.MIN_NAME_LENGTH} символа:"
    NAME_TOO_LONG = f"{Emoji.ERROR} Название слишком длинное. Максимум {ValidationLimits.MAX_NAME_LENGTH} символов:"
    NAME_EXISTS = f"{Emoji.ERROR} Категория с названием '{{name}}' уже существует.\nВведите другое название:"
    INVALID_EMOJI = f"{Emoji.ERROR} Это не похоже на эмодзи. Попробуйте еще раз или выберите из предложенных:"
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

    @classmethod
    def from_context(cls, context: ContextTypes.DEFAULT_TYPE, prefix: str) -> 'CategoryData':
        """Create CategoryData from context user_data."""
        return cls(
            family_id=context.user_data.get(f'{prefix}_family_id'),
            category_id=context.user_data.get(f'{prefix}_id'),
            name=context.user_data.get(f'{prefix}_name'),
            icon=context.user_data.get(f'{prefix}_icon'),
            target_category_id=context.user_data.get(f'{prefix}_target_cat_id')
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

    def clear_from_context(self, context: ContextTypes.DEFAULT_TYPE, prefix: str) -> None:
        """Clear category data from context."""
        context.user_data.pop(f'{prefix}_family_id', None)
        context.user_data.pop(f'{prefix}_id', None)
        context.user_data.pop(f'{prefix}_name', None)
        context.user_data.pop(f'{prefix}_icon', None)
        context.user_data.pop(f'{prefix}_target_cat_id', None)


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


def validate_emoji(emoji: str) -> bool:
    """
    Validate if string is a valid emoji.
    
    Args:
        emoji: String to validate
        
    Returns:
        True if valid emoji, False otherwise
    """
    if len(emoji) > ValidationLimits.MAX_EMOJI_LENGTH:
        return False
    
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F700-\U0001F77F"  # alchemical symbols
        "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
        "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "\U00002702-\U000027B0"  # Dingbats
        "\U000024C2-\U0001F251"
        "]+"
    )
    
    return bool(emoji_pattern.search(emoji))


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
            if result and hasattr(result, '__iter__') and not isinstance(result, (str, bytes)):
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
    def build_categories_list_message(family_name: str, default_cats: List, custom_cats: List) -> str:
        """Build message showing categories."""
        message = f"{Emoji.TAG} <b>Категории семьи '{family_name}'</b>\n\n"
        
        if default_cats:
            message += f"<b>{Emoji.PIN} Стандартные категории:</b>\n"
            for cat in default_cats:
                message += f"{cat.icon} {cat.name}\n"
            message += "\n"
        
        if custom_cats:
            message += f"<b>{Emoji.STAR} Ваши категории:</b>\n"
            for cat in custom_cats:
                message += f"{cat.icon} {cat.name}\n"
            message += "\n"
        else:
            message += "У вас пока нет собственных категорий.\n\n"
        
        message += "Выберите действие:"
        return message
    
    @staticmethod
    def build_add_category_name_prompt() -> str:
        """Build prompt for category name input."""
        return (
            f"{Emoji.PLUS} <b>Добавление новой категории</b>\n\n"
            "Введите название категории (например: 'Рестораны', 'Такси', 'Спорт'):"
        )
    
    @staticmethod
    def build_add_category_emoji_prompt(name: str) -> str:
        """Build prompt for emoji selection."""
        return (
            f"{Emoji.SUCCESS} Название: <b>{name}</b>\n\n"
            "Теперь выберите иконку для категории из списка ниже "
            "или отправьте свою (любой эмодзи):"
        )
    
    @staticmethod
    def build_add_category_confirmation(name: str, icon: str) -> str:
        """Build confirmation message for category creation."""
        return (
            f"{Emoji.NOTE} <b>Подтверждение</b>\n\n"
            f"Название: <b>{name}</b>\n"
            f"Иконка: {icon}\n\n"
            "Создать категорию?"
        )
    
    @staticmethod
    def build_category_created_message(name: str, icon: str) -> str:
        """Build success message after category creation."""
        return (
            f"{Emoji.SUCCESS} <b>Категория создана!</b>\n\n"
            f"{icon} <b>{name}</b>\n\n"
            "Теперь вы можете использовать эту категорию при добавлении расходов."
        )
    
    @staticmethod
    def build_edit_category_list_prompt() -> str:
        """Build prompt for category selection (editing)."""
        return (
            f"{Emoji.EDIT} <b>Редактирование категории</b>\n\n"
            "Выберите категорию для редактирования:"
        )
    
    @staticmethod
    def build_edit_action_selection(name: str, icon: str) -> str:
        """Build message for edit action selection."""
        return (
            f"{Emoji.EDIT} <b>Редактирование: {icon} {name}</b>\n\n"
            "Что вы хотите изменить?"
        )
    
    @staticmethod
    def build_category_updated_message(name: str, icon: str, field: str) -> str:
        """Build success message after category update."""
        if field == "name":
            return f"{Emoji.SUCCESS} Название категории изменено на:\n{icon} <b>{name}</b>"
        else:
            return f"{Emoji.SUCCESS} Иконка категории изменена:\n{icon} <b>{name}</b>"
    
    @staticmethod
    def build_delete_category_list_prompt() -> str:
        """Build prompt for category selection (deletion)."""
        return (
            f"{Emoji.DELETE} <b>Удаление категории</b>\n\n"
            f"{Emoji.WARNING} <b>Внимание!</b> Можно удалить любую категорию, включая стандартные.\n\n"
            "Выберите категорию для удаления:"
        )
    
    @staticmethod
    def build_delete_with_expenses_prompt(name: str, icon: str, count: int) -> str:
        """Build message when category has expenses."""
        return (
            f"{Emoji.WARNING} <b>Внимание!</b>\n\n"
            f"В категории '{icon} {name}' есть {count} расход(ов).\n\n"
            "Что вы хотите сделать?"
        )
    
    @staticmethod
    def build_delete_confirm_no_expenses(name: str, icon: str) -> str:
        """Build confirmation message for deletion (no expenses)."""
        return (
            f"{Emoji.DELETE} <b>Удаление категории</b>\n\n"
            f"Вы уверены, что хотите удалить категорию?\n\n"
            f"{icon} <b>{name}</b>\n\n"
            "В этой категории нет расходов."
        )
    
    @staticmethod
    def build_delete_confirm_with_move(
        from_name: str,
        from_icon: str,
        to_name: str,
        to_icon: str,
        count: int
    ) -> str:
        """Build confirmation message for deletion with expense move."""
        return (
            f"{Emoji.DELETE} <b>Подтверждение удаления</b>\n\n"
            f"Удалить: {from_icon} <b>{from_name}</b>\n"
            f"Переместить {count} расход(ов) в: {to_icon} <b>{to_name}</b>\n\n"
            "Подтвердите удаление:"
        )
    
    @staticmethod
    def build_category_deleted_message(name: str, icon: str, moved_count: int = 0, deleted_count: int = 0, target_name: str = "", target_icon: str = "") -> str:
        """Build success message after category deletion."""
        message = f"{Emoji.SUCCESS} <b>Категория удалена!</b>\n\n{icon} {name}"
        
        if moved_count > 0:
            message += f"\n\n{moved_count} расход(ов) перемещено в {target_icon} {target_name}"
        elif deleted_count > 0:
            message += f"\n\n{deleted_count} расход(ов) также удалено"
        
        return message
    
    @staticmethod
    def build_delete_confirm_with_expenses(name: str, icon: str, count: int) -> str:
        """Build confirmation message for deletion with expenses."""
        return (
            f"{Emoji.DELETE} <b>Подтверждение удаления</b>\n\n"
            f"Удалить категорию {icon} <b>{name}</b>\n"
            f"вместе со всеми {count} расход(ами)?\n\n"
            f"{Emoji.WARNING} <b>Это действие нельзя отменить!</b>"
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
        
        if has_custom:
            keyboard.append([InlineKeyboardButton(f"{Emoji.EDIT} Изменить категорию", callback_data=f"{CallbackPattern.CAT_EDIT_PREFIX}{family_id}")])
        
        if has_any:
            keyboard.append([InlineKeyboardButton(f"{Emoji.DELETE} Удалить категорию", callback_data=f"{CallbackPattern.CAT_DELETE_PREFIX}{family_id}")])
        
        keyboard = add_navigation_buttons(keyboard, context, current_state="categories")
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_emoji_selection_keyboard(context: ContextTypes.DEFAULT_TYPE, pattern_prefix: str, state: str) -> InlineKeyboardMarkup:
        """Build keyboard for emoji selection."""
        emojis = Emoji.get_all_common_emojis()
        keyboard = []
        row = []
        
        for i, emoji in enumerate(emojis):
            row.append(InlineKeyboardButton(emoji, callback_data=f"{pattern_prefix}{emoji}"))
            if (i + 1) % 5 == 0:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        keyboard = add_navigation_buttons(keyboard, context, current_state=state)
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_confirmation_keyboard() -> InlineKeyboardMarkup:
        """Build keyboard for confirmation."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{Emoji.SUCCESS} Создать", callback_data=CallbackPattern.CAT_ADD_CONFIRM),
                InlineKeyboardButton(f"{Emoji.ERROR} Отмена", callback_data=CallbackPattern.CAT_ADD_CANCEL)
            ]
        ])
    
    @staticmethod
    def build_category_list_keyboard(categories: List, pattern_prefix: str, context: ContextTypes.DEFAULT_TYPE, state: str) -> InlineKeyboardMarkup:
        """Build keyboard with list of categories."""
        keyboard = [
            [InlineKeyboardButton(
                f"{cat.icon} {cat.name}",
                callback_data=f"{pattern_prefix}{cat.id}"
            )]
            for cat in categories
        ]
        keyboard = add_navigation_buttons(keyboard, context, current_state=state)
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def build_edit_action_keyboard(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
        """Build keyboard for edit action selection."""
        keyboard = [
            [InlineKeyboardButton(f"{Emoji.NOTE} Изменить название", callback_data=CallbackPattern.EDIT_NAME)],
            [InlineKeyboardButton(f"{Emoji.PALETTE} Изменить иконку", callback_data=CallbackPattern.EDIT_ICON)]
        ]
        keyboard = add_navigation_buttons(keyboard, context)
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
            [InlineKeyboardButton(f"📦 Переместить расходы в другую категорию", callback_data=CallbackPattern.MOVETARGET_PREFIX + "select")],
            [InlineKeyboardButton(f"{Emoji.DELETE} Удалить категорию вместе с расходами", callback_data=CallbackPattern.DELETE_WITH_EXPENSES)]
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
        await send_or_edit_message(update, ErrorMessage.NO_FAMILIES)
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
        categories = await crud.get_family_categories(session, family_id)
        return family, categories
    
    result = await handle_db_operation(get_family_and_categories, f"Error showing categories for family {family_id}")
    
    if result is None:
        await send_or_edit_message(update, ErrorMessage.GENERAL_ERROR)
        return
    
    family, categories = result
    
    # Separate default and custom categories
    default_cats = [c for c in categories if c.is_default]
    custom_cats = [c for c in categories if not c.is_default]
    
    message = MessageBuilder.build_categories_list_message(family.name, default_cats, custom_cats)
    keyboard = KeyboardBuilder.build_category_management_keyboard(family_id, bool(custom_cats), bool(categories), context)
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
    
    message = MessageBuilder.build_add_category_name_prompt()
    keyboard = add_navigation_buttons([], context, current_state="add_category")
    await safe_edit_message(query, message, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    
    return ConversationState.ADD_ENTER_NAME


async def add_category_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle category name input."""
    name, error_message = validate_category_name(update.message.text)
    
    if error_message:
        await update.message.reply_text(error_message)
        return ConversationState.ADD_ENTER_NAME
    
    cat_data = CategoryData.from_context(context, "add_cat")
    
    # Check if name already exists
    async def check_name_exists(session):
        return await crud.category_name_exists(session, name, cat_data.family_id)
    
    exists = await handle_db_operation(check_name_exists, "Error checking category name")
    
    if exists:
        await update.message.reply_text(ErrorMessage.NAME_EXISTS.format(name=name))
        return ConversationState.ADD_ENTER_NAME
    
    cat_data.name = name
    cat_data.save_to_context(context, "add_cat")
    
    message = MessageBuilder.build_add_category_emoji_prompt(name)
    keyboard = KeyboardBuilder.build_emoji_selection_keyboard(
        context,
        CallbackPattern.EMOJI_PREFIX,
        "add_category_emoji"
    )
    await update.message.reply_text(message, reply_markup=keyboard, parse_mode="HTML")
    
    return ConversationState.ADD_SELECT_EMOJI


async def add_category_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle emoji selection or custom emoji input."""
    cat_data = CategoryData.from_context(context, "add_cat")
    
    # Check if it's a callback (emoji button) or message (custom emoji)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        emoji = query.data.split("_")[1]
        cat_data.icon = emoji
        cat_data.save_to_context(context, "add_cat")
        
        message = MessageBuilder.build_add_category_confirmation(cat_data.name, emoji)
        keyboard = KeyboardBuilder.build_confirmation_keyboard()
        await safe_edit_message(query, message, reply_markup=keyboard, parse_mode="HTML")
        
        return ConversationState.ADD_CONFIRM
    else:
        # Custom emoji from message
        emoji = update.message.text.strip()
        
        if not validate_emoji(emoji):
            await update.message.reply_text(ErrorMessage.INVALID_EMOJI)
            return ConversationState.ADD_SELECT_EMOJI
        
        cat_data.icon = emoji
        cat_data.save_to_context(context, "add_cat")
        
        message = MessageBuilder.build_add_category_confirmation(cat_data.name, emoji)
        keyboard = KeyboardBuilder.build_confirmation_keyboard()
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
            family_id=cat_data.family_id
        )
        await session.commit()
        return category
    
    category = await handle_db_operation(create_category, "Error creating category")
    
    if category is None:
        await safe_edit_message(query, ErrorMessage.CREATE_ERROR)
    else:
        message = MessageBuilder.build_category_created_message(cat_data.name, cat_data.icon)
        await safe_edit_message(query, message, parse_mode="HTML")
        logger.info(f"Created category {category.id} for family {cat_data.family_id}")
    
    cat_data.clear_from_context(context, "add_cat")
    return ConversationHandler.END


async def add_category_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel add category conversation."""
    query = update.callback_query
    await query.answer()
    
    await safe_edit_message(query, f"{Emoji.ERROR} Добавление категории отменено.")
    
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
    
    async def get_custom_categories(session):
        return await crud.get_family_custom_categories(session, family_id)
    
    categories = await handle_db_operation(get_custom_categories, "Error getting custom categories")
    
    if not categories:
        await safe_edit_message(query, ErrorMessage.NO_CUSTOM_CATEGORIES_EDIT)
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
    """Handle category selection for editing."""
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
        await safe_edit_message(query, ErrorMessage.CATEGORY_NOT_FOUND)
        return ConversationHandler.END
    
    message = MessageBuilder.build_edit_action_selection(category.name, category.icon)
    keyboard = KeyboardBuilder.build_edit_action_keyboard(context)
    await safe_edit_message(query, message, reply_markup=keyboard, parse_mode="HTML")
    
    return ConversationState.EDIT_SELECT_ACTION


async def edit_category_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle edit action selection."""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    
    if action == CallbackPattern.EDIT_NAME:
        await safe_edit_message(query, f"{Emoji.NOTE} Введите новое название категории:")
        return ConversationState.EDIT_ENTER_NAME
    
    elif action == CallbackPattern.EDIT_ICON:
        message = f"{Emoji.PALETTE} Выберите новую иконку из списка или отправьте свою:"
        keyboard = KeyboardBuilder.build_emoji_selection_keyboard(
            context,
            CallbackPattern.EDITEMOJI_PREFIX,
            "edit_category_emoji"
        )
        await safe_edit_message(query, message, reply_markup=keyboard)
        return ConversationState.EDIT_SELECT_EMOJI


async def edit_category_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle new category name input."""
    name, error_message = validate_category_name(update.message.text)
    
    if error_message:
        await update.message.reply_text(error_message)
        return ConversationState.EDIT_ENTER_NAME
    
    cat_data = CategoryData.from_context(context, "edit_cat")
    
    async def check_and_update(session):
        exists = await crud.category_name_exists(
            session, name, cat_data.family_id, exclude_category_id=cat_data.category_id
        )
        
        if exists:
            return None, "exists"
        
        category = await crud.update_category(session, cat_data.category_id, name=name)
        await session.commit()
        return category, None
    
    result = await handle_db_operation(check_and_update, "Error updating category name")
    
    if result is None:
        await update.message.reply_text(ErrorMessage.UPDATE_ERROR)
    else:
        category, error = result
        if error == "exists":
            await update.message.reply_text(ErrorMessage.NAME_EXISTS.format(name=name))
            return ConversationState.EDIT_ENTER_NAME
        
        message = MessageBuilder.build_category_updated_message(category.name, category.icon, "name")
        await update.message.reply_text(message, parse_mode="HTML")
        logger.info(f"Updated category {cat_data.category_id} name to '{name}'")
    
    cat_data.clear_from_context(context, "edit_cat")
    return ConversationHandler.END


async def edit_category_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle new category emoji selection."""
    cat_data = CategoryData.from_context(context, "edit_cat")
    
    # Check if it's a callback (emoji button) or message (custom emoji)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        emoji = query.data.split("_")[1]
    else:
        emoji = update.message.text.strip()
        
        if not validate_emoji(emoji):
            await update.message.reply_text(ErrorMessage.INVALID_EMOJI)
            return ConversationState.EDIT_SELECT_EMOJI
    
    async def update_category_icon(session):
        category = await crud.update_category(session, cat_data.category_id, icon=emoji)
        await session.commit()
        return category
    
    category = await handle_db_operation(update_category_icon, "Error updating category icon")
    
    if category is None:
        error_msg = ErrorMessage.UPDATE_ERROR
        if update.callback_query:
            await update.callback_query.edit_message_text(error_msg)
        else:
            await update.message.reply_text(error_msg)
    else:
        message = MessageBuilder.build_category_updated_message(category.name, category.icon, "icon")
        if update.callback_query:
            await update.callback_query.edit_message_text(message, parse_mode="HTML")
        else:
            await update.message.reply_text(message, parse_mode="HTML")
        logger.info(f"Updated category {cat_data.category_id} icon to '{emoji}'")
    
    cat_data.clear_from_context(context, "edit_cat")
    return ConversationHandler.END


async def edit_category_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel edit category conversation."""
    query = update.callback_query
    await query.answer()
    
    await safe_edit_message(query, f"{Emoji.ERROR} Редактирование категории отменено.")
    
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
    
    async def get_all_categories(session):
        return await crud.get_family_categories(session, family_id)
    
    categories = await handle_db_operation(get_all_categories, "Error getting categories")
    
    if not categories:
        await safe_edit_message(query, ErrorMessage.NO_CATEGORIES_DELETE)
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
        return category, expense_count
    
    result = await handle_db_operation(get_category_and_expenses, "Error checking category")
    
    if result is None:
        await safe_edit_message(query, ErrorMessage.GENERAL_ERROR)
        return ConversationHandler.END
    
    category, expense_count = result
    
    if not category:
        await safe_edit_message(query, ErrorMessage.CATEGORY_NOT_FOUND)
        return ConversationHandler.END
    
    # Save expense count to context
    context.user_data['delete_cat_expense_count'] = expense_count
    
    if expense_count > 0:
        # Show options: move or delete with expenses
        message = MessageBuilder.build_delete_with_expenses_prompt(category.name, category.icon, expense_count)
        keyboard = KeyboardBuilder.build_delete_with_expenses_keyboard(context)
        await safe_edit_message(query, message, reply_markup=keyboard, parse_mode="HTML")
        return ConversationState.DELETE_SELECT_TARGET
    else:
        # No expenses, can delete directly
        message = MessageBuilder.build_delete_confirm_no_expenses(category.name, category.icon)
        keyboard = KeyboardBuilder.build_delete_confirmation_keyboard(context)
        await safe_edit_message(query, message, reply_markup=keyboard, parse_mode="HTML")
        return ConversationState.DELETE_CONFIRM


async def delete_category_choose_move(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show category list for moving expenses."""
    query = update.callback_query
    await query.answer()
    
    cat_data = CategoryData.from_context(context, "delete_cat")
    
    async def get_other_categories(session):
        all_categories = await crud.get_family_categories(session, cat_data.family_id)
        other_categories = [c for c in all_categories if c.id != cat_data.category_id]
        return other_categories
    
    other_categories = await handle_db_operation(get_other_categories, "Error getting categories")
    
    if not other_categories:
        await safe_edit_message(query, ErrorMessage.GENERAL_ERROR)
        return ConversationHandler.END
    
    async def get_category(session):
        return await crud.get_category_by_id(session, cat_data.category_id)
    
    category = await handle_db_operation(get_category, "Error getting category")
    expense_count = context.user_data.get('delete_cat_expense_count', 0)
    
    message = (
        f"{Emoji.WARNING} <b>Переместить расходы</b>\n\n"
        f"В категории '{category.icon} {category.name}' есть {expense_count} расход(ов).\n\n"
        "Выберите категорию, в которую переместить эти расходы:"
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
        return category, target_category, expense_count
    
    result = await handle_db_operation(get_categories_and_count, "Error getting categories")
    
    if result is None:
        await safe_edit_message(query, ErrorMessage.GENERAL_ERROR)
        return ConversationHandler.END
    
    category, target_category, expense_count = result
    
    message = MessageBuilder.build_delete_confirm_with_move(
        category.name, category.icon,
        target_category.name, target_category.icon,
        expense_count
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
        return category, expense_count
    
    result = await handle_db_operation(get_category_and_count, "Error getting category")
    
    if result is None:
        await safe_edit_message(query, ErrorMessage.GENERAL_ERROR)
        return ConversationHandler.END
    
    category, expense_count = result
    
    message = MessageBuilder.build_delete_confirm_with_expenses(category.name, category.icon, expense_count)
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
        category_icon = category.icon
        
        moved_count = 0
        deleted_count = 0
        target_name = ""
        target_icon = ""
        
        if cat_data.target_category_id:
            # Move expenses to another category
            moved_count = await crud.move_expenses_to_category(
                session,
                cat_data.category_id,
                cat_data.target_category_id
            )
            target_category = await crud.get_category_by_id(session, cat_data.target_category_id)
            target_name = target_category.name
            target_icon = target_category.icon
        else:
            # Delete all expenses in this category
            deleted_count = await crud.delete_category_expenses(session, cat_data.category_id)
        
        await crud.delete_category(session, cat_data.category_id)
        await session.commit()
        
        return category_name, category_icon, moved_count, deleted_count, target_name, target_icon
    
    result = await handle_db_operation(delete_and_process, "Error deleting category")
    
    if result is None:
        await safe_edit_message(query, ErrorMessage.DELETE_ERROR)
    else:
        category_name, category_icon, moved_count, deleted_count, target_name, target_icon = result
        message = MessageBuilder.build_category_deleted_message(
            category_name, category_icon, moved_count, deleted_count, target_name, target_icon
        )
        await safe_edit_message(query, message, parse_mode="HTML")
        logger.info(f"Deleted category {cat_data.category_id}, moved {moved_count} expenses, deleted {deleted_count} expenses")
    
    cat_data.clear_from_context(context, "delete_cat")
    context.user_data.pop('delete_cat_expense_count', None)
    return ConversationHandler.END


async def delete_category_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel delete category conversation."""
    query = update.callback_query
    await query.answer()
    
    await safe_edit_message(query, f"{Emoji.ERROR} Удаление категории отменено.")
    
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
        ConversationState.ADD_ENTER_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, add_category_name)
        ],
        ConversationState.ADD_SELECT_EMOJI: [
            CallbackQueryHandler(add_category_emoji, pattern=f"^{CallbackPattern.EMOJI_PREFIX}"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, add_category_emoji)
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
        CallbackQueryHandler(end_conversation_and_route, pattern="^(start|categories|settings|help|add_expense|my_expenses|family_expenses|my_families|create_family|join_family|family_settings|stats_start|quick_expense|search)$")
    ],
    name="add_category_conversation",
    allow_reentry=True,
    persistent=False,
    per_chat=True,
    per_user=True
)

edit_category_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(edit_category_start, pattern=f"^{CallbackPattern.CAT_EDIT_PREFIX}\\d+$")
    ],
    states={
        ConversationState.EDIT_SELECT_CATEGORY: [
            CallbackQueryHandler(edit_category_select, pattern=f"^{CallbackPattern.EDITCAT_PREFIX}\\d+$"),
            CallbackQueryHandler(edit_category_cancel, pattern=f"^{CallbackPattern.CAT_EDIT_CANCEL}$")
        ],
        ConversationState.EDIT_SELECT_ACTION: [
            CallbackQueryHandler(edit_category_action, pattern="^edit_(name|icon)$"),
            CallbackQueryHandler(edit_category_cancel, pattern=f"^{CallbackPattern.CAT_EDIT_CANCEL}$")
        ],
        ConversationState.EDIT_ENTER_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, edit_category_name)
        ],
        ConversationState.EDIT_SELECT_EMOJI: [
            CallbackQueryHandler(edit_category_emoji, pattern=f"^{CallbackPattern.EDITEMOJI_PREFIX}"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, edit_category_emoji)
        ]
    },
    fallbacks=[
        CallbackQueryHandler(edit_category_cancel, pattern=f"^{CallbackPattern.CAT_EDIT_CANCEL}$"),
        CallbackQueryHandler(end_conversation_silently, pattern=f"^{CallbackPattern.NAV_BACK}$"),
        # Main navigation fallbacks - end conversation and route to new section
        CallbackQueryHandler(end_conversation_and_route, pattern="^(start|categories|settings|help|add_expense|my_expenses|family_expenses|my_families|create_family|join_family|family_settings|stats_start|quick_expense|search)$")
    ],
    allow_reentry=True,
    name="edit_category_conversation",
    persistent=False,
    per_chat=True,
    per_user=True
)

delete_category_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(delete_category_start, pattern=f"^{CallbackPattern.CAT_DELETE_PREFIX}\\d+$")
    ],
    states={
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
        CallbackQueryHandler(end_conversation_and_route, pattern="^(start|categories|settings|help|add_expense|my_expenses|family_expenses|my_families|create_family|join_family|family_settings|stats_start|quick_expense|search)$")
    ],
    allow_reentry=True,
    name="delete_category_conversation",
    persistent=False,
    per_chat=True,
    per_user=True
)

categories_callback_handler = CallbackQueryHandler(
    categories_command,
    pattern=f"^{CallbackPattern.CATEGORIES}$"
)
