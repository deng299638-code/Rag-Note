from fastapi import FastAPI

from core.exception_handlers import note_not_found_handler, note_template_not_found_handler
from exceptions.note_exceptions import NoteNotFoundError
from exceptions.note_template_exceptions import TemplateNotFoundError
from router.agent import agent_router
from router.note_template import note_template_router
from router.user import user_router
from router.health import health_router
from router.notes import note_router
from db.db_config import create_tables, create_admin
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app:FastAPI):
    await create_tables()
    await create_admin()
    yield

app = FastAPI(lifespan= lifespan)
app.include_router(user_router)
app.include_router(health_router)
app.include_router(note_router)
app.include_router(note_template_router)
app.include_router(agent_router)
app.add_exception_handler(NoteNotFoundError,note_not_found_handler)#出现1处理2
app.add_exception_handler(TemplateNotFoundError,note_template_not_found_handler)
