from __future__ import annotations

import datetime
import random
from dataclasses import dataclass
import html
from typing import Dict, List, Optional

from loguru import logger
from sqlalchemy.exc import IntegrityError

from app.db import Group, GroupStatus, User, repo
from app.services.assignment import AssignmentError, generate_assignments
from app.services.entitlements import (
    FEATURE_BUDGET,
    FEATURE_DEADLINE,
    FEATURE_EXCLUSIONS,
    FEATURE_NO_REPEAT,
    FEATURE_WISHLIST,
    EntitlementError,
    for_group,
)


@dataclass(frozen=True)
class JoinResult:
    added: bool
    message: str
    group: Group
    user: User


@dataclass(frozen=True)
class AssignmentResult:
    assignments: Dict[int, int]
    participants: List[User]
    group: Group


def format_user_label(user: User) -> str:
    if user.telegram_username:
        return f"@{html.escape(user.telegram_username)}"
    if user.display_name:
        return html.escape(user.display_name)
    return f"user-{user.telegram_id}"


def format_user_display(user: User) -> str:
    if user.display_name:
        return html.escape(user.display_name)
    if user.telegram_username:
        return f"@{html.escape(user.telegram_username)}"
    return f"user-{user.telegram_id}"


def ensure_user(
    session,
    telegram_id: int,
    telegram_username: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
) -> User:
    display_name = " ".join(filter(None, [first_name, last_name])) or None
    return repo.upsert_user(session, telegram_id, telegram_username, display_name)


def register_private_chat(
    session,
    telegram_id: int,
    telegram_username: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
) -> User:
    user = ensure_user(session, telegram_id, telegram_username, first_name, last_name)
    user.has_private_chat = True
    return user


def join_group(
    session,
    telegram_user_id: int,
    telegram_username: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
    group_telegram_id: int,
    group_title: Optional[str],
) -> JoinResult:
    user = ensure_user(session, telegram_user_id, telegram_username, first_name, last_name)
    group = repo.get_or_create_group(session, group_telegram_id, telegram_user_id, group_title)

    if group.status in {GroupStatus.ASSIGNED, GroupStatus.ARCHIVED}:
        return JoinResult(False, "This Secret Santa is already finished.", group, user)

    already_member = repo.is_user_in_group(session, user.id, group.id)
    if group.status == GroupStatus.LOCKED and not already_member:
        return JoinResult(False, "This Secret Santa is locked. Ask an admin to unlock it.", group, user)

    if already_member:
        return JoinResult(False, "You are already in this Secret Santa game!", group, user)

    entitlements = for_group(session, group.id)
    if entitlements.max_participants:
        current_count = repo.count_group_participants(session, group.id)
        if current_count >= entitlements.max_participants:
            return JoinResult(
                False,
                "This group is on the free plan and reached the 20 participant limit.",
                group,
                user,
            )

    added = repo.add_user_to_group(session, user.id, group.id)
    if not added:
        return JoinResult(False, "You are already in this Secret Santa game!", group, user)

    return JoinResult(True, "You have joined the Secret Santa game!", group, user)


def list_participants(session, group: Group) -> List[User]:
    return repo.list_group_participants(session, group.id)


def lock_group(session, group: Group) -> bool:
    if group.status == GroupStatus.LOCKED:
        return False
    if group.status in {GroupStatus.ASSIGNED, GroupStatus.ARCHIVED}:
        return False
    repo.update_group_status(session, group, GroupStatus.LOCKED, locked_at=datetime.datetime.utcnow())
    return True


def unlock_group(session, group: Group) -> bool:
    if group.status != GroupStatus.LOCKED:
        return False
    repo.update_group_status(session, group, GroupStatus.OPEN, locked_at=None)
    return True


def reset_group(session, group: Group) -> None:
    repo.archive_assignments(session, group.id)
    repo.clear_assignments(session, group.id)
    repo.update_group_status(session, group, GroupStatus.OPEN, locked_at=None, assigned_at=None)
    repo.update_group_assignment_seed(session, group, None)


def set_budget(session, group: Group, amount: Optional[int], currency: Optional[str]) -> None:
    repo.update_group_budget(session, group, amount, currency)


def set_deadline(session, group: Group, deadline: Optional[datetime.date]) -> None:
    repo.update_group_deadline(session, group, deadline)


