"""Family management handlers for creating and joining families."""

import logging
from urllib.parse import quote
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
from bot.database.models import Family
from bot.utils.constants import (
    ERROR_USER_NOT_FOUND,
    ERROR_USER_NOT_REGISTERED,
    FAMILY_NAME_MAX_LENGTH,
    FAMILY_NAME_MIN_LENGTH,
    INVITE_CODE_MAX_LENGTH,
    INVITE_CODE_MIN_LENGTH,
    MSG_ALREADY_MEMBER,
    MSG_FAMILY_NAME_TOO_LONG,
    MSG_FAMILY_NAME_TOO_SHORT,
    MSG_FAMILY_NOT_FOUND,
    MSG_INVITE_CODE_INVALID,
    MSG_WITHOUT_FAMILIES,
    MSG_WITH_FAMILIES,
)
from bot.utils.helpers import end_conversation_silently, end_conversation_and_route, get_user_id
from bot.utils.keyboards import add_navigation_buttons, get_main_menu_keyboard
from bot.utils.message_utils import (
    MessageHandler as MsgHandler,
    UserDataExtractor,
    ValidationHelper,
    format_families_list,
    get_user_from_context_or_db,
)

logger = logging.getLogger(__name__)

# Conversation states
FAMILY_NAME, INVITE_CODE = range(2)


# ============================================================================
# Helper Functions
# ============================================================================

def _create_family_start_message() -> str:
    """Create message for family creation start.
    
    Returns:
        Formatted message text
    """
    return (
        "👨‍👩‍👧‍👦 <b>Создание новой семьи</b>\n\n"
        "Введите название вашей семьи:\n\n"
        "💡 <b>Примеры:</b>\n"
        "• Семья Ивановых\n"
        "• Наша семья\n"
        "• Дом №5"
    )


def _create_join_family_message() -> str:
    """Create message for joining family.
    
    Returns:
        Formatted message text
    """
    return (
        "🔗 <b>Присоединение к семье</b>\n\n"
        "Введите код приглашения, который вам отправил "
        "администратор семьи:\n\n"
        "💡 Код выглядит примерно так: <code>ABC12345</code>"
    )


def _create_family_success_message(family: Family) -> str:
    """Create success message after family creation.
    
    Args:
        family: Created family object
        
    Returns:
        Formatted success message
    """
    return (
        f"✅ <b>Семья '{family.name}' успешно создана!</b>\n\n"
        f"🔑 <b>Код приглашения:</b> <code>{family.invite_code}</code>\n\n"
        "Поделитесь этим кодом с членами вашей семьи, "
        "чтобы они могли присоединиться.\n\n"
        "💡 <b>Как присоединиться:</b>\n"
        "1. Нажать кнопку «Присоединиться к семье»\n"
        "2. Ввести код приглашения\n\n"
        "Используйте команду /my_families для просмотра всех ваших семей."
    )


def _create_join_success_message(family: Family) -> str:
    """Create success message after joining family.
    
    Args:
        family: Joined family object
        
    Returns:
        Formatted success message
    """
    return (
        f"✅ <b>Вы успешно присоединились к семье!</b>\n\n"
        f"👨‍👩‍👧‍👦 <b>Семья:</b> {family.name}\n\n"
        "Теперь вы можете:\n"
        "• Добавлять расходы\n"
        "• Просматривать статистику семьи\n"
        "• Смотреть историю транзакций\n\n"
        "Используйте команду /my_families для просмотра всех ваших семей."
    )


def _create_share_button(family: Family) -> InlineKeyboardButton:
    """Create share button for family invite.
    
    Args:
        family: Family object
        
    Returns:
        Inline keyboard button with share link
    """
    share_text = (
        f"👋 Присоединяйся к нашей семье в Family Finance Bot!\n\n"
        f"🔑 Код приглашения:`{family.invite_code}`\n\n"
        f"Запусти бота: @family_finance_calculator_bot"
    )
    share_url = f"https://t.me/share/url?url={quote(share_text)}"
    
    return InlineKeyboardButton("📤 Поделиться кодом", url=share_url)


