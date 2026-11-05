"""SQLAlchemy 表定义。

只用 Core Table 不建 ORM 实体：存档是一整块 JSON，不需要对象关系映射。
"""

from __future__ import annotations

from sqlalchemy import Column, Integer, MetaData, Table, Text

metadata = MetaData()

save_slots = Table(
    "save_slots",
    metadata,
    Column("slot_id", Integer, primary_key=True),
    Column("owner_id", Integer, nullable=False, default=1),
    Column("name", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    Column("last_settled_at", Text, nullable=False),
    Column("schema_version", Integer, nullable=False),
    Column("revision", Integer, nullable=False),
    Column("state_json", Text, nullable=False),
)

save_snapshots = Table(
    "save_snapshots",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("slot_id", Integer, nullable=False, index=True),
    Column("schema_version", Integer, nullable=False),
    Column("state_json", Text, nullable=False),
    Column("reason", Text, nullable=False),
    Column("created_at", Text, nullable=False),
)
