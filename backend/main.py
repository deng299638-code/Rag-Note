from fastapi import FastAPI
from router.user import user_router
from router.health import health_router
from router.notes import note_router
from db.db_config import create_tables
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app:FastAPI):
    await create_tables()
    yield

app = FastAPI(lifespan= lifespan)
app.include_router(user_router)
app.include_router(health_router)
app.include_router(note_router)
