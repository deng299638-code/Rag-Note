import fnmatch
import json
from unittest.mock import AsyncMock

import pytest
from langchain_core.documents import Document

import services.knowledge_service as service_module
from db.redis_client import get_redis
from services.knowledge_service import KnowledgeService


class FakeRedis:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ex=None):
        self.values[key] = value

    async def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)

    async def scan_iter(self, match):
        for key in list(self.values):
            if fnmatch.fnmatch(key, match):
                yield key


@pytest.fixture
def redis(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(
        service_module,
        "get_redis",
        lambda: fake_redis,
    )
    return fake_redis


@pytest.fixture
def service():
    return KnowledgeService(db=None)


@pytest.mark.asyncio
async def test_detail_cache_miss_writes_cache(
    service,
    redis,
):
    service._get_user_documents = AsyncMock(
        return_value={
            "ids": ["chunk-1"],
            "documents": ["PDF 内容"],
            "metadatas": [
                {
                    "original_filename": "demo.pdf",
                    "md5": "a" * 32,
                    "image_paths": ["p0_i0.png"],
                    "page": 1,
                    "chunk_index": 0,
                }
            ],
        }
    )

    detail = await service.get_document(
        filename="demo.pdf",
        user_id=1,
    )

    cache_key = service._document_cache_key(
        1,
        "demo.pdf",
    )

    assert detail["images"] == [
        f"/knowledge/image/{'a' * 32}/p0_i0.png"
    ]

    assert cache_key in redis.values
    assert json.loads(redis.values[cache_key]) == detail
    service._get_user_documents.assert_awaited_once()


@pytest.mark.asyncio
async def test_detail_cache_hit_skips_milvus(
    service,
    redis,
):
    cache_key = service._document_cache_key(
        1,
        "demo.pdf",
    )

    cached_detail = {
        "filename": "demo.pdf",
        "user_id": "1",
        "content": "缓存内容",
        "images": [],
        "chunks": [],
    }

    redis.values[cache_key] = json.dumps(
        cached_detail,
        ensure_ascii=False,
    )

    service._get_user_documents = AsyncMock(
        side_effect=AssertionError(
            "命中缓存时不应该查询 Milvus"
        )
    )

    result = await service.get_document(
        filename="demo.pdf",
        user_id=1,
    )

    assert result == cached_detail


@pytest.mark.asyncio
async def test_delete_single_detail_cache(
    service,
    redis,
):
    cache_key = service._document_cache_key(
        1,
        "demo.pdf",
    )

    redis.values[cache_key] = "{}"

    await service._delete_document_cache(
        user_id=1,
        filename="demo.pdf",
    )

    assert cache_key not in redis.values


@pytest.mark.asyncio
async def test_delete_user_detail_caches(
    service,
    redis,
):
    redis.values.update(
        {
            "knowledge:detail:1:a": "{}",
            "knowledge:detail:1:b": "{}",
            "knowledge:detail:2:c": "{}",
        }
    )

    await service._delete_user_document_cache(1)

    assert "knowledge:detail:1:a" not in redis.values
    assert "knowledge:detail:1:b" not in redis.values
    assert "knowledge:detail:2:c" in redis.values

# tests/test_redis_connection.py

import pytest

from db.redis_client import (
    close_redis,
    get_redis,
    init_redis,
)


@pytest.mark.asyncio
async def test_real_redis_connection():
    await init_redis()

    try:
        redis = get_redis()
        key = "test:redis:connection"

        await redis.set(key, "ok", ex=10)

        assert await redis.get(key) == "ok"

        await redis.delete(key)

    finally:
        await close_redis()