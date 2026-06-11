"""User 的 Pydantic 模型：请求入参与响应出参分离。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64, description="用户名")
    email: EmailStr = Field(description="邮箱")
    password: str = Field(min_length=6, max_length=64, description="密码")


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=2, max_length=64)
    email: EmailStr | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LoginRequest(BaseModel):
    username: str = Field(description="用户名")
    password: str = Field(description="密码")


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="过期秒数")
