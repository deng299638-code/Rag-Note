import os
from arq import ArqRedis, create_pool
from arq.connections import RedisSettings

arq_client : ArqRedis | None = None

def get_arq_settings():
    return RedisSettings(
        host = os.getenv("REDIS_HOST","localhost"),
        port = int(os.getenv("REDIS_PORT","6379")),
        database=int(os.getenv("REDIS_DB","0"))
    )

async def init_arq():
    global arq_client
    arq_client = await create_pool(get_arq_settings())

async def close_arq():
    global arq_client

    if arq_client is not None:
        await arq_client.aclose()
        arq_client = None


def get_arq():
    if arq_client is None:
        raise RuntimeError("ARQ 尚未初始化")
    return arq_client
