import logging

from rag.knowledge_rag_service import KnowledgeRagService
from rag.note_hybrid_retriever import NoteHybridRetriever
from rag.reorder_service import ReorderService
from rag.rerank_confidence import assess_rerank_confidence

logger = logging.getLogger(__name__)
class NoteRagService:

    def __init__(self):
        self.retriever = NoteHybridRetriever()
        self.reorder_service = ReorderService()

    async def retrieve_documents(self,query : str , user_id : int):
        retriever = await self.retriever.get_retriever(query,user_id)
        return await retriever.ainvoke(query)

    async def search_notes(self,query : str,user_id : int,limit : int = 3):

        documents = await self.retrieve_documents(query,user_id)

        if not documents:
            return []

        candidates = [(
            f"笔记来源：《{document.metadata.get("title","无标题")}》\n"
            f"{document.page_content}"
            ) for document in documents
        ] #

        metadata = [
            {
                "note_id": document.metadata.get("note_id"),
                "title": document.metadata.get("title", "无标题"),
            }
            for document in documents
        ]


        reorder = await self.reorder_service.reorder_documents(
            query, candidates,metadata
        )
        assessment = assess_rerank_confidence(reorder,min_score=0.5,min_margin=0.1)
        logger.info("RAG confidence: query=%s, assessment=%s",query,assessment,)
        return reorder[:limit]

    async def retriever_context(self,query,user_id):

        result = await self.search_notes(query,user_id)
        return "\n\n".join(
            item["document"]
            for item in result
        )

    async def retriever_context_with_sources(self,query:str,user_id:int,limit:int = 3):
        result = await self.search_notes(query, user_id, limit)

        context_parts = []
        sources = []

        for item in result:
            metadata = item.get("metadata",{})
            title = metadata.get("title","无标题")
            note_id = metadata.get("note_id")

            context_parts.append(item["document"])
            sources.append({
                "note_id": note_id,
                "title": title,
                "score": item.get("similarity", 0),
            })

        return {
            "context": "\n\n".join(context_parts),
            "sources": sources,
        }