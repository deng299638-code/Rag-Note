from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from rag.note_hybrid_retriever import bm25_tokenize


def test_chinese_bm25_matches_title():
    # rank_bm25 的 idf 公式 idf=log((N-df+0.5)/(df+0.5)) 在语料只有 2 篇文档时，
    # 单文档词会得到 idf=0，所有文档得分归零导致平局，无法体现中文分词匹配。
    # 因此测试语料至少需要 3 篇文档。
    retriever = BM25Retriever.from_documents(
        [
            Document(
                page_content="Milvus 混合检索方案\n"
                "向量检索结合关键词检索",
                metadata={"note_id": 1},
            ),
            Document(
                page_content="Redis 缓存设计",
                metadata={"note_id": 2},
            ),
            Document(
                page_content="Python 异步编程实践",
                metadata={"note_id": 3},
            ),
        ],
        k=1,
        preprocess_func=bm25_tokenize,
    )

    results = retriever.invoke("Milvus 混合检索")

    assert results
    assert results[0].metadata["note_id"] == 1

from time import monotonic

from langchain_core.documents import Document

from rag.note_hybrid_retriever import (
    BM25CacheEntry,
    BM25_TOKENIZER_VERSION,
    NoteHybridRetriever,
)


def test_bm25_cache_invalidates_when_tokenizer_changes():
    entry = BM25CacheEntry(
        data_version=1,
        tokenizer_version="v1",
        expires_at=monotonic() + 300,
        retriever=None,
    )

    assert (
        NoteHybridRetriever._is_cache_valid(
            entry,
            1,
        )
        is False
    )

def test_bm25_cache_is_valid_for_same_version():
    entry = BM25CacheEntry(
        data_version=1,
        tokenizer_version=BM25_TOKENIZER_VERSION,
        expires_at=monotonic() + 300,
        retriever=None,
    )

    assert (
        NoteHybridRetriever._is_cache_valid(
            entry,
            1,
        )
        is True
    )