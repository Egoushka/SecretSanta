import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_url: str
    log_level: str
    log_path: str


def load_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN")
    database_url = os.getenv("DATABASE_URL")
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_path = os.getenv("LOG_PATH", "logs/telegram_bot.log")

    if not bot_token:
        raise ValueError("BOT_TOKEN is required. Set it in the environment or .env file.")
    if not database_url:
        raise ValueError("DATABASE_URL is required. Set it in the environment or .env file.")

    return Settings(
        bot_token=bot_token,
        database_url=database_url,
        log_level=log_level,
        log_path=log_path,
    )
