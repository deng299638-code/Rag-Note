from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from exceptions.chat_exception import ChatSessionNotFoundError
from models.chat import ChatSession, ChatMessage


class  ChatRepository:
    def __init__(self,db:AsyncSession):
        self.db = db


    async def list_sessions(self,user_id : int , page : int ,page_size : int):
        base = select(ChatSession).where(
            ChatSession.user_id == user_id,
        )

        result = await self.db.scalars(
            base.order_by(
                ChatSession.updated_at.desc()
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        total = await self.db.scalar(select(func.count()).select_from(base.subquery()))

        return result.all(),total


    async def get_owned_session(self,session_id: str,user_id : int):

        session = await self.db.scalar(select(ChatSession).where(
            ChatSession.user_id == user_id,
            ChatSession.id == session_id,
        ))

        if not session:
            raise ChatSessionNotFoundError(session_id)
        return session

    async def list_messages(self,session_id : str,page : int , page_size : int):
        statement = select(ChatMessage).where(
            ChatMessage.session_id == session_id,
        )

        total = await self.db.scalar(
            select(func.count()).select_from(statement.subquery())
        )

        result = await self.db.scalars(
            statement
            .order_by(ChatMessage.created_at.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        return list(result.all()), total or 0


    async def create_session(self,user_id : int , title : str):
        session = ChatSession(
            user_id = user_id,
            title = title
        )
        self.db.add(session)
        await self.db.flush()
        return session


    async def create_message(self,session_id : str , content : str , role : str):

        message = ChatMessage(
            session_id = session_id,
            content = content,
            role = role,
        )

        self.db.add(message)
        await self.db.flush()
        return message


    async def get_recent_message(self,session_id : str , limit : int = 20):

        messages = await self.db.scalars(select(ChatMessage).where(
            ChatMessage.session_id == session_id
            ).order_by(
            ChatMessage.created_at.desc(),
            ChatMessage.id.desc(),
            ).limit(limit)
        )

        return messages.all()


    async def touch_session(self,session_id : str):

        await self.db.execute(
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(updated_at=func.now())
        )

    async def delete(self,session : ChatSession):

        await self.db.delete(session)

