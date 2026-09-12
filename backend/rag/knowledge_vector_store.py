import os

from core.embedding_factory import create_embedding_model
from rag.milvus_store import MilvusStore

KNOWLEDGE_COLLECTION_NAME = "knowledge_collection"
class knowledgeVectorStore:
    def __init__(self):
        connection_args = {
            "uri": os.getenv("MILVUS_URI", "http://localhost:19530"),
        }

        if token := os.getenv("MILVUS_TOKEN"):
            connection_args["token"] = token

        self.store = MilvusStore(
            collection_name=KNOWLEDGE_COLLECTION_NAME,  # 知识库集合名
            embedding_function=create_embedding_model(),
            connection_args=connection_args,
            enable_dynamic_field=True,
        )


_knowledgeVectorStore: knowledgeVectorStore| None = None

def get_knowledge_Vector_Store():
    global _knowledgeVectorStore

    if _knowledgeVectorStore is None:

        _knowledgeVectorStore = knowledgeVectorStore()

    return _knowledgeVectorStore