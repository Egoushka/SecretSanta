from __future__ import annotations

import datetime
import html
from decimal import Decimal, InvalidOperation

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from loguru import logger

from app.bot.keyboards import confirm_end_keyboard
from app.bot.utils import check_rate_limit, is_admin, log_handler_exception
from app.db import GroupStatus, get_session
from app.db import repo
from app.services import entitlements, game_flow
from app.services.assignment import AssignmentError

router = Router()


@router.callback_query(lambda c: c.data == "join")
async def join_callback_handler(query: types.CallbackQuery) -> None:
    if not check_rate_limit(query.from_user.id, "join"):
        await query.answer("You're doing that too often. Please slow down.", show_alert=True)
        return

    try:
        with get_session() as session:
            result = game_flow.join_group(
                session,
                query.from_user.id,
                query.from_user.username,
                query.from_user.first_name,
                query.from_user.last_name,
                query.message.chat.id,
                query.message.chat.title,
            )
            joined = result.added
            user_label = game_flow.format_user_label(result.user)
            group_id = result.group.telegram_id

        if joined:
            await query.answer(result.message, show_alert=True)
            await query.message.bot.send_message(
                group_id,
                f"{user_label} joined the Secret Santa game!",
            )
        else:
            await query.answer(result.message, show_alert=True)
    except Exception as exc:
        log_handler_exception("join", query.from_user.id, query.message.chat.id, exc)
        await query.answer("Error joining the Secret Santa game.", show_alert=True)


@router.message(Command("list"))
async def list_command_handler(message: types.Message) -> None:
    if not check_rate_limit(message.from_user.id, "list"):
        await message.answer("You're doing that too often. Please slow down.")
        return

    try:
        with get_session() as session:
            group = repo.get_group_by_telegram_id(session, message.chat.id)
            if not group:
                await message.answer("This group is not currently active in Secret Santa.")
                return

            participants = game_flow.list_participants(session, group)
            if not participants:
                await message.answer("No participants found in this Secret Santa game.")
                return

            lines = []
            for user in participants:
                label = game_flow.format_user_label(user)
                suffix = " ✓" if user.has_private_chat else ""
                lines.append(f"{label}{suffix}")

            message_text = "Participants in Secret Santa:\n" + "\n".join(lines)
            if any(not user.has_private_chat for user in participants):
                message_text += (
                    "\n\nNote: Users without a ✓ need to start a private chat with the bot by sending /start."
                )

            group_entitlements = entitlements.for_group(session, group.id)
            show_budget = group_entitlements.has(entitlements.FEATURE_BUDGET)
            show_deadline = group_entitlements.has(entitlements.FEATURE_DEADLINE)

            if (show_budget and group.budget_amount is not None) or (show_deadline and group.gift_deadline):
                message_text += "\n\nDetails:"
                if show_budget and group.budget_amount is not None:
                    message_text += f"\nBudget: {game_flow.format_budget(group)}"
                if show_deadline and group.gift_deadline:
                    message_text += f"\nDeadline: {game_flow.format_deadline(group)}"

            await message.answer(message_text)
    except Exception as exc:
        log_handler_exception("list", message.from_user.id, message.chat.id, exc)
        await message.answer("Something went wrong. Please try again later.")


@router.message(Command("end"))
async def end_command_handler(message: types.Message) -> None:
    if not check_rate_limit(message.from_user.id, "end"):
        await message.answer("You're doing that too often. Please slow down.")
        return

    if message.chat.type not in {"group", "supergroup"}:
        await message.answer("This command can only be used in a group chat.")
        return

    if not await is_admin(message.bot, message.chat.id, message.from_user.id):
        await message.answer("Only group admins can end the Secret Santa.")
        return

    try:
        with get_session() as session:
            group = repo.get_group_by_telegram_id(session, message.chat.id)
            if not group:
                await message.answer("This group is not currently active in Secret Santa.")
                return

            if group.status == GroupStatus.ASSIGNED:
                await message.answer("Secret Santa assignments already exist for this group.")
                return
            if group.status == GroupStatus.ARCHIVED:
                await message.answer("This Secret Santa is archived.")
                return

        await message.answer(
            "Are you sure you want to end the Secret Santa and distribute the participants?",
            reply_markup=confirm_end_keyboard(),
        )
    except Exception as exc:
        log_handler_exception("end", message.from_user.id, message.chat.id, exc)
        await message.answer("Something went wrong. Please try again later.")


