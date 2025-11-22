"""Rate limiting for bot commands."""

import logging
import time
from collections import defaultdict
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple in-memory rate limiter for bot commands."""
    
    def __init__(
        self,
        max_requests: int = 10,
        time_window: int = 60
    ):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed in time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: Dict[int, list] = defaultdict(list)
    
    def is_allowed(self, user_id: int) -> Tuple[bool, int]:
        """
        Check if user is allowed to make a request.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Tuple of (is_allowed, seconds_until_reset)
        """
        now = time.time()
        user_requests = self.requests[user_id]
        
        # Remove old requests outside the time window
        user_requests[:] = [
            req_time for req_time in user_requests
            if now - req_time < self.time_window
        ]
        
        # Check if user has exceeded the limit
        if len(user_requests) >= self.max_requests:
            oldest_request = min(user_requests)
            seconds_until_reset = int(self.time_window - (now - oldest_request)) + 1
            logger.warning(
                f"Rate limit exceeded for user {user_id}. "
                f"Reset in {seconds_until_reset}s"
            )
            return False, seconds_until_reset
        
        # Add current request
        user_requests.append(now)
        return True, 0
    
    def reset_user(self, user_id: int) -> None:
        """
        Reset rate limit for a user.
        
        Args:
            user_id: Telegram user ID
        """
        if user_id in self.requests:
            del self.requests[user_id]
            logger.info(f"Rate limit reset for user {user_id}")
    
    def cleanup_old_entries(self) -> None:
        """Remove entries for users who haven't made requests recently."""
        now = time.time()
        users_to_remove = []
        
        for user_id, requests in self.requests.items():
            if not requests or (now - max(requests)) > self.time_window * 2:
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            del self.requests[user_id]
        
        if users_to_remove:
            logger.debug(f"Cleaned up rate limiter entries for {len(users_to_remove)} users")


# Global rate limiter instance
_rate_limiter = RateLimiter(max_requests=10, time_window=60)


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    return _rate_limiter


def rate_limit_decorator(func):
    """
    Decorator to add rate limiting to command handlers.
    
    Usage:
        @rate_limit_decorator
        async def my_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            pass
    """
    async def wrapper(update, context):
        user_id = update.effective_user.id
        limiter = get_rate_limiter()
        
        is_allowed, wait_time = limiter.is_allowed(user_id)
        
        if not is_allowed:
            await update.message.reply_text(
                f"⏳ Вы отправляете команды слишком часто. "
                f"Пожалуйста, подождите {wait_time} секунд."
            )
            return
        
        return await func(update, context)
    
    return wrapper

