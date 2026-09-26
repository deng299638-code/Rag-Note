
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from schemas.common_schemas import ApiResponse
from schemas.writing_schemas import AutocompleteRequest, WritingAssistRequest
from services.writing_assistant_service import WritingAssistantService, get_writing_Service
from utils.JWT import get_current_user_id

WritingRouter = APIRouter(prefix="/writing",tags=["writing"],)


@WritingRouter.post("/autocomplete",response_model=ApiResponse[dict])
async def autocomplete(payload:AutocompleteRequest,user_id : int = Depends(get_current_user_id),service:WritingAssistantService = Depends(get_writing_Service)):
    completion = await service.autocomplete(payload.context)

    return {
        "code":200,
        "message":"补全成功",
        "data":{
            "completion": completion,
        }
    }


@WritingRouter.post("/assist/stream")
async def assist_stream(payload:WritingAssistRequest,user_id:int = Depends(get_current_user_id),service:WritingAssistantService = Depends(get_writing_Service)):
    return StreamingResponse(
        service.assist_stream(payload.context,payload.action,user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )