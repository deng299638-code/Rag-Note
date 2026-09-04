from typing import List

from fastapi import Depends
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from db.db_config import get_db
from exceptions.note_template_exceptions import InvalidTemplateOrderError
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

    async def delete(self,user_id : int, template_id : str):
        template = await self.repository.get_owned_template(user_id,template_id)
        await self.db.delete(template)
        await self.db.commit()


    async def update_template(self,template_id,user_id,payload):

        template = await self.repository.get_owned_template(user_id,template_id)

        update_data = payload.model_dump(exclude_unset= True)
        for field,value in update_data.items():
            setattr(template,field,value)

        await self.repository.update(template)
        await self.db.commit()
        return template


    async def reorder(self,ids:List,user_id : int):
        if len(ids) != len(set(ids)):
            raise InvalidTemplateOrderError(
                "模板 ID 不能重复"
            )

        templates = await self.repository.list_by_ids(ids,user_id)

        for index,template in enumerate(templates):
            template.sort_order = index

        await self.db.commit()


def get_note_template_service(db:AsyncSession = Depends(get_db)):
    repository = NoteTemplateRepository(db)

    return NoteTemplateService(repository,db,)