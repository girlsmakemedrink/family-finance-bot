"""Navigation system for tracking user's navigation history."""

from typing import Optional, List
from telegram import InlineKeyboardButton


class NavigationManager:
    """Manages navigation history for users."""
    
    MAX_HISTORY_SIZE = 10  # Максимальное количество шагов в истории
    
    @staticmethod
    def push_state(context, state: str) -> None:
        """Add a new state to navigation history.
        
        Args:
            context: Telegram context object
            state: State identifier (e.g., 'categories', 'expenses', etc.)
        """
        if 'nav_history' not in context.user_data:
            context.user_data['nav_history'] = []
        
        history: List[str] = context.user_data['nav_history']
        
        # Avoid duplicating the last state
        if history and history[-1] == state:
            return
        
        history.append(state)
        
        # Limit history size
        if len(history) > NavigationManager.MAX_HISTORY_SIZE:
            history.pop(0)
    
    @staticmethod
    def pop_state(context) -> Optional[str]:
        """Remove and return the last state from history.
        
        Args:
            context: Telegram context object
            
        Returns:
            Previous state or None if history is empty
        """
        if 'nav_history' not in context.user_data:
            return None
        
        history: List[str] = context.user_data['nav_history']
        
        if not history:
            return None
        
        # Remove current state
        if history:
            history.pop()
        
        # Return previous state (but don't remove it)
        return history[-1] if history else None
    
    @staticmethod
    def get_previous_state(context) -> Optional[str]:
        """Get the previous state without removing it.
        
        Args:
            context: Telegram context object
            
        Returns:
            Previous state or None if history is empty or has only one item
        """
        if 'nav_history' not in context.user_data:
            return None
        
        history: List[str] = context.user_data['nav_history']
        
        # Return previous state (second from the end)
        return history[-2] if len(history) > 1 else None
    
    @staticmethod
    def clear_history(context) -> None:
        """Clear navigation history.
        
        Args:
            context: Telegram context object
        """
        context.user_data['nav_history'] = []
    
    @staticmethod
    def get_navigation_buttons(context, current_state: str = None) -> List[List[InlineKeyboardButton]]:
        """Generate navigation buttons based on history.
        
        Args:
            context: Telegram context object
            current_state: Current state identifier (to push to history if needed)
            
        Returns:
            List of button rows for navigation
        """
        buttons = []
        
        # Push current state if provided
        if current_state:
            NavigationManager.push_state(context, current_state)
        
        previous = NavigationManager.get_previous_state(context)
        
        # Create button row
        row = []
        
        # Add "Back" button if there's a previous state
        if previous:
            row.append(
                InlineKeyboardButton("◀️ Назад", callback_data=f"nav_back")
            )
        
        # Always add "Main Menu" button
        row.append(
            InlineKeyboardButton("🏠 Главное меню", callback_data="start")
        )
        
        if row:
            buttons.append(row)
        
        return buttons


# State constants
STATE_START = "start"
STATE_CATEGORIES = "categories"
STATE_EXPENSES = "expenses"
STATE_MY_EXPENSES = "my_expenses"
STATE_FAMILY_EXPENSES = "family_expenses"
STATE_STATISTICS = "statistics"
STATE_SETTINGS = "settings"
STATE_FAMILY_SETTINGS = "family_settings"
STATE_MY_FAMILIES = "my_families"
STATE_HELP = "help"

