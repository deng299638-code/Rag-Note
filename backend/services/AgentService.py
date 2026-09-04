import asyncio
import json
import os
import uuid
from fastapi import Depends
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from db.db_config import get_db
from router.user import get_current_user
from schemas.agent_schemas import AgentQueryRequest


class AgentService:

    def __init__(self):
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

    async def stream_response(
            self,
            payload: AgentQueryRequest,
            user_id: int,
    ):
        session_id = payload.session_id or str(uuid.uuid4())

        think_event = {
            "type": "thinking",
            "stage": "prepare",
            "content": "正在分析你的问题",
            "session_id": session_id,
        }

        yield self._format_sse(think_event)

        try:
            async for chunk in self.chat_model.astream(
                [
                    HumanMessage(
                        payload.query
                    )
                ]
            ):

                content = chunk.content
                yield self._format_sse(
                    {
                        "type": "response",
                        "content": content,
                        "session_id": session_id,
                    }
                )
            yield self._format_sse({
                "type": "done",
                "session_id": session_id,
            })
        except Exception as e:
            yield self._format_sse({
                "type": "error",
                "content": str(e),
                "session_id": session_id,
            })

            yield self._format_sse({
                "type": "done",
                "session_id": session_id,
            })




    @staticmethod  #静态方法无self
    def _format_sse(data: dict):
        return (
            f"data: {json.dumps(data,ensure_ascii=False)}"
            "\n\n"
        )


async def get_agent_service(db = Depends(get_db)):
    return AgentService()

