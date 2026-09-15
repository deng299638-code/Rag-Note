from pathlib import Path

from db.arq_client import get_arq_settings, init_arq
from db.redis_client import init_redis, close_redis
from services.knowledge_service import KnowledgeService, UPLOAD_TERMINAL_STATUSES


async def process_knowledge_upload(ctx,user_id : int,task_id : str,temp_dir :str,items:list[dict]):
    service = KnowledgeService(db=None)
    state = await service.get_upload_progress(user_id, task_id)

    if state["status"] in UPLOAD_TERMINAL_STATUSES:
        return

    await service._run_upload_task(user_id, Path(temp_dir), items, state,)

async def worker_startup(ctx):
    await init_redis()

async def worker_shutdown(ctx):
    await close_redis()


class WorkerSettings:
    functions = [process_knowledge_upload]
    redis_settings = get_arq_settings()
    on_startup = staticmethod(lambda  ctx:init_redis())
    on_shutdown = staticmethod(lambda ctx:close_redis())
    job_timeout = 3600