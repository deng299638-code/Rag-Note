from fastapi import HTTPException,status
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from exceptions.chat_exception import ChatSessionNotFoundError
from models.chat import ChatSession, ChatMessage

DEFAULT_SESSION_TITLE = "新的对话"
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

    async def get_or_create_session(self, session_id: str, user_id: int):
        session = await self.db.scalar(select(ChatSession).where(
            ChatSession.id == session_id,
        ))

        if session is not None:
            if session.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="当前会话不属于你",
                )
            return session

        session =  ChatSession(
            id=session_id,
            user_id=user_id,
            title=DEFAULT_SESSION_TITLE,
        )

        self.db.add(session)
        await self.db.flush()
        return session
    async def get_history(self,session_id:str,user_id:int):
        session = await self.get_or_create_session(session_id, user_id)
        result = await self.db.scalars(
            select(ChatMessage).where(ChatMessage.session_id == session.id)
            .order_by(
                ChatMessage.created_at.asc(),
                ChatMessage.id.asc(),
            )

        )

        messages = result.all()
        history : list[tuple[str,str]] = []
        index,length = 0,len(messages)
        while index < length:
            current = messages[index]
            if (current.role == "user" and index + 1 < length and messages[index + 1].role == "assistant"):
                history.append(
                    (
                        current.content,
                        messages[index+1].content,
                    )
                )
                index += 2
            else:
                index += 1
        return history

    async def save_turn(self,session_id:str,user_id:int,user_message:str,assistant_message:str,):
        session = await self.get_or_create_session(session_id, user_id)

        if session.title in {"新对话",DEFAULT_SESSION_TITLE}:
            title = user_message[:30].strip()
            if len(user_message) > 30:
                title += "..."

            session.title = title

        self.db.add_all(
            [
                ChatMessage(session_id=session.id,
                    role="user",
                    content=user_message,
                ),
                ChatMessage(
                    session_id=session.id,
                    role="assistant",
                    content=assistant_message,
                ),
            ]
        )

        await self.db.flush()
        await self.touch_session(session.id)
        await self.db.commit()

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

        return list(reversed(messages.all()))


    async def touch_session(self,session_id : str):

        await self.db.execute(
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(updated_at=func.now())
        )

    async def delete(self,session : ChatSession):

        await self.db.delete(session)

