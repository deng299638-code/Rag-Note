from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from models.note_template import NoteTemplate

class NoteTemplateRepository:
    def __init__(self,db:AsyncSession):
        self.db = db


    async def list_by_user(self,user_id : int):
        result = await self.db.scalars(select(NoteTemplate).where(NoteTemplate.user_id == user_id)
                                            .order_by(NoteTemplate.sort_order.asc(),NoteTemplate.created_at.asc(),)
                                     )
        templates = result.all()
        return templates

    async def get_next_sort_order(self,user_id:int):
        maximum = await self.db.scalar(
            select(func.max(NoteTemplate.sort_order))
            .where(
                NoteTemplate.user_id == user_id,
            )
        )

        if not maximum:
            maximum = 0

        return maximum + 1

    async def create_template(self,template:NoteTemplate):
        self.db.add(template)
        await self.db.flush()
        await self.db.refresh(template)
        return template