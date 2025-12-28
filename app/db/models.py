from __future__ import annotations

import enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class GroupStatus(str, enum.Enum):
    OPEN = "open"
    LOCKED = "locked"
    ASSIGNED = "assigned"
    ARCHIVED = "archived"


group_participants = Table(
    "group_participants",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", Integer, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
    UniqueConstraint("user_id", "group_id", name="uq_group_participants_user_group"),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    telegram_username = Column(String, nullable=True)
    display_name = Column(String, nullable=True)
    has_private_chat = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    groups = relationship("Group", secondary=group_participants, back_populates="participants")

    def __repr__(self) -> str:
        return (
            "<User(id={0}, telegram_id={1}, username={2}, has_private_chat={3})>"
        ).format(self.id, self.telegram_id, self.telegram_username, self.has_private_chat)


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    title = Column(String, nullable=True)
    status = Column(
        Enum(GroupStatus, name="group_status"),
        nullable=False,
        default=GroupStatus.OPEN,
        server_default=GroupStatus.OPEN.value,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    created_by_telegram_id = Column(BigInteger, nullable=True)
    last_assignment_seed = Column(Integer, nullable=True)
    budget_amount = Column(Integer, nullable=True)
    currency = Column(String(3), nullable=False, server_default="EUR")
    gift_deadline = Column(Date, nullable=True)

    participants = relationship("User", secondary=group_participants, back_populates="groups")
    assignments = relationship("Assignment", back_populates="group", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Group(id={self.id}, telegram_id={self.telegram_id}, status={self.status})>"


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    giver_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    receiver_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    group = relationship("Group", back_populates="assignments")
    giver = relationship("User", foreign_keys=[giver_user_id])
    receiver = relationship("User", foreign_keys=[receiver_user_id])

    __table_args__ = (
        UniqueConstraint("group_id", "giver_user_id", name="uq_assignments_group_giver"),
    )


class AssignmentHistory(Base):
    __tablename__ = "assignment_history"

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    giver_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    receiver_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WishlistItem(Base):
    __tablename__ = "wishlist_items"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    text = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class GroupEntitlement(Base):
    __tablename__ = "group_entitlements"

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, unique=True)
    plan = Column(String, nullable=False, default="free")
    valid_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UpgradeSession(Base):
    __tablename__ = "upgrade_sessions"

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    token = Column(String, nullable=False, unique=True, index=True)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
