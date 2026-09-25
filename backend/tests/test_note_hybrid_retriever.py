import asyncio

import pytest

import rag.note_hybrid_retriever as target


class FakeStore:
    def __init__(self):
        self.get_calls = 0

    def get(self, **kwargs):
        self.get_calls += 1

        return {
            "documents": [
                "Milvus 混合检索方案",
                "Redis 缓存设计",
            ],
            "metadatas": [
                {
                    "user_id": 7,
                    "note_id": 1,
                    "doc_type": "note",
                    "title": "Milvus",
                },
                {
                    "user_id": 7,
                    "note_id": 2,
                    "doc_type": "note",
                    "title": "Redis",
                },
            ],
        }


class FakeVectorStore:
    def __init__(self, store):
        self.store = store


@pytest.fixture
def fake_dependencies(monkeypatch):
    store = FakeStore()
    versions = {7: 1}

    async def fake_get_version(source, user_id):
        return versions[user_id]

    async def fake_bump_version(source, user_id):
        versions[user_id] += 1
        return versions[user_id]

    monkeypatch.setattr(
        target,
        "get_note_vector_store",
        lambda: FakeVectorStore(store),
    )
    monkeypatch.setattr(
        target,
        "get_rag_version",
        fake_get_version,
    )
    monkeypatch.setattr(
        target,
        "bump_rag_version",
        fake_bump_version,
    )

    target.NoteHybridRetriever._bm25_cache.clear()
    target.NoteHybridRetriever._user_locks.clear()

    return store, versions


@pytest.mark.asyncio
async def test_bm25_cache_hit(fake_dependencies):
    store, _ = fake_dependencies
    retriever = target.NoteHybridRetriever()

    first = await retriever._get_bm25_retriever(7)
    second = await retriever._get_bm25_retriever(7)

    assert first is not None
    assert first is second
    assert store.get_calls == 1


@pytest.mark.asyncio
async def test_bm25_cache_rebuilds_after_invalidation(
    fake_dependencies,
):
    store, versions = fake_dependencies
    retriever = target.NoteHybridRetriever()

    first = await retriever._get_bm25_retriever(7)

    await target.NoteHybridRetriever.invalidate_user(7)

    second = await retriever._get_bm25_retriever(7)

    assert first is not second
    assert store.get_calls == 2
    assert versions[7] == 2


@pytest.mark.asyncio
async def test_concurrent_requests_build_once(
    fake_dependencies,
):
    store, _ = fake_dependencies

    async def load_index():
        retriever = target.NoteHybridRetriever()
        return await retriever._get_bm25_retriever(7)

    results = await asyncio.gather(
        *(load_index() for _ in range(10))
    )

    assert all(result is not None for result in results)
    assert len({id(result) for result in results}) == 1
    assert store.get_calls == 1