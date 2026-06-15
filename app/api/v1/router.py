"""v1 路由聚合。"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, pipeline, user

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(user.router)
api_router.include_router(pipeline.router)
