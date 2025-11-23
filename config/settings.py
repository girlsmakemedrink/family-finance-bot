"""Configuration settings for the Family Finance Bot."""

import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# Get the base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / ".env")


class Settings:
    """Application settings loaded from environment variables."""

    # Telegram Bot Configuration
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    
    # Database Configuration
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        f"sqlite:///{BASE_DIR}/family_finance.db"
    )
    
    # Application Settings
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Admin Configuration
    ADMIN_USER_IDS: List[int] = [
        int(user_id.strip()) 
        for user_id in os.getenv("ADMIN_USER_IDS", "").split(",") 
        if user_id.strip()
    ]
    
    # Bot Settings
    MAX_RETRIES: int = 3
    TIMEOUT: int = 30
    
    def __init__(self):
        """Validate settings on initialization."""
        self.validate()
    
    def validate(self) -> None:
        """Validate required settings."""
        if not self.BOT_TOKEN:
            raise ValueError(
                "BOT_TOKEN is not set. Please check your .env file."
            )
        
        if not self.DATABASE_URL:
            raise ValueError(
                "DATABASE_URL is not set. Please check your .env file."
            )
    
    @property
    def is_sqlite(self) -> bool:
        """Check if the database is SQLite."""
        return self.DATABASE_URL.startswith("sqlite")
    
    @property
    def is_postgresql(self) -> bool:
        """Check if the database is PostgreSQL."""
        return self.DATABASE_URL.startswith("postgresql")


# Create a global settings instance
settings = Settings()