async def _get_user_id_or_error(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> Optional[int]:
    """Get user ID or send error message.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        User ID or None if not found
    """
    user_id = await get_user_from_context_or_db(update, context)
    
    if not user_id:
        await MsgHandler.send_or_edit(update, ERROR_USER_NOT_REGISTERED)
        return None
    
    return user_id


async def _create_family_in_db(session, family_name: str, user_id: int) -> Family:
    """Create family and add creator as admin.
    
    Args:
        session: Database session
        family_name: Name of the family
        user_id: ID of the user creating the family
        
    Returns:
        Created family object
    """
    # Create the family
    family = await crud.create_family(session, name=family_name)
    
    # Add creator as admin
    await crud.add_family_member(
        session,
        user_id=user_id,
        family_id=family.id,
        role="admin"
    )
    
    await session.commit()
    return family


async def _join_family_in_db(session, invite_code: str, user_id: int) -> Optional[Family]:
    """Join user to family by invite code.
    
    Args:
        session: Database session
        invite_code: Family invite code
        user_id: ID of the user joining
        
    Returns:
        Family object or None if not found/already member
    """
    # Find family by invite code
    family = await crud.get_family_by_invite_code(session, invite_code)
    
    if not family:
        return None
    
    # Check if user is already in this family
    is_member = await crud.is_user_in_family(session, user_id, family.id)
    
    if is_member:
        # Return family with special flag to indicate already member
        family._already_member = True
        return family
    
    # Add user to family as member
    await crud.add_family_member(
        session,
        user_id=user_id,
        family_id=family.id,
        role="member"
    )
    
    await session.commit()
    return family


# ============================================================================
# Create Family Handlers
# ============================================================================

async def create_family_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Start the family creation process.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        Next conversation state
    """
    user_id = await _get_user_id_or_error(update, context)
    if not user_id:
        return ConversationHandler.END
    
    message_text = _create_family_start_message()
    keyboard = add_navigation_buttons([], context, current_state="create_family")
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await MsgHandler.send_or_edit(update, message_text, reply_markup=reply_markup)
    
    logger.info(f"User {user_id} started family creation process")
    return FAMILY_NAME


async def create_family_name_received(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle family name input and create the family.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        End conversation state
    """
    if not update.message:
        return FAMILY_NAME
    
    family_name = MsgHandler.get_message_text(update)
    
    # Validate family name
    is_valid, error_msg = ValidationHelper.validate_text_input(
        family_name,
        FAMILY_NAME_MIN_LENGTH,
        FAMILY_NAME_MAX_LENGTH
    )
    
    if not is_valid:
        await update.message.reply_text(error_msg)
        return FAMILY_NAME
    
    user_id = await get_user_id(update, context)
    if not user_id:
        await update.message.reply_text(ERROR_USER_NOT_FOUND)
        return ConversationHandler.END
    
    # Create family in database
    async for session in get_db():
        try:
            family = await _create_family_in_db(session, family_name, user_id)
            
            logger.info(
                f"User {user_id} created family '{family_name}' "
                f"with invite code {family.invite_code}"
            )
            
            # Build success response
            success_message = _create_family_success_message(family)
            
            keyboard = [
                [_create_share_button(family)],
                [InlineKeyboardButton("👨‍👩‍👧‍👦 Мои семьи", callback_data="my_families")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                success_message,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error creating family: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Произошла ошибка при создании семьи. Пожалуйста, попробуйте позже."
            )
    
    return ConversationHandler.END


# ============================================================================
# Join Family Handlers
# ============================================================================

async def join_family_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Start the family joining process.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        Next conversation state
    """
    user_id = await _get_user_id_or_error(update, context)
    if not user_id:
        return ConversationHandler.END
    
    message_text = _create_join_family_message()
    keyboard = add_navigation_buttons([], context, current_state="join_family")
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await MsgHandler.send_or_edit(update, message_text, reply_markup=reply_markup)
    
    logger.info(f"User {user_id} started family joining process")
    return INVITE_CODE


async def join_family_code_received(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle invite code input and add user to family.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        End conversation state
    """
    if not update.message:
        return INVITE_CODE
    
    invite_code = MsgHandler.get_message_text(update)
    if not invite_code:
        await update.message.reply_text("❌ Пожалуйста, введите код приглашения.")
        return INVITE_CODE
    
    invite_code = invite_code.upper()
    
    # Validate invite code format
    if not (INVITE_CODE_MIN_LENGTH <= len(invite_code) <= INVITE_CODE_MAX_LENGTH):
        await update.message.reply_text(MSG_INVITE_CODE_INVALID)
        return INVITE_CODE
    
    user_id = await get_user_id(update, context)
    if not user_id:
        await update.message.reply_text(ERROR_USER_NOT_FOUND)
        return ConversationHandler.END
    
    # Join family in database
    async for session in get_db():
        try:
            family = await _join_family_in_db(session, invite_code, user_id)
            
            if not family:
                logger.info(f"Family not found for invite code: {invite_code}")
                await update.message.reply_text(MSG_FAMILY_NOT_FOUND)
                return INVITE_CODE
            
            # Check if already member
            if getattr(family, '_already_member', False):
                logger.info(f"User {user_id} is already member of family {family.id}")
                await update.message.reply_text(
                    MSG_ALREADY_MEMBER.format(family_name=family.name),
                    parse_mode="HTML"
                )
                return ConversationHandler.END
            
            logger.info(f"User {user_id} joined family '{family.name}' (id={family.id})")
            
            # Build success response
            success_message = _create_join_success_message(family)
            
            keyboard = [
                [InlineKeyboardButton("💰 Добавить расход", callback_data="add_expense")],
                [InlineKeyboardButton("👨‍👩‍👧‍👦 Мои семьи", callback_data="my_families")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                success_message,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error joining family: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Произошла ошибка при присоединении к семье. Пожалуйста, попробуйте позже."
            )
    
    return ConversationHandler.END


# ============================================================================
# Common Handlers
# ============================================================================

async def cancel_conversation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Cancel the current conversation and return to main menu.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        End conversation state
    """
    user_id = await get_user_id(update, context)
    
    if not user_id:
        await MsgHandler.send_or_edit(update, ERROR_USER_NOT_FOUND)
        return ConversationHandler.END
    
    # Get user and families
    async for session in get_db():
        user = await crud.get_user_by_id(session, user_id)
        if not user:
            await MsgHandler.send_or_edit(update, ERROR_USER_NOT_FOUND)
            return ConversationHandler.END
        
        families = await crud.get_user_families(session, user.id)
        
        # Create welcome message
        welcome_message = f"С возвращением, <b>{user.name}</b>! 👋\n\n"
        
        if families:
            families_list = format_families_list(families)
            welcome_message += MSG_WITH_FAMILIES.format(families_list=families_list)
        else:
            welcome_message += MSG_WITHOUT_FAMILIES
        
        reply_markup = get_main_menu_keyboard(has_families=bool(families))
        
        await MsgHandler.send_or_edit(update, welcome_message, reply_markup=reply_markup)
        
        logger.info(f"User {user_id} returned to main menu from conversation")
        return ConversationHandler.END


# ============================================================================
# My Families Command
# ============================================================================

def _create_no_families_message() -> str:
    """Create message when user has no families.
    
    Returns:
        Formatted message text
    """
    return (
        "📋 <b>Ваши семьи</b>\n\n"
        "У вас пока нет семей.\n\n"
        "Вы можете:\n"
        "• Создать новую семью\n"
        "• Присоединиться к существующей семье по коду"
    )


def _create_families_list_message(families, user_id, session) -> str:
    """Create message with list of user's families.
    
    Args:
        families: List of family objects
        user_id: User ID
        session: Database session
        
    Returns:
        Formatted message text
    """
    message = (
        "📋 <b>Ваши семьи:</b>\n\n"
        "Выберите семью для просмотра деталей:\n\n"
        "💡 <b>Доступные действия:</b>\n"
        "• Просмотр информации о семье\n"
        "• Выход из семьи\n"
        "• Удаление семьи (для администраторов)\n"
    )
    
    return message


async def _create_family_detail_message(session, family, user_id: int) -> str:
    """Create detailed message for a specific family.
    
    Args:
        session: Database session
        family: Family object
        user_id: User ID
        
    Returns:
        Formatted message text
    """
    # Get member info
    members = await crud.get_family_members(session, family.id)
    member_count = len(members)
    admin_count = sum(1 for _, member in members if member.role.value == "admin")
    
    # Check if user is admin
    is_admin = await crud.is_family_admin(session, user_id, family.id)
    
    message = (
        f"👨‍👩‍👧 <b>{family.name}</b>\n\n"
        f"🔑 <b>Код приглашения:</b> <code>{family.invite_code}</code>\n"
        f"👥 <b>Участников:</b> {member_count} (админов: {admin_count})\n"
        f"📅 <b>Создана:</b> {family.created_at.strftime('%d.%m.%Y')}\n\n"
    )
    
    if is_admin:
        message += "👑 Вы администратор этой семьи\n\n"
        message += (
            "<b>Доступные действия:</b>\n"
            "• Покинуть семью\n"
            "• Удалить семью (удалит все данные)\n"
            "• Поделиться кодом приглашения\n"
        )
    else:
        message += (
            "<b>Доступные действия:</b>\n"
            "• Покинуть семью\n"
            "• Поделиться кодом приглашения\n"
        )
    
    return message


async def my_families_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show list of user's families.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = await get_user_from_context_or_db(update, context)
    if not user_id:
        await MsgHandler.send_or_edit(update, ERROR_USER_NOT_REGISTERED)
        return
    
    async for session in get_db():
        try:
            families = await crud.get_user_families(session, user_id)
            
            if not families:
                message = _create_no_families_message()
                keyboard = [
                    [InlineKeyboardButton("👨‍👩‍👧 Создать семью", callback_data="create_family")],
                    [InlineKeyboardButton("🔗 Присоединиться к семье", callback_data="join_family")]
                ]
            else:
                message = _create_families_list_message(families, user_id, session)
                # Create buttons for each family
                keyboard = []
                for family in families:
                    keyboard.append([
                        InlineKeyboardButton(
                            f"👨‍👩‍👧 {family.name}",
                            callback_data=f"view_family_{family.id}"
                        )
                    ])
                keyboard.append([InlineKeyboardButton("➕ Создать еще семью", callback_data="create_family")])
            
            keyboard = add_navigation_buttons(keyboard, context, current_state="my_families")
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await MsgHandler.send_or_edit(update, message, reply_markup=reply_markup)
            
            logger.info(f"Showed {len(families)} families to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error showing families: {e}", exc_info=True)
            await MsgHandler.send_or_edit(
                update,
                "❌ Произошла ошибка при получении списка семей."
            )


async def view_family_details(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show details for a specific family.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    # Extract family_id from callback_data
    family_id = int(query.data.split("_")[-1])
    
    user_id = await get_user_from_context_or_db(update, context)
    if not user_id:
        await MsgHandler.send_or_edit(update, ERROR_USER_NOT_REGISTERED)
        return
    
    # Store family_id in context for later use
    context.user_data['selected_family_id'] = family_id
    
    async for session in get_db():
        try:
            # Get family
            family = await crud.get_family_by_id(session, family_id)
            
            if not family:
                await MsgHandler.send_or_edit(update, MSG_FAMILY_NOT_FOUND)
                return
            
            # Check if user is member
            is_member = await crud.is_user_in_family(session, user_id, family_id)
            if not is_member:
                await MsgHandler.send_or_edit(
                    update,
                    "❌ Вы не являетесь членом этой семьи."
                )
                return
            
            # Check if user is admin
            is_admin = await crud.is_family_admin(session, user_id, family_id)
            
            # Create detail message
            message = await _create_family_detail_message(session, family, user_id)
            
            # Create action buttons
            keyboard = []
            keyboard.append([_create_share_button(family)])
            keyboard.append([
                InlineKeyboardButton("🚪 Покинуть семью", callback_data=f"leave_family_{family_id}")
            ])
            
            if is_admin:
                keyboard.append([
                    InlineKeyboardButton("🗑 Удалить семью", callback_data=f"delete_family_{family_id}")
                ])
            
            keyboard.append([
                InlineKeyboardButton("◀️ Назад к списку", callback_data="my_families")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await MsgHandler.send_or_edit(update, message, reply_markup=reply_markup)
            
            logger.info(f"User {user_id} viewed details for family {family_id}")
            
        except Exception as e:
            logger.error(f"Error showing family details: {e}", exc_info=True)
            await MsgHandler.send_or_edit(
                update,
                "❌ Произошла ошибка при получении информации о семье."
            )


async def leave_family_confirm(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show confirmation dialog for leaving family.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    # Extract family_id from callback_data
    family_id = int(query.data.split("_")[-1])
    
    user_id = await get_user_from_context_or_db(update, context)
    if not user_id:
        await MsgHandler.send_or_edit(update, ERROR_USER_NOT_REGISTERED)
        return
    
    async for session in get_db():
        try:
            family = await crud.get_family_by_id(session, family_id)
            
            if not family:
                await MsgHandler.send_or_edit(update, MSG_FAMILY_NOT_FOUND)
                return
            
            message = (
                f"🚪 <b>Покинуть семью</b>\n\n"
                f"⚠️ Вы уверены, что хотите покинуть семью <b>{family.name}</b>?\n\n"
                "Ваши расходы останутся в истории семьи, но вы потеряете доступ к ней."
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Да, покинуть", callback_data=f"confirm_leave_{family_id}"),
                    InlineKeyboardButton("❌ Отмена", callback_data=f"view_family_{family_id}")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await MsgHandler.send_or_edit(update, message, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error showing leave confirmation: {e}", exc_info=True)
            await MsgHandler.send_or_edit(
                update,
                "❌ Произошла ошибка."
            )


async def leave_family_execute(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Execute leaving family action.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    # Extract family_id from callback_data
    family_id = int(query.data.split("_")[-1])
    
    user_id = await get_user_from_context_or_db(update, context)
    if not user_id:
        await MsgHandler.send_or_edit(update, ERROR_USER_NOT_REGISTERED)
        return
    
    async for session in get_db():
        try:
            family = await crud.get_family_by_id(session, family_id)
            family_name = family.name if family else "Unknown"
            
            success = await crud.remove_family_member(session, user_id, family_id)
            
            if success:
                await session.commit()
                message = (
                    f"✅ <b>Вы успешно покинули семью <b>{family_name}</b></b>\n\n"
                    "Используйте /my_families для просмотра оставшихся семей."
                )
                
                keyboard = [
                    [InlineKeyboardButton("👨‍👩‍👧‍👦 Мои семьи", callback_data="my_families")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="start")]
                ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await MsgHandler.send_or_edit(update, message, reply_markup=reply_markup)
                
                logger.info(f"User {user_id} left family {family_id}")
            else:
                await MsgHandler.send_or_edit(
                    update,
                    "❌ Ошибка при выходе из семьи. Возможно, вы уже не являетесь её членом."
                )
            
        except Exception as e:
            logger.error(f"Error leaving family: {e}", exc_info=True)
            await MsgHandler.send_or_edit(
                update,
                "❌ Произошла ошибка при выходе из семьи."
            )


async def delete_family_confirm(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show confirmation dialog for deleting family.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    # Extract family_id from callback_data
    family_id = int(query.data.split("_")[-1])
    
    user_id = await get_user_from_context_or_db(update, context)
    if not user_id:
        await MsgHandler.send_or_edit(update, ERROR_USER_NOT_REGISTERED)
        return
    
    async for session in get_db():
        try:
            # Check if user is admin
            is_admin = await crud.is_family_admin(session, user_id, family_id)
            
            if not is_admin:
                await query.answer("❌ Только администратор может удалить семью", show_alert=True)
                return
            
            family = await crud.get_family_by_id(session, family_id)
            
            if not family:
                await MsgHandler.send_or_edit(update, MSG_FAMILY_NOT_FOUND)
                return
            
            message = (
                f"🗑 <b>Удаление семьи</b>\n\n"
                f"⚠️ <b>ВНИМАНИЕ!</b> Это действие необратимо!\n\n"
                f"Вы собираетесь удалить семью <b>{family.name}</b>.\n\n"
                "При удалении семьи:\n"
                "• Все участники потеряют доступ\n"
                "• Вся история расходов будет удалена\n"
                "• Восстановление невозможно\n\n"
                "Вы точно уверены?"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_delete_{family_id}"),
                    InlineKeyboardButton("❌ Отмена", callback_data=f"view_family_{family_id}")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await MsgHandler.send_or_edit(update, message, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error showing delete confirmation: {e}", exc_info=True)
            await MsgHandler.send_or_edit(
                update,
                "❌ Произошла ошибка."
            )


async def delete_family_execute(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Execute deleting family action.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    # Extract family_id from callback_data
    family_id = int(query.data.split("_")[-1])
    
    user_id = await get_user_from_context_or_db(update, context)
    if not user_id:
        await MsgHandler.send_or_edit(update, ERROR_USER_NOT_REGISTERED)
        return
    
    async for session in get_db():
        try:
            # Check if user is admin
            is_admin = await crud.is_family_admin(session, user_id, family_id)
            
            if not is_admin:
                await query.answer("❌ Только администратор может удалить семью", show_alert=True)
                return
            
            family = await crud.get_family_by_id(session, family_id)
            family_name = family.name if family else "Unknown"
            
            if family:
                await session.delete(family)
                await session.commit()
                
                message = (
                    f"✅ <b>Семья <b>{family_name}</b> успешно удалена</b>\n\n"
                    "Все данные семьи были удалены.\n\n"
                    "Используйте /my_families для просмотра оставшихся семей."
                )
                
                keyboard = [
                    [InlineKeyboardButton("👨‍👩‍👧‍👦 Мои семьи", callback_data="my_families")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="start")]
                ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await MsgHandler.send_or_edit(update, message, reply_markup=reply_markup)
                
                logger.info(f"User {user_id} deleted family {family_id}")
            else:
                await MsgHandler.send_or_edit(update, MSG_FAMILY_NOT_FOUND)
            
        except Exception as e:
            logger.error(f"Error deleting family: {e}", exc_info=True)
            await MsgHandler.send_or_edit(
                update,
                "❌ Произошла ошибка при удалении семьи."
            )


# ============================================================================
# Conversation Handlers Setup
# ============================================================================

# Create family conversation handler
create_family_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(create_family_start, pattern="^create_family$"),
        CommandHandler("create_family", create_family_start)
    ],
    states={
        FAMILY_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, create_family_name_received)
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_conversation),
        CallbackQueryHandler(cancel_conversation, pattern="^cancel_create_family$"),
        CallbackQueryHandler(end_conversation_silently, pattern="^nav_back$"),
        # Main navigation fallbacks - end conversation and route to new section
        CallbackQueryHandler(end_conversation_and_route, pattern="^(start|categories|settings|help|add_expense|my_expenses|family_expenses|my_families|join_family|family_settings|stats_start|quick_expense|search)$")
    ],
    allow_reentry=True,
    name="create_family_conversation",
    persistent=False,
    per_chat=True,
    per_user=True
)

# Join family conversation handler
join_family_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(join_family_start, pattern="^join_family$"),
        CommandHandler("join_family", join_family_start)
    ],
    states={
        INVITE_CODE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, join_family_code_received)
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_conversation),
        CallbackQueryHandler(cancel_conversation, pattern="^cancel_join_family$"),
        CallbackQueryHandler(end_conversation_silently, pattern="^nav_back$"),
        # Main navigation fallbacks - end conversation and route to new section
        CallbackQueryHandler(end_conversation_and_route, pattern="^(start|categories|settings|help|add_expense|my_expenses|family_expenses|my_families|create_family|family_settings|stats_start|quick_expense|search)$")
    ],
    allow_reentry=True,
    name="join_family_conversation",
    persistent=False,
    per_chat=True,
    per_user=True
)

# My families command handler
my_families_handler_cmd = CommandHandler("my_families", my_families_command)
my_families_handler_callback = CallbackQueryHandler(
    my_families_command,
    pattern="^my_families$"
)

# Family detail view handlers
view_family_handler = CallbackQueryHandler(
    view_family_details,
    pattern="^view_family_\\d+$"
)

# Leave family handlers
leave_family_handler = CallbackQueryHandler(
    leave_family_confirm,
    pattern="^leave_family_\\d+$"
)
confirm_leave_family_handler = CallbackQueryHandler(
    leave_family_execute,
    pattern="^confirm_leave_\\d+$"
)

# Delete family handlers
delete_family_handler = CallbackQueryHandler(
    delete_family_confirm,
    pattern="^delete_family_\\d+$"
)
confirm_delete_family_handler = CallbackQueryHandler(
    delete_family_execute,
    pattern="^confirm_delete_\\d+$"
)
