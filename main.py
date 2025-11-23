"""Main entry point for the Family Finance Bot.

This module starts the Telegram bot and handles graceful shutdown.
"""

import asyncio
import signal
import sys
from typing import Optional

from bot import FamilyFinanceBot
from bot.utils.logging_config import setup_logging, get_logger
from config.settings import settings

# Setup logging first
setup_logging()
logger = get_logger(__name__)


class BotRunner:
    """Manages the bot lifecycle with proper startup and shutdown."""

    def __init__(self) -> None:
        """Initialize the bot runner."""
        self.bot: FamilyFinanceBot = FamilyFinanceBot()
        self.shutdown_event: asyncio.Event = asyncio.Event()
    
    def handle_shutdown(self, signum: int, frame) -> None:
        """Handle shutdown signals (SIGINT, SIGTERM)."""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self.shutdown_event.set()
    
    async def run(self) -> None:
        """Run the bot with graceful shutdown support."""
        try:
            # Setup signal handlers for graceful shutdown
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(
                    sig,
                    lambda s=sig: asyncio.create_task(self.shutdown(s))
                )
            
            # Start the bot
            await self.bot.start()
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
        except Exception as e:
            logger.error(f"Error running bot: {e}", exc_info=True)
            raise
        finally:
            await self.bot.stop()
    
    async def shutdown(self, sig: Optional[int] = None) -> None:
        """Perform graceful shutdown."""
        if sig:
            logger.info(f"Received exit signal {sig}...")
        self.shutdown_event.set()


async def main() -> None:
    """Main async function to run the bot."""
    logger.info("=" * 50)
    logger.info("Family Finance Bot Starting")
    logger.info("=" * 50)
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"Log level: {settings.LOG_LEVEL}")
    logger.info(f"Database: {settings.DATABASE_URL}")
    logger.info("=" * 50)
    
    runner = BotRunner()
    
    try:
        await runner.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Bot shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        sys.exit(0)

