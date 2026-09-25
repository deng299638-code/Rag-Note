import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from models.note import Note
from models.user import Base, User
from schemas.note_schemas import NoteCreate, NoteUpdate, NoteQueryParams
from services.note_service import NoteService
from collections import defaultdict

import pytest

from rag.note_hybrid_retriever import NoteHybridRetriever
from schemas.note_schemas import NoteCreate, NoteUpdate, NoteQueryParams
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
            params=NoteQueryParams(
                page=1,
                page_size=20,
            ),
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

@pytest.fixture
def note_index_spies(monkeypatch):
    calls = defaultdict(list)

    async def fake_upsert(self, note):
        calls["upsert"].append(note.id)

    async def fake_delete(self, note_id, user_id):
        calls["delete"].append(
            (note_id, user_id)
        )

    async def fake_invalidate(user_id):
        calls["invalidate"].append(user_id)

    monkeypatch.setattr(
        NoteService,
        "_upsert_note_vecto",
        fake_upsert,
    )

    monkeypatch.setattr(
        NoteService,
        "_delete_note_vector",
        fake_delete,
    )

    monkeypatch.setattr(
        NoteHybridRetriever,
        "invalidate_user",
        fake_invalidate,
    )

    return calls

@pytest.mark.asyncio
async def test_create_note_invalidates_bm25(
    session_factory,
    seed_users,
    note_index_spies,
):
    user, _ = seed_users

    async with session_factory() as session:
        service = NoteService(session)

        note = await service.create(
            user_id=user.id,
            payload=NoteCreate(
                title="Milvus",
                content="混合检索",
            ),
        )

    assert note.id in note_index_spies["upsert"]
    assert note_index_spies["invalidate"] == [
        user.id
    ]

@pytest.mark.asyncio
async def test_update_note_invalidates_bm25(
    session_factory,
    seed_users,
    note_index_spies,
):
    user, _ = seed_users

    async with session_factory() as session:
        service = NoteService(session)

        note = await service.create(
            user_id=user.id,
            payload=NoteCreate(
                title="旧标题",
                content="旧内容",
            ),
        )

        # 清除创建笔记产生的调用记录
        note_index_spies["invalidate"].clear()
        note_index_spies["upsert"].clear()

        updated = await service.update(
            note_id=note.id,
            user_id=user.id,
            payload=NoteUpdate(
                title="新标题",
                content="新内容",
            ),
        )

    assert updated.title == "新标题"
    assert updated.content == "新内容"
    assert note_index_spies["upsert"] == [
        note.id
    ]
    assert note_index_spies["invalidate"] == [
        user.id
    ]
@pytest.mark.asyncio
async def test_pin_only_does_not_rebuild_bm25(
    session_factory,
    seed_users,
    note_index_spies,
):
    user, _ = seed_users

    async with session_factory() as session:
        service = NoteService(session)

        note = await service.create(
            user_id=user.id,
            payload=NoteCreate(
                title="标题",
                content="正文",
            ),
        )

        note_index_spies["invalidate"].clear()

        await service.update(
            note_id=note.id,
            user_id=user.id,
            payload=NoteUpdate(
                is_pinned=True,
            ),
        )

    assert note_index_spies["invalidate"] == []

@pytest.mark.asyncio
async def test_delete_note_invalidates_bm25(
    session_factory,
    seed_users,
    note_index_spies,
):
    user, _ = seed_users

    async with session_factory() as session:
        service = NoteService(session)

        note = await service.create(
            user_id=user.id,
            payload=NoteCreate(
                title="待删除",
                content="内容",
            ),
        )

        note_index_spies["invalidate"].clear()
        note_index_spies["delete"].clear()

        await service.delete(
            note_id=note.id,
            user_id=user.id,
        )

    assert note_index_spies["delete"] == [
        (note.id, user.id)
    ]
    assert note_index_spies["invalidate"] == [
        user.id
    ]

@pytest.mark.asyncio
async def test_create_invalidates_even_when_vector_write_fails(
    session_factory,
    seed_users,
    monkeypatch,
):
    user, _ = seed_users
    invalidated_users = []

    async def failing_upsert(self, note):
        raise RuntimeError("Milvus 不可用")

    async def fake_invalidate(user_id):
        invalidated_users.append(user_id)

    monkeypatch.setattr(
        NoteService,
        "_upsert_note_vecto",
        failing_upsert,
    )

    monkeypatch.setattr(
        NoteHybridRetriever,
        "invalidate_user",
        fake_invalidate,
    )

    async with session_factory() as session:
        service = NoteService(session)

        note = await service.create(
            user_id=user.id,
            payload=NoteCreate(
                title="测试",
                content="内容",
            ),
        )

    assert note.id is not None
    assert invalidated_users == [user.id]