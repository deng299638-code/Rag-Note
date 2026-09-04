import uuid
from typing import List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from exceptions.note_template_exceptions import TemplateNotFoundError
from models.note_template import NoteTemplate





DEFAULT_TEMPLATES = [
    {
        "name": "空白笔记",
        "icon": "FileText",
        "category": "",
        "title": "",
        "content": "",
        "tags": [],
    },
    {
        "name": "会议纪要",
        "icon": "Users",
        "category": "work",
        "title": "会议纪要 - ",
        "content": "## 会议信息\n- **时间**：\n- **参与人**：\n- **主题**：\n\n## 会议内容\n\n\n## 待办事项\n- [ ] \n",
        "tags": ["会议"],
    },
    {
        "name": "学习笔记",
        "icon": "GraduationCap",
        "category": "study",
        "title": "",
        "content": "## 学习目标\n\n\n## 核心内容\n\n\n## 总结与反思\n\n",
        "tags": ["学习"],
    },
    {
        "name": "日记",
        "icon": "BookOpen",
        "category": "life",
        "title": "",
        "content": "## 今日记录\n\n\n## 心情\n\n\n## 明日计划\n- [ ] \n",
        "tags": ["日记"],
    },
    {
        "name": "项目计划",
        "icon": "ListTodo",
        "category": "project",
        "title": "",
        "content": "## 项目概述\n\n\n## 目标\n- [ ] \n\n## 里程碑\n| 阶段 | 内容 | 截止日期 | 状态 |\n|------|------|----------|------|\n| 1    |      |          | 待开始 |\n\n## 备注\n\n",
        "tags": ["项目"],
    },
    {
        "name": "读书笔记",
        "icon": "BookMarked",
        "category": "study",
        "title": "",
        "content": "## 书籍信息\n- **书名**：\n- **作者**：\n\n## 核心观点\n\n\n## 精彩摘录\n\n\n## 读后感\n\n",
        "tags": ["读书"],
    },
]



class NoteTemplateRepository:
    def __init__(self,db:AsyncSession):
        self.db = db

    async def create_default_template(self,user_id):
        for i,base in enumerate(DEFAULT_TEMPLATES):
            template = NoteTemplate(
                id = str(uuid.uuid4()),
                user_id = user_id,
                name=base["name"],
                icon=base["icon"],
                category=base["category"],
                title=base["title"],
                content=base["content"],
                tags=base["tags"],
                is_default=True,
                sort_order=i,

            )

            self.db.add(template)
            await self.db.commit()


    async def list_by_user(self,user_id : int):

        num = await self.db.scalar(select(func.count()).where(NoteTemplate.user_id == user_id))
        if num == 0:
            await self.create_default_template(user_id)

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


    async def get_owned_template(self,user_id:int,template_id:str):
        template = await self.db.scalar(select(NoteTemplate).where(NoteTemplate.user_id == user_id,NoteTemplate.id == template_id))
        if not template:
            raise TemplateNotFoundError(template_id)
        return template

    async def update(self,template:NoteTemplate):
        await self.db.flush()
        await self.db.refresh(template)

        return template


    async def list_by_ids(self,ids:List,user_id : int):
        templates = await self.db.scalars(select(NoteTemplate).where(
            NoteTemplate.user_id == user_id,
            NoteTemplate.id.in_(ids)
        ))

        return templates.all()