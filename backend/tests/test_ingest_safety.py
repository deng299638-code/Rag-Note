from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.documents import Document

import rag.document_processor as module
from rag.chunk_store import load_existing_chunks
from utils.hash_utils import build_chunk_ids, hash_text


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [True, False])
@pytest.mark.parametrize("empty", [True, False])
async def test_failed_ingest_does_not_delete_old_chunks(
    monkeypatch,
    legacy,
    empty,
):
    old = Document(
        page_content="旧内容",
        metadata={
            "document_id": "d1",
            "user_id": "u1",
            "file_hash": "old-file",
            "chunk_hash": hash_text("旧内容"),
        },
    )
    old_id = build_chunk_ids("d1", [old])[0]

    if legacy:
        old.metadata.clear()

    monkeypatch.setattr(
        module,
        "load_existing_chunks",
        lambda store, where: [(old_id, old)],
    )

    # 绕过初始化；本测试只检查入库流程。
    processor = object.__new__(module.DocumentProcessor)
    processor.process_file = AsyncMock(
        return_value=[] if empty else [
            Document(
                page_content="新内容",
                metadata={"chunk_hash": hash_text("新内容")},
            )
        ]
    )

    store = Mock()
    store.upsert.side_effect = RuntimeError("模拟向量写入失败")

    expected_error = ValueError if empty else RuntimeError

    with pytest.raises(expected_error):
        await processor.ingest_file(
            store, "demo.txt", "d1", "u1", "new-file"
        )

    store.delete.assert_not_called()
    store.add_documents.assert_not_called()

    if empty:
        store.upsert.assert_not_called()
    else:
        store.upsert.assert_called_once()

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "old_texts,new_texts,collection_exists,expected_added",
    [
        ([], ["A", "B"], False, 2),       # 首次创建集合
        ([], ["A", "B"], True, 2),        # 已有集合中的新文档
        (["A", "B"], ["A", "C"], True, 1),  # 保留、新增、删除
        (["A", "B"], ["B", "A"], True, 0),  # 只调整顺序
    ],
)
async def test_ingest_writes_all_chunks_with_matching_ids(
    monkeypatch,
    old_texts,
    new_texts,
    collection_exists,
    expected_added,
):
    def make_chunks(texts, version):
        return [
            Document(
                page_content=text,
                metadata={
                    "document_id": "d1",
                    "user_id": "u1",
                    "file_hash": version,
                    "chunk_hash": hash_text(text),
                    "chunk_index": index,
                },
            )
            for index, text in enumerate(texts)
        ]

    old_chunks = make_chunks(old_texts, "old")
    old_ids = build_chunk_ids("d1", old_chunks)

    monkeypatch.setattr(
        module,
        "load_existing_chunks",
        lambda store, where: list(zip(old_ids, old_chunks)),
    )

    new_chunks = make_chunks(new_texts, "new")
    processor = object.__new__(module.DocumentProcessor)
    processor.process_file = AsyncMock(return_value=new_chunks)

    store = Mock()
    store.collection_name = "test_collection"
    store.client.has_collection.return_value = collection_exists

    result = await processor.ingest_file(
        store, "demo.txt", "d1", "u1", "new"
    )

    writer = store.upsert if collection_exists else store.add_documents
    unused_writer = store.add_documents if collection_exists else store.upsert

    writer.assert_called_once()
    unused_writer.assert_not_called()

    kwargs = writer.call_args.kwargs
    documents = kwargs["documents"]
    ids = kwargs["ids"]

    assert len(documents) == len(ids) == len(new_texts)
    assert [doc.page_content for doc in documents] == new_texts
    assert ids == [doc.metadata["chunk_id"] for doc in documents]
    assert all(doc.metadata["file_hash"] == "new" for doc in documents)
    assert [doc.metadata["chunk_index"] for doc in documents] == list(
        range(len(new_texts))
    )

    expected_deleted = [
        old_id for old_id in old_ids if old_id not in set(ids)
    ]
    if expected_deleted:
        store.delete.assert_called_once_with(ids=expected_deleted)
    else:
        store.delete.assert_not_called()

    assert result["added"] == expected_added
    assert result["status"] == ("updated" if old_texts else "created")