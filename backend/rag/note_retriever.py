# rag/note_retriever.py
import asyncio

from rag.note_vector_store import get_note_vector_store


class NoteRetriever:
    async def retrieve(
        self,
        query: str,
        user_id: int,
        top_k: int = 3,
    ):
        store = get_note_vector_store().store

        expr = f'user_id == {user_id} and doc_type == "note"'

        return await asyncio.to_thread(
            store.similarity_search,
            query,
            k=top_k,
            expr = expr,
        )


