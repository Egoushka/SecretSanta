from __future__ import annotations

import datetime

from aiogram import Router, types
from aiogram.filters import Command

from app.bot.utils import check_rate_limit, is_admin, log_handler_exception
from app.db import get_session
from app.db import repo
from app.services import entitlements

router = Router()


@router.message(Command("upgrade"))
async def upgrade_command_handler(message: types.Message) -> None:
    if not check_rate_limit(message.from_user.id, "upgrade"):
        await message.answer("You're doing that too often. Please slow down.")
        return

    if message.chat.type not in {"group", "supergroup"}:
        await message.answer("Run /upgrade from the group you want to upgrade.")
        return

    if not await is_admin(message.bot, message.chat.id, message.from_user.id):
        await message.answer("Only group admins can upgrade the Secret Santa.")
        return

    try:
        with get_session() as session:
            group = repo.get_or_create_group(
                session,
                message.chat.id,
                message.from_user.id,
                message.chat.title,
            )

            current = entitlements.for_group(session, group.id)
            if current.plan == "pro":
                await message.answer("This group is already on the Pro plan.")
                return

            token = entitlements.create_upgrade_token(session, group.id, days_valid=7)

        await message.answer(
            "Upgrade to Pro to unlock wishlists, exclusions, no-repeat, budgets, and deadlines.\n\n"
            f"To activate manually, use this command:\n/activate {token}\n"
            "(This token expires in 7 days.)"
        )
    except Exception as exc:
        log_handler_exception("upgrade", message.from_user.id, message.chat.id, exc)
        await message.answer("Something went wrong. Please try again later.")


@router.message(Command("activate"))
async def activate_command_handler(message: types.Message) -> None:
    if not check_rate_limit(message.from_user.id, "activate"):
        await message.answer("You're doing that too often. Please slow down.")
        return

    tokens = message.text.split(maxsplit=1)
    if len(tokens) < 2:
        await message.answer("Usage: /activate <token>")
        return

    token = tokens[1].strip()

    try:
        with get_session() as session:
            upgrade_session = repo.get_upgrade_session_by_token(session, token)
            if not upgrade_session:
                await message.answer("Invalid upgrade token.")
                return

            if upgrade_session.status != "pending":
                await message.answer("This upgrade token has already been used.")
                return

            if upgrade_session.expires_at and upgrade_session.expires_at < datetime.datetime.utcnow():
                await message.answer("This upgrade token has expired.")
                return

            if not await is_admin(message.bot, upgrade_session.group_id, message.from_user.id):
                await message.answer("Only group admins can activate this upgrade.")
                return

            if entitlements.activate_upgrade_token(session, token):
                await message.answer("Pro activated for this group. Enjoy the new features!")
                return

        await message.answer("Unable to activate this upgrade token.")
    except Exception as exc:
        log_handler_exception("activate", message.from_user.id, message.chat.id, exc)
        await message.answer("Something went wrong. Please try again later.")
