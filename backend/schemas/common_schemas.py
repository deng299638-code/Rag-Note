from typing import TypeVar, Generic

from pydantic import BaseModel

from schemas.note_schemas import NoteResponse

T = TypeVar("T")

class ApiResponse(BaseModel,Generic[T]):
    code : int = 200
    message: str = "操作成功"
    data: T | None = None


class NoteStatsData(BaseModel):
    total:int
    categories: list[dict[str,int | str]]
    uncategorized: int


class OperationData(BaseModel):
    updated_count: int | None = None
    deleted_count: int | None = None
    category: str | None = None
    is_pinned: bool | None = None