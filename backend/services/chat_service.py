from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from db.db_config import get_db
from exceptions.chat_exception import ChatSessionNotFoundError
from models.chat import ChatSession
from repository.chat import ChatRepository


class ChatService:
    def __init__(self, chatRepository:ChatRepository,db:AsyncSession):
        self.chatRepository = chatRepository
        self.db = db

    async def list_session(self,user_id : int ,page : int ,page_size : int):


        return await self.chatRepository.list_sessions(
            user_id=user_id,
            page=page,
            page_size=page_size,
        )

    async def list_messages(self,user_id :int,session_id : str, page : int , page_size : int ):
        session = await self.chatRepository.get_owned_session(
            session_id=session_id,
            user_id=user_id,
        )

        if session is None:
            raise ChatSessionNotFoundError(session_id)

        return await self.chatRepository.list_messages(
            session_id=session_id,
            page=page,
            page_size=page_size,
        )

    async def delete_session(self,user_id : int ,session_id : str):
        session = await self.chatRepository.get_owned_session(session_id,user_id)
        await self.chatRepository.delete(session)
        await self.db.commit()



def get_chat_service(
    db: AsyncSession = Depends(get_db),
):
    chatRepository = ChatRepository(db)
    return ChatService(chatRepository,db)