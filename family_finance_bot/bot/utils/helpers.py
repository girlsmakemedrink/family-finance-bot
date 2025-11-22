"""Helper utilities for bot handlers."""

import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Optional

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def safe_edit_message(query, text: str, **kwargs):
    """Safely edit message, handling 'Message is not modified' error.
    
    Args:
        query: CallbackQuery object
        text: New message text
        **kwargs: Additional arguments for edit_message_text
        
    This function prevents BadRequest exceptions when trying to edit a message
    with the same content. If the message hasn't changed, it just answers the
    callback query without raising an error.
    """
    try:
        await query.edit_message_text(text, **kwargs)
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise
        # If message is not modified, just answer the callback query
        await query.answer()


async def end_conversation_silently(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Silently end a conversation without handling the callback.
    
    This is used as a fallback handler for 'nav_back' in ConversationHandlers.
    Since navigation_back_callback_handler is registered in group=-1,
    it will process the callback first and handle navigation before
    ConversationHandlers see it.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        ConversationHandler.END
    """
    from telegram.ext import ConversationHandler
    
    # Just end the conversation
    # navigation_back_callback_handler (in group=-1) will handle the actual navigation
    return ConversationHandler.END


async def end_conversation_and_route(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """End conversation and route to the requested handler.
    
    This handler is used for main navigation callbacks that should
    exit the current conversation and navigate to a different section.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        ConversationHandler.END
    """
    from telegram.ext import ConversationHandler
    from bot.handlers.navigation import _handle_navigation_state
    
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    
    # Answer callback to remove loading state
    await query.answer()
    
    # Get callback data (which is the navigation state)
    callback_data = query.data
    
    # Map callback data to navigation state
    # The callback_data matches the state names in NAVIGATION_ROUTES
    navigation_state = callback_data
    
    # Route to the appropriate handler
    await _handle_navigation_state(navigation_state, update, context)
    
    return ConversationHandler.END


async def get_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    """Get user_id from context or fetch from database.
    
    This helper function ensures that user_id is always available, even if
    the bot was restarted or context was cleared. It first tries to get
    user_id from context.user_data, and if not found, fetches it from the
    database using telegram_id.
    
    If the user doesn't exist in the database, it automatically creates them.
    This ensures that users can interact with the bot without explicitly
    running /start first.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        
    Returns:
        User ID if found or created, None otherwise
    """
    # Try to get user_id from context
    user_id = context.user_data.get('user_id')
    if user_id:
        return user_id
    
    # Get telegram_id from update
    if not update.effective_user:
        logger.warning("Cannot get user_id: no effective_user in update")
        return None
    
    telegram_id = update.effective_user.id
    effective_user = update.effective_user
    
    # Fetch user from database
    from bot.database import crud, get_db
    
    async for session in get_db():
        user = await crud.get_user_by_telegram_id(session, telegram_id)
        
        # If user doesn't exist, create them automatically
        if not user:
            logger.info(f"User with telegram_id {telegram_id} not found, creating new user")
            
            # Build full name from Telegram user data
            full_name = effective_user.full_name or effective_user.first_name or "Unknown"
            username = effective_user.username
            
            try:
                user = await crud.create_user(
                    session,
                    telegram_id=telegram_id,
                    name=full_name,
                    username=username
                )
                await session.commit()
                logger.info(f"Auto-created user: {user.name} (id={user.id}, telegram_id={telegram_id})")
            except Exception as e:
                logger.error(f"Error auto-creating user with telegram_id {telegram_id}: {e}")
                await session.rollback()
                return None
        
        # Save user_id in context for future use
        user_id = user.id
        context.user_data['user_id'] = user_id
        context.user_data['telegram_id'] = telegram_id
        logger.info(f"Retrieved user_id {user_id} from database for telegram_id {telegram_id}")
        return user_id
    
    return None


def validate_amount(amount_str: str) -> Optional[Decimal]:
    """
    Validate and parse amount string.
    
    Args:
        amount_str: Amount as string
        
    Returns:
        Decimal amount if valid, None otherwise
        
    Rules:
        - Must be positive number
        - Can have up to 2 decimal places
        - Maximum 10 digits before decimal point
    """
    if not amount_str or not amount_str.strip():
        return None
    
    amount_str = amount_str.strip().replace(',', '.')
    
    # Check format with regex
    if not re.match(r'^\d{1,10}(\.\d{1,2})?$', amount_str):
        return None
    
    try:
        amount = Decimal(amount_str)
        
        # Check if positive
        if amount <= 0:
            return None
        
        # Check maximum value
        if amount > Decimal('9999999999.99'):
            return None
        
        return amount
    except (InvalidOperation, ValueError):
        return None


def validate_description(description: str, max_length: int = 500) -> bool:
    """
    Validate expense description.
    
    Args:
        description: Description text
        max_length: Maximum allowed length (default: 500)
        
    Returns:
        True if valid, False otherwise
        
    Rules:
        - Not empty after stripping whitespace
        - Length <= max_length
        - No control characters
    """
    if not description:
        return False
    
    description = description.strip()
    
    if not description:
        return False
    
    if len(description) > max_length:
        return False
    
    # Check for control characters (except newline and tab)
    if any(ord(char) < 32 and char not in '\n\t' for char in description):
        return False
    
    return True


def validate_family_name(name: str) -> bool:
    """
    Validate family name.
    
    Args:
        name: Family name
        
    Returns:
        True if valid, False otherwise
        
    Rules:
        - Not empty after stripping
        - Length between 1 and 100 characters
        - No control characters
    """
    if not name:
        return False
    
    name = name.strip()
    
    if not name or len(name) > 100:
        return False
    
    # Check for control characters
    if any(ord(char) < 32 for char in name):
        return False
    
    return True


def validate_invite_code(code: str) -> bool:
    """
    Validate invite code format.
    
    Args:
        code: Invite code
        
    Returns:
        True if valid, False otherwise
        
    Rules:
        - 8-16 uppercase alphanumeric characters
    """
    if not code:
        return False
    
    code = code.strip().upper()
    
    # Check format
    if not re.match(r'^[A-Z0-9]{8,16}$', code):
        return False
    
    return True


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """
    Sanitize user input by removing potentially harmful content.
    
    Args:
        text: Input text
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Strip whitespace
    text = text.strip()
    
    # Truncate to max length
    text = text[:max_length]
    
    # Remove control characters (except newline and tab)
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
    
    return text


async def notify_large_expense(
    session,
    bot,
    expense,
    family_members
) -> None:
    """Send notifications about large expenses to family members.
    
    Args:
        session: Database session
        bot: Bot instance
        expense: Expense object
        family_members: List of family members to notify
    """
    from bot.utils.formatters import format_amount
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Get user who created the expense
        expense_user = expense.user
        
        # Check if user has large expense threshold set
        if not expense_user.large_expense_threshold:
            return
        
        # Check if expense exceeds threshold
        if expense.amount < expense_user.large_expense_threshold:
            return
        
        # Prepare notification message
        message = (
            f"🚨 <b>Большая трата!</b>\n\n"
            f"👤 {expense_user.name}\n"
            f"{expense.category.icon} <b>{expense.category.name}</b>\n"
            f"💰 Сумма: <b>{format_amount(expense.amount)}</b>\n"
        )
        
        if expense.description:
            message += f"📝 {expense.description}\n"
        
        # Send notification to all family members except the one who created expense
        for member in family_members:
            if member.user_id != expense.user_id:
                try:
                    await bot.send_message(
                        chat_id=member.user.telegram_id,
                        text=message,
                        parse_mode="HTML"
                    )
                    logger.info(
                        f"Sent large expense notification to user {member.user_id} "
                        f"for expense {expense.id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Error sending large expense notification "
                        f"to user {member.user_id}: {e}"
                    )
                    # Continue sending to other members even if one fails
        
    except Exception as e:
        logger.error(f"Error in notify_large_expense: {e}")

