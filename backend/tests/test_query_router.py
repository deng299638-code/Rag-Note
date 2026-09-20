import pytest
from langchain_core.runnables import RunnableLambda

from rag.query import QueryRouter
from schemas.query import QueryPlan


@pytest.mark.asyncio
async def test_note_stats_skips_rag():
    router = QueryRouter(None)

    plan = await router.route("请查看我的笔记统计")

    assert plan.intent == "note_stats"
    assert plan.use_rag is False
    assert plan.rewritten_query == "请查看我的笔记统计"

# dummy对象，仅用于规则分支，不会被调用
class DummyLLM:
    pass

@pytest.mark.asyncio
async def test_note_search_skips_rag():
    router = QueryRouter(DummyLLM())
    plan = await router.route("搜索我的 Milvus 笔记")
    assert plan.intent == "note_search"
    assert plan.use_rag is False



@pytest.mark.asyncio
async def test_greeting_skips_rag():
    router = QueryRouter(None)

    plan = await router.route("你好")

    assert plan.intent == "chat"
    assert plan.use_rag is False


class FakeChatModel:
    def with_structured_output(self, schema):
        return RunnableLambda(
            lambda _: QueryPlan(
                intent="rag",
                rewritten_query="Milvus 如何实现混合检索",
                use_rag=True,
                confidence=0.9,
                reason="需要检索知识库",
            )
        )


@pytest.mark.asyncio
async def test_rag_query_is_rewritten():
    router = QueryRouter(FakeChatModel())

    plan = await router.route(
        "它是怎么实现混合检索的？",
        history=[
            ("我上传过一篇 Milvus 文档", "已找到该资料"),
        ],
    )

    assert plan.intent == "rag"
    assert plan.use_rag is True
    assert plan.rewritten_query == "Milvus 如何实现混合检索"
