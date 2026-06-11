"""认证接口：注册、登录（JSON 与 OAuth2 表单两种）、获取当前用户。"""
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, DBSession
from app.core.response import success
from app.schemas.user import LoginRequest, UserCreate
from app.services.user import user_service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", summary="注册")
async def register(payload: UserCreate, db: DBSession):
    data = await user_service.create_user(db, payload)
    return success(data.model_dump(mode="json"), msg="注册成功")


@router.post("/login", summary="登录(JSON)")
async def login(payload: LoginRequest, db: DBSession):
    token = await user_service.login(db, payload.username, payload.password)
    return success(token.model_dump(), msg="登录成功")


@router.post("/login/form", summary="登录(OAuth2 表单, 供 Swagger 授权)")
async def login_form(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DBSession
):
    token = await user_service.login(db, form.username, form.password)
    # OAuth2 规范要求返回 access_token / token_type，供 Swagger 自动识别
    return token.model_dump()


@router.get("/me", summary="当前登录用户")
async def me(current_user: CurrentUser):
    return success(
        {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "is_active": current_user.is_active,
        }
    )
