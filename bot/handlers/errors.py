"""Error handler for the bot with improved structure and logging."""

import html
import logging
import traceback
from typing import Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config.settings import settings

logger = logging.getLogger(__name__)


# ============================================================================
# Error Message Templates
# ============================================================================

USER_ERROR_MESSAGE = (
    "😔 Извините, произошла ошибка при обработке вашего запроса.\n"
    "Пожалуйста, попробуйте позже или обратитесь к администратору."
)


# ============================================================================
# Helper Functions
# ============================================================================

def _format_error_info(context: ContextTypes.DEFAULT_TYPE) -> tuple[str, str, str]:
    """Extract and format error information.
    
    Args:
        context: Telegram context object containing the error
        
    Returns:
        Tuple of (error_type, error_text, traceback_string)
    """
    error = context.error
    
    error_type = type(error).__name__
    error_text = str(error)
    
    # Generate traceback
    tb_list = traceback.format_exception(None, error, error.__traceback__)
    tb_string = "".join(tb_list)
    
    return error_type, error_text, tb_string


def _build_admin_error_message(
    error_type: str,
    error_text: str,
    tb_string: str,
    update: Optional[Update]
) -> str:
    """Build error message for administrators.
    
    Args:
        error_type: Type of the error
        error_text: Error message
        tb_string: Traceback string
        update: Telegram update object (optional)
        
    Returns:
        Formatted error message
    """
    message = (
        f"⚠️ <b>Error occurred</b>\n\n"
        f"<b>Type:</b> {html.escape(error_type)}\n"
        f"<b>Message:</b> {html.escape(error_text[:200])}\n\n"
    )
    
    # Add user info if available
    if update and update.effective_user:
        user = update.effective_user
        message += (
            f"<b>User:</b> {html.escape(user.full_name)} "
            f"(ID: {user.id})\n\n"
        )
    
    # Add truncated traceback
    tb_preview = tb_string[:500] if len(tb_string) > 500 else tb_string
    message += f"<b>Traceback:</b>\n<code>{html.escape(tb_preview)}</code>"
    
    if len(tb_string) > 500:
        message += "\n\n<i>...truncated</i>"
    
    return message


async def _notify_admins(
    context: ContextTypes.DEFAULT_TYPE,
    error_message: str
) -> None:
    """Send error notification to administrators.
    
    Args:
        context: Telegram context object
        error_message: Formatted error message
    """
    if not settings.ADMIN_USER_IDS or not context.bot:
        return
    
    for admin_id in settings.ADMIN_USER_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=error_message,
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.error(f"Failed to send error message to admin {admin_id}: {e}")


async def _notify_user(update: Optional[Update]) -> None:
    """Send user-friendly error message to the user.
    
    Args:
        update: Telegram update object (optional)
    """
    if not update or not update.effective_message:
        return
    
    try:
        await update.effective_message.reply_text(USER_ERROR_MESSAGE)
    except Exception as e:
        logger.error(f"Failed to send error message to user: {e}")


# ============================================================================
# Main Error Handler
# ============================================================================

async def error_handler(
    update: Optional[Update],
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle errors in the telegram bot.
    
    This handler:
    - Logs detailed error information
    - Sends notifications to administrators
    - Provides user-friendly feedback to users
    
    Args:
        update: Telegram update object (may be None)
        context: Telegram context object containing the error
    """
    # Log the error with full traceback
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    # Extract error information
    error_type, error_text, tb_string = _format_error_info(context)
    
    # Build admin notification message
    admin_message = _build_admin_error_message(
        error_type,
        error_text,
        tb_string,
        update
    )
    
    # Notify administrators
    await _notify_admins(context, admin_message)
    
    # Notify user with friendly message
    await _notify_user(update)
