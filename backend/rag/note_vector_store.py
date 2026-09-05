import os

from core.embedding_factory import create_embedding_model
from rag.milvus_store import MilvusStore

NOTES_COLLECTION_NAME = "notes_collection"

class NoteVectorStore:
    def __init__(self):
        connection_args = {
            "uri":os.getenv("MILVUS_URI","http://localhost:19530"),
        }

        if token:=os.getenv("MILVUS_TOKEN"):
            connection_args["token"] = token

        self.store = MilvusStore(
            collection_name=NOTES_COLLECTION_NAME,#知识库集合名
            embedding_function=create_embedding_model(),
            connection_args = connection_args,
            enable_dynamic_field=True,
        )

_note_vector_store: NoteVectorStore | None = None

def get_note_vector_store():
    global _note_vector_store
    if not _note_vector_store:
        _note_vector_store = NoteVectorStore()

    return _note_vector_store