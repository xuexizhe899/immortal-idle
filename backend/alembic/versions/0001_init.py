"""初始存档表

Revision ID: 0001
Revises:
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建存档槽与快照表。"""
    op.create_table(
        "save_slots",
        sa.Column("slot_id", sa.Integer, primary_key=True),
        sa.Column("owner_id", sa.Integer, nullable=False, server_default="1"),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.Column("last_settled_at", sa.Text, nullable=False),
        sa.Column("schema_version", sa.Integer, nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("state_json", sa.Text, nullable=False),
    )
    op.create_table(
        "save_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("slot_id", sa.Integer, nullable=False, index=True),
        sa.Column("schema_version", sa.Integer, nullable=False),
        sa.Column("state_json", sa.Text, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False),
    )


def downgrade() -> None:
    """删除快照表与存档槽表。"""
    op.drop_table("save_snapshots")
    op.drop_table("save_slots")
