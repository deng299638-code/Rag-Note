from uuid import UUID

from fastapi import APIRouter, Depends

from schemas.common_schemas import ApiResponse
from schemas.note_template_schemas import NoteTemplateResponse, NoteTemplateCreate, NoteTemplateUpdate, \
    NoteTemplateReorder
from services.note_template_service import NoteTemplateService, get_note_template_service
from utils.JWT import get_current_user_id

note_template_router = APIRouter(prefix="/note-template",tags=["note-template"])


@note_template_router.get("/list",response_model=ApiResponse[list[NoteTemplateResponse]])
async def list_templates(
        user_id : int = Depends(get_current_user_id),
        service :  NoteTemplateService = Depends(get_note_template_service),
):

    templates = await service.list(user_id)
    return {
        "code": 200,
        "message": "获取模板列表成功",
        "data": templates,
    }


@note_template_router.post("/create",response_model=ApiResponse[NoteTemplateResponse])
async def create_template(
        req:NoteTemplateCreate,
        user_id: int = Depends(get_current_user_id),
        service: NoteTemplateService = Depends(get_note_template_service),
):
    template = await service.create_template(req,user_id)
    return {
        "code": 201,
        "message": "创建模板成功",
        "data": template,
    }

@note_template_router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    user_id : int = Depends(get_current_user_id),
    service: NoteTemplateService = Depends(get_note_template_service),
):
    await service.delete(user_id,template_id)


@note_template_router.put("/reorder",)
async def reorder_templates(
        ids:NoteTemplateReorder,
        user_id : int = Depends(get_current_user_id),
        service : NoteTemplateService = Depends(get_note_template_service)
):
    await service.reorder(ids.ids,user_id)
    return {
        "code":200,
        "message":"模板排序成功",
        "data":None,
    }


@note_template_router.put("/{template_id}",response_model=ApiResponse[NoteTemplateResponse])
async def update_template(
        template_id: str,
        payload: NoteTemplateUpdate,
        user_id : int = Depends(get_current_user_id),
        service: NoteTemplateService = Depends(get_note_template_service)
):

    template = await service.update_template(template_id,user_id,payload)
    return {
        "code" : 200,
        "message": "模板更新成功",
        "data": template,
    }



