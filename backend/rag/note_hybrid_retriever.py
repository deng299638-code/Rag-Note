import asyncio

from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from rag.note_vector_store import get_note_vector_store

TOP_K = 5

class NoteHybridRetrieve:
    async def _get_bm25_retriever(self,user_id:int) ->  BM25Retriever | None:

        store = get_note_vector_store().store

        #从向量库中检索出该用户的所有文档
        result = await asyncio.to_thread(
            store.get,
            include=["documents", "metadatas"],
            where = {
                "user_id" : user_id,
                "doc_ytpe" : "note"
            },
        )

        documents = []

        for i, doc_content in enumerate(result['documents']):
            metadata = result['metadatas'][i] if i < len(result['metadatas']) else {}
            documents.append(Document(page_content=doc_content, metadata=metadata))

        if not documents:
            return None

        return BM25Retriever.from_documents(
            documents = documents,
            k = TOP_K,
        )



    async def get_retriever(self,query,user_id):
        store = get_note_vector_store().store

        vector_retriever = store.as_retriever(
            serch_type = "similarity",
            search_kwargs = {
                "k" : TOP_K,
                "filter" : {
                    "user_id" : user_id,
                    "doc_type" : "note"
                }
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

