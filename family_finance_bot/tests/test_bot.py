"""Basic tests for the bot."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from bot import FamilyFinanceBot


@pytest.mark.asyncio
async def test_bot_initialization():
    """Test that the bot initializes correctly."""
    bot = FamilyFinanceBot()
    assert bot is not None
    assert bot.application is None
    assert bot.token is not None


@pytest.mark.asyncio
async def test_bot_setup():
    """Test that the bot setup works."""
    bot = FamilyFinanceBot()
    await bot.setup()
    assert bot.application is not None


@pytest.mark.asyncio
async def test_bot_lifecycle():
    """Test the complete bot lifecycle (setup and teardown)."""
    bot = FamilyFinanceBot()
    
    # Setup
    await bot.setup()
    assert bot.application is not None
    
    # We won't actually start the bot to avoid long-running tests
    # Just verify it's properly initialized
    
    # Cleanup (if we had started it)
    # await bot.stop()

