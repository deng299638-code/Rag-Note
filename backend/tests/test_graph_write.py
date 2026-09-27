import asyncio
import pytest
from schemas.graph import GraphEntityCreate
from schemas.graph_store import Neo4jGraphStore
from graph.storage.neo4j_client import close_neo4j_driver


# 异步测试标记
@pytest.mark.asyncio
async def test_graph_upsert_entity():
    # 这才是pytest会识别的测试函数，名字必须test_开头
    entity = await Neo4jGraphStore().upsert_entity(
        user_id=1,
        payload=GraphEntityCreate(
            name="机器学习",
            type_id="concept",
            aliases=["ML"],
        ),
    )

    print(entity.model_dump())

    await close_neo4j_driver()
