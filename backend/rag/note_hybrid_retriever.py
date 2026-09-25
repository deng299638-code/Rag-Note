import asyncio
import logging
from dataclasses import dataclass
from time import monotonic
import re
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from rag.note_vector_store import get_note_vector_store
from utils.cache import get_rag_version, bump_rag_version

_TOKEN_PATTERN = re.compile(
    r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+"
)
logger = logging.getLogger(__name__)
TOP_K = 5
BM25_CACHE_TTL = 300
INDEX_SOURCE = "notes"
BM25_TOKENIZER_VERSION = "v2"

def bm25_tokenize(text:str):
    tokens: list[str] = []
    for part in _TOKEN_PATTERN.findall(str(text or "").casefold()):
        #判断是开头是英文
        if part[0].isascii():
            tokens.append(part)
            continue

        tokens.extend(part)

        tokens.extend(part[index:index+2] for index in range(len(part) - 1))

    return tokens

@dataclass(slots=True)
class BM25CacheEntry:
    data_version: int | None
    tokenizer_version:str
    expires_at: float
    retriever: BM25Retriever | None


class NoteHybridRetriever:

    _bm25_cache: dict[int,BM25CacheEntry] = {}
    _user_locks:dict[int,asyncio.Lock] = {}
    _locks_guard = asyncio.Lock()

    @classmethod
    async def _get_user_lock(cls,user_id: int):
        async with cls._locks_guard:
            return cls._user_locks.setdefault(user_id,asyncio.Lock())

    @staticmethod
    async def _get_index_version(user_id: int):
        try:
            return await get_rag_version(INDEX_SOURCE,user_id)

        except Exception as exc:
            logger.warning(
                "读取笔记索引版本失败，使用 TTL 兜底：user_id=%s error=%s",
                user_id,
                exc,
            )
            return None

    @classmethod
    def _is_cache_valid(cls,entry:BM25CacheEntry | None,version: int | None):
        if entry is None:
            return False

        if entry.expires_at <= monotonic():
            return False

        if entry.tokenizer_version != BM25_TOKENIZER_VERSION:
            return False

        if version is not None and entry.data_version != version:
            return False

        return True



    async def _get_bm25_documents(self,user_id:int) ->  BM25Retriever | None:

        store = get_note_vector_store().store

        #从向量库中检索出该用户的所有文档
        result = await asyncio.to_thread(
            store.get,
            include=["documents", "metadatas"],
            where = {
                "user_id" : user_id,
                "doc_type" : "note"
            },
        )

        documents = []
        metadata_list = result.get("metadatas",[])

        for i, doc_content in enumerate(result['documents']):
            metadata = (metadata_list[i] if i < len(metadata_list) else {})
            title = str(metadata.get("title","")).strip()
            body = str(doc_content).strip()

            searchable_text = "/n".join(
                value for value in (title,body) if value
            )
            documents.append(Document(page_content=searchable_text, metadata=metadata))

        if not documents:
            return None

        return documents

    async def _get_bm25_retriever(self,user_id:int):
        version = await self._get_index_version(user_id)
        cache = self._bm25_cache.get(user_id)

        if self._is_cache_valid(cache,version):
            return cache.retriever

        lock = await self._get_user_lock(user_id)

        async with lock:
            version = await self._get_index_version(user_id)
            cache = self._bm25_cache.get(user_id)

            if self._is_cache_valid(cache,version):
                return cache.retriever

            documents = await self._get_bm25_documents(user_id)

            retriever = (BM25Retriever.from_documents(documents=documents,k=TOP_K,preprocess_func=bm25_tokenize) if documents else None )

            self._bm25_cache[user_id] = BM25CacheEntry(
                data_version=version,
                tokenizer_version=BM25_TOKENIZER_VERSION,
                expires_at=monotonic() + BM25_CACHE_TTL,
                retriever = retriever,
            )

            return retriever

    @classmethod
    async def invalidate_user(cls,user_id : int):
        lock = await cls._get_user_lock(user_id)

        async with lock:
            cls._bm25_cache.pop(user_id,None)

            try:
                await bump_rag_version(INDEX_SOURCE,user_id)

            except Exception as exc:
                logger.warning(
                    "更新笔记索引版本失败：user_id=%s error=%s",
                    user_id,
                    exc,
                )





    async def get_retriever(self,query,user_id):
        store = get_note_vector_store().store

        expr = f'user_id == {user_id} and doc_type == "note"'

        #异步不支持filter字典
        vector_retriever = store.as_retriever(
            search_type = "similarity",
            search_kwargs = {
                "k" : TOP_K,
                "expr" : expr,
            }
        )

        bm25_retriever = await self._get_bm25_retriever(user_id)

        if not bm25_retriever:
            return vector_retriever

        return EnsembleRetriever(
            retrievers=[
                vector_retriever,
                bm25_retriever,
            ],
            weights=self._get_dynamic_weights(query)
        )


    @staticmethod
    def _get_dynamic_weights(query : str):
        default_vector_weight = 0.5
        default_bm25_weight = 0.5

        if not query:
            return [default_vector_weight, default_bm25_weight]

        query_length = len(query)
        query_words = len(query.split())

        if query_length > 50:
            vector_weight = 0.7
            bm25_weight = 0.3
        elif query_length >= 25:
            vector_weight = 0.6
            bm25_weight = 0.4
        elif query_length < 20:
            vector_weight = 0.3
            bm25_weight = 0.7
        else:
            vector_weight = default_vector_weight
            bm25_weight = default_bm25_weight

        if query_words > 0:
            word_density = query_words / query_length
            if word_density > 0.1:
                bm25_weight = min(bm25_weight + 0.1, 0.7)
                vector_weight = max(vector_weight - 0.1, 0.3)

        return [vector_weight, bm25_weight]

