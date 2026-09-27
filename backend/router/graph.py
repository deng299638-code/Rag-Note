from fastapi import APIRouter, Depends, status, HTTPException, Query

from graph.storage.neo4j_client import GraphUnavailableError
from schemas.common_schemas import ApiResponse
from schemas.graph import GraphEntityCreate, GraphEntityRead, GraphView, GraphRelationCreate, GraphEdge
from schemas.graph_store import Neo4jGraphStore
from utils.JWT import get_current_user_id

graph_router = APIRouter(prefix="/api/graph",tags=["graph"])

@graph_router.post("/entities",response_model=ApiResponse[GraphEntityRead],status_code=status.HTTP_201_CREATED,)
async def create_graph_entity(payload:GraphEntityCreate,user_id: int = Depends(get_current_user_id)):
    try:
        entity = await Neo4jGraphStore().upsert_entity(user_id, payload)

    except GraphUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return {
        "code": 201,
        "message": "实体创建成功",
        "data": entity,
    }


@graph_router.get("/overview",response_model=ApiResponse[GraphView])
async def get_graph_overview(types : str | None = Query(default= None,description="实体类型多个类型用逗号隔开"),limit:int = Query(default=200,ge=1,le=1000,),user_id : int = Depends(get_current_user_id)):
    type_ids = None
    if types:
        type_ids = [
            item.strip()
            for item in types.split(",")
            if item.strip()
        ]

    try:
        graph = await Neo4jGraphStore().get_overview(user_id,type_ids,limit)
    except GraphUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return {
        "code":200,
        "message":"获取图谱成功",
        "data":graph,
    }

@graph_router.post("/relations",response_model=ApiResponse[GraphEdge], status_code=status.HTTP_201_CREATED,)
async def create_graph_relation(payload:GraphRelationCreate,user_id:int = Depends(get_current_user_id)):
    try:
        relation = await Neo4jGraphStore().create_relation(user_id, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except GraphUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return {
        "code": 201,
        "message": "实体关系创建成功",
        "data": relation,
    }