from langchain_core.documents import Document

from rag.note_hybrid_retriever import NoteHybridRetriever
from utils.hash_utils import build_chunk_ids, hash_text, plan_update


def make_chunk(text: str, file_hash: str = "f1"):
    return Document(
        page_content=text,
        metadata={
            "document_id": "d1",
            "user_id": 1,
            "file_hash": file_hash,
            "chunk_hash": hash_text(text),
        },
    )


def test_plan_update_identifies_changed_chunks():
    old_a = make_chunk("A", "old")
    old_b = make_chunk("B", "old")
    old_ids = build_chunk_ids("d1", [old_a, old_b])

    new_a = make_chunk("A", "new")
    new_c = make_chunk("C", "new")

    plan = plan_update(
        list(zip(old_ids, [old_a, old_b])),
        [new_a, new_c],
        "d1",
    )

    assert plan.kept_ids == [old_ids[0]]
    assert plan.delete_ids == [old_ids[1]]
    assert len(plan.add_documents) == 1
    assert plan.add_documents[0].page_content == "C"


def test_dynamic_weights():
    retriever = NoteHybridRetriever()

    assert retriever._get_dynamic_weights("短问题") == [0.3, 0.7]
    assert retriever._get_dynamic_weights("这是一个足够长的问题，用来测试向量检索和关键词检索的权重变化") == [0.6, 0.4]