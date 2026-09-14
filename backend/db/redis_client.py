import os
from pathlib import Path

from dotenv import load_dotenv
from redis.asyncio import Redis

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

redis_client : Redis | None = None
REDIS_URL = (f"redis://{os.getenv('REDIS_HOST')}:{os.getenv('REDIS_PORT')}/{os.getenv('REDIS_DB')}")
async def init_redis():
    global redis_client
    redis_client = Redis.from_url(
        REDIS_URL,
        decode_responses=True,
    )

    await redis_client.ping()

async def close_redis():
    global redis_client

    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None



def get_redis():
    if redis_client is None:
        raise RuntimeError("Redis 尚未初始化")

    return redis_client
