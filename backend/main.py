import logging
import warnings

from fastapi import FastAPI

from graph.storage.neo4j_client import verify_neo4j_connection, GraphUnavailableError, \
    initialize_neo4j_schema, close_neo4j_driver
from router.writing import WritingRouter

# langchain-core 1.x 的 Generation.parsed 字段类型标注与 pydantic v2 序列化器不完全一致，
# 结构化输出正常返回 QueryPlan，仅在序列化内部对象时刷出 UserWarning，不影响业务结果。
warnings.filterwarnings(
    "ignore",
    message=".*Pydantic serializer warnings.*Expected `none`.*",
    category=UserWarning,
)
from core.exception_handlers import note_not_found_handler, note_template_not_found_handler, session_not_found_handler
from db.arq_client import init_arq, close_arq
from db.redis_client import init_redis, close_redis
from exceptions.chat_exception import ChatSessionNotFoundError
from exceptions.note_exceptions import NoteNotFoundError
from exceptions.note_template_exceptions import TemplateNotFoundError
from router.agent import agent_router
from router.knowledge import Knowledge_Router
from router.note_template import note_template_router
from router.user import user_router
from router.health import health_router
from router.notes import note_router
from db.db_config import create_tables, create_admin
from contextlib import asynccontextmanager
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app:FastAPI):
    await init_redis()
    await init_arq()
    await create_tables()
    await create_admin()
    try:
        try:
            result = await verify_neo4j_connection()
            await initialize_neo4j_schema()
            logger.info(
                "Neo4j 已连接，连通性检查值=%s",
                result["value"],
            )
        except GraphUnavailableError as exc:
            logger.warning(
                "Neo4j 未就绪，知识图谱功能已禁用：%s",
                exc,
            )
        yield
    finally:
        await close_arq()
        await close_redis()
        await close_neo4j_driver()

app = FastAPI(lifespan= lifespan)
app.include_router(user_router)
app.include_router(health_router)
app.include_router(note_router)
app.include_router(note_template_router)
app.include_router(agent_router)
app.include_router(Knowledge_Router)
app.include_router(WritingRouter)
app.add_exception_handler(NoteNotFoundError,note_not_found_handler)#出现1处理2
app.add_exception_handler(TemplateNotFoundError,note_template_not_found_handler)
app.add_exception_handler(ChatSessionNotFoundError,session_not_found_handler)