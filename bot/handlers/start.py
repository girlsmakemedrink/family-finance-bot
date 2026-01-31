"""Start command handler with user registration."""

import logging
from decimal import Decimal
from typing import Optional, Tuple

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from bot.database import crud, get_db
from bot.utils.constants import (
    MSG_WITHOUT_FAMILIES,
    MSG_WITH_FAMILIES,
    WELCOME_NEW_USER,
    WELCOME_RETURNING_USER,
)
from bot.utils.keyboards import get_main_menu_keyboard
from bot.utils.message_utils import UserDataExtractor, format_families_list
from bot.utils.navigation import NavigationManager
from bot.utils.formatters import format_amount

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================

async def _get_or_create_user(session, telegram_id: int, full_name: str, username: Optional[str]) -> Tuple[object, bool]:
    """Get existing user or create new one.
    
    Args:
        session: Database session
        telegram_id: User's Telegram ID
        full_name: User's full name
        username: User's username (optional)
        
    Returns:
        Tuple of (user object, is_new_user)
    """
    user = await crud.get_user_by_telegram_id(session, telegram_id)
    
    if user is None:
        # Create new user
        user = await crud.create_user(
            session,
            telegram_id=telegram_id,
            name=full_name,
            username=username
        )
        logger.info(f"Created new user: {user.name} (id={user.id})")
        return user, True
    
    logger.info(f"Existing user: {user.name} (id={user.id})")
    return user, False


def _build_welcome_message(user, families, is_new_user: bool = False) -> str:
    """Build welcome message based on user state.
    
    Args:
        user: User object
        families: List of user's families
        is_new_user: Whether this is a new user
        
    Returns:
        Formatted welcome message
    """
    # Start with greeting
    if is_new_user:
        message = WELCOME_NEW_USER.format(name=user.name)
    else:
        message = WELCOME_RETURNING_USER.format(name=user.name)
    
    # Add family information
    if families:
        families_list = format_families_list(families)
        message += MSG_WITH_FAMILIES.format(families_list=families_list)
    else:
        message += MSG_WITHOUT_FAMILIES
    
    return message


def _save_user_to_context(context: ContextTypes.DEFAULT_TYPE, user_id: int, telegram_id: int) -> None:
    """Save user information to context for future use.
    
    Args:
        context: Telegram context object
        user_id: Database user ID
        telegram_id: Telegram user ID
    """
    context.user_data['user_id'] = user_id
    context.user_data['telegram_id'] = telegram_id


def _pick_family_scope_for_main_menu(context: ContextTypes.DEFAULT_TYPE, families) -> tuple[str, Optional[int], str, list[int]]:
    """Pick which family scope to show in main menu balance block.
    
    Priority:
    - selected_family_id (if still available)
    - the only family (if exactly one)
    - all families (aggregate)
    
    Returns:
        (scope_kind, family_id, label, family_ids)
    """
    family_ids = [f.id for f in families] if families else []
    selected_id = context.user_data.get("selected_family_id")
    
    if selected_id in family_ids:
        selected_family = next((f for f in families if f.id == selected_id), None)
        label = selected_family.name if selected_family else "Семья"
        return ("single", int(selected_id), label, family_ids)
    
    if len(family_ids) == 1:
        return ("single", int(family_ids[0]), families[0].name, family_ids)
    
    return ("all", None, "Все семьи", family_ids)


async def _build_family_balance_block(
    session,
    context: ContextTypes.DEFAULT_TYPE,
    families,
) -> str:
    """Build 'family balance' block for main menu."""
    if not families:
        return ""
    
    scope_kind, family_id, label, family_ids = _pick_family_scope_for_main_menu(context, families)
    
    if scope_kind == "single" and family_id is not None:
        totals = await crud.get_family_income_expense_totals(session, family_id)
    else:
        totals = await crud.get_families_income_expense_totals(session, family_ids)
    
    income_total: Decimal = totals.get("income_total", Decimal("0"))
    expense_total: Decimal = totals.get("expense_total", Decimal("0"))
    balance: Decimal = totals.get("balance", income_total - expense_total)

    total_flow = income_total + expense_total
    if total_flow > 0:
        income_pct = float((income_total / total_flow) * 100)
        expense_pct = 100.0 - income_pct
        income_line = f"📈 Доходы: {format_amount(income_total)} ({income_pct:.0f}%)"
        expense_line = f"📉 Расходы: {format_amount(expense_total)} ({expense_pct:.0f}%)"
    else:
        income_line = f"📈 Доходы: {format_amount(income_total)}"
        expense_line = f"📉 Расходы: {format_amount(expense_total)}"
    
    return (
        "\n\n"
        f"📌 <b>Баланс: {label}</b>\n"
        f"{income_line}\n"
        f"{expense_line}\n"
        f"💰 Баланс: {format_amount(balance)}"
    )


