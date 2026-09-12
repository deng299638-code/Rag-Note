import os

# 必须先于 import torch 设置，才能禁用 C++ pytree（_cxx_pytree）加载
os.environ["TORCH_USE_CXX_PYTREE"] = "0"

import torch  # noqa: E402
from rag.chunk_store import load_existing_chunks  # noqa: E402


class FakeStore:
    def __init__(self):
        self.last_kwargs = None

    def get(self, **kwargs):
        # 记录 store.get 实际收到的参数，供测试断言
        self.last_kwargs = kwargs
        return {
            "ids": ["id1"],
            "documents": ["内容A"],
            "metadatas": [
                {
                    "document_id": "d1",
                    "user_id": "u1",
                    "chunk_hash": "h1",
                }
            ],
        }


store = FakeStore()
chunks = load_existing_chunks(
    store,
    where={
        "document_id": "d1",
        "user_id": "u1",
    },
)

# 断言 load_existing_chunks 是否正确透传了查询参数
assert store.last_kwargs["where"] == {
    "document_id": "d1",
    "user_id": "u1",
}
assert store.last_kwargs["include"] == ["documents", "metadatas"]

assert len(chunks) == 1
assert chunks[0][0] == "id1"
assert chunks[0][1].page_content == "内容A"
assert chunks[0][1].metadata["user_id"] == "u1"

print("ok")
