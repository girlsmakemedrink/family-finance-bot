"""Navigation handler for back button and state management."""

import logging
from typing import Dict, Callable, Awaitable, Optional

from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes

from bot.utils.navigation import NavigationManager, STATE_START

logger = logging.getLogger(__name__)


# ============================================================================
# Navigation Route Mapping
# ============================================================================

# This maps navigation states to their corresponding handler functions
# Handlers are imported lazily to avoid circular dependencies
NAVIGATION_ROUTES: Dict[str, tuple[str, str]] = {
    STATE_START: ("bot.handlers.start", "start_callback"),
    "start": ("bot.handlers.start", "start_callback"),
    "settings": ("bot.handlers.settings", "settings_command"),
    "help": ("bot.handlers.help", "help_command"),
    "categories": ("bot.handlers.categories", "categories_command"),
    "add_category": ("bot.handlers.categories", "categories_command"),
    "edit_category": ("bot.handlers.categories", "categories_command"),
    "delete_category": ("bot.handlers.categories", "categories_command"),
    "statistics": ("bot.handlers.statistics", "stats_start"),
    "stats_start": ("bot.handlers.statistics", "stats_start"),
    "my_families": ("bot.handlers.family", "my_families_command"),
    "family_settings": ("bot.handlers.family_settings", "family_settings_command"),
}


async def _import_and_call_handler(
    module_name: str,
    function_name: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Dynamically import and call a handler function.
    
    This approach avoids circular dependencies by importing handlers only when needed.
    
    Args:
        module_name: Full module path (e.g., "bot.handlers.start")
        function_name: Name of the function to call
        update: Telegram update object
        context: Telegram context object
    """
    try:
        import importlib
        module = importlib.import_module(module_name)
        handler_func = getattr(module, function_name)
        await handler_func(update, context)
    except (ImportError, AttributeError) as e:
        logger.error(f"Failed to import handler {module_name}.{function_name}: {e}")
        # Fallback to start
        from bot.handlers.start import start_callback
        await start_callback(update, context)


async def _handle_navigation_state(
    previous_state: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Route to appropriate handler based on navigation state.
    
    Args:
        previous_state: State to navigate to
        update: Telegram update object
        context: Telegram context object
    """
    # Check if we have a route for this state
    if previous_state in NAVIGATION_ROUTES:
        module_name, function_name = NAVIGATION_ROUTES[previous_state]
        await _import_and_call_handler(module_name, function_name, update, context)
    else:
        # Unknown state, go to start
        logger.warning(f"Unknown navigation state: {previous_state}, redirecting to start")
        from bot.handlers.start import start_callback
        await start_callback(update, context)


# ============================================================================
# Navigation Handler
# ============================================================================

async def navigation_back_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle navigation back button press.
    
    This handler manages the navigation history and routes users to the
    appropriate previous state.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    if not query:
        return
    
    # Answer callback to remove loading state
    await query.answer()
    
    # Get previous state from history
    previous_state = NavigationManager.get_previous_state(context)
    
    if not previous_state:
        # No history, go to start
        logger.info("No navigation history, redirecting to start")
        NavigationManager.pop_state(context)
        from bot.handlers.start import start_callback
        await start_callback(update, context)
        return
    
    logger.info(f"Navigating back to state: {previous_state}")
    
    # Pop the state now that we know where we're going
    NavigationManager.pop_state(context)
    
    # Route to appropriate handler
    await _handle_navigation_state(previous_state, update, context)


# ============================================================================
# Handler Registration
# ============================================================================

navigation_back_callback_handler = CallbackQueryHandler(
    navigation_back_handler,
    pattern="^nav_back$"
)
