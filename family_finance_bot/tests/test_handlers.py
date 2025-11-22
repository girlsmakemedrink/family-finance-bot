"""Tests for bot handlers."""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, User as TelegramUser, Message, Chat
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User, Family, FamilyMember, Category, RoleEnum, Expense
from bot.handlers import start, family, expenses


class TestStartHandler:
    """Test /start command handler."""
    
    @pytest.mark.asyncio
    async def test_start_new_user(self, test_session: AsyncSession, mock_settings):
        """Test /start command for a new user."""
        # Create mocks
        update = MagicMock(spec=Update)
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        
        # Mock user
        telegram_user = MagicMock(spec=TelegramUser)
        telegram_user.id = 999888777
        telegram_user.first_name = "New"
        telegram_user.last_name = "User"
        telegram_user.username = "newuser"
        
        update.effective_user = telegram_user
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()
        
        # Patch the database session
        with patch('bot.handlers.start.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = test_session
            
            from bot.handlers.start import start_command
            await start_command(update, context)
            
            # Verify reply was sent
            update.message.reply_text.assert_called()
            call_args = update.message.reply_text.call_args
            assert "Привет" in call_args[0][0] or "Hello" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_start_existing_user(
        self,
        test_session: AsyncSession,
        test_user: User,
        mock_settings
    ):
        """Test /start command for an existing user."""
        update = MagicMock(spec=Update)
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        
        telegram_user = MagicMock(spec=TelegramUser)
        telegram_user.id = test_user.telegram_id
        telegram_user.first_name = "Test"
        telegram_user.last_name = "User"
        telegram_user.username = test_user.username
        
        update.effective_user = telegram_user
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()
        
        with patch('bot.handlers.start.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = test_session
            
            from bot.handlers.start import start_command
            await start_command(update, context)
            
            update.message.reply_text.assert_called()


class TestFamilyHandlers:
    """Test family-related handlers."""
    
    @pytest.mark.asyncio
    async def test_create_family_start(self, test_session: AsyncSession, mock_settings):
        """Test starting family creation."""
        update = MagicMock(spec=Update)
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {}
        
        telegram_user = MagicMock(spec=TelegramUser)
        telegram_user.id = 123456789
        
        update.effective_user = telegram_user
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()
        
        with patch('bot.handlers.family.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = test_session
            
            from bot.handlers.family import create_family_start
            result = await create_family_start(update, context)
            
            # Should ask for family name
            update.message.reply_text.assert_called()
            # Result should be the next state
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_create_family_name(
        self,
        test_session: AsyncSession,
        test_user: User,
        mock_settings
    ):
        """Test receiving family name."""
        update = MagicMock(spec=Update)
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {}
        
        telegram_user = MagicMock(spec=TelegramUser)
        telegram_user.id = test_user.telegram_id
        
        update.effective_user = telegram_user
        update.message = MagicMock(spec=Message)
        update.message.text = "My New Family"
        update.message.reply_text = AsyncMock()
        
        with patch('bot.handlers.family.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = test_session
            
            from bot.handlers.family import create_family_name
            result = await create_family_name(update, context)
            
            # Should confirm family creation
            update.message.reply_text.assert_called()
            call_args = update.message.reply_text.call_args[0][0]
            assert "My New Family" in call_args or "успешно" in call_args
    
    @pytest.mark.asyncio
    async def test_join_family_with_code(
        self,
        test_session: AsyncSession,
        test_user: User,
        test_family: Family,
        mock_settings
    ):
        """Test joining a family with invite code."""
        update = MagicMock(spec=Update)
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {}
        
        telegram_user = MagicMock(spec=TelegramUser)
        telegram_user.id = test_user.telegram_id
        
        update.effective_user = telegram_user
        update.message = MagicMock(spec=Message)
        update.message.text = test_family.invite_code
        update.message.reply_text = AsyncMock()
        
        with patch('bot.handlers.family.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = test_session
            
            from bot.handlers.family import join_family_code
            result = await join_family_code(update, context)
            
            # Should confirm joining
            update.message.reply_text.assert_called()
    
    @pytest.mark.asyncio
    async def test_join_family_invalid_code(
        self,
        test_session: AsyncSession,
        test_user: User,
        mock_settings
    ):
        """Test joining a family with invalid invite code."""
        update = MagicMock(spec=Update)
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {}
        
        telegram_user = MagicMock(spec=TelegramUser)
        telegram_user.id = test_user.telegram_id
        
        update.effective_user = telegram_user
        update.message = MagicMock(spec=Message)
        update.message.text = "INVALIDCODE"
        update.message.reply_text = AsyncMock()
        
        with patch('bot.handlers.family.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = test_session
            
            from bot.handlers.family import join_family_code
            result = await join_family_code(update, context)
            
            # Should show error
            update.message.reply_text.assert_called()
            call_args = update.message.reply_text.call_args[0][0]
            assert "не найдена" in call_args.lower() or "not found" in call_args.lower()


class TestExpenseHandlers:
    """Test expense-related handlers."""
    
    @pytest.mark.asyncio
    async def test_add_expense_start(
        self,
        test_session: AsyncSession,
        test_user: User,
        test_family: Family,
        test_family_member: FamilyMember,
        mock_settings
    ):
        """Test starting expense addition."""
        update = MagicMock(spec=Update)
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {}
        
        telegram_user = MagicMock(spec=TelegramUser)
        telegram_user.id = test_user.telegram_id
        
        update.effective_user = telegram_user
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()
        
        with patch('bot.handlers.expenses.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = test_session
            
            from bot.handlers.expenses import add_expense_start
            result = await add_expense_start(update, context)
            
            # Should ask for family selection or amount
            update.message.reply_text.assert_called()
    
    @pytest.mark.asyncio
    async def test_add_expense_amount_valid(
        self,
        test_session: AsyncSession,
        test_user: User,
        test_family: Family,
        mock_settings
    ):
        """Test entering valid expense amount."""
        update = MagicMock(spec=Update)
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {'family_id': test_family.id}
        
        telegram_user = MagicMock(spec=TelegramUser)
        telegram_user.id = test_user.telegram_id
        
        update.effective_user = telegram_user
        update.message = MagicMock(spec=Message)
        update.message.text = "150.50"
        update.message.reply_text = AsyncMock()
        
        with patch('bot.handlers.expenses.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = test_session
            
            from bot.handlers.expenses import add_expense_amount
            result = await add_expense_amount(update, context)
            
            # Should ask for category
            update.message.reply_text.assert_called()
            assert context.user_data.get('amount') == Decimal("150.50")
    
    @pytest.mark.asyncio
    async def test_add_expense_amount_invalid(
        self,
        test_session: AsyncSession,
        test_user: User,
        mock_settings
    ):
        """Test entering invalid expense amount."""
        update = MagicMock(spec=Update)
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {}
        
        telegram_user = MagicMock(spec=TelegramUser)
        telegram_user.id = test_user.telegram_id
        
        update.effective_user = telegram_user
        update.message = MagicMock(spec=Message)
        update.message.text = "invalid_amount"
        update.message.reply_text = AsyncMock()
        
        with patch('bot.handlers.expenses.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = test_session
            
            from bot.handlers.expenses import add_expense_amount
            result = await add_expense_amount(update, context)
            
            # Should ask again
            update.message.reply_text.assert_called()
            call_args = update.message.reply_text.call_args[0][0]
            assert "ошибка" in call_args.lower() or "error" in call_args.lower() or "некорректно" in call_args.lower()
    
    @pytest.mark.asyncio
    async def test_view_expenses(
        self,
        test_session: AsyncSession,
        test_user: User,
        test_family: Family,
        test_family_member: FamilyMember,
        test_expense: Expense,
        mock_settings
    ):
        """Test viewing expenses."""
        update = MagicMock(spec=Update)
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {}
        
        telegram_user = MagicMock(spec=TelegramUser)
        telegram_user.id = test_user.telegram_id
        
        update.effective_user = telegram_user
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()
        
        with patch('bot.handlers.expenses.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = test_session
            
            from bot.handlers.expenses import view_expenses_start
            result = await view_expenses_start(update, context)
            
            # Should show expenses or ask for family
            update.message.reply_text.assert_called()


class TestStatisticsHandlers:
    """Test statistics handlers."""
    
    @pytest.mark.asyncio
    async def test_stats_handler(
        self,
        test_session: AsyncSession,
        test_user: User,
        test_family: Family,
        test_family_member: FamilyMember,
        test_expense: Expense,
        mock_settings
    ):
        """Test statistics command."""
        update = MagicMock(spec=Update)
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {}
        
        telegram_user = MagicMock(spec=TelegramUser)
        telegram_user.id = test_user.telegram_id
        
        update.effective_user = telegram_user
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()
        
        with patch('bot.handlers.statistics.get_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = test_session
            
            from bot.handlers.statistics import stats_start
            result = await stats_start(update, context)
            
            # Should show statistics or ask for family
            update.message.reply_text.assert_called()


class TestErrorHandling:
    """Test error handling."""
    
    @pytest.mark.asyncio
    async def test_cancel_handler(self):
        """Test cancel command."""
        update = MagicMock(spec=Update)
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {'some_data': 'value'}
        
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()
        
        from bot.handlers.navigation import cancel_handler
        result = await cancel_handler(update, context)
        
        # Should clear user_data and return ConversationHandler.END
        assert result == ConversationHandler.END
        update.message.reply_text.assert_called()
    
    @pytest.mark.asyncio
    async def test_error_handler(self):
        """Test global error handler."""
        update = MagicMock(spec=Update)
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.error = Exception("Test error")
        
        update.effective_message = MagicMock(spec=Message)
        update.effective_message.reply_text = AsyncMock()
        
        from bot.handlers.errors import error_handler
        await error_handler(update, context)
        
        # Should log error (we can't easily test logging, but we ensure no exception is raised)
        assert True


class TestInputValidation:
    """Test input validation."""
    
    def test_validate_amount_valid(self):
        """Test validating valid amounts."""
        from bot.utils.helpers import validate_amount
        
        assert validate_amount("100") == Decimal("100")
        assert validate_amount("100.50") == Decimal("100.50")
        assert validate_amount("0.01") == Decimal("0.01")
        assert validate_amount("999999.99") == Decimal("999999.99")
    
    def test_validate_amount_invalid(self):
        """Test validating invalid amounts."""
        from bot.utils.helpers import validate_amount
        
        assert validate_amount("") is None
        assert validate_amount("abc") is None
        assert validate_amount("-100") is None
        assert validate_amount("0") is None
        assert validate_amount("100.123") is None  # Too many decimal places
    
    def test_validate_description(self):
        """Test validating descriptions."""
        from bot.utils.helpers import validate_description
        
        assert validate_description("Valid description")
        assert validate_description("   spaces   ")  # Should be trimmed
        assert not validate_description("")
        assert not validate_description("   ")  # Only spaces
        assert not validate_description("a" * 501)  # Too long

