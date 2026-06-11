"""统一响应结构：{"code": 0, "msg": "", "data": {}}。"""
from typing import Any, Generic, TypeVar

from fastapi.responses import JSONResponse
from pydantic import BaseModel

T = TypeVar("T")


class ResponseModel(BaseModel, Generic[T]):
    code: int = 0
    msg: str = "success"
    data: T | None = None


def success(data: Any = None, msg: str = "success") -> dict:
    return {"code": 0, "msg": msg, "data": data}


def fail(code: int = -1, msg: str = "error", data: Any = None) -> dict:
    return {"code": code, "msg": msg, "data": data}


class JSONResult(JSONResponse):
    """可直接返回的统一 JSON 响应（HTTP 状态码恒为 200，业务码放 code）。"""

    def __init__(
        self,
        data: Any = None,
        code: int = 0,
        msg: str = "success",
        status_code: int = 200,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            content={"code": code, "msg": msg, "data": data},
            status_code=status_code,
            **kwargs,
        )
