"""依赖注入聚合：DB 会话、Redis 客户端、当前登录用户。"""
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizError, ErrorCode
from app.core.security import decode_access_token
from app.crud.user import user_crud
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.user import User

DBSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis)]

# tokenUrl 仅用于 Swagger 的“Authorize”表单
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login/form", auto_error=False)


async def get_current_user(
    db: DBSession, token: Annotated[str | None, Depends(oauth2_scheme)]
) -> User:
    if not token:
        raise BizError("未提供认证凭据", code=ErrorCode.UNAUTHORIZED)
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise BizError("登录已过期", code=ErrorCode.UNAUTHORIZED)
    except jwt.PyJWTError:
        raise BizError("无效的认证凭据", code=ErrorCode.UNAUTHORIZED)

    user_id = payload.get("sub")
    user = await user_crud.get(db, int(user_id)) if user_id else None
    if not user:
        raise BizError("用户不存在", code=ErrorCode.UNAUTHORIZED)
    if not user.is_active:
        raise BizError("账号已被禁用", code=ErrorCode.FORBIDDEN)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
