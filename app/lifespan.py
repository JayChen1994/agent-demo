"""应用生命周期：启动时初始化资源（Redis、可选建表），关闭时优雅释放。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app.core.config import settings
from app.db.redis import close_redis, init_redis
from app.db.session import close_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"应用启动中... env={settings.ENV}")

    # 初始化 Redis（连接懒建立，此处仅创建客户端）
    init_redis()

    # 表结构由 Alembic 管理：alembic upgrade head
    logger.info(f"{settings.APP_NAME} 启动完成 -> http://{settings.HOST}:{settings.PORT}")
    yield

    logger.info("应用关闭中...")
    await close_redis()
    await close_engine()
    logger.info("资源已释放，再见。")
