from langchain_core.documents import Document


def load_existing_chunks(store,where : dict):
    result = store.get(
        include = ["documents","metadatas"],
        where = where
    )

    chunks = []

    for index,content in enumerate(result["documents"]):
        metadata = result["metadatas"][index]
        vector_id = result["ids"][index]

        chunks.append(
            (
                vector_id,
                Document(
                    page_content=content,
                    metadata = metadata,
                )
            )
        )

    return chunks