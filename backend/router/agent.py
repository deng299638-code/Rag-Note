



from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from schemas.agent_schemas import AgentQueryRequest
from services.AgentService import (
    AgentService,
    get_agent_service,
)
from utils.JWT import get_current_user_id


agent_router = APIRouter(
    prefix="/chat",
    tags=["agent"],
)


@agent_router.post(
    "/agent/query/stream",
)
async def query_agent_stream(
    payload: AgentQueryRequest,
    user_id: int = Depends(get_current_user_id),
    service: AgentService = Depends(
        get_agent_service
    ),
):
    return StreamingResponse(
        service.stream_response(
            payload,user_id
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )