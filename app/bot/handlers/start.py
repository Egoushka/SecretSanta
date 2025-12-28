from aiogram import Router, types
from aiogram.filters import CommandStart
from loguru import logger

from app.bot.keyboards import join_keyboard
from app.bot.utils import check_rate_limit, log_handler_exception
from app.db import get_session
from app.services import game_flow

router = Router()


@router.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    if not check_rate_limit(message.from_user.id, "start"):
        await message.answer("You're doing that too often. Please slow down.")
        return

    try:
        if message.chat.type == "private":
            with get_session() as session:
                game_flow.register_private_chat(
                    session,
                    message.from_user.id,
                    message.from_user.username,
                    message.from_user.first_name,
                    message.from_user.last_name,
                )

            await message.answer(
                "Hello! I'm your Secret Santa bot!\n\n"
                "To participate in a Secret Santa game, join a group that uses me, "
                "then click the 'Join Secret Santa!' button.\n\n"
                "You can then see a list of participants with the /list command, "
                "and end the Secret Santa with /end command.\n\n"
                "When everyone clicks the button, an admin can use /end to distribute participants."
            )
            return

        await message.answer(
            "Hello! Please start a private chat with me first (send /start), "
            "then click the button below to join the Secret Santa game.",
            reply_markup=join_keyboard(),
        )
    except Exception as exc:
        log_handler_exception("start", message.from_user.id, message.chat.id, exc)
        await message.answer("Something went wrong. Please try again later.")
