import os
from fastapi import HTTPException

from dotenv import load_dotenv
from fastapi import Depends
from sqlalchemy import text, select
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
    pool_size=10,  # 连接池中保持的持久连接数
    max_overflow=20,  # 连接池中允许创建的额外连接数
    echo=False  # 输出sql日志
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
    from models import chat, note, user, note_template  # noqa: F401
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)



async def create_admin():
    from models.user import User
    from utils.security import hash_password
    async with SessionLocal() as db:
        result = await db.scalar(select(User).where(User.username == "admin"))
    if result:
        return
    user = User(
        username = 'admin',
        email = 'admin@qq.com',
        password = hash_password("123456")

    )
    db.add(user)
    await db.commit()




async def test_mysql():
        try:
            async with engine.begin() as con:
                result = await con.execute(text("select 1"))
                return result.scalar()

        except Exception as e:
            raise HTTPException(
                status_code= 400,
                detail= e,
            )
