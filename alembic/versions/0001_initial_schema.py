"""Initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2025-01-01 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_username", sa.String(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("has_private_chat", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("open", "locked", "assigned", "archived", name="group_status"),
            nullable=False,
            server_default="open",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("last_assignment_seed", sa.Integer(), nullable=True),
        sa.Column("budget_amount", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="EUR"),
        sa.Column("gift_deadline", sa.Date(), nullable=True),
    )
    op.create_index("ix_groups_telegram_id", "groups", ["telegram_id"], unique=True)

    op.create_table(
        "group_participants",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "group_id"),
        sa.UniqueConstraint("user_id", "group_id", name="uq_group_participants_user_group"),
    )

    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("giver_user_id", sa.Integer(), nullable=False),
        sa.Column("receiver_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["giver_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["receiver_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("group_id", "giver_user_id", name="uq_assignments_group_giver"),
    )

    op.create_table(
        "assignment_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("giver_user_id", sa.Integer(), nullable=False),
        sa.Column("receiver_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["giver_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["receiver_user_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "wishlist_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "group_entitlements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("plan", sa.String(), nullable=False, server_default="free"),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("group_id", name="uq_group_entitlements_group"),
    )

    op.create_table(
        "upgrade_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token", name="uq_upgrade_sessions_token"),
    )
    op.create_index("ix_upgrade_sessions_token", "upgrade_sessions", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_upgrade_sessions_token", table_name="upgrade_sessions")
    op.drop_table("upgrade_sessions")
    op.drop_table("group_entitlements")
    op.drop_table("wishlist_items")
    op.drop_table("assignment_history")
    op.drop_table("assignments")
    op.drop_table("group_participants")
    op.drop_index("ix_groups_telegram_id", table_name="groups")
    op.drop_table("groups")
    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS group_status")
