import asyncio
import logging
import os

from langchain_core.documents import Document
from sqlalchemy import select

from core.embedding_factory import create_embedding_model
from models.memory import UserMemory
from rag.milvus_store import MilvusStore

logger = logging.getLogger(__name__)
ALLOWED_KINDS = {"profile","preference","fact",}
SENSITIVE_WORDS = {"password","token","secret","api_key","密码","验证码","身份证","银行卡",}

class LongTermMemoryService:
    def __init__(self,db):
        self.db = db
        self._store = None

    def _get_store(self):
        if self._store is None:
            connection_arg = {
                "url":os.getenv("MILVUS_URI","http://localhost:19530")
            }

            if token := os.getenv("MILVUS_TOKEN"):
                connection_arg["token"] = token

            self._store = MilvusStore(
                collection_name="user_memory_collection",
                connection_args=connection_arg,
                embedding_function=create_embedding_model(),
                enable_dynamic_field=True,#允许写入表之外的字段
            )

        return self._store
    @staticmethod
    def _validate(key:str,content:str,kind:str,):
        if not key or len(key) > 100:
            raise ValueError("记忆 key 长度无效")

        if not content or len(content) > 2000:
            raise ValueError("记忆内容长度无效")

        if kind not in ALLOWED_KINDS:
            raise ValueError("记忆类型无效")

        text = f"{key} {content}".lower()

        if any(word in text for word in SENSITIVE_WORDS):
            raise ValueError("不保存密码、Token 等敏感信息")

    async def remember(self,user_id:int,key:str,content:str,kind:str = "fact",source_session_id:str |None = None,):
        key = key.strip()
        content = content.strip()

        self._validate(key,content, kind)

        memory = await self.db.scalar(select(UserMemory).where(UserMemory.user_id == user_id ,UserMemory.memory_key == key))

        if memory is None:
            memory = UserMemory(
                user_id = user_id,
                memory_key = key,
                kind = kind,
                content= content,
                source_session_id = source_session_id,
                is_active=True,
            )
            self.db.add(memory)

        else:
            memory.kind = kind
            memory.content = content
            memory.source_session_id = source_session_id
            memory.is_active = True
        await self.db.flush()
        memory_id = str(memory.id)
        await self.db.commit()

        try:
            store = self._get_store()
            try:
                await asyncio.to_thread(
                    store.delete,
                    ids = [memory_id]
                )

            except Exception:
                pass

            document = Document(
                page_content=content,
                metadata = {
                    "user_id": user_id,
                    "memory_id": memory_id,
                    "memory_key": key,
                    "kind": kind,
                    "is_active": True,
                },
            )

            await asyncio.to_thread(
                store.add_documents,
                [document],
                ids=[memory_id],
            )
        except Exception as exc:
            logger.warning("长期记忆向量索引失败：%s",exc,)

        return memory

    async def search(self,user_id:int,query:str,limit:int = 5):
        active_ids = {
            str(memory_id)
            for memory_id in (
                await self.db.scalars(
                    select(UserMemory.id).where(
                        UserMemory.user_id == user_id,
                        UserMemory.is_active.is_(True),
                    )
                )
            ).all()
        }

        if not active_ids:
            return []

        try:
            matches = await asyncio.to_thread(
                self._get_store().similarity_search_with_score,
                query,
                k = limit * 2,
                filter={
                    "user_id": user_id,
                    "is_active": True,
                },
            )
            results = []
            for doc,score in matches:
                metadata = doc.metadata or {}
                memory_id = str(metadata.get("memory_id", ""))

                if memory_id not in active_ids:
                    continue

                results.append(
                    {
                        "key": metadata.get("memory_key", ""),
                        "kind": metadata.get("kind", "fact"),
                        "content": doc.page_content,
                        "score": float(score),
                    }
                )

            return results[:limit]
        except Exception as exc:
            logger.warning("长期记忆向量检索失败，使用 SQL 兜底：%s",exc,)

            rows = await self.db.scalars(
                select(UserMemory).where(UserMemory.user_id == user_id,UserMemory.is_active.is_(True),)
                .order_by(
                    UserMemory.importance.desc(),
                    UserMemory.updated_at.desc(),
                )
                .limit(limit)
            )

            return [
                {
                    "key": row.memory_key,
                    "kind": row.kind,
                    "content": row.content,
                    "score": 0.0,


                }
                for row in rows.all()

            ]

    async def build_context(self,user_id:int,query:str):
        memories = await self.search(user_id, query,limit=5,)

        if not memories:
            return ""

        return "\n".join(
            f"- [{item['kind']}/{item['key']}] "
            f"{item['content']}"
            for item in memories
        )


    async def forget(self,user_id:int,key:str):
        memory = await self.db.scalar(
            select(UserMemory).where(
                UserMemory.user_id == user_id,
                UserMemory.memory_key == key,
                UserMemory.is_active.is_(True),
            )
        )
        if memory is None:
            return False

        memory_id = str(memory.id)

        memory.is_active = False
        await self.db.commit()

        try:
            await asyncio.to_thread(
                self._get_store().delete,
                ids = [memory_id],
            )

        except Exception as exc:
            logger.warning(
                "删除长期记忆向量失败：%s",
                exc,
            )

        return True