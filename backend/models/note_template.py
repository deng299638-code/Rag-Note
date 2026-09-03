import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.user import Base


def generate_template_id() -> str:
    return str(uuid.uuid4())


class NoteTemplate(Base):
    __tablename__ = "note_templates"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_template_id,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    icon: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="FileText",
    )

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="",
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    tags: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )