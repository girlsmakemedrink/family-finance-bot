"""Family settings handler with improved architecture."""

import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.database import crud, get_db
from bot.utils.helpers import end_conversation_silently, end_conversation_and_route
from bot.utils.keyboards import (
    get_back_button,
    get_confirmation_keyboard,
    get_family_selection_keyboard,
    get_family_settings_keyboard,
    get_home_button,
)

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

class ConversationState(IntEnum):
    """Conversation states for family settings."""
    RENAME_FAMILY = 0
    DELETE_CONFIRMATION = 1
    REMOVE_MEMBER = 2


class CallbackPattern:
    """Callback data patterns."""
    FAMILY_SETTINGS = "family_settings"
    FAMILY_SETTINGS_SELECT_PREFIX = "family_settings_select_"
    FAMILY_RENAME = "family_rename"
    FAMILY_REGENERATE_CODE = "family_regenerate_code"
    FAMILY_MANAGE_MEMBERS = "family_manage_members"
    FAMILY_LEAVE = "family_leave"
    CONFIRM_LEAVE_FAMILY = "confirm_leave_family"
    FAMILY_DELETE = "family_delete"
    CONFIRM_DELETE_FAMILY = "confirm_delete_family"
    START = "start"
    NAV_BACK = "nav_back"


class ValidationLimits:
    """Validation limits for family settings."""
    MIN_NAME_LENGTH = 3
    MAX_NAME_LENGTH = 50


class Emoji:
    """Emoji constants."""
    SETTINGS = "⚙️"
    FAMILY = "👨‍👩‍👧‍👦"
    USERS = "👥"
    KEY = "🔑"
    CROWN = "👑"
    USER = "👤"
    ERROR = "❌"
    SUCCESS = "✅"
    EDIT = "✏️"
    BULB = "💡"
    DOOR = "🚪"
    WARNING = "⚠️"
    DELETE = "🗑️"


