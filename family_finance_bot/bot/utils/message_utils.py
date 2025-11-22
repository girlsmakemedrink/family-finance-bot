"""Utility functions for working with Telegram messages and updates."""

import logging
from typing import Optional, Tuple

from telegram import InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class MessageHandler:
    """Helper class for handling Telegram messages consistently."""

    @staticmethod
    async def send_or_edit(
        update: Update,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: Optional[InlineKeyboardMarkup] = None
    ) -> Optional[Message]:
        """Send or edit message depending on update type.
        
        Args:
            update: Telegram update object
            text: Message text to send
            parse_mode: Parse mode for the message
            reply_markup: Optional keyboard markup
            
        Returns:
            Sent or edited message, or None on error
        """
        try:
            if update.callback_query:
                await update.callback_query.answer()
                return await update.callback_query.edit_message_text(
                    text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
            elif update.message:
                return await update.message.reply_text(
                    text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
        except Exception as e:
            logger.error(f"Error sending/editing message: {e}")
            return None

    @staticmethod
    def is_callback_query(update: Update) -> bool:
        """Check if update is a callback query.
        
        Args:
            update: Telegram update object
            
        Returns:
            True if update contains callback query
        """
        return update.callback_query is not None

    @staticmethod
    def get_message_text(update: Update) -> Optional[str]:
        """Extract message text from update.
        
        Args:
            update: Telegram update object
            
        Returns:
            Message text or None
        """
        if update.message and update.message.text:
            return update.message.text.strip()
        return None


class UserDataExtractor:
    """Helper class for extracting user data from Telegram updates."""

    @staticmethod
    def get_user_full_name(telegram_user) -> str:
        """Build full name from Telegram user object.
        
        Args:
            telegram_user: Telegram user object
            
        Returns:
            Full name string or default User_ID format
        """
        name_parts = []
        if telegram_user.first_name:
            name_parts.append(telegram_user.first_name)
        if telegram_user.last_name:
            name_parts.append(telegram_user.last_name)
        
        return " ".join(name_parts) if name_parts else f"User_{telegram_user.id}"

    @staticmethod
    def get_user_info(update: Update) -> Tuple[Optional[int], Optional[str], Optional[str]]:
        """Extract user information from update.
        
        Args:
            update: Telegram update object
            
        Returns:
            Tuple of (telegram_id, full_name, username)
        """
        if not update.effective_user:
            return None, None, None

        telegram_user = update.effective_user
        telegram_id = telegram_user.id
        full_name = UserDataExtractor.get_user_full_name(telegram_user)
        username = telegram_user.username

        return telegram_id, full_name, username


class ValidationHelper:
    """Helper class for common validation tasks."""

    @staticmethod
    def validate_text_input(text: Optional[str], min_length: int, max_length: int) -> Tuple[bool, Optional[str]]:
        """Validate text input length.
        
        Args:
            text: Text to validate
            min_length: Minimum allowed length
            max_length: Maximum allowed length
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not text:
            return False, "❌ Пожалуйста, введите текст."

        text = text.strip()
        
        if len(text) < min_length:
            return False, f"❌ Текст слишком короткий. Минимум {min_length} символов."
        
        if len(text) > max_length:
            return False, f"❌ Текст слишком длинный. Максимум {max_length} символов."
        
        return True, None

    @staticmethod
    def validate_amount(amount_str: str, max_value: str = "999999999.99") -> Tuple[bool, Optional[str], Optional[float]]:
        """Validate amount input.
        
        Args:
            amount_str: Amount string to validate
            max_value: Maximum allowed value
            
        Returns:
            Tuple of (is_valid, error_message, decimal_value)
        """
        from decimal import Decimal, InvalidOperation

        try:
            # Replace comma with dot for decimal separator
            amount_str = amount_str.strip().replace(',', '.')
            amount = Decimal(amount_str)
            
            if amount <= 0:
                return False, "❌ Сумма должна быть положительной.", None
            
            if amount > Decimal(max_value):
                return False, f"❌ Сумма слишком большая. Максимум {max_value}", None
            
            return True, None, amount
            
        except (InvalidOperation, ValueError):
            return False, "❌ Неверный формат. Введите число (например: 5000 или 5000.50)", None


async def get_user_from_context_or_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get user ID from context or database.
    
    This is a helper function that reduces code duplication across handlers.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        User ID or None if not found
    """
    from bot.utils.helpers import get_user_id
    return await get_user_id(update, context)


def format_families_list(families) -> str:
    """Format list of families for display.
    
    Args:
        families: List of family objects
        
    Returns:
        Formatted string with family list
    """
    if not families:
        return ""
    
    family_lines = [f"• {family.name}" for family in families]
    return "\n".join(family_lines)

