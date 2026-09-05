import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from models.chat import ChatSession
from models.user import Base, User
from services.chat_service import ChatService


@pytest.mark.asyncio
async def test_list_sessions_only_returns_current_user_sessions():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        session.add_all([
            User(username="alice", email="alice@example.com", password="password"),
            User(username="bob", email="bob@example.com", password="password"),
        ])
        await session.flush()

        users = (await session.scalars(select(User).order_by(User.id))).all()
        session.add_all([
            ChatSession(user_id=users[0].id, title="Alice 的会话"),
            ChatSession(user_id=users[1].id, title="Bob 的会话"),
        ])
        await session.commit()

        sessions, total = await ChatService(session).list_sessions(
            user_id=users[0].id,
            page=1,
            page_size=20,
        )

        assert total == 1
        assert [item.title for item in sessions] == ["Alice 的会话"]

    await engine.dispose()
