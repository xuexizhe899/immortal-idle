"""FastAPI 应用入口：生命周期内创建数据库引擎与会话工厂。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.craft import router as craft_router
from app.api.disciples import router as disciples_router
from app.api.duty import router as duty_router
from app.api.health import router as health_router
from app.api.recruit import router as recruit_router
from app.api.run import router as run_router
from app.api.saves import router as saves_router
from app.api.settle import router as settle_router
from app.db import create_engine, create_session_factory


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时创建引擎，关闭时释放连接池。"""
    engine = create_engine()
    app.state.session_factory = create_session_factory(engine)
    yield
    await engine.dispose()


app = FastAPI(
    title="Xiuxian Idle API",
    version="0.1.0",
    description="Self-hosted idle roguelite. Single player, multi-slot saves.",
    lifespan=lifespan,
)

app.include_router(health_router, prefix="/api")
app.include_router(saves_router, prefix="/api")
app.include_router(craft_router, prefix="/api")
app.include_router(disciples_router, prefix="/api")
app.include_router(duty_router, prefix="/api")
app.include_router(recruit_router, prefix="/api")
app.include_router(run_router, prefix="/api")
app.include_router(settle_router, prefix="/api")
