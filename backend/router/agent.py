from typing import Annotated

from fastapi import APIRouter, Depends, Query,status
from fastapi.responses import StreamingResponse
from schemas.agent_schemas import (
    AgentQueryRequest,
    ChatSessionListResponse,
    ChatSessionQueryParams, ChatMessageQueryParams, ChatMessageListResponse,
)
from schemas.common_schemas import ApiResponse
from services.AgentService import (
    AgentService,
    get_agent_service,
)
from services.chat_service import ChatService, get_chat_service
from utils.JWT import get_current_user_id


agent_router = APIRouter(
    prefix="/chat",
    tags=["agent"],
)



@agent_router.post("/agent/query/stream",)
async def query_agent_stream(
    payload: AgentQueryRequest,
    user_id: int = Depends(get_current_user_id),
    service: AgentService = Depends(
        get_agent_service
    ),
):
    session_id,messages = await service.prepare_stream(payload,user_id)

    return StreamingResponse(
        service.stream_response(
            session_id, messages,user_id
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@agent_router.get("/sessions",response_model= ApiResponse[ChatSessionListResponse])
async def list_chat_session(
        params:Annotated[ChatSessionQueryParams,Query()],
        user_id : int = Depends(get_current_user_id),
        service : ChatService = Depends(get_chat_service),
):
    sessions,total = await service.list_session(user_id,params.page,params.page_size)
    total_pages = (total + params.page_size - 1 ) // params.page_size

    return {
        "code" : 200,
        "message" : "获取会话列表成功",
        "data":{
            "sessions": sessions,
            "total": total,
            "page": params.page,
            "page_size": params.page_size,
            "total_pages": total_pages,
        }
    }

@agent_router.delete("/sessions/{session_id}",status_code=status.HTTP_204_NO_CONTENT,)
async def delete_chat_session(
    session_id: str,
    user_id: int = Depends(get_current_user_id),
    service: ChatService = Depends(get_chat_service),
):
    await service.delete_session(
        user_id=user_id,
        session_id=session_id,
    )



@agent_router.get("/sessions/{session_id}/messages",response_model=ApiResponse[ChatMessageListResponse],)
async def list_chat_messages(
    session_id: str,
    params: Annotated[ChatMessageQueryParams, Query()],
    user_id: int = Depends(get_current_user_id),
    service: ChatService = Depends(get_chat_service),
):
    messages, total = await service.list_messages(
        user_id=user_id,
        session_id=session_id,
        page=params.page,
        page_size=params.page_size,
    )

    total_pages = (
        total + params.page_size - 1
    ) // params.page_size

    return {
        "code": 200,
        "message": "获取会话消息成功",
        "data": {
            "messages": messages,
            "total": total,
            "page": params.page,
            "page_size": params.page_size,
            "total_pages": total_pages,
        },
    }

