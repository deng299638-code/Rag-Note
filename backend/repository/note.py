from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.note import Note


class NoteRepository:

    def __init__(self,db:AsyncSession):
        self.db = db

    async def get_owned_by_ids(self,ids:list[int],user_id:int):

        if not ids:
            return []
        notes = await self.db.scalars(select(Note).where(
            Note.id.in_(ids),
            Note.user_id == user_id
        ))

        return notes.all()


    async def search_notes(self,user_id :int,keyword: str,limit: int = 5):

        patten = f"%{keyword}%"

        result = await self.db.scalars(
            select(Note).where(
                Note.content.like(patten),
                Note.title.like(patten),
            ).order_by(Note.created_at.desc())
            .limit(limit)
        )

        return result.all()