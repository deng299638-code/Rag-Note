import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass

from langchain_community.docstore import document
from langchain_core.documents import Document


def hash_text(text : str):
    normalized = text.strip()

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()#将二进制转化为64 位的十六进制字符串。

def build_chunk_ids(document_id : str , chunks : list[Document]):
    occurrences = defaultdict(int)
    ids = []

    for chunk in chunks:
        chunk_hash = chunk.metadata["chunk_hash"]
        index = occurrences[chunk_hash]
        occurrences[chunk_hash] += 1

        chunk_id = f"{document_id}:{chunk_hash}:{index}"

        chunk.metadata["chunk_id"] = chunk_id
        ids.append(chunk_id)

    return ids


REQUIRED_METADATA ={
    "document_id",
    "file_hash",
    "chunk_hash",
    "chunk_id",
}
def supports_incremental(old_records : list[tuple[str,Document]]):
    if not old_records:
        return True

    return all(
        REQUIRED_METADATA.issubset(document.metadata)
        for _,document in old_records
    )



@dataclass
class ChunkDiff:
    added : list[Document]
    kept : list[Document]
    removed_hashes : list[str]

@dataclass
class ChunkUpdatePlan:
    delete_ids : list[str]
    add_documents : list[Document]
    add_ids : list[str]
    kept_ids : list[str]


def plan_update(old_records : list[tuple[str,Document]],new_chunks:list[Document],document_id: str,):
    old_by_id = {
        vector_id : document
        for vector_id,document in old_records
    }

    new_by_ids = build_chunk_ids(
        document_id,
        new_chunks,
    )

    add_documents = []
    add_ids = []
    kept_ids = []

    for chunk,chunk_id in zip(new_chunks,new_by_ids):
        if chunk_id in old_by_id:
            kept_ids.append(chunk_id)
        else:
            add_documents.append(chunk)
            add_ids.append(chunk_id)

    new_id_set = set(new_by_ids)
    delete_ids = [
        vector_id
        for vector_id in old_by_id
        if vector_id not in new_id_set
    ]

    return ChunkUpdatePlan(
        delete_ids,add_documents,add_ids,kept_ids,
    )