@router.callback_query(lambda c: c.data == "confirm_end")
async def confirm_end_callback_handler(query: types.CallbackQuery) -> None:
    if not check_rate_limit(query.from_user.id, "confirm_end"):
        await query.answer("You're doing that too often. Please slow down.", show_alert=True)
        return

    if not await is_admin(query.message.bot, query.message.chat.id, query.from_user.id):
        await query.answer("Only group admins can end the Secret Santa.", show_alert=True)
        return

    try:
        with get_session() as session:
            group = repo.get_group_by_telegram_id(session, query.message.chat.id)
            if not group:
                await query.answer("This group is not currently active in Secret Santa.", show_alert=True)
                return

            entitlements_for_group = entitlements.for_group(session, group.id)
            result = game_flow.assign_group(session, group)
            participants = {participant.id: participant for participant in result.participants}

            wishlist_enabled = entitlements_for_group.has(entitlements.FEATURE_WISHLIST)
            wishlists = {}
            if wishlist_enabled:
                for receiver_id in result.assignments.values():
                    wishlists[receiver_id] = game_flow.list_wishlist_items(
                        session, group, receiver_id
                    )

            budget_text = None
            if entitlements_for_group.has(entitlements.FEATURE_BUDGET):
                budget_text = game_flow.format_budget(group)
            deadline_text = None
            if entitlements_for_group.has(entitlements.FEATURE_DEADLINE):
                deadline_text = game_flow.format_deadline(group)

        for giver_id, receiver_id in result.assignments.items():
            giver = participants[giver_id]
            receiver = participants[receiver_id]
            receiver_label = game_flow.format_user_label(receiver)

            message_lines = [
                f"Secret Santa: You're giving a gift to {receiver_label}!",
            ]
            if wishlist_enabled:
                items = wishlists.get(receiver_id, [])
                if items:
                    message_lines.append("")
                    message_lines.append("Wishlist:")
                    message_lines.extend([f"- {html.escape(item)}" for item in items])
            if budget_text:
                message_lines.append("")
                message_lines.append(f"Budget: {budget_text}")
            if deadline_text:
                message_lines.append("")
                message_lines.append(f"Deadline: {deadline_text}")

            try:
                await query.message.bot.send_message(
                    giver.telegram_id,
                    "\n".join(message_lines),
                    parse_mode=ParseMode.HTML,
                )
            except Exception as exc:  # pragma: no cover - network dependent
                logger.bind(user_id=giver.telegram_id).warning(
                    "Failed to send assignment DM: {error}", error=str(exc)
                )

        await query.answer("Secret Santa distribution completed!", show_alert=True)
        await query.message.bot.send_message(
            query.message.chat.id,
            "Secret Santa distribution completed! Check your private messages.",
        )
    except AssignmentError as exc:
        await query.answer(str(exc), show_alert=True)
    except Exception as exc:
        log_handler_exception("confirm_end", query.from_user.id, query.message.chat.id, exc)
        await query.answer("Something went wrong. Please try again later.", show_alert=True)


@router.message(Command("lock"))
async def lock_command_handler(message: types.Message) -> None:
    if not check_rate_limit(message.from_user.id, "lock"):
        await message.answer("You're doing that too often. Please slow down.")
        return

    if not await is_admin(message.bot, message.chat.id, message.from_user.id):
        await message.answer("Only group admins can lock the Secret Santa.")
        return

    try:
        with get_session() as session:
            group = repo.get_group_by_telegram_id(session, message.chat.id)
            if not group:
                await message.answer("This group is not currently active in Secret Santa.")
                return

            if game_flow.lock_group(session, group):
                await message.answer("Secret Santa is now locked.")
            else:
                await message.answer("Secret Santa is already locked or assigned.")
    except Exception as exc:
        log_handler_exception("lock", message.from_user.id, message.chat.id, exc)
        await message.answer("Something went wrong. Please try again later.")


