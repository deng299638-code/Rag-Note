from datetime import datetime

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


class BatchIdsRequest(BaseModel):

    ids : list[int] = Field(...,min_length= 1 )


class BatchPinRequest(BaseModel):

    ids : list[int] = Field(...,min_length= 1 )
    is_pinned : bool