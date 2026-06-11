"""日志配置：基于 loguru，输出带 trace_id，并把标准 logging 重定向到 loguru。"""
import logging
import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings
from app.core.context import get_trace_id


class InterceptHandler(logging.Handler):
    """把标准库 logging（uvicorn/sqlalchemy 等）转发给 loguru。"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _patch_trace_id(record: dict) -> None:
    record["extra"].setdefault("trace_id", get_trace_id())


def setup_logging() -> None:
    logger.remove()
    logger.configure(patcher=_patch_trace_id)

    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{extra[trace_id]}</cyan> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format=fmt,
        enqueue=True,
        backtrace=settings.DEBUG,
        diagnose=settings.DEBUG,
    )

    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        level=settings.LOG_LEVEL,
        format=fmt,
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        encoding="utf-8",
        enqueue=True,
    )

    # 接管标准库日志
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        lg = logging.getLogger(name)
        lg.handlers = [InterceptHandler()]
        lg.propagate = False
