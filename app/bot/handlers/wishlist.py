from __future__ import annotations

import html

from aiogram import Router, types
from aiogram.filters import Command

from app.bot.utils import check_rate_limit, log_handler_exception
from app.db import get_session
from app.db import repo
from app.services import entitlements, game_flow

router = Router()


@router.message(Command("wish"))
async def wish_command_handler(message: types.Message) -> None:
    if not check_rate_limit(message.from_user.id, "wish"):
        await message.answer("You're doing that too often. Please slow down.")
        return

    if message.chat.type != "private":
        await message.answer("Wishlist commands only work in a private chat.")
        return

    tokens = message.text.split()
    if len(tokens) < 2:
        await message.answer("Usage: /wish add <text> | /wish list | /wish clear")
        return

    action = tokens[1].lower()
    group_identifier = None
    text = None

    if action == "add":
        if len(tokens) < 3:
            await message.answer("Usage: /wish add <text>")
            return
        if tokens[2].lstrip("-").isdigit():
            if len(tokens) < 4:
                await message.answer("Usage: /wish add <group_id> <text>")
                return
            group_identifier = tokens[2]
            text = " ".join(tokens[3:])
        else:
            text = " ".join(tokens[2:])
    elif action in {"list", "clear"}:
        if len(tokens) >= 3 and tokens[2].lstrip("-").isdigit():
            group_identifier = tokens[2]
    else:
        await message.answer("Usage: /wish add <text> | /wish list | /wish clear")
        return

    try:
        with get_session() as session:
            group = game_flow.resolve_user_group(session, message.from_user.id, group_identifier)
            if not group:
                user = repo.get_user_by_telegram_id(session, message.from_user.id)
                groups = repo.list_groups_for_user(session, user.id) if user else []
                if not groups:
                    await message.answer("You are not in any Secret Santa groups yet.")
                else:
                    group_lines = [
                        f"- {html.escape(g.title or 'Unnamed group')} (id: {g.telegram_id})"
                        for g in groups
                    ]
                    await message.answer(
                        "You are in multiple groups. Add the group id to the command, e.g.\n"
                        "/wish add -1001234567890 Socks\n"
                        "Groups:\n" + "\n".join(group_lines)
                    )
                return

            game_flow.require_feature(session, group, entitlements.FEATURE_WISHLIST)

            if action == "add":
                if not text:
                    await message.answer("Wishlist item text cannot be empty.")
                    return
                game_flow.add_wishlist_item(session, group, message.from_user.id, text)
                await message.answer("Wishlist item added.")
                return

            if action == "list":
                items = game_flow.list_wishlist_items(session, group, message.from_user.id)
                if not items:
                    await message.answer("Your wishlist is empty.")
                    return
                await message.answer(
                    "Your wishlist:\n"
                    + "\n".join([f"- {html.escape(item)}" for item in items])
                )
                return

            if action == "clear":
                cleared = game_flow.clear_wishlist_items(session, group, message.from_user.id)
                await message.answer(f"Cleared {cleared} wishlist items.")
                return
    except entitlements.EntitlementError:
        await message.answer("Wishlist is available on the Pro plan. Use /upgrade to unlock it.")
    except Exception as exc:
        log_handler_exception("wish", message.from_user.id, message.chat.id, exc)
        await message.answer("Something went wrong. Please try again later.")
