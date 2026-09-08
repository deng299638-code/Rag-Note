import asyncio
import json
import os
import logging
from fastapi import Depends
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from db.db_config import get_db
from exceptions.chat_exception import ChatSessionNotFoundError
from rag.NoteRagService import NoteRagService
from rag.tools import build_note_tools
from repository.chat import ChatRepository
from repository.note import NoteRepository
from schemas.agent_schemas import AgentQueryRequest
from services.note_service import NoteService

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
        self.note_rag_service = NoteRagService()
        self.note_service = NoteService(db)
        self.db = db
        self.note_repository = note_repository
        self.repository = repository



    def _build_agent_executor(self,user_id: int):
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system","{system_prompt}"),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        tools = build_note_tools(self.note_service,self.note_rag_service,user_id)
        agent = create_tool_calling_agent(self.chat_model,tools,prompt)

        return AgentExecutor(
            agent =agent,
            tools=tools,
            max_iterations=3,
            handle_parsing_errors=True,#大模型输出格式错乱、JSON 解析失败、tool_call 格式不对的时候，不会直接抛异常崩溃
            return_intermediate_steps=True,#中间步可视化
            stream_runnable=False,
        )

    #准备聊天记录 无会话记录 -> 创建新会话 -> 创建聊天信息 -> 加载会话记录
    async def prepare_stream(self,payload : AgentQueryRequest, user_id : int,):
        if payload.session_id:
            session = await self.repository.get_owned_session(payload.session_id,user_id)
            if session is None:
                raise ChatSessionNotFoundError(payload.session_id)

        else:
            title = " ".join(payload.query.split())[:50]
            session = await self.repository.create_session(user_id, title or "新对话")

        await self.repository.create_message(session.id,payload.query,role="user") #保存本次聊天信息

        await self.db.commit()

        try:
            rag_content = await self.note_rag_service.retriever_context(payload.query,user_id) #从向量数据库检索
        except Exception as e:
            logger.error(f"向量数据检索错误: {e}", exc_info=True)
            rag_content = ""

        messages = await self.repository.get_recent_message(session.id) #加载本轮对话的聊天记录

        return session.id,self.to_model_messages(messages,rag_content)


    async def stream_response(
            self,
            session_id : str,
            messages : list,
            user_id : int,
    ):

        think_event = {
            "type": "thinking",
            "stage": "prepare",
            "content": "正在分析你的问题",
            "session_id": session_id,
        }

        yield self._format_sse(think_event)

        try:
            system_prompt = messages[0].content
            chat_history = messages[1:-1]
            query = messages[-1].content

            agent_executor = self._build_agent_executor(user_id)
            answer = ""
            agent_input = {
                "input": query,
                "chat_history": chat_history,
                "system_prompt": system_prompt,
            }
            async for chunk in agent_executor.astream_events(agent_input,version = "v2"):

                #List[(AgentAction, tool_result)]
                event_type = chunk["event"]
                tool_name = chunk["name"]

                if event_type == "on_tool_start":
                    yield self._format_sse({
                        "type": "thinking",
                        "stage": "tool_start",
                        "content": f"正在调用工具：{tool_name}",
                        "session_id": session_id,
                    })

                elif event_type == "on_tool_end":
                    yield self._format_sse({
                        "type": "thinking",
                        "stage": "tool_end",
                        "content": f"工具执行完成：{tool_name}",
                        "session_id": session_id,
                    })

                elif (
                        event_type == "on_chain_end"
                        and tool_name == "AgentExecutor"
                ):
                    result = chunk["data"].get("output", {})

                    if isinstance(result, dict):
                        answer = result.get("output", "")

            answer = answer or "抱歉，我暂时无法生成回答。"
            await self.repository.create_message(session_id, answer, "assistant")
            await self.db.commit()

            yield self._format_sse({
                "type": "response",
                "content": answer,
                "session_id": session_id,
            })

            yield self._format_sse({
                "type": "done",
                "session_id": session_id,
            })
        except asyncio.CancelledError:
            await self.db.rollback()
            logger.info(
                "客户端断开，已取消 Agent 请求，session_id=%s",
                session_id,
            )
            raise

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
    def to_model_messages(messages,rag_content):

        system_content = (
            "你是用户的智能笔记助手。"
            "优先依据参考笔记回答。"
            "笔记中没有相关信息时，请明确说明。"
            "当用户要求搜索、查找或列出笔记时，调用 search_notes。"
            "当用户询问笔记数量或分类统计时，调用 get_note_stats。"
            "仅当用户明确要求创建、保存或记录笔记时，调用 create_note。"
            "当用户要求查找某篇笔记的相似笔记或关联资料时，调用 get_related_notes。"
        )

        if rag_content:
            system_content += (
                "\n\n以下是检索到的相关笔记:\n\n"
                f"{rag_content}"
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

