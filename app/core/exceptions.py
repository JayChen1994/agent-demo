"""自定义异常 + 全局异常处理：所有异常都收敛成统一响应体。"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.response import JSONResult


class BizError(Exception):
    """业务异常：携带业务 code 与 msg。"""

    def __init__(self, msg: str = "业务异常", code: int = -1, data=None) -> None:
        self.code = code
        self.msg = msg
        self.data = data
        super().__init__(msg)


# 预置错误码（可按需扩展）
class ErrorCode:
    OK = 0
    UNKNOWN = -1
    PARAM_ERROR = 4000
    UNAUTHORIZED = 4010
    FORBIDDEN = 4030
    NOT_FOUND = 4040
    DB_ERROR = 5001
    SERVER_ERROR = 5000


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BizError)
    async def _biz_error(request: Request, exc: BizError):
        logger.warning(f"业务异常 code={exc.code} msg={exc.msg}")
        return JSONResult(code=exc.code, msg=exc.msg, data=exc.data)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        errors = [
            {"field": ".".join(str(x) for x in e["loc"]), "msg": e["msg"]}
            for e in exc.errors()
        ]
        logger.warning(f"参数校验失败 {errors}")
        return JSONResult(code=ErrorCode.PARAM_ERROR, msg="参数校验失败", data=errors)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        logger.warning(f"HTTP 异常 status={exc.status_code} detail={exc.detail}")
        return JSONResult(code=exc.status_code, msg=str(exc.detail))

    @app.exception_handler(SQLAlchemyError)
    async def _db_error(request: Request, exc: SQLAlchemyError):
        logger.exception("数据库异常")
        return JSONResult(code=ErrorCode.DB_ERROR, msg="数据库异常")

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception("未捕获异常")
        return JSONResult(code=ErrorCode.SERVER_ERROR, msg="服务器内部错误")
