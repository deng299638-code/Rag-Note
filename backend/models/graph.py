import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.user import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


class GraphBuildTask(Base):
    """
    待执行的图谱构建任务。

    任务状态：
    pending -> running -> completed
                     -> failed
    """

    __tablename__ = "graph_build_tasks"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "source_type",
            "source_id",
            name="uq_graph_task_user_source",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )

    user_id: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="note",
    )

    source_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    payload: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    force: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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


class GraphExtractLog(Base):
    """记录每篇笔记上一次实体抽取的结果。"""

    __tablename__ = "graph_extract_logs"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "source_type",
            "source_id",
            name="uq_graph_log_user_source",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )

    user_id: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="note",
    )

    source_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )

    entity_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    relation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )