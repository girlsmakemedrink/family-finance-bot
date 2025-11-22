"""Middleware for logging, performance tracking, and error handling."""

import logging
import time
from typing import Any, Optional

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


# ============================================================================
# Logging Middleware
# ============================================================================

def _extract_update_info(update: Update) -> tuple[str, str]:
    """Extract message type and content from update.
    
    Args:
        update: Telegram update object
        
    Returns:
        Tuple of (message_type, content)
    """
    if update.message:
        message_type = "message"
        content = update.message.text or "[media/other]"
    elif update.callback_query:
        message_type = "callback"
        content = update.callback_query.data or "[no_data]"
    else:
        message_type = "other"
        content = "[unknown]"
    
    return message_type, content


async def error_logging_middleware(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Middleware to log all incoming updates.
    
    Logs user ID, username, message type, and content for debugging
    and monitoring purposes.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    if not update.effective_user:
        return
    
    user_id = update.effective_user.id
    username = update.effective_user.username or "no_username"
    
    message_type, content = _extract_update_info(update)
    
    logger.info(f"[{message_type}] User {user_id} (@{username}): {content}")


# ============================================================================
# Performance Tracking Middleware
# ============================================================================

def _store_request_start_time(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Store request start time in context for performance tracking.
    
    Args:
        context: Telegram context object
    """
    context.user_data['_request_start_time'] = time.time()


def _log_request_duration(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log request duration if start time is available.
    
    Args:
        context: Telegram context object
    """
    start_time = context.user_data.get('_request_start_time')
    if start_time:
        duration = time.time() - start_time
        logger.debug(f"Request completed in {duration:.2f} seconds")
        # Clean up
        context.user_data.pop('_request_start_time', None)


async def performance_logging_middleware(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Middleware to track and log performance metrics.
    
    Stores request start time for later calculation of request duration.
    Actual logging happens in the enhanced error handler or can be added
    to individual handlers.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    _store_request_start_time(context)


# ============================================================================
# User Context Enrichment Middleware
# ============================================================================

async def user_context_middleware(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Middleware to enrich context with user data.
    
    Stores commonly used user information in context for easy access
    by handlers without repeated lookups.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    if not update.effective_user:
        return
    
    user = update.effective_user
    
    # Store user info in context for easy access
    context.user_data['effective_user_id'] = user.id
    context.user_data['effective_username'] = user.username
    context.user_data['effective_user_name'] = user.full_name


# ============================================================================
# Enhanced Error Handler
# ============================================================================

def _build_detailed_error_log(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
    tb_string: str
) -> str:
    """Build detailed error log message.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        tb_string: Traceback string
        
    Returns:
        Formatted error log message
    """
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    
    return (
        f"An exception was raised while handling an update\n"
        f"update = {update_str}\n\n"
        f"context.chat_data = {context.chat_data}\n"
        f"context.user_data = {context.user_data}\n\n"
        f"{tb_string}"
    )


async def _send_user_error_message(update: Update) -> None:
    """Send user-friendly error message.
    
    Args:
        update: Telegram update object
    """
    if not update.effective_message:
        return
    
    error_text = (
        "❌ <b>Произошла ошибка</b>\n\n"
        "К сожалению, при обработке вашего запроса произошла ошибка. "
        "Мы уже работаем над её исправлением.\n\n"
        "Пожалуйста, попробуйте:\n"
        "• Повторить операцию через несколько секунд\n"
        "• Использовать команду /start для перезапуска\n"
        "• Связаться с поддержкой, если проблема повторяется\n\n"
        "Приносим извинения за неудобства! 🙏"
    )
    
    try:
        await update.effective_message.reply_text(error_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error sending error message to user: {e}")


async def enhanced_error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Enhanced error handler with detailed logging and user-friendly messages.
    
    This handler:
    - Logs detailed error information including context
    - Sends user-friendly error messages
    - Tracks performance metrics for failed requests
    
    Args:
        update: Telegram update object
        context: Telegram context object containing the error
    """
    # Log the error with full traceback
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    # Get detailed traceback
    import traceback
    tb_list = traceback.format_exception(
        None,
        context.error,
        context.error.__traceback__
    )
    tb_string = ''.join(tb_list)
    
    # Build and log detailed error message
    error_log = _build_detailed_error_log(update, context, tb_string)
    logger.error(error_log)
    
    # Send user-friendly message
    if isinstance(update, Update):
        await _send_user_error_message(update)
        
        # Log performance if available
        if context.user_data and '_request_start_time' in context.user_data:
            start_time = context.user_data['_request_start_time']
            duration = time.time() - start_time
            logger.warning(f"Request failed after {duration:.2f} seconds")


# ============================================================================
# Middleware Setup
# ============================================================================

def setup_middlewares(application: Any) -> None:
    """Setup all middlewares for the application.
    
    Note: python-telegram-bot doesn't have a traditional middleware system.
    Instead, middleware logic is called manually in handlers or through
    the error handler mechanism.
    
    Args:
        application: Telegram application instance
    """
    logger.info("Middleware setup completed")
    
    # Additional middleware initialization can be added here if needed
    # For example, setting up database connection pools, caches, etc.
