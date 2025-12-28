from __future__ import annotations

import datetime
import secrets
from dataclasses import dataclass
from typing import Optional, Set

from app.db import repo

FEATURE_WISHLIST = "wishlist"
FEATURE_EXCLUSIONS = "exclusions"
FEATURE_NO_REPEAT = "no_repeat"
FEATURE_BUDGET = "budget"
FEATURE_DEADLINE = "deadline"
FEATURE_REMINDERS = "reminders"


class EntitlementError(RuntimeError):
    pass


@dataclass(frozen=True)
class Entitlements:
    plan: str
    valid_until: Optional[datetime.datetime]
    max_participants: Optional[int]
    features: Set[str]

    def has(self, feature: str) -> bool:
        return feature in self.features


def _is_valid(valid_until: Optional[datetime.datetime]) -> bool:
    if valid_until is None:
        return True
    if valid_until.tzinfo is not None:
        now = datetime.datetime.now(tz=valid_until.tzinfo)
    else:
        now = datetime.datetime.utcnow()
    return valid_until >= now


def for_group(session, group_id: int) -> Entitlements:
    entitlement = repo.get_group_entitlement(session, group_id)
    plan = entitlement.plan.lower() if entitlement else "free"
    if not entitlement or plan != "pro" or not _is_valid(entitlement.valid_until):
        return Entitlements(plan="free", valid_until=None, max_participants=20, features=set())

    return Entitlements(
        plan="pro",
        valid_until=entitlement.valid_until,
        max_participants=None,
        features={
            FEATURE_WISHLIST,
            FEATURE_EXCLUSIONS,
            FEATURE_NO_REPEAT,
            FEATURE_BUDGET,
            FEATURE_DEADLINE,
            FEATURE_REMINDERS,
        },
    )


def create_upgrade_token(session, group_id: int, days_valid: int = 7) -> str:
    token = secrets.token_urlsafe(16)
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=days_valid)
    repo.create_upgrade_session(session, group_id, token, expires_at)
    return token


def activate_upgrade_token(session, token: str) -> bool:
    upgrade_session = repo.get_upgrade_session_by_token(session, token)
    if not upgrade_session or upgrade_session.status != "pending":
        return False
    if upgrade_session.expires_at and upgrade_session.expires_at < datetime.datetime.utcnow():
        return False
    repo.upsert_group_entitlement(session, upgrade_session.group_id, "pro", None)
    repo.activate_upgrade_session(session, upgrade_session)
    return True
