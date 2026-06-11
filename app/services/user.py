"""User 业务逻辑层：编排 CRUD 与缓存，处理业务规则与异常。"""
import json

from loguru import logger
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BizError, ErrorCode
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.crud.user import user_crud
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserOut, UserUpdate

_CACHE_PREFIX = "user:"
_CACHE_TTL = 300


class UserService:
    def _cache_key(self, user_id: int) -> str:
        return f"{_CACHE_PREFIX}{user_id}"

    async def create_user(self, db: AsyncSession, data: UserCreate) -> UserOut:
        if await user_crud.get_by_username(db, data.username):
            raise BizError("用户名已存在", code=ErrorCode.PARAM_ERROR)
        values = {
            "username": data.username,
            "email": data.email,
            "password_hash": hash_password(data.password),
        }
        user = await user_crud.create(db, values)
        logger.info(f"创建用户成功 id={user.id} username={user.username}")
        return UserOut.model_validate(user)

    async def authenticate(
        self, db: AsyncSession, username: str, password: str
    ) -> User:
        user = await user_crud.get_by_username(db, username)
        if not user or not verify_password(password, user.password_hash):
            raise BizError("用户名或密码错误", code=ErrorCode.UNAUTHORIZED)
        if not user.is_active:
            raise BizError("账号已被禁用", code=ErrorCode.FORBIDDEN)
        return user

    async def login(self, db: AsyncSession, username: str, password: str) -> Token:
        user = await self.authenticate(db, username, password)
        token = create_access_token(user.id, username=user.username)
        logger.info(f"登录成功 id={user.id} username={user.username}")
        return Token(
            access_token=token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def get_user(
        self, db: AsyncSession, redis: Redis, user_id: int
    ) -> UserOut:
        key = self._cache_key(user_id)
        cached = await redis.get(key)
        if cached:
            logger.debug(f"命中缓存 {key}")
            return UserOut.model_validate(json.loads(cached))

        user = await user_crud.get(db, user_id)
        if not user:
            raise BizError("用户不存在", code=ErrorCode.NOT_FOUND)

        out = UserOut.model_validate(user)
        await redis.set(key, out.model_dump_json(), ex=_CACHE_TTL)
        return out

    async def list_users(
        self, db: AsyncSession, page: int = 1, size: int = 20
    ) -> list[UserOut]:
        offset = (page - 1) * size
        users = await user_crud.list(db, offset=offset, limit=size)
        return [UserOut.model_validate(u) for u in users]

    async def update_user(
        self, db: AsyncSession, redis: Redis, user_id: int, data: UserUpdate
    ) -> UserOut:
        user = await user_crud.get(db, user_id)
        if not user:
            raise BizError("用户不存在", code=ErrorCode.NOT_FOUND)
        user = await user_crud.update(db, user, data)
        await redis.delete(self._cache_key(user_id))
        return UserOut.model_validate(user)

    async def delete_user(
        self, db: AsyncSession, redis: Redis, user_id: int
    ) -> None:
        user = await user_crud.get(db, user_id)
        if not user:
            raise BizError("用户不存在", code=ErrorCode.NOT_FOUND)
        await user_crud.delete(db, user)
        await redis.delete(self._cache_key(user_id))


user_service = UserService()
