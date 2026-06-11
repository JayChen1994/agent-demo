"""User 接口层：只做参数接收与调用 service，返回统一响应。"""
from fastapi import APIRouter, Depends, Query

from app.api.deps import DBSession, RedisClient, get_current_user
from app.core.response import success
from app.schemas.user import UserCreate, UserUpdate
from app.services.user import user_service

# 整个用户管理模块需要登录后访问
router = APIRouter(prefix="/users", tags=["用户"], dependencies=[Depends(get_current_user)])


@router.post("", summary="创建用户")
async def create_user(payload: UserCreate, db: DBSession):
    data = await user_service.create_user(db, payload)
    return success(data.model_dump(mode="json"), msg="创建成功")


@router.get("", summary="用户列表")
async def list_users(
    db: DBSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    data = await user_service.list_users(db, page=page, size=size)
    return success([u.model_dump(mode="json") for u in data])


@router.get("/{user_id}", summary="用户详情")
async def get_user(user_id: int, db: DBSession, redis: RedisClient):
    data = await user_service.get_user(db, redis, user_id)
    return success(data.model_dump(mode="json"))


@router.put("/{user_id}", summary="更新用户")
async def update_user(
    user_id: int, payload: UserUpdate, db: DBSession, redis: RedisClient
):
    data = await user_service.update_user(db, redis, user_id, payload)
    return success(data.model_dump(mode="json"), msg="更新成功")


@router.delete("/{user_id}", summary="删除用户")
async def delete_user(user_id: int, db: DBSession, redis: RedisClient):
    await user_service.delete_user(db, redis, user_id)
    return success(msg="删除成功")
