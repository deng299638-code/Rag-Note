import asyncio

from langchain_core import documents

from rag.knowledge_vector_store import get_knowledge_Vector_Store
from rag.reorder_service import ReorderService


class KnowledgeRagService:
    def __init__(self):
        self.reorder_service = ReorderService()

    async def search(self,query:str,user_id:str):
        store = await asyncio.to_thread(
            lambda : get_knowledge_Vector_Store().store
        )

        exists = await asyncio.to_thread(
            store.client.has_collection,
            store.collection_name
        )

        if not exists:
            return []

        documents = await asyncio.to_thread(
            store.similarity_search,
            query,
            k = 5,
            filter = {"user_id":user_id},
        )#list[document]

        if not documents:
            return []


        candidates = [content.page_content for content in documents]

        metadata = [
            {
                "source_type": "knowledge_base",
                "document_id": doc.metadata.get("document_id"),
                "filename": (
                        doc.metadata.get("original_filename")
                        or "未命名资料"
                ),
                "chunk_id": doc.metadata.get("chunk_id"),
            }
            for doc in documents
        ]

        ranked = await self.reorder_service.reorder_documents(
            query,
            candidates,
            metadata
        )

        return ranked[:3]

    async def retriever_context(self,query:str,user_id:str):
        result = await self.search(query, user_id)
        return "\n\n".join(
            f"资料来源:《{item["metadata"]['filename']}》\n\n"
            f"{item["document"]}"
            for item in result
        )