import asyncio
import json
import os
import logging
from fastapi import Depends
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from db.db_config import get_db
from exceptions.chat_exception import ChatSessionNotFoundError
from repository.chat import ChatRepository
from repository.note import NoteRepository
from router.user import get_current_user
from schemas.agent_schemas import AgentQueryRequest

logger = logging.getLogger(__name__)


class AgentService:

    def __init__(self,db:AsyncSession,repository : ChatRepository,note_repository: NoteRepository,):
        self.chat_model = ChatOpenAI(
            model = os.getenv(
                "OPENAI_MODEL_NAME",
                "qwen3.8-max"
            ),
            api_key= os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            streaming= True,
            temperature= 0.7,
        )
        self.db = db
        self.note_repository = note_repository
        self.repository = repository


    #准备聊天记录 无会话记录 -> 创建新会话 -> 创建聊天信息 -> 加载会话记录
    async def prepare_stream(self,payload : AgentQueryRequest, user_id : int,):
        if payload.session_id:
            session = await self.repository.get_owned_session(payload.session_id,user_id)
            if session is None:
                raise ChatSessionNotFoundError(payload.session_id)

        else:
            title = " ".join(payload.query.split())[:50]
            session = await self.repository.create_session(user_id, title or "新对话")

        await self.repository.create_message(session.id,payload.query,role="user")

        await self.db.commit()

        #决定笔记来源

        messages = await self.repository.get_recent_message(session.id)

        return session.id,self.to_model_messages(messages)


    async def stream_response(
            self,
            session_id : str,
            messages : list,
    ):

        think_event = {
            "type": "thinking",
            "stage": "prepare",
            "content": "正在分析你的问题",
            "session_id": session_id,
        }

        yield self._format_sse(think_event)

        try:
            content_parts : list[str] = []
            async for chunk in self.chat_model.astream(messages):
                content = chunk.content
                if not isinstance(content,str) or not content:
                    continue
                content_parts.append(content)
                yield self._format_sse(
                    {
                        "type": "response",
                        "content": content,
                        "session_id": session_id,
                    }
                )

            answer = "".join(content_parts)

            await self.repository.create_message(session_id,answer,"assistant")

            await self.db.commit()

            yield self._format_sse({
                "type": "done",
                "session_id": session_id,
            })
        except Exception as e:
            await self.db.rollback()
            logger.exception(
                "生成或保存 AI 回复失败，session_id=%s",
                session_id,
            )
            yield self._format_sse({
                "type": "error",
                "content": "回答生成失败，请稍后重试",
                "session_id": session_id,
            })
            yield self._format_sse({
                "type": "done",
                "session_id": session_id,
            })
    @staticmethod
    def to_model_messages(messages):

        system_content = (
            "你是用户的智能笔记助手。"
            "优先依据用户提供的笔记回答。"
            "笔记中没有依据时，请明确说明。"
        )

        return [
            SystemMessage(system_content),
            *[
                HumanMessage(message.content)
                if message.role == "user"
                else AIMessage(message.content)
                for message in messages
            ],
        ]
    @staticmethod  #静态方法无self
    def _format_sse(data: dict):
        return (
            f"data: {json.dumps(data,ensure_ascii=False)}"
            "\n\n"
        )


async def get_agent_service(db = Depends(get_db)):

    repository = ChatRepository(db)
    note_repository = NoteRepository(db)
    return AgentService(db,repository,note_repository)

