from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AgentQueryRequest(BaseModel):
    query: str = Field(...,min_length=1,max_length=4000)
    session_id : str | None = None
    ids : list[int] = Field(
        default_factory= list,
        max_length=10,
    )


class ChatSessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime | None
    updated_at: datetime | None
    model_config = {"from_attributes": True}


class ChatSessionListResponse(BaseModel):
    sessions: list[ChatSessionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ChatSessionQueryParams(BaseModel):

    page: int = Field(default= 1 ,ge= 1)
    page_size : int = Field(default= 20 ,le= 100)


class ChatMessageResponse(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime | None

    model_config = {"from_attributes": True}


class ChatMessageListResponse(BaseModel):
    messages: list[ChatMessageResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ChatMessageQueryParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)