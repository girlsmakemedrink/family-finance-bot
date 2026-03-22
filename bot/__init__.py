"""Family Finance Bot - Main bot package.

This package contains the core functionality of the Telegram bot
for tracking family expenses and income.
"""

import logging
import warnings
from typing import Optional

from telegram.ext import Application
from telegram.warnings import PTBUserWarning

from config.settings import settings

# Suppress PTBUserWarning about per_message=False with CallbackQueryHandler
# This is expected behavior for ConversationHandlers that mix CallbackQueryHandler with MessageHandler/CommandHandler
warnings.filterwarnings(
    "ignore",
    message=".*'CallbackQueryHandler' will not be tracked for every message.*",
    category=PTBUserWarning
)

logger = logging.getLogger(__name__)


class FamilyFinanceBot:
    """Main bot class that encapsulates the bot's functionality."""

    def __init__(self) -> None:
        """Initialize the bot with configuration from settings."""
        self.application: Optional[Application] = None
        self.token: str = settings.BOT_TOKEN
        
        logger.info("Family Finance Bot initialized")
    
    async def setup(self) -> None:
        """Set up the bot application and register handlers."""
        # Initialize database
        from bot.database import init_database
        
        logger.info("Initializing database...")
        try:
            await init_database()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}", exc_info=True)
            raise
        
        # Build the application
        self.application = (
            Application.builder()
            .token(self.token)
            .build()
        )
        app = self.application
        
        # Import handlers
        from telegram.ext import CallbackQueryHandler
        
        from bot.handlers.categories import (
            add_category_handler,
            categories_callback_handler,
            categories_handler,
            delete_category_handler,
            edit_category_handler,
            show_categories_handler,
        )
        from bot.handlers.errors import error_handler
        from bot.handlers.expenses import (
            add_expense_handler,
            view_expenses_handler,
            family_expenses_handler,
            family_grouping_handler,
            family_pagination_handler,
            pagination_handler,
        )
        from bot.handlers.incomes import add_income_handler
        from bot.handlers.family import (
            confirm_delete_family_handler as my_families_confirm_delete_handler,
            confirm_leave_family_handler as my_families_confirm_leave_handler,
            create_family_handler,
            delete_family_handler as my_families_delete_handler,
            join_family_handler,
            leave_family_handler as my_families_leave_handler,
            my_families_handler_callback,
            my_families_handler_cmd,
            view_family_handler,
        )
        from bot.handlers.family_settings import (
            confirm_delete_family_handler,
            confirm_leave_family_handler,
            family_delete_handler,
            family_leave_handler,
            family_manage_members_handler,
            family_regenerate_code_handler,
            family_rename_handler,
            family_settings_callback_handler,
            family_settings_handler_cmd,
            family_settings_select_handler,
        )
        from bot.handlers.help import (
            help_callback_handler,
            help_expenses_handler,
            help_families_handler,
            help_handler,
            help_settings_handler,
            help_stats_handler,
        )
        from bot.handlers.middleware import enhanced_error_handler
        from bot.handlers.navigation import navigation_back_callback_handler
        from bot.handlers.quick_expense import quick_expense_handler
        from bot.handlers.recent_operations import (
            recent_operations_callback_handler,
            recent_operations_command_handler,
        )
        from bot.handlers.search import search_handler
        from bot.handlers.settings import (
            currency_selection_handler,
            date_format_selection_handler,
            monthly_summary_time_handler,
            settings_callback_handler,
            settings_currency_handler,
            settings_date_format_handler,
            settings_expense_notifications_handler,
            settings_handler,
            settings_monthly_summary_handler,
            settings_timezone_handler,
            timezone_selection_handler,
        )
        from bot.handlers.start import about_handler, start_callback_handler, start_handler
        from bot.handlers.statistics import stats_handler

        def register_handlers(*handlers) -> None:
            """Register multiple handlers preserving input order."""
            for handler in handlers:
                app.add_handler(handler)

        def register_callback_handler(callback, pattern: str) -> None:
            """Register callback query handler by callback and pattern."""
            app.add_handler(CallbackQueryHandler(callback, pattern=pattern))
        
        # Register navigation handler FIRST with high priority (group=-1)
        # This ensures it can end conversations before they process the callback
        app.add_handler(navigation_back_callback_handler, group=-1)
        
        # Register command handlers
        register_handlers(
            start_handler,
            help_handler,
            settings_handler,
            family_settings_handler_cmd,
            about_handler,
            categories_handler,
            recent_operations_command_handler,
        )
        
        # Register conversation handlers (must be before callback handlers)
        register_handlers(
            create_family_handler,
            join_family_handler,
            add_expense_handler,
            add_income_handler,
            view_expenses_handler,
            family_expenses_handler,
            stats_handler,
            search_handler,
            quick_expense_handler,
            add_category_handler,
            edit_category_handler,
            delete_category_handler,
            family_rename_handler,
        )
        
        # Register family command handlers
        register_handlers(
            my_families_handler_cmd,
            my_families_handler_callback,
            view_family_handler,
            my_families_leave_handler,
            my_families_confirm_leave_handler,
            my_families_delete_handler,
            my_families_confirm_delete_handler,
        )
        
        # Register pagination and family-expenses callback handlers
        register_callback_handler(pagination_handler, "^page_(prev|next|current)$")
        register_callback_handler(family_pagination_handler, "^family_page_(prev|next|current)$")
        register_callback_handler(family_grouping_handler, "^family_group_(user|category|default)$")
        
        # Detailed report handlers are no longer needed as they are integrated into statistics
        
        # Register categories callback handlers
        register_handlers(show_categories_handler, categories_callback_handler)
        
        # Register help callback handlers
        register_handlers(
            help_callback_handler,
            help_families_handler,
            help_expenses_handler,
            help_stats_handler,
            help_settings_handler,
        )
        
        # Register settings callback handlers
        register_handlers(
            settings_callback_handler,
            settings_currency_handler,
            currency_selection_handler,
            settings_timezone_handler,
            timezone_selection_handler,
            settings_date_format_handler,
            date_format_selection_handler,
            settings_monthly_summary_handler,
            monthly_summary_time_handler,
            settings_expense_notifications_handler,
        )
        
        # Register family settings callback handlers
        register_handlers(
            family_settings_callback_handler,
            family_settings_select_handler,
            family_regenerate_code_handler,
            family_manage_members_handler,
            family_leave_handler,
            confirm_leave_family_handler,
            family_delete_handler,
            confirm_delete_family_handler,
        )

        # Register recent operations callback handler
        app.add_handler(recent_operations_callback_handler)
        
        # Register start callback handler
        app.add_handler(start_callback_handler)
        
        # Navigation handler already registered in group=-1 at the beginning
        
        # Register enhanced error handler
        app.add_error_handler(enhanced_error_handler)
        app.add_error_handler(error_handler)
        
        logger.info("Bot setup completed")
    
    async def start(self) -> None:
        """Start the bot."""
        if not self.application:
            await self.setup()
        
        logger.info("Starting bot...")
        
        # Initialize the bot
        await self.application.initialize()
        await self.application.start()
        
        # Start scheduler for monthly summaries
        from bot.scheduler import start_scheduler
        logger.info("Starting monthly summary scheduler...")
        await start_scheduler(self.application.bot)
        
        # Start polling for updates
        await self.application.updater.start_polling(
            allowed_updates=["message", "callback_query"]
        )
        
        logger.info("Bot is running. Press Ctrl+C to stop.")
    
    async def stop(self) -> None:
        """Stop the bot gracefully."""
        if self.application:
            logger.info("Stopping bot...")
            try:
                # Only stop updater if it's running
                if self.application.updater and self.application.updater.running:
                    await self.application.updater.stop()
                # Only stop application if it's running
                if self.application.running:
                    await self.application.stop()
                # Always try to shutdown
                await self.application.shutdown()
                logger.info("Bot stopped successfully")
            except Exception as e:
                logger.warning(f"Error during bot shutdown: {e}")


__version__ = "0.1.0"
__all__ = ["FamilyFinanceBot", "logger"]

