"""Redis 异步客户端：单例连接池，按需注入。"""
from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings

_pool: ConnectionPool | None = None
_client: Redis | None = None


def init_redis() -> Redis:
    global _pool, _client
    if _client is None:
        _pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=50,
        )
        _client = Redis(connection_pool=_pool)
    return _client


def get_redis() -> Redis:
    """FastAPI 依赖：返回全局 Redis 客户端。"""
    if _client is None:
        return init_redis()
    return _client


async def close_redis() -> None:
    global _client, _pool
    if _client is not None:
        await _client.aclose()
        _client = None
    if _pool is not None:
        await _pool.aclose()
        _pool = None
