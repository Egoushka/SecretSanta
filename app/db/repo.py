from __future__ import annotations

import datetime
from typing import Iterable, List, Optional

from sqlalchemy import and_, delete, func, select
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    Assignment,
    AssignmentHistory,
    Group,
    GroupEntitlement,
    GroupStatus,
    UpgradeSession,
    User,
    WishlistItem,
    group_participants,
)


def get_user_by_telegram_id(session, telegram_id: int) -> Optional[User]:
    return session.scalar(select(User).where(User.telegram_id == telegram_id))


def upsert_user(
    session,
    telegram_id: int,
    telegram_username: Optional[str],
    display_name: Optional[str],
) -> User:
    user = get_user_by_telegram_id(session, telegram_id)
    if user:
        user.telegram_username = telegram_username
        user.display_name = display_name
        return user

    user = User(
        telegram_id=telegram_id,
        telegram_username=telegram_username,
        display_name=display_name,
    )
    session.add(user)
    session.flush()
    return user


def mark_user_private_chat(session, telegram_id: int) -> Optional[User]:
    user = get_user_by_telegram_id(session, telegram_id)
    if not user:
        return None
    user.has_private_chat = True
    return user


def get_group_by_telegram_id(session, telegram_id: int) -> Optional[Group]:
    return session.scalar(select(Group).where(Group.telegram_id == telegram_id))


def get_group_by_id(session, group_id: int) -> Optional[Group]:
    return session.scalar(select(Group).where(Group.id == group_id))


def create_group(
    session,
    telegram_id: int,
    created_by_telegram_id: Optional[int],
    title: Optional[str],
) -> Group:
    group = Group(
        telegram_id=telegram_id,
        created_by_telegram_id=created_by_telegram_id,
        title=title,
    )
    session.add(group)
    session.flush()
    return group


def get_or_create_group(
    session,
    telegram_id: int,
    created_by_telegram_id: Optional[int],
    title: Optional[str],
) -> Group:
    group = get_group_by_telegram_id(session, telegram_id)
    if group:
        if title and group.title != title:
            group.title = title
        if created_by_telegram_id and group.created_by_telegram_id is None:
            group.created_by_telegram_id = created_by_telegram_id
        return group
    return create_group(session, telegram_id, created_by_telegram_id, title)


def count_group_participants(session, group_id: int) -> int:
    return session.scalar(
        select(func.count()).select_from(group_participants).where(group_participants.c.group_id == group_id)
    )


def is_user_in_group(session, user_id: int, group_id: int) -> bool:
    return session.scalar(
        select(func.count())
        .select_from(group_participants)
        .where(
            and_(group_participants.c.user_id == user_id, group_participants.c.group_id == group_id)
        )
    ) > 0


def add_user_to_group(session, user_id: int, group_id: int) -> bool:
    if is_user_in_group(session, user_id, group_id):
        return False
    try:
        session.execute(group_participants.insert().values(user_id=user_id, group_id=group_id))
        return True
    except IntegrityError:
        return False


def list_group_participants(session, group_id: int) -> List[User]:
    group = session.scalar(select(Group).where(Group.id == group_id))
    return list(group.participants) if group else []


def list_groups_for_user(session, user_id: int) -> List[Group]:
    user = session.scalar(select(User).where(User.id == user_id))
    return list(user.groups) if user else []


def update_group_status(
    session,
    group: Group,
    status: GroupStatus,
    locked_at: Optional[datetime.datetime] = None,
    assigned_at: Optional[datetime.datetime] = None,
) -> None:
    group.status = status
    group.locked_at = locked_at
    group.assigned_at = assigned_at


def update_group_budget(
    session,
    group: Group,
    budget_amount: Optional[int],
    currency: Optional[str],
) -> None:
    group.budget_amount = budget_amount
    if currency:
        group.currency = currency


def update_group_deadline(session, group: Group, gift_deadline: Optional[datetime.date]) -> None:
    group.gift_deadline = gift_deadline


def update_group_assignment_seed(session, group: Group, seed: Optional[int]) -> None:
    group.last_assignment_seed = seed


def create_assignments(session, group_id: int, assignments: dict[int, int]) -> None:
    rows = [
        Assignment(group_id=group_id, giver_user_id=giver_id, receiver_user_id=receiver_id)
        for giver_id, receiver_id in assignments.items()
    ]
    session.add_all(rows)


def list_assignments(session, group_id: int) -> List[Assignment]:
    return list(session.scalars(select(Assignment).where(Assignment.group_id == group_id)).all())


def archive_assignments(session, group_id: int) -> int:
    assignments = list_assignments(session, group_id)
    if not assignments:
        return 0
    history_rows = [
        AssignmentHistory(
            group_id=group_id,
            giver_user_id=assignment.giver_user_id,
            receiver_user_id=assignment.receiver_user_id,
        )
        for assignment in assignments
    ]
    session.add_all(history_rows)
    return len(history_rows)


def clear_assignments(session, group_id: int) -> None:
    session.execute(delete(Assignment).where(Assignment.group_id == group_id))


def get_latest_assignment_history(session, group_id: int) -> List[AssignmentHistory]:
    return list(
        session.scalars(
            select(AssignmentHistory)
            .where(AssignmentHistory.group_id == group_id)
            .order_by(AssignmentHistory.created_at.desc())
        ).all()
    )


def list_wishlist_items(session, group_id: int, user_id: int) -> List[WishlistItem]:
    return list(
        session.scalars(
            select(WishlistItem).where(
                and_(WishlistItem.group_id == group_id, WishlistItem.user_id == user_id)
            )
        ).all()
    )


def add_wishlist_item(session, group_id: int, user_id: int, text: str) -> WishlistItem:
    item = WishlistItem(group_id=group_id, user_id=user_id, text=text)
    session.add(item)
    session.flush()
    return item


def clear_wishlist_items(session, group_id: int, user_id: int) -> int:
    result = session.execute(
        delete(WishlistItem).where(
            and_(WishlistItem.group_id == group_id, WishlistItem.user_id == user_id)
        )
    )
    return result.rowcount or 0


def get_group_entitlement(session, group_id: int) -> Optional[GroupEntitlement]:
    return session.scalar(select(GroupEntitlement).where(GroupEntitlement.group_id == group_id))


def upsert_group_entitlement(
    session,
    group_id: int,
    plan: str,
    valid_until: Optional[datetime.datetime],
) -> GroupEntitlement:
    entitlement = get_group_entitlement(session, group_id)
    if entitlement:
        entitlement.plan = plan
        entitlement.valid_until = valid_until
        return entitlement
    entitlement = GroupEntitlement(group_id=group_id, plan=plan, valid_until=valid_until)
    session.add(entitlement)
    session.flush()
    return entitlement


def create_upgrade_session(
    session,
    group_id: int,
    token: str,
    expires_at: Optional[datetime.datetime],
) -> UpgradeSession:
    upgrade_session = UpgradeSession(
        group_id=group_id,
        token=token,
        status="pending",
        expires_at=expires_at,
    )
    session.add(upgrade_session)
    session.flush()
    return upgrade_session


def get_upgrade_session_by_token(session, token: str) -> Optional[UpgradeSession]:
    return session.scalar(select(UpgradeSession).where(UpgradeSession.token == token))


def activate_upgrade_session(session, upgrade_session: UpgradeSession) -> None:
    upgrade_session.status = "activated"