def resolve_user_group(session, telegram_user_id: int, group_identifier: Optional[str]) -> Optional[Group]:
    user = repo.get_user_by_telegram_id(session, telegram_user_id)
    if not user:
        return None

    groups = [
        group
        for group in repo.list_groups_for_user(session, user.id)
        if group.status in {GroupStatus.OPEN, GroupStatus.LOCKED, GroupStatus.ASSIGNED}
    ]
    if not groups:
        return None

    if group_identifier:
        group = repo.get_group_by_telegram_id(session, int(group_identifier))
        if group and group in groups:
            return group
        group = repo.get_group_by_id(session, int(group_identifier))
        if group and group in groups:
            return group
        return None

    if len(groups) == 1:
        return groups[0]
    return None


def require_feature(session, group: Group, feature: str) -> None:
    entitlements = for_group(session, group.id)
    if not entitlements.has(feature):
        raise EntitlementError("This feature is available on the Pro plan.")


def build_no_repeat_map(session, group: Group) -> Dict[int, int]:
    history = repo.get_latest_assignment_history(session, group.id)
    if not history:
        return {}

    latest_timestamp = max(item.created_at for item in history)
    latest = [item for item in history if item.created_at == latest_timestamp]
    return {item.giver_user_id: item.receiver_user_id for item in latest}


def assign_group(
    session,
    group: Group,
    seed: Optional[int] = None,
) -> AssignmentResult:
    if group.status == GroupStatus.ASSIGNED:
        raise AssignmentError("Secret Santa has already been assigned for this group.")
    if group.status == GroupStatus.ARCHIVED:
        raise AssignmentError("This Secret Santa is archived.")

    participants = repo.list_group_participants(session, group.id)
    if len(participants) < 2:
        raise AssignmentError("Not enough participants to start Secret Santa.")

    entitlements = for_group(session, group.id)
    if entitlements.max_participants and len(participants) > entitlements.max_participants:
        raise AssignmentError("This group is over the free plan participant limit.")

    if any(not participant.has_private_chat for participant in participants):
        missing = [format_user_display(p) for p in participants if not p.has_private_chat]
        raise AssignmentError(
            "The following participants must start a private chat with the bot: "
            + ", ".join(missing)
        )

    no_repeat_map: Dict[int, int] = {}
    if entitlements.has(FEATURE_NO_REPEAT):
        no_repeat_map = build_no_repeat_map(session, group)

    exclusions: List[tuple[int, int]] = []
    if entitlements.has(FEATURE_EXCLUSIONS):
        exclusions = []

    if seed is None:
        seed = random.randint(1, 2**31 - 1)

    assignments = generate_assignments(
        [participant.id for participant in participants],
        exclusions=exclusions,
        no_repeat_map=no_repeat_map,
        seed=seed,
    )

    try:
        repo.create_assignments(session, group.id, assignments)
    except IntegrityError as exc:
        raise AssignmentError("Secret Santa assignments already exist for this group.") from exc
    repo.update_group_status(
        session,
        group,
        GroupStatus.ASSIGNED,
        locked_at=group.locked_at,
        assigned_at=datetime.datetime.utcnow(),
    )
    repo.update_group_assignment_seed(session, group, seed)
    logger.bind(group_id=group.id, seed=seed).info("Assignments generated")

    return AssignmentResult(assignments=assignments, participants=participants, group=group)


def list_wishlist_items(session, group: Group, user_id: int) -> List[str]:
    require_feature(session, group, FEATURE_WISHLIST)
    items = repo.list_wishlist_items(session, group.id, user_id)
    return [item.text for item in items]


def add_wishlist_item(session, group: Group, user_id: int, text: str) -> None:
    require_feature(session, group, FEATURE_WISHLIST)
    repo.add_wishlist_item(session, group.id, user_id, text)


def clear_wishlist_items(session, group: Group, user_id: int) -> int:
    require_feature(session, group, FEATURE_WISHLIST)
    return repo.clear_wishlist_items(session, group.id, user_id)


def format_budget(group: Group) -> Optional[str]:
    if group.budget_amount is None:
        return None
    currency = (group.currency or "EUR").upper()
    return f"{group.budget_amount} {currency}"


def format_deadline(group: Group) -> Optional[str]:
    if not group.gift_deadline:
        return None
    return group.gift_deadline.isoformat()
