"""数据库引擎与会话工厂。

SQLite 走 aiosqlite，每个连接开启 WAL，避免读写互相阻塞。
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "xiuxian.db"


def database_url() -> str:
    """返回数据库连接串，可用 XIUXIAN_DB_URL 覆盖（测试与部署用）。"""
    url = os.getenv("XIUXIAN_DB_URL")
    if url:
        return url
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+aiosqlite:///{DEFAULT_DB_PATH.as_posix()}"


def create_engine(url: str | None = None) -> AsyncEngine:
    """创建异步引擎，并为每个 SQLite 连接启用 WAL 与外键约束。"""
    engine = create_async_engine(url or database_url())

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record) -> None:
        """连接建立时执行的 PRAGMA 设置。"""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    """基于引擎创建异步会话工厂。"""
    return async_sessionmaker(engine, expire_on_commit=False)
