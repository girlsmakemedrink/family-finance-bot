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
            # family_export_handler,  # Export moved to statistics section
            # family_export_csv_handler,  # CSV export removed
            # family_export_gdocs_handler,  # Export moved to statistics section
            family_grouping_handler,
            family_pagination_handler,
            # my_export_handler,  # Export moved to statistics section
            # my_export_csv_handler,  # CSV export removed
            # my_export_gdocs_handler,  # Export moved to statistics section
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
        
        # Register navigation handler FIRST with high priority (group=-1)
        # This ensures it can end conversations before they process the callback
        self.application.add_handler(navigation_back_callback_handler, group=-1)
        
        # Register command handlers
        self.application.add_handler(start_handler)
        self.application.add_handler(help_handler)
        self.application.add_handler(settings_handler)
        self.application.add_handler(family_settings_handler_cmd)
        self.application.add_handler(about_handler)
        self.application.add_handler(categories_handler)
        
        # Register conversation handlers (must be before callback handlers)
        self.application.add_handler(create_family_handler)
        self.application.add_handler(join_family_handler)
        self.application.add_handler(add_expense_handler)
        self.application.add_handler(add_income_handler)
        self.application.add_handler(view_expenses_handler)
        self.application.add_handler(family_expenses_handler)
        self.application.add_handler(stats_handler)
        self.application.add_handler(search_handler)
        self.application.add_handler(quick_expense_handler)
        self.application.add_handler(add_category_handler)
        self.application.add_handler(edit_category_handler)
        self.application.add_handler(delete_category_handler)
        self.application.add_handler(family_rename_handler)
        
        # Register family command handlers
        self.application.add_handler(my_families_handler_cmd)
        self.application.add_handler(my_families_handler_callback)
        self.application.add_handler(view_family_handler)
        self.application.add_handler(my_families_leave_handler)
        self.application.add_handler(my_families_confirm_leave_handler)
        self.application.add_handler(my_families_delete_handler)
        self.application.add_handler(my_families_confirm_delete_handler)
        
        # Register pagination handler
        pagination_callback_handler = CallbackQueryHandler(
            pagination_handler,
            pattern="^page_(prev|next|current)$"
        )
        self.application.add_handler(pagination_callback_handler)
        
        # Register family expenses handlers
        family_pagination_callback_handler = CallbackQueryHandler(
            family_pagination_handler,
            pattern="^family_page_(prev|next|current)$"
        )
        self.application.add_handler(family_pagination_callback_handler)
        
        family_grouping_callback_handler = CallbackQueryHandler(
            family_grouping_handler,
            pattern="^family_group_(user|category|default)$"
        )
        self.application.add_handler(family_grouping_callback_handler)
        
        # Export handlers moved to statistics section
        # my_export_callback_handler = CallbackQueryHandler(
        #     my_export_handler,
        #     pattern="^my_export$"
        # )
        # self.application.add_handler(my_export_callback_handler)
        
        # CSV export removed - only HTML export is supported
        # my_export_csv_callback_handler = CallbackQueryHandler(
        #     my_export_csv_handler,
        #     pattern="^my_export_csv$"
        # )
        # self.application.add_handler(my_export_csv_callback_handler)
        
        # Export handlers moved to statistics section
        # my_export_gdocs_callback_handler = CallbackQueryHandler(
        #     my_export_gdocs_handler,
        #     pattern="^my_export_gdocs$"
        # )
        # self.application.add_handler(my_export_gdocs_callback_handler)
        
        # Export handlers moved to statistics section
        # family_export_callback_handler = CallbackQueryHandler(
        #     family_export_handler,
        #     pattern="^family_export$"
        # )
        # self.application.add_handler(family_export_callback_handler)
        
        # CSV export removed - only HTML export is supported
        # family_export_csv_callback_handler = CallbackQueryHandler(
        #     family_export_csv_handler,
        #     pattern="^family_export_csv$"
        # )
        # self.application.add_handler(family_export_csv_callback_handler)
        
        # Export handlers moved to statistics section
        # family_export_gdocs_callback_handler = CallbackQueryHandler(
        #     family_export_gdocs_handler,
        #     pattern="^family_export_gdocs$"
        # )
        # self.application.add_handler(family_export_gdocs_callback_handler)
        
        # Detailed report handlers are no longer needed as they are integrated into statistics
        
        # Register categories callback handlers
        self.application.add_handler(show_categories_handler)
        self.application.add_handler(categories_callback_handler)
        
        # Register help callback handlers
        self.application.add_handler(help_callback_handler)
        self.application.add_handler(help_families_handler)
        self.application.add_handler(help_expenses_handler)
        self.application.add_handler(help_stats_handler)
        self.application.add_handler(help_settings_handler)
        
        # Register settings callback handlers
        self.application.add_handler(settings_callback_handler)
        self.application.add_handler(settings_currency_handler)
        self.application.add_handler(currency_selection_handler)
        self.application.add_handler(settings_timezone_handler)
        self.application.add_handler(timezone_selection_handler)
        self.application.add_handler(settings_date_format_handler)
        self.application.add_handler(date_format_selection_handler)
        self.application.add_handler(settings_monthly_summary_handler)
        self.application.add_handler(monthly_summary_time_handler)
        self.application.add_handler(settings_expense_notifications_handler)
        
        # Register family settings callback handlers
        self.application.add_handler(family_settings_callback_handler)
        self.application.add_handler(family_settings_select_handler)
        self.application.add_handler(family_regenerate_code_handler)
        self.application.add_handler(family_manage_members_handler)
        self.application.add_handler(family_leave_handler)
        self.application.add_handler(confirm_leave_family_handler)
        self.application.add_handler(family_delete_handler)
        self.application.add_handler(confirm_delete_family_handler)
        
        # Register start callback handler
        self.application.add_handler(start_callback_handler)
        
        # Navigation handler already registered in group=-1 at the beginning
        
        # Register enhanced error handler
        self.application.add_error_handler(enhanced_error_handler)
        self.application.add_error_handler(error_handler)
        
        # TODO: Add inline query handlers
        
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

