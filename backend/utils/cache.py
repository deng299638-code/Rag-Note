import hashlib
import json
import logging

from redis import RedisError

from db.redis_client import get_redis

logger = logging.getLogger(__name__)

async def cache_get_json(key:str):
    try:
        value = await get_redis().get(key)

        if value is None:
            return {}

        return json.loads(value)

    except (RedisError, RuntimeError, json.JSONDecodeError) as exc:
        logger.warning("读取 Redis 缓存失败，key=%s，error=%s", key, exc)
        return {}

async def cache_set_json(key:str,value,ttl:int):
    try:
        await get_redis().set(
            key,
            json.dumps(value, ensure_ascii=False),
            ex=ttl,
        )

    except (RedisError, RuntimeError) as exc:
        logger.warning("写入 Redis 缓存失败，key=%s，error=%s", key, exc)



def normalize_query(query:str):
    return " ".join(query.strip().casefold().split())


def build_rag_cache_key(source:str,user_id:int,query:str,data_version:int,model_version:str,):
    normalized_query = normalize_query(query)

    query_hash = hashlib.sha256(normalized_query.encode("utf-8")).hexdigest()

    return (
        f"rag:{source}:v1:"
        f"{user_id}:"
        f"{data_version}:"
        f"{model_version}:"
        f"{query_hash}"
    )
def rag_version_key(source: str, user_id: int) -> str:
    return f"rag:version:{source}:{user_id}"


async def get_rag_version(source: str, user_id: int) -> int:
    value = await get_redis().get(
        rag_version_key(source, user_id)
    )

    return int(value or 0)

async def bump_rag_version(source: str, user_id: int) -> int:
    return await get_redis().incr(
        rag_version_key(source, user_id)#版本号+1
    )


