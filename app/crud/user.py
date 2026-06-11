"""User 数据访问层：只负责与 DB 交互，不含业务规则。"""
from collections.abc import Sequence

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserUpdate


class CRUDUser:
    async def get(self, db: AsyncSession, user_id: int) -> User | None:
        return await db.get(User, user_id)

    async def get_by_username(self, db: AsyncSession, username: str) -> User | None:
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def list(
        self, db: AsyncSession, offset: int = 0, limit: int = 20
    ) -> Sequence[User]:
        result = await db.execute(
            select(User).order_by(User.id.desc()).offset(offset).limit(limit)
        )
        return result.scalars().all()

    async def create(self, db: AsyncSession, values: dict[str, Any]) -> User:
        user = User(**values)
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user

    async def update(
        self, db: AsyncSession, user: User, data: UserUpdate
    ) -> User:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        await db.flush()
        await db.refresh(user)
        return user

    async def delete(self, db: AsyncSession, user: User) -> None:
        await db.delete(user)
        await db.flush()


user_crud = CRUDUser()
