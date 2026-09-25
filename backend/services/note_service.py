import asyncio
import logging
from typing import List

from langchain_core.documents import Document
from sqlalchemy import func, or_, select,update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from db.db_config import get_db
from exceptions.note_exceptions import NoteNotFoundError
from models.note import Note
from rag.note_hybrid_retriever import NoteHybridRetriever
from rag.note_vector_store import get_note_vector_store
from schemas.note_schemas import NoteCreate, NoteUpdate, NoteQueryParams

logger = logging.getLogger(__name__)

class NoteService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: int,
        payload: NoteCreate,
    ) -> Note:
        note = Note(
            user_id=user_id,
            **payload.model_dump(),
        )

        self.db.add(note)
        await self.db.commit()
        await self.db.refresh(note)

        try:
            await self._upsert_note_vecto(note)
        except Exception:
            logger.exception(
                "笔记向量写入失败，note_id=%s",
                note.id,
            )
        finally:
            await NoteHybridRetriever.invalidate_user(user_id)

        return note

    async def list(
        self,
        user_id: int,
        params: NoteQueryParams,
    ) -> tuple[list[Note], int]:
        conditions = [Note.user_id == user_id]

        if params.category:
            conditions.append(Note.category == params.category)

        if params.tag:
            conditions.append(Note.tags.contains([params.tag]))

        statement = select(Note).where(*conditions)

        total = await self.db.scalar(
            select(func.count()).select_from(
                statement.subquery()
            )
        )

        result = await self.db.scalars(
            statement
            .order_by(
                Note.is_pinned.desc(),
                Note.updated_at.desc(),
            )
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
        )

        return list(result.all()), total or 0

    async def search(
        self,
        user_id: int,
        keyword: str,
    ):
        pattern = f"%{keyword}%"

        statement = select(Note).where(
            Note.user_id == user_id,
            or_(
                Note.title.ilike(pattern),
                Note.content.ilike(pattern),
            ),
        )

        total = await self.db.scalar(
            select(func.count()).select_from(
                statement.subquery()
            )
        )

        result = await self.db.scalars(
            statement.order_by(Note.updated_at.desc())
        )

        return list(result.all()), total or 0

    async def get_owned(
        self,
        note_id: int,
        user_id: int,
    ) -> Note:
        note = await self.db.scalar(
            select(Note).where(
                Note.id == note_id,
                Note.user_id == user_id,
            )
        )

        if note is None:
            raise NoteNotFoundError(note_id)
        return note

    async def update(
        self,
        note_id: int,
        user_id: int,
        payload: NoteUpdate,
    ) -> Note:
        note = await self.get_owned(note_id, user_id)

        update_data = payload.model_dump(
            exclude_unset=True
        )

        for field, value in update_data.items():
            setattr(note, field, value)

        await self.db.commit()
        await self.db.refresh(note)

        if "content" in update_data or "title" in update_data:
            try:
                await self._upsert_note_vecto(note)
            except Exception:
                logger.exception(
                    "笔记向量更新失败，note_id=%s",
                    note.id,
                )
            finally:
                await NoteHybridRetriever.invalidate_user(user_id)

        return note

    async def delete(
        self,
        note_id: int,
        user_id: int,
    ) -> None:
        note = await self.get_owned(note_id, user_id)

        await self.db.delete(note)
        await self.db.commit()

        try:
            await self._delete_note_vector(note_id, user_id)
        except Exception:
            logger.exception(
                "笔记向量删除失败，note_id=%s",
                note_id,
            )
        finally:
            await NoteHybridRetriever.invalidate_user(user_id)

    async def toggle_pin(
        self,
        note_id: int,
        user_id: int,
    ) -> Note:
        note = await self.get_owned(note_id, user_id)

        note.is_pinned = not note.is_pinned

        await self.db.commit()
        await self.db.refresh(note)

        return note
    async def batch_update_category(self,ids:List[int],user_id:int,default:str):
        statement = (
            update(Note).where(
                Note.id.in_(ids),
                Note.user_id == user_id,
            )
            .values(category = default)
        )
        result = await self.db.execute(statement)
        await self.db.commit()
        return result.rowcount # type: ignore

    async def get_stats(self,user_id: int,):
        category_result = await self.db.execute(
            select(
                Note.category,
                func.count(Note.id).label("count"),
            )
            .where(
                Note.user_id == user_id,
                Note.category.is_not(None),
            )
            .group_by(Note.category)
            .order_by(func.count(Note.id).desc())
        )

        categories = [
            {
                "category": category,
                "count": count,
            }
            for category, count in category_result.all()
        ]

        total = await self.db.scalar(
            select(func.count(Note.id)).where(
                Note.user_id == user_id,
            )
        )

        uncategorized = await self.db.scalar(
            select(func.count(Note.id)).where(
                Note.user_id == user_id,
                Note.category.is_(None),
            )
        )

        return {
            "total": total or 0,
            "categories": categories,
            "uncategorized": uncategorized or 0,
        }

    async def _upsert_note_vecto(self,note:Note):
        document = Document(
            page_content= note.content ,
            metadata = {
                "user_id" : note.user_id,
                "note_id" : note.id,
                "doc_type" : "note",
                "title" : note.title,
            }
        )

        store = get_note_vector_store().store

        collection_exists = await asyncio.to_thread(
            store.client.has_collection,
            store.collection_name,
        )
        if collection_exists:
            await asyncio.to_thread(
                store.delete,
                where = {
                    "note_id":note.id,
                    "user_id": note.user_id,
                    "doc_type": "note"
                }
            )

        await asyncio.to_thread(
            store.add_documents,
            [document],
            ids = [str(note.id)]
        )


    async def _delete_note_vector(self,note_id:int,user_id : int):
        store = get_note_vector_store().store

        collection_exists = await asyncio.to_thread(
            store.client.has_collection,
            store.collection_name,
        )
        if collection_exists:
            await asyncio.to_thread(
                store.delete,
                where = {
                    "note_id":note_id,
                    "user_id":user_id,
                    "doc_type":"note"
                }
            )

def get_note_service(
    db: AsyncSession = Depends(get_db),
):
    return NoteService(db)