async def _process_start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    is_callback: bool = False
) -> None:
    """Process start command logic (shared between command and callback).
    
    Args:
        update: Telegram update object
        context: Telegram context object
        is_callback: Whether this is called from callback handler
    """
    if not update.effective_user:
        logger.warning("Received /start command without user")
        return
    
    # Extract user information
    telegram_id, full_name, username = UserDataExtractor.get_user_info(update)
    if not telegram_id:
        logger.warning("Could not extract user info from update")
        return
    
    logger.info(
        f"User {telegram_id} ({username or 'no username'}) "
        f"{'opened start via callback' if is_callback else 'started the bot'}"
    )
    
    # Clear navigation history when returning to start
    NavigationManager.clear_history(context)
    
    # Work with database
    async for session in get_db():
        # Get or create user
        user, is_new_user = await _get_or_create_user(
            session,
            telegram_id,
            full_name,
            username
        )
        
        # Save user data to context
        _save_user_to_context(context, user.id, telegram_id)
        
        # Get user's families
        families = await crud.get_user_families(session, user.id)
        
        # Build welcome message
        welcome_message = _build_welcome_message(
            user,
            families,
            is_new_user and not is_callback
        )

        # Add family balance block (if any family exists)
        welcome_message += await _build_family_balance_block(session, context, families)
        
        # Get appropriate keyboard
        reply_markup = get_main_menu_keyboard(has_families=bool(families))
        
        # Send or edit message
        if is_callback and update.callback_query:
            await update.callback_query.answer()
            try:
                await update.callback_query.edit_message_text(
                    welcome_message,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
            except BadRequest as e:
                # Handle case when message has no text (e.g., document with caption)
                if "no text in the message" in str(e).lower():
                    await update.callback_query.message.reply_text(
                        welcome_message,
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )
                else:
                    raise
            logger.info(f"Edited message to show start menu for user {user.id}")
        elif update.message:
            await update.message.reply_text(
                welcome_message,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            logger.info(
                f"Sent welcome message to user {user.id} "
                f"(is_new={is_new_user}, families_count={len(families)})"
            )


# ============================================================================
# Command Handlers
# ============================================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle the /start command with user registration.
    
    This command:
    - Checks if user exists in database
    - Creates new user if needed
    - Shows welcome message with action buttons
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    await _process_start_command(update, context, is_callback=False)


async def start_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle start callback from inline buttons.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    await _process_start_command(update, context, is_callback=True)


async def about_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle the /about command.
    
    Shows information about the bot.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    if not update.message or not update.effective_user:
        return
    
    logger.info(f"User {update.effective_user.id} requested about info")
    
    about_text = (
        "ℹ️ <b>О боте Family Finance Bot</b>\n\n"
        
        "Семейный финансовый помощник для учёта общих финансов.\n\n"
        
        "<b>Версия:</b> 1.0.0\n"
        "<b>Разработчик:</b> Family Finance Team\n\n"
        
        "<b>Возможности:</b>\n"
        "👨‍👩‍👧‍👦 Совместный учёт для всей семьи\n"
        "💵 Расходы и доходы\n"
        "🏷️ Категории (свои + стандартные)\n"
        "⚡ Быстрые расходы — шаблоны\n"
        "📊 Детальная аналитика и графики\n"
        "📅 Автоматические месячные сводки\n"
        "📄 Экспорт: HTML отчёты\n"
        "⚙️ Валюта, часовой пояс, персонализация\n\n"
        
        "Спасибо, что используете наш бот! ❤️"
    )
    
    await update.message.reply_text(
        about_text,
        parse_mode="HTML"
    )


# ============================================================================
# Handler Registration
# ============================================================================

start_handler = CommandHandler("start", start_command)
start_callback_handler = CallbackQueryHandler(start_callback, pattern="^start$")
about_handler = CommandHandler("about", about_command)
