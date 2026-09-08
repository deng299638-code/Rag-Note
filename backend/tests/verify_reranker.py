import asyncio

from rag.reorder_service import ReorderService


async def main():
    documents = [
        "FastAPI 的 Depends 用于依赖注入。",
        "Milvus 用于保存向量并执行相似度搜索。",
        "Depends 可以注入数据库会话和当前用户。",
    ]

    results = await ReorderService().reorder_documents(
        query="FastAPI 如何进行依赖注入？",
        documents=documents,
    )

    for item in results:
        print(
            round(item["similarity"], 4),
            item["document"],
        )


asyncio.run(main())