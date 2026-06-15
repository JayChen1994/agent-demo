"""应用生命周期：启动时初始化资源（Redis、可选建表），关闭时优雅释放。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app.core.config import settings
from app.db.redis import close_redis, init_redis
from app.db.session import AsyncSessionLocal, close_engine, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"应用启动中... env={settings.ENV}")

    # 初始化 Redis（连接懒建立，此处仅创建客户端）
    init_redis()

    # 注册流水线步骤到 Registry（import 即注册）
    import app.engine.steps  # noqa: F401
    from app.db.base import Base
    from app.models import PipelineTemplate  # noqa: F401  确保 metadata 完整
    from app.services.pipeline import pipeline_service

    # demo 便捷起见：启动时自动建表（生产请改用 Alembic）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # 种入默认流程模板（注册表 -> 默认 DAG）
    async with AsyncSessionLocal() as db:
        await pipeline_service.ensure_default_template(db)
        await db.commit()

    logger.info(f"{settings.APP_NAME} 启动完成 -> http://{settings.HOST}:{settings.PORT}")
    yield

    logger.info("应用关闭中...")
    await close_redis()
    await close_engine()
    logger.info("资源已释放，再见。")
