"""应用工厂：组装日志、中间件、异常处理、路由。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.response import success
from app.lifespan import lifespan
from app.middleware.logging import RequestLoggingMiddleware


def create_app() -> FastAPI:
    setup_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # 中间件（注意顺序：CORS 在最外层）
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 全局异常处理
    register_exception_handlers(app)

    # 业务路由
    app.include_router(api_router, prefix=settings.API_PREFIX)

    @app.get("/health", tags=["系统"], summary="健康检查")
    async def health():
        return success({"status": "ok", "env": settings.ENV})

    return app


app = create_app()
