from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.bot.handlers import router as handlers_router
from app.core.config import load_settings

settings = load_settings()

bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

dp = Dispatcher()
dp.include_router(handlers_router)
