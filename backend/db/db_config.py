import os
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from models.user import Base

load_dotenv()
ASYNC_DATABSE_URL = (f"mysql+aiomysql://{os.getenv('MYSQL_USER','root')}:"
                     f"{os.getenv('MYSQL_PASSWORD', '')}"
                     f"@{os.getenv('MYSQL_HOST', 'localhost')}:"
                     f"{os.getenv('MYSQL_PORT', '3306')}/"
                     f"{os.getenv('MYSQL_DATABASE', 'learning_db')}"
                     "?charset=utf8mb4")

engine = create_async_engine(
    url=ASYNC_DATABSE_URL,
    echo=True,#打印日志
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db():
    async with SessionLocal() as db:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

async def create_tables():
    from models import note  # noqa: F401
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
