from datetime import datetime

from pydantic import BaseModel, Field


class NoteTemplateCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    icon: str = Field(
        default="FileText",
        max_length=50,
    )

    category: str = Field(
        default="",
        max_length=50,
    )

    title: str = Field(
        default="",
        max_length=200,
    )

    content: str = ""

    tags: list[str] = Field(
        default_factory=list,
    )


class NoteTemplateUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    icon: str | None = Field(
        default=None,
        max_length=50,
    )

    category: str | None = Field(
        default=None,
        max_length=50,
    )

    title: str | None = Field(
        default=None,
        max_length=200,
    )

    content: str | None = None
    tags: list[str] | None = None


class NoteTemplateReorder(BaseModel):
    ids: list[str] = Field(
        ...,
        min_length=1,
    )


class NoteTemplateResponse(BaseModel):
    id: str
    user_id: int
    name: str
    icon: str
    category: str
    title: str
    content: str
    tags: list[str]
    is_default: bool
    sort_order: int
    created_at: datetime | None
    updated_at: datetime | None

    model_config = {
        "from_attributes": True,
    }