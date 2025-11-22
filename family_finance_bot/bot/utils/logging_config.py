"""Logging configuration for the Family Finance Bot."""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

from config.settings import settings


def setup_logging(
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> None:
    """
    Configure logging for the application.
    
    Args:
        log_file: Path to log file (default: logs/bot.log)
        max_bytes: Maximum size of log file before rotation (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)
    """
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    if log_file is None:
        log_file = str(log_dir / "bot.log")
    
    # Set log level
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        fmt='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(simple_formatter)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(detailed_formatter)
    
    # Error file handler - only errors and above
    error_log_file = str(log_dir / "errors.log")
    error_handler = logging.handlers.RotatingFileHandler(
        filename=error_log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Add handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)
    
    # Reduce verbosity of third-party libraries
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    # If debug mode, set SQLAlchemy to INFO to see queries
    if settings.DEBUG:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    
    logging.info("=" * 60)
    logging.info("Logging configured successfully")
    logging.info(f"Log level: {settings.LOG_LEVEL}")
    logging.info(f"Log file: {log_file}")
    logging.info(f"Error log file: {error_log_file}")
    logging.info(f"Max log file size: {max_bytes / 1024 / 1024:.1f}MB")
    logging.info(f"Backup count: {backup_count}")
    logging.info("=" * 60)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Name of the logger (usually __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


# Request logging decorator
def log_user_action(action_name: str):
    """
    Decorator to log user actions.
    
    Args:
        action_name: Name of the action being logged
        
    Example:
        @log_user_action("add_expense")
        async def add_expense_handler(update, context):
            pass
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            
            # Try to extract user info from args
            user_id = None
            try:
                if len(args) > 0 and hasattr(args[0], 'effective_user'):
                    user_id = args[0].effective_user.id
            except Exception:
                pass
            
            logger.info(
                f"Action: {action_name} | User: {user_id or 'Unknown'} | "
                f"Function: {func.__name__}"
            )
            
            try:
                result = await func(*args, **kwargs)
                logger.debug(f"Action {action_name} completed successfully")
                return result
            except Exception as e:
                logger.error(
                    f"Action {action_name} failed: {str(e)}",
                    exc_info=True
                )
                raise
        
        return wrapper
    return decorator

