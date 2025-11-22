"""Utility decorators for bot handlers."""

from functools import wraps
from typing import Callable, TypeVar, cast

from telegram import Update
from telegram.ext import ContextTypes

from bot import logger
from config.settings import settings

F = TypeVar('F', bound=Callable)


def admin_only(func: F) -> F:
    """Decorator to restrict handler to admin users only.
    
    Args:
        func: The handler function to decorate.
        
    Returns:
        Wrapped function that checks admin status.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        
        if user_id not in settings.ADMIN_USER_IDS:
            logger.warning(
                f"Unauthorized access attempt by user {user_id} "
                f"({update.effective_user.username})"
            )
            if update.message:
                await update.message.reply_text(
                    "⛔️ Эта команда доступна только администраторам."
                )
            return
        
        return await func(update, context, *args, **kwargs)
    
    return cast(F, wrapper)


def log_handler(func: F) -> F:
    """Decorator to log handler calls.
    
    Args:
        func: The handler function to decorate.
        
    Returns:
        Wrapped function with logging.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_user and update.message:
            logger.info(
                f"Handler {func.__name__} called by user "
                f"{update.effective_user.id} ({update.effective_user.username}): "
                f"{update.message.text}"
            )
        
        return await func(update, context, *args, **kwargs)
    
    return cast(F, wrapper)


def typing_action(func: F) -> F:
    """Decorator to send typing action while processing.
    
    Args:
        func: The handler function to decorate.
        
    Returns:
        Wrapped function that sends typing action.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_chat:
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action="typing"
            )
        
        return await func(update, context, *args, **kwargs)
    
    return cast(F, wrapper)

