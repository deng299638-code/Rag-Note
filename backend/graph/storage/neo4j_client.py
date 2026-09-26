import os

from dotenv import load_dotenv
from pathlib import Path
from neo4j import AsyncDriver, AsyncGraphDatabase

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
class GraphUnavailableError(RuntimeError):
    """Neo4j 未配置或不可连接时的统一异常。"""

_driver: AsyncDriver | None = None

def get_neo4j_driver():
    global _driver

    if _driver is not None:
        return _driver

    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    if not uri or not username or not password:
        raise GraphUnavailableError(
            "请配置 NEO4J_URI、NEO4J_USER、NEO4J_PASSWORD"
        )

    _driver = AsyncGraphDatabase.driver(uri,auth=(username,password),)
    return _driver

async def verify_neo4j_connection():
    driver = get_neo4j_driver()

    try:
        await driver.verify_connectivity()

        async with driver.session() as session:
            result = await session.run("RETURN 1 AS value")
            row = await result.single()

        return {
            "connected":True,
            "value":row["value"],
        }
    except Exception as exc:
        raise GraphUnavailableError(
            f"Neo4j 连接失败：{exc}"
        ) from exc

async def initialize_neo4j_schema():
    driver = get_neo4j_driver()

    statements = (
        "CREATE CONSTRAINT graph_entity_key_unique IF NOT EXISTS "
        "FOR (entity:Entity) REQUIRE entity.entity_key IS UNIQUE",
        "CREATE INDEX graph_entity_user_id IF NOT EXISTS "
        "FOR (entity:Entity) ON (entity.user_id)",
    )

    try:
        async with driver.session() as session:
            for statement in statements:
                result = await session.run(statement)
                await result.consume()
    except Exception as exc:
        raise GraphUnavailableError(
            f"Neo4j 图谱结构初始化失败：{exc}"
        ) from exc


async def close_neo4j_driver():
    """FastAPI 关闭时释放连接池。"""
    global _driver

    if _driver is not None:
        await _driver.close()
        _driver = None