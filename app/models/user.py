"""User ORM 模型。"""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class User(BaseModel):
    __tablename__ = "user"

    username: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, comment="用户名"
    )
    email: Mapped[str] = mapped_column(String(128), unique=True, comment="邮箱")
    password_hash: Mapped[str] = mapped_column(String(128), comment="密码哈希")
    is_active: Mapped[bool] = mapped_column(default=True, comment="是否启用")
