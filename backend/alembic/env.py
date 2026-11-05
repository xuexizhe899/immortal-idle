"""Alembic 迁移环境：用同步连接操作 SQLite，与应用共用同一份表定义。"""

from __future__ import annotations

from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.repositories.tables import metadata

(Path(__file__).resolve().parents[1] / "data").mkdir(exist_ok=True)

config = context.config
target_metadata = metadata


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL，不连接数据库。"""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库直接执行迁移。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
