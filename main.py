from __future__ import annotations

import asyncio

import uvloop
from aiogram.types import BotCommand, BotCommandScopeDefault
from loguru import logger

from app.bot import bot, dp
from app.core.config import load_settings
from app.core.logging import setup_logging
from app.db import init_engine


USERS_COMMANDS: dict[str, str] = {
    "start": "start",
    "list": "list participants",
    "end": "end Secret Santa",
    "lock": "lock joining",
    "unlock": "unlock joining",
    "reset": "reset assignments",
    "wish": "wishlist commands",
    "setbudget": "set budget",
    "setdeadline": "set deadline",
    "upgrade": "upgrade plan",
    "activate": "activate upgrade",
}


async def set_default_commands() -> None:
    await bot.set_my_commands(
        [
            BotCommand(command=command, description=description)
            for command, description in USERS_COMMANDS.items()
        ],
        scope=BotCommandScopeDefault(),
    )


async def on_startup() -> None:
    logger.info("bot starting...")

    await set_default_commands()

    bot_info = await bot.get_me()

    logger.info("Name     - {name}", name=bot_info.full_name)
    logger.info("Username - @{username}", username=bot_info.username)
    logger.info("ID       - {id}", id=bot_info.id)

    states: dict[bool | None, str] = {
        True: "Enabled",
        False: "Disabled",
        None: "Unknown (This's not a bot)",
    }

    logger.info("Groups Mode  - {mode}", mode=states[bot_info.can_join_groups])
    logger.info("Privacy Mode - {mode}", mode=states[not bot_info.can_read_all_group_messages])
    logger.info("Inline Mode  - {mode}", mode=states[bot_info.supports_inline_queries])

    logger.info("bot started")


async def on_shutdown() -> None:
    logger.info("bot stopping...")

    await dp.storage.close()
    await dp.fsm.storage.close()

    await bot.session.close()

    logger.info("bot stopped")


async def main() -> None:
    settings = load_settings()
    setup_logging(settings.log_level, settings.log_path)
    init_engine(settings.database_url)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    if not getattr(asyncio, "debug", False):
        uvloop.install()

    asyncio.run(main())
