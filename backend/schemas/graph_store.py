import re
import unicodedata

from schemas.graph import GraphEntityCreate, GraphEntityRead, GraphNode, GraphView, GraphRelationCreate, GraphEdge
from graph.storage.neo4j_client import get_neo4j_driver


def normalize_entity_name(name: str) -> str:
    """
    将实体名称转换成稳定的 key 片段。
    例如：Machine Learning -> machine-learning
    """
    value = unicodedata.normalize("NFKC", name).casefold().strip()#半角转园，小写化，
    value = re.sub(r"[^\w]+", "-", value)#非字母转-
    return value.strip("-") or "unnamed"


class Neo4jGraphStore:
    async def upsert_entity(
        self,
        user_id: int,
        payload: GraphEntityCreate,
    ) -> GraphEntityRead:
        normalized_name = normalize_entity_name(payload.name)
        type_id = payload.type_id or "entity"

        # entity_key 必须包含 user_id，避免不同用户互相冲突。
        entity_key = f"{user_id}:{normalized_name}:{type_id}"

        query = """
        MERGE (entity:Entity {entity_key: $entity_key})
        ON CREATE SET
            entity.id = randomUUID(),
            entity.created_at = datetime()
        SET
            entity.user_id = $user_id,
            entity.name = $name,
            entity.display_name = $display_name,
            entity.type_id = $type_id,
            entity.description = $description,
            entity.aliases = $aliases,
            entity.confidence = $confidence,
            entity.source_note_ids = $source_note_ids,
            entity.updated_at = datetime()
        RETURN
            entity.id AS id,
            entity.entity_key AS entity_key,
            entity.user_id AS user_id,
            entity.name AS name,
            entity.display_name AS display_name,
            entity.type_id AS type_id,
            entity.description AS description,
            entity.aliases AS aliases,
            entity.confidence AS confidence,
            entity.source_note_ids AS source_note_ids
        """

        driver = get_neo4j_driver()

        async with driver.session() as session:
            result = await session.run(
                query,
                entity_key=entity_key,
                user_id=user_id,
                name=payload.name,
                display_name=payload.display_name or payload.name,
                type_id=payload.type_id,
                description=payload.description,
                aliases=payload.aliases,
                confidence=payload.confidence,
                source_note_ids=payload.source_note_ids,
            )
            record = await result.single()

        if record is None:
            raise RuntimeError("实体写入失败")

        return GraphEntityRead(**record.data())

    async def get_overview(self,user_id:int,type_ids: list[str] | None = None,limit: int = 200,):
        query = """
        MATCH(entity:Entity)
        WHERE entity.user_id = $user_id
            AND(
                $type_ids IS NULL
                OR entity.type_id IN $type_ids
            )
        RETURN
            entity.id AS id,
            coalesce(entity.display_name, entity.name) AS label,
            "entity" AS node_type,
            entity.type_id AS entity_type_id
        ORDER BY label
        LIMIT $limit
        """

        driver = get_neo4j_driver()

        async with driver.session() as session:
            result  = await session.run(
                query,
                user_id = user_id,
                type_ids = type_ids,
                limit=limit,
            )

            records = [record async for record in result]

        nodes = [
            GraphNode(**record.data())
            for record in records
        ]
        node_ids = [node.id for node in nodes]

        relation_query = """
        MATCH(source:Entity)-[relation:RELATED_TO]->(target:Entity)
        WHERE source.user_id = $user_id
          AND target.user_id = $user_id
          AND source.id IN $node_ids
          AND target.id IN $node_ids
          
        RETURN
            relation.id AS id,
            source.id AS source,
            target.id AS target,
            "relation" AS kind,
            relation.relation_type AS relation_type
        """

        async with driver.session() as session:
            relation_result = await session.run(
                relation_query,
                user_id=user_id,
                node_ids=list(node_ids),
            )
            relation_records = [
                record async for record in relation_result
            ]

        edges = [
            GraphEdge(**record.data())
            for record in relation_records
        ]

        return GraphView(
            nodes= nodes,
            edges= edges,
        )

    async def create_relation(self,user_id:int,payload:GraphRelationCreate):
        relation_key = (
            f"{payload.source_entity_id}:"
            f"{payload.relation_type}:"
            f"{payload.target_entity_id}"
        )

        query="""
        MATCH (
            source:Entity{
                id:$source_entity_id,
                user_id: $user_id
            }
        )
        MATCH (
            target:Entity{
                id:$target_entity_id,
                user_id: $user_id
            }
        )
        MERGE (source)-[
            relation:RELATED_TO {
                relation_key: $relation_key
            }
        ]->(target)
        ON CREATE SET
            relation.id = randomUUID(),
            relation.created_at = datetime()
        SET
            relation.relation_type = $relation_type,
            relation.updated_at = datetime()
        RETURN
            relation.id AS id,
            source.id AS source,
            target.id AS target,
            "relation" AS kind,
            relation.relation_type AS relation_type
        """

        driver = get_neo4j_driver()

        async with driver.session() as session:
            result = await session.run(
                query,
                user_id = user_id,
                source_entity_id=payload.source_entity_id,
                target_entity_id=payload.target_entity_id,
                relation_key=relation_key,
                relation_type=payload.relation_type,
            )

            record = result.single()

        if record is None:
            raise ValueError(
                "源实体或目标实体不存在，或者不属于当前用户"
            )

        return GraphEdge(**record.data())