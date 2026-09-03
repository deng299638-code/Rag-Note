from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.db_config import get_db
from models.note_template import NoteTemplate
from repository.note_template import NoteTemplateRepository
from schemas.note_template_schemas import NoteTemplateCreate


class NoteTemplateService:
    def __init__(self,repository: NoteTemplateRepository,db:AsyncSession):
        self.repository = repository
        self.db = db

    async def list(self,user_id : int):
        return await self.repository.list_by_user(user_id)

    async def create_template(self,req:NoteTemplateCreate,user_id : int):
        sort_order = await self.repository.get_next_sort_order(user_id)
        template = NoteTemplate(
            user_id=user_id,
            **req.model_dump(),
            is_default=False,
            sort_order=sort_order,
        )

        await self.repository.create_template(template)
        await self.db.commit()
        await self.db.refresh(template)
        return template


def get_note_template_service(db:AsyncSession = Depends(get_db)):
    repository = NoteTemplateRepository(db)

    return NoteTemplateService(repository,db,)