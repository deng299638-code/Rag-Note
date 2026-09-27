from typing import Literal

from pydantic import BaseModel, Field


class GraphEntityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    type_id: str | None = Field(default=None, max_length=64)
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_note_ids: list[str] = Field(default_factory=list)


class GraphEntityRead(GraphEntityCreate):
    id: str
    entity_key: str
    user_id: int


class GraphNode(BaseModel):
    id:str
    label:str
    node_type: Literal["entity", "note", "doc"]
    entity_type_id : str | None = None

class GraphEdge(BaseModel):
    id:str
    source:str
    target: str
    kind:Literal["relation", "wiki"]
    relation_type: str | None = None

class GraphView(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class GraphRelationCreate(BaseModel):
    source_entity_id : str = Field(min_length=1)
    target_entity_id : str = Field(min_length=1)
    relation_type: str = Field(min_length=1,max_length=100)

