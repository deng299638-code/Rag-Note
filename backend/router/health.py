from fastapi import APIRouter, HTTPException

from db.redis_client import get_redis

health_router = APIRouter(prefix="/health")

@health_router.get("/redis")
async def redis_health():
    try:
        await get_redis().ping()

    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Redis 不可用",
        )

    return {
        "status": "ok",
        "redis": "up",
    }


