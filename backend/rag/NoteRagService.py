from rag.note_hybrid_retriever import NoteHybridRetriever
from rag.reorder_service import ReorderService


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

        return reorder[:limit]

    async def retriever_context(self,query,user_id):

        result = await self.search_notes(query,user_id)
        return "\n\n".join(
            item["document"]
            for item in result
        )