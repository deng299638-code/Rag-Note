import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from models.note import Note
from models.user import Base, User
from schemas.note_schemas import NoteCreate, NoteUpdate
from services.note_service import NoteService


@pytest.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    yield factory

    await engine.dispose()


@pytest.fixture
async def seed_users(session_factory):
    async with session_factory() as session:
        user1 = User(
            username="alice",
            email="alice@example.com",
            password="password",
        )

        user2 = User(
            username="bob",
            email="bob@example.com",
            password="password",
        )

        session.add_all([user1, user2])
        await session.commit()

        await session.refresh(user1)
        await session.refresh(user2)

        return user1, user2


@pytest.mark.asyncio
async def test_create_note(session_factory, seed_users):
    user1, _ = seed_users

    async with session_factory() as session:
        service = NoteService(session)

        note = await service.create(
            user_id=user1.id,
            payload=NoteCreate(
                title="FastAPI",
                content="学习依赖注入",
                tags=["Python"],
                category="学习",
            ),
        )

        assert note.id is not None
        assert note.user_id == user1.id
        assert note.title == "FastAPI"
        assert note.tags == ["Python"]


@pytest.mark.asyncio
async def test_list_only_returns_current_user_notes(
    session_factory,
    seed_users,
):
    user1, user2 = seed_users

    async with session_factory() as session:
        service = NoteService(session)

        await service.create(
            user_id=user1.id,
            payload=NoteCreate(
                title="Alice 的笔记",
                content="内容",
            ),
        )

        await service.create(
            user_id=user2.id,
            payload=NoteCreate(
                title="Bob 的笔记",
                content="内容",
            ),
        )

        notes, total = await service.list(
            user_id=user1.id,
            page=1,
            page_size=20,
        )

        assert total == 1
        assert len(notes) == 1
        assert notes[0].title == "Alice 的笔记"


@pytest.mark.asyncio
async def test_user_cannot_access_other_users_note(
    session_factory,
    seed_users,
):
    user1, user2 = seed_users

    async with session_factory() as session:
        service = NoteService(session)

        note = await service.create(
            user_id=user1.id,
            payload=NoteCreate(
                title="私有笔记",
                content="只有 Alice 能看",
            ),
        )

        with pytest.raises(Exception):
            await service.get_owned(
                note_id=note.id,
                user_id=user2.id,
            )


@pytest.mark.asyncio
async def test_update_note(session_factory, seed_users):
    user1, _ = seed_users

    async with session_factory() as session:
        service = NoteService(session)

        note = await service.create(
            user_id=user1.id,
            payload=NoteCreate(
                title="旧标题",
                content="旧内容",
            ),
        )

        updated = await service.update(
            note_id=note.id,
            user_id=user1.id,
            payload=NoteUpdate(
                title="新标题",
                is_pinned=True,
            ),
        )

        assert updated.title == "新标题"
        assert updated.content == "旧内容"
        assert updated.is_pinned is True


@pytest.mark.asyncio
async def test_delete_note(session_factory, seed_users):
    user1, _ = seed_users

    async with session_factory() as session:
        service = NoteService(session)

        note = await service.create(
            user_id=user1.id,
            payload=NoteCreate(
                title="待删除",
                content="内容",
            ),
        )

        await service.delete(
            note_id=note.id,
            user_id=user1.id,
        )

        with pytest.raises(Exception):
            await service.get_owned(
                note_id=note.id,
                user_id=user1.id,
            )