@router.message(Command("unlock"))
async def unlock_command_handler(message: types.Message) -> None:
    if not check_rate_limit(message.from_user.id, "unlock"):
        await message.answer("You're doing that too often. Please slow down.")
        return

    if not await is_admin(message.bot, message.chat.id, message.from_user.id):
        await message.answer("Only group admins can unlock the Secret Santa.")
        return

    try:
        with get_session() as session:
            group = repo.get_group_by_telegram_id(session, message.chat.id)
            if not group:
                await message.answer("This group is not currently active in Secret Santa.")
                return

            if game_flow.unlock_group(session, group):
                await message.answer("Secret Santa is now open.")
            else:
                await message.answer("Secret Santa is not locked.")
    except Exception as exc:
        log_handler_exception("unlock", message.from_user.id, message.chat.id, exc)
        await message.answer("Something went wrong. Please try again later.")


@router.message(Command("reset"))
async def reset_command_handler(message: types.Message) -> None:
    if not check_rate_limit(message.from_user.id, "reset"):
        await message.answer("You're doing that too often. Please slow down.")
        return

    if not await is_admin(message.bot, message.chat.id, message.from_user.id):
        await message.answer("Only group admins can reset the Secret Santa.")
        return

    try:
        with get_session() as session:
            group = repo.get_group_by_telegram_id(session, message.chat.id)
            if not group:
                await message.answer("This group is not currently active in Secret Santa.")
                return
            game_flow.reset_group(session, group)
        await message.answer("Secret Santa has been reset. Participants are kept, assignments cleared.")
    except Exception as exc:
        log_handler_exception("reset", message.from_user.id, message.chat.id, exc)
        await message.answer("Something went wrong. Please try again later.")


@router.message(Command("setbudget"))
async def set_budget_handler(message: types.Message) -> None:
    if not check_rate_limit(message.from_user.id, "setbudget"):
        await message.answer("You're doing that too often. Please slow down.")
        return

    if not await is_admin(message.bot, message.chat.id, message.from_user.id):
        await message.answer("Only group admins can set the budget.")
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        await message.answer("Usage: /setbudget 20 EUR")
        return

    try:
        amount = Decimal(parts[1])
        if amount <= 0 or amount != amount.to_integral_value():
            raise InvalidOperation
        budget_amount = int(amount)
    except (InvalidOperation, ValueError):
        await message.answer("Budget amount should be a positive whole number, e.g. 20")
        return

    currency = parts[2].upper() if len(parts) > 2 else None

    try:
        with get_session() as session:
            group = repo.get_group_by_telegram_id(session, message.chat.id)
            if not group:
                await message.answer("This group is not currently active in Secret Santa.")
                return
            game_flow.require_feature(session, group, entitlements.FEATURE_BUDGET)
            game_flow.set_budget(session, group, budget_amount, currency)
        await message.answer("Budget updated.")
    except entitlements.EntitlementError:
        await message.answer("Budget is available on the Pro plan. Use /upgrade to unlock it.")
    except Exception as exc:
        log_handler_exception("setbudget", message.from_user.id, message.chat.id, exc)
        await message.answer("Something went wrong. Please try again later.")


@router.message(Command("setdeadline"))
async def set_deadline_handler(message: types.Message) -> None:
    if not check_rate_limit(message.from_user.id, "setdeadline"):
        await message.answer("You're doing that too often. Please slow down.")
        return

    if not await is_admin(message.bot, message.chat.id, message.from_user.id):
        await message.answer("Only group admins can set the deadline.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /setdeadline 2026-12-20")
        return

    try:
        deadline = datetime.date.fromisoformat(parts[1])
    except ValueError:
        await message.answer("Deadline should be in YYYY-MM-DD format.")
        return

    try:
        with get_session() as session:
            group = repo.get_group_by_telegram_id(session, message.chat.id)
            if not group:
                await message.answer("This group is not currently active in Secret Santa.")
                return
            game_flow.require_feature(session, group, entitlements.FEATURE_DEADLINE)
            game_flow.set_deadline(session, group, deadline)
        await message.answer("Deadline updated.")
    except entitlements.EntitlementError:
        await message.answer("Deadlines are available on the Pro plan. Use /upgrade to unlock it.")
    except Exception as exc:
        log_handler_exception("setdeadline", message.from_user.id, message.chat.id, exc)
        await message.answer("Something went wrong. Please try again later.")
