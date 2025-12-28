from __future__ import annotations

from aiogram.enums import ChatMemberStatus
from loguru import logger

from app.services.rate_limit import rate_limiter


async def is_admin(bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
    except Exception as exc:  # pragma: no cover - network dependent
        logger.bind(chat_id=chat_id, user_id=user_id).warning(
            "Failed to check admin status: {error}", error=str(exc)
        )
        return False
    return member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}


def check_rate_limit(user_id: int, action: str) -> bool:
    key = f"{user_id}:{action}"
    result = rate_limiter.allow(key)
    return result.allowed


def log_handler_exception(action: str, user_id: int | None, chat_id: int | None, error: Exception) -> None:
    logger.bind(action=action, user_id=user_id, chat_id=chat_id).exception(
        "Handler error: {error}", error=str(error)
    )