class ErrorMessage:
    """Error messages."""
    USER_NOT_FOUND = f"{Emoji.ERROR} Ошибка: пользователь не найден. Используйте /start для регистрации."
    NO_FAMILIES = f"{Emoji.ERROR} Вы не состоите ни в одной семье.\n\nСоздайте семью или присоединитесь к существующей!"
    FAMILY_NOT_FOUND = f"{Emoji.ERROR} Семья не найдена"
    FAMILY_NOT_SELECTED = f"{Emoji.ERROR} Ошибка: семья не выбрана"
    NAME_TOO_SHORT = f"{Emoji.ERROR} Название слишком короткое. Минимум {ValidationLimits.MIN_NAME_LENGTH} символа."
    NAME_TOO_LONG = f"{Emoji.ERROR} Название слишком длинное. Максимум {ValidationLimits.MAX_NAME_LENGTH} символов."
    NOT_ADMIN_RENAME = f"{Emoji.ERROR} Только администратор может изменять название"
    NOT_ADMIN_CODE = f"{Emoji.ERROR} Только администратор может изменять код"
    NOT_ADMIN_DELETE = f"{Emoji.ERROR} Только администратор может удалить семью"
    LEAVE_ERROR = f"{Emoji.ERROR} Ошибка при выходе из семьи"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class FamilySettingsData:
    """Data class for family settings context."""
    selected_family_id: Optional[int] = None

    @classmethod
    def from_context(cls, context: ContextTypes.DEFAULT_TYPE) -> 'FamilySettingsData':
        """Create FamilySettingsData from context user_data."""
        return cls(selected_family_id=context.user_data.get('selected_family_id'))

    def save_to_context(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Save family settings data to context."""
        if self.selected_family_id is not None:
            context.user_data['selected_family_id'] = self.selected_family_id

    def clear_from_context(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Clear family settings data from context."""
        context.user_data.pop('selected_family_id', None)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def answer_query_safely(query) -> None:
    """Answer callback query safely."""
    if query:
        try:
            await query.answer()
        except Exception as e:
            logger.debug(f"Failed to answer query: {e}")


def validate_family_name(name: str) -> tuple[Optional[str], Optional[str]]:
    """
    Validate family name.
    
    Args:
        name: Family name
        
    Returns:
        Tuple of (validated_name, error_message)
    """
    name = name.strip()
    
    if len(name) < ValidationLimits.MIN_NAME_LENGTH:
        return None, ErrorMessage.NAME_TOO_SHORT
    
    if len(name) > ValidationLimits.MAX_NAME_LENGTH:
        return None, ErrorMessage.NAME_TOO_LONG
    
    return name, None


async def handle_db_operation(operation, error_message: str):
    """Handle database operations with error handling."""
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
    def build_family_selection_message() -> str:
        """Build message for family selection."""
        return (
            f"{Emoji.FAMILY} <b>Выбор семьи</b>\n\n"
            "Выберите семью для управления настройками:"
        )
    
    @staticmethod
    def build_settings_message(family_name: str, member_count: int, admin_count: int, invite_code: str, is_admin: bool) -> str:
        """Build family settings message."""
        message = (
            f"{Emoji.SETTINGS} <b>Настройки семьи</b>\n\n"
            f"{Emoji.FAMILY} <b>Название:</b> {family_name}\n"
            f"{Emoji.USERS} <b>Участников:</b> {member_count} (админов: {admin_count})\n"
            f"{Emoji.KEY} <b>Инвайт-код:</b> <code>{invite_code}</code>\n\n"
        )
        
        if is_admin:
            message += (
                f"{Emoji.CROWN} Вы являетесь администратором этой семьи.\n"
                "Выберите действие:"
            )
        else:
            message += "Вы можете покинуть эту семью."
        
        return message
    
    @staticmethod
    def build_rename_prompt() -> str:
        """Build prompt for family rename."""
        return (
            f"{Emoji.EDIT} <b>Изменение названия семьи</b>\n\n"
            "Введите новое название семьи:\n\n"
            f"{Emoji.BULB} Название должно быть от {ValidationLimits.MIN_NAME_LENGTH} до {ValidationLimits.MAX_NAME_LENGTH} символов"
        )
    
    @staticmethod
    def build_rename_success_message(new_name: str) -> str:
        """Build success message after rename."""
        return f"{Emoji.SUCCESS} Название семьи изменено на: <b>{new_name}</b>"
    
    @staticmethod
    def build_members_list_message(members: list) -> str:
        """Build message with family members list."""
        message = f"{Emoji.USERS} <b>Участники семьи</b>\n\n"
        
        for user, member in members:
            role_emoji = Emoji.CROWN if member.role.value == "admin" else Emoji.USER
            message += f"{role_emoji} {user.name}"
            if user.username:
                message += f" (@{user.username})"
            message += f"\n<code>{user.id}</code>\n\n"
        
        message += (
            f"{Emoji.BULB} Для удаления участника используйте команду:\n"
            "/remove_member {user_id}"
        )
        
        return message
    
    @staticmethod
    def build_leave_confirmation_message() -> str:
        """Build confirmation message for leaving family."""
        return (
            f"{Emoji.DOOR} <b>Покинуть семью</b>\n\n"
            f"{Emoji.WARNING} Вы уверены, что хотите покинуть эту семью?\n\n"
            "Ваши расходы останутся в истории семьи, но вы потеряете доступ к ней."
        )
    
    @staticmethod
    def build_delete_confirmation_message() -> str:
        """Build confirmation message for deleting family."""
        return (
            f"{Emoji.DELETE} <b>Удаление семьи</b>\n\n"
            f"{Emoji.WARNING} <b>ВНИМАНИЕ!</b> Это действие необратимо!\n\n"
            "При удалении семьи:\n"
            "• Все участники потеряют доступ\n"
            "• Вся история расходов будет удалена\n"
            "• Восстановление невозможно\n\n"
            "Вы точно уверены?"
        )


# ============================================================================
# HANDLERS
# ============================================================================

async def family_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /family_settings command."""
    if not update.effective_user:
        return
    
    message = update.message or update.callback_query.message
    if not message:
        return
    
    telegram_id = update.effective_user.id
    logger.info(f"User {telegram_id} opened family settings")
    
    async def get_user_and_families(session):
        user = await crud.get_user_by_telegram_id(session, telegram_id)
        if not user:
            return None, None
        families = await crud.get_user_families(session, user.id)
        return user, families
    
    result = await handle_db_operation(get_user_and_families, "Error in family_settings_command")
    
    if result is None:
        keyboard = get_home_button()
        await message.reply_text(ErrorMessage.USER_NOT_FOUND, reply_markup=keyboard)
        return
    
    user, families = result
    
    if not user:
        keyboard = get_home_button()
        await message.reply_text(ErrorMessage.USER_NOT_FOUND, reply_markup=keyboard)
        return
    
    if not families:
        text = ErrorMessage.NO_FAMILIES
        keyboard = get_back_button(CallbackPattern.START)
        
        if update.callback_query:
            await answer_query_safely(update.callback_query)
            await message.edit_text(text, reply_markup=keyboard)
        else:
            await message.reply_text(text, reply_markup=keyboard)
        return
    
    async def get_session():
        async for session in get_db():
            return session
    
    session = await get_session()
    
    if len(families) == 1:
        await show_family_settings(update, context, user.id, families[0].id, session)
    else:
        text = MessageBuilder.build_family_selection_message()
        family_list = [(f.id, f.name) for f in families]
        keyboard = get_family_selection_keyboard(family_list, CallbackPattern.FAMILY_SETTINGS_SELECT_PREFIX)
        
        if update.callback_query:
            await answer_query_safely(update.callback_query)
            await message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def show_family_settings(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    family_id: int,
    session
) -> None:
    """Show settings for a specific family."""
    message = update.callback_query.message if update.callback_query else update.message
    if not message:
        return
    
    is_admin = await crud.is_family_admin(session, user_id, family_id)
    family = await crud.get_family_by_id(session, family_id)
    
    if not family:
        keyboard = get_home_button()
        await message.reply_text(ErrorMessage.FAMILY_NOT_FOUND, reply_markup=keyboard)
        return
    
    members = await crud.get_family_members(session, family_id)
    admin_count = sum(1 for _, member in members if member.role.value == "admin")
    member_count = len(members)
    
    settings_text = MessageBuilder.build_settings_message(
        family.name,
        member_count,
        admin_count,
        family.invite_code,
        is_admin
    )
    
    settings_data = FamilySettingsData(selected_family_id=family_id)
    settings_data.save_to_context(context)
    
    keyboard = get_family_settings_keyboard(is_admin)
    
    if update.callback_query:
        await answer_query_safely(update.callback_query)
        await message.edit_text(settings_text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await message.reply_text(settings_text, parse_mode="HTML", reply_markup=keyboard)


async def family_settings_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle family selection for settings."""
    if not update.callback_query or not update.effective_user:
        return
    
    family_id = int(update.callback_query.data.split("_")[-1])
    telegram_id = update.effective_user.id
    
    async def get_user_and_session(session):
        user = await crud.get_user_by_telegram_id(session, telegram_id)
        return user, session
    
    result = await handle_db_operation(get_user_and_session, "Error selecting family for settings")
    
    if result is None or result[0] is None:
        await update.callback_query.answer(ErrorMessage.USER_NOT_FOUND)
        return
    
    user, session = result
    await show_family_settings(update, context, user.id, family_id, session)


async def family_rename_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start family rename process."""
    if not update.callback_query or not update.callback_query.message:
        return ConversationHandler.END
    
    await update.callback_query.answer()
    
    text = MessageBuilder.build_rename_prompt()
    await update.callback_query.message.edit_text(text, parse_mode="HTML")
    
    return ConversationState.RENAME_FAMILY


async def family_rename_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process new family name."""
    if not update.message or not update.effective_user:
        return ConversationHandler.END
    
    new_name, error_message = validate_family_name(update.message.text)
    
    if error_message:
        keyboard = get_home_button()
        await update.message.reply_text(error_message, reply_markup=keyboard)
        return ConversationState.RENAME_FAMILY
    
    settings_data = FamilySettingsData.from_context(context)
    
    if not settings_data.selected_family_id:
        keyboard = get_home_button()
        await update.message.reply_text(ErrorMessage.FAMILY_NOT_SELECTED, reply_markup=keyboard)
        return ConversationHandler.END
    
    telegram_id = update.effective_user.id
    
    async def rename_family(session):
        user = await crud.get_user_by_telegram_id(session, telegram_id)
        if not user:
            return None, ErrorMessage.USER_NOT_FOUND
        
        is_admin = await crud.is_family_admin(session, user.id, settings_data.selected_family_id)
        if not is_admin:
            return None, ErrorMessage.NOT_ADMIN_RENAME
        
        await crud.update_family_settings(session, settings_data.selected_family_id, name=new_name)
        await session.commit()
        
        return user, None
    
    result = await handle_db_operation(rename_family, "Error renaming family")
    
    keyboard = get_home_button()
    if result is None:
        await update.message.reply_text(ErrorMessage.USER_NOT_FOUND, reply_markup=keyboard)
        return ConversationHandler.END
    
    user, error = result
    
    if error:
        await update.message.reply_text(error, reply_markup=keyboard)
        return ConversationHandler.END
    
    await update.message.reply_text(
        MessageBuilder.build_rename_success_message(new_name),
        parse_mode="HTML",
        reply_markup=keyboard
    )
    
    async def get_session():
        async for session in get_db():
            return session
    
    session = await get_session()
    await show_family_settings(update, context, user.id, settings_data.selected_family_id, session)
    
    return ConversationHandler.END


async def family_regenerate_code_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Regenerate family invite code."""
    if not update.callback_query or not update.effective_user:
        return
    
    settings_data = FamilySettingsData.from_context(context)
    
    if not settings_data.selected_family_id:
        await update.callback_query.answer(ErrorMessage.FAMILY_NOT_SELECTED)
        return
    
    telegram_id = update.effective_user.id
    
    async def regenerate_code(session):
        user = await crud.get_user_by_telegram_id(session, telegram_id)
        if not user:
            return None, ErrorMessage.USER_NOT_FOUND
        
        is_admin = await crud.is_family_admin(session, user.id, settings_data.selected_family_id)
        if not is_admin:
            return None, ErrorMessage.NOT_ADMIN_CODE
        
        await crud.regenerate_invite_code(session, settings_data.selected_family_id)
        await session.commit()
        
        return user, None
    
    result = await handle_db_operation(regenerate_code, "Error regenerating invite code")
    
    if result is None:
        await update.callback_query.answer(ErrorMessage.USER_NOT_FOUND)
        return
    
    user, error = result
    
    if error:
        await update.callback_query.answer(error)
        return
    
    await update.callback_query.answer(f"{Emoji.SUCCESS} Новый инвайт-код сгенерирован")
    
    async def get_session():
        async for session in get_db():
            return session
    
    session = await get_session()
    await show_family_settings(update, context, user.id, settings_data.selected_family_id, session)


async def family_manage_members_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show family members list."""
    if not update.callback_query or not update.callback_query.message:
        return
    
    settings_data = FamilySettingsData.from_context(context)
    
    if not settings_data.selected_family_id:
        await update.callback_query.answer(ErrorMessage.FAMILY_NOT_SELECTED)
        return
    
    await update.callback_query.answer()
    
    async def get_members(session):
        return await crud.get_family_members(session, settings_data.selected_family_id)
    
    members = await handle_db_operation(get_members, "Error getting family members")
    
    if members is None:
        return
    
    text = MessageBuilder.build_members_list_message(members)
    keyboard = get_back_button(CallbackPattern.FAMILY_SETTINGS)
    await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


async def family_leave_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle family leave request."""
    if not update.callback_query or not update.callback_query.message:
        return
    
    await update.callback_query.answer()
    
    text = MessageBuilder.build_leave_confirmation_message()
    keyboard = get_confirmation_keyboard(CallbackPattern.CONFIRM_LEAVE_FAMILY, CallbackPattern.FAMILY_SETTINGS)
    await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


async def confirm_leave_family_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Confirm and process family leave."""
    if not update.callback_query or not update.effective_user:
        return
    
    settings_data = FamilySettingsData.from_context(context)
    
    if not settings_data.selected_family_id:
        await update.callback_query.answer(ErrorMessage.FAMILY_NOT_SELECTED)
        return
    
    telegram_id = update.effective_user.id
    
    async def leave_family(session):
        user = await crud.get_user_by_telegram_id(session, telegram_id)
        if not user:
            return False
        
        success = await crud.remove_family_member(session, user.id, settings_data.selected_family_id)
        if success:
            await session.commit()
        return success
    
    success = await handle_db_operation(leave_family, "Error leaving family")
    
    keyboard = get_home_button()
    if success:
        await update.callback_query.answer(f"{Emoji.SUCCESS} Вы покинули семью")
        text = (
            f"{Emoji.SUCCESS} Вы успешно покинули семью.\n\n"
            "Используйте /start для возврата в главное меню."
        )
        await update.callback_query.message.edit_text(text, reply_markup=keyboard)
    else:
        await update.callback_query.answer(ErrorMessage.LEAVE_ERROR)


async def family_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle family deletion request (admin only)."""
    if not update.callback_query or not update.callback_query.message:
        return
    
    await update.callback_query.answer()
    
    text = MessageBuilder.build_delete_confirmation_message()
    keyboard = get_confirmation_keyboard(CallbackPattern.CONFIRM_DELETE_FAMILY, CallbackPattern.FAMILY_SETTINGS)
    await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


async def confirm_delete_family_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Confirm and process family deletion."""
    if not update.callback_query or not update.effective_user:
        return
    
    settings_data = FamilySettingsData.from_context(context)
    
    if not settings_data.selected_family_id:
        await update.callback_query.answer(ErrorMessage.FAMILY_NOT_SELECTED)
        return
    
    telegram_id = update.effective_user.id
    
    async def delete_family(session):
        user = await crud.get_user_by_telegram_id(session, telegram_id)
        if not user:
            return False, ErrorMessage.USER_NOT_FOUND
        
        is_admin = await crud.is_family_admin(session, user.id, settings_data.selected_family_id)
        if not is_admin:
            return False, ErrorMessage.NOT_ADMIN_DELETE
        
        family = await crud.get_family_by_id(session, settings_data.selected_family_id)
        if family:
            await session.delete(family)
            await session.commit()
            return True, None
        return False, ErrorMessage.FAMILY_NOT_FOUND
    
    result = await handle_db_operation(delete_family, "Error deleting family")
    
    if result is None:
        await update.callback_query.answer(ErrorMessage.USER_NOT_FOUND)
        return
    
    success, error = result
    
    keyboard = get_home_button()
    if success:
        await update.callback_query.answer(f"{Emoji.SUCCESS} Семья удалена")
        text = (
            f"{Emoji.SUCCESS} Семья успешно удалена.\n\n"
            "Используйте /start для возврата в главное меню."
        )
        await update.callback_query.message.edit_text(text, reply_markup=keyboard)
    else:
        await update.callback_query.answer(error)


async def cancel_rename(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel rename operation."""
    if update.message:
        keyboard = get_home_button()
        await update.message.reply_text(f"{Emoji.ERROR} Операция отменена", reply_markup=keyboard)
    return ConversationHandler.END


# ============================================================================
# HANDLERS REGISTRATION
# ============================================================================

family_settings_handler_cmd = CommandHandler("family_settings", family_settings_command)

family_settings_callback_handler = CallbackQueryHandler(
    family_settings_command,
    pattern=f"^{CallbackPattern.FAMILY_SETTINGS}$"
)

family_settings_select_handler = CallbackQueryHandler(
    family_settings_select_callback,
    pattern=f"^{CallbackPattern.FAMILY_SETTINGS_SELECT_PREFIX}"
)

family_regenerate_code_handler = CallbackQueryHandler(
    family_regenerate_code_callback,
    pattern=f"^{CallbackPattern.FAMILY_REGENERATE_CODE}$"
)

family_manage_members_handler = CallbackQueryHandler(
    family_manage_members_callback,
    pattern=f"^{CallbackPattern.FAMILY_MANAGE_MEMBERS}$"
)

family_leave_handler = CallbackQueryHandler(
    family_leave_callback,
    pattern=f"^{CallbackPattern.FAMILY_LEAVE}$"
)

confirm_leave_family_handler = CallbackQueryHandler(
    confirm_leave_family_callback,
    pattern=f"^{CallbackPattern.CONFIRM_LEAVE_FAMILY}$"
)

family_delete_handler = CallbackQueryHandler(
    family_delete_callback,
    pattern=f"^{CallbackPattern.FAMILY_DELETE}$"
)

confirm_delete_family_handler = CallbackQueryHandler(
    confirm_delete_family_callback,
    pattern=f"^{CallbackPattern.CONFIRM_DELETE_FAMILY}$"
)

family_rename_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(family_rename_start, pattern=f"^{CallbackPattern.FAMILY_RENAME}$")
    ],
    states={
        ConversationState.RENAME_FAMILY: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, family_rename_process)
        ]
    },
    fallbacks=[
        CommandHandler("cancel", cancel_rename),
        CallbackQueryHandler(end_conversation_silently, pattern=f"^{CallbackPattern.NAV_BACK}$"),
        # Main navigation fallbacks - end conversation and route to new section
        CallbackQueryHandler(end_conversation_and_route, pattern="^(start|categories|settings|help|add_expense|add_income|my_expenses|family_expenses|my_families|create_family|join_family|family_settings|stats_start|quick_expense|search)$")
    ],
    allow_reentry=True,
    name="family_rename_conversation",
    persistent=False,
    per_chat=True,
    per_user=True
)
