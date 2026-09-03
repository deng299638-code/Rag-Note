from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = ""
    tags: list[str] = Field(default_factory=list)#默认空的列表
    category: str | None = Field(default=None, max_length=50)


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = None
    tags: list[str] | None = None
    category: str | None = Field(default=None, max_length=50)
    is_pinned: bool | None = None


class NoteResponse(BaseModel):
    id: int
    user_id: int
    title: str
    content: str
    tags: list[str]
    category: str | None
    is_pinned: bool
    created_at: datetime | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class NoteListResponse(BaseModel):
    notes: list[NoteResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

class SearchResponse(BaseModel):
    notes: list[NoteResponse]
    total: int

class BatchIdsRequest(BaseModel):

    ids : list[int] = Field(...,min_length= 1 )


class BatchPinRequest(BaseModel):

    ids : list[int] = Field(...,min_length= 1 )
    is_pinned : bool


class BatchCategoryRequest(BaseModel):
    ids: list[int] = Field(..., min_length=1)
    category: str = Field(..., min_length=1, max_length=50)


class NoteQueryParams(BaseModel):
    page:int = Field(default=1,ge=1)
    page_size : int = Field(default=20,ge=1,le=100)
    category: str | None = Field(default=None, max_length=50)
    tag: str | None = Field(default=None, max_length=50)
    sort_by : Literal[
        "create_at",
        "updated_at",
        "title",
    ] = "create_at"
    sort_order : Literal["asc","desc"] = "desc"