import mimetypes
from typing import Annotated
from fastapi.responses import FileResponse
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from starlette.responses import StreamingResponse
from pathlib import Path
from schemas.common_schemas import ApiResponse
from services.knowledge_service import get_knowledge_service, KnowledgeService
from utils.JWT import get_current_user_id
from utils.image_extractor import get_image_file_path

Knowledge_Router = APIRouter(prefix="/knowledge",tags=["knowledge"],)

@Knowledge_Router.post("/add/single",response_model=ApiResponse[dict],)
async def add_single_file(file:UploadFile = File(...),user_id : int = Depends(get_current_user_id),service :KnowledgeService = Depends(get_knowledge_service)):
    try:
        result = await service.add_single(file,user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    return {
        "code": 201,
        "message":"文件上传成功",
        "data": result,
    }

@Knowledge_Router.post("/add/multiple",response_model=ApiResponse[list[dict]])
async def add_multiple_files(files : list[UploadFile],user_id : int = Depends(get_current_user_id),service :KnowledgeService = Depends(get_knowledge_service)):
    results = await service.add_multiple(files,user_id)
    return {
        "code":200,
        "message": "批量上传处理完成",
        "data":results,
    }
@Knowledge_Router.post("/add/multiple/stream")
async def add_multiple_stream(files : Annotated[list[UploadFile],File(...)],user_id : int = Depends(get_current_user_id),service:KnowledgeService = Depends(get_knowledge_service)):
    return StreamingResponse(
        service.add_multiple_stream(files,user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

@Knowledge_Router.get("/list",response_model=ApiResponse[dict])
async def list_knowledge_documents(user_id:int = Depends(get_current_user_id),service:KnowledgeService = Depends(get_knowledge_service)):
    documents = await service.list_documents(user_id)
    return {
        "code":200,
        "message":"获取知识库列表成功",
        "data":{
            "documents":documents,
            "total_count":len(documents),
        }
    }

@Knowledge_Router.get("/detail",response_model=ApiResponse[dict])
async def get_knowledge_detail(filename:str = Query(...),user_id : int = Depends(get_current_user_id),service:KnowledgeService = Depends(get_knowledge_service)):
    try:
        detail = await service.get_document(filename,user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    return {
        "code":200,
        "message":"获取文档详情成功",
        "data":detail,
    }


@Knowledge_Router.delete("/delete/filename")
async def delete_knowledge_filename(filename : str = Query(...),user_id:int = Depends(get_current_user_id),service:KnowledgeService = Depends(get_knowledge_service)):
    deleted = await service.delete_by_filename(filename,user_id)
    return {
        "code": 200,
        "message": (
            "文档删除成功"
            if deleted
            else "未找到文档"
        ),
        "data": {
            "deleted": deleted,
        },
    }


@Knowledge_Router.delete("/clean")
async def clean_knowledge(user_id:int = Depends(get_current_user_id),service:KnowledgeService = Depends(get_knowledge_service)):
    deleted_count = await service.delete_user_vectors(user_id)
    return {
        "code": 200,
        "message": "知识库清理完成",
        "data": {
            "deleted_count": deleted_count,
        },
    }

@Knowledge_Router.get("/image/{md5}/{filename}")
async def get_knowledge_image(md5:str,filename:str,user_id: int = Depends(get_current_user_id)):
    #防止用户传入图片路径
    if Path(filename).name != filename:
        raise HTTPException(
            status_code=400,
            detail="非法图片文件名",
        )

    image_path = get_image_file_path(str(user_id), md5, filename)
    if not image_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="图片不存在",
        )

    media_type,_ = mimetypes.guess_type(str(image_path))#根据文件名后缀猜类型

    return FileResponse(
        path=image_path,
        media_type=media_type or "application/octet-stream",
    )

@Knowledge_Router.get("/add/multiple/{task_id}/progress",response_model=ApiResponse[dict],)
async def get_multiple_upload_progress(task_id:str,user_id : int =Depends(get_current_user_id),service: KnowledgeService = Depends(get_knowledge_service),):
    try:
        progress = await service.get_upload_progress(user_id, task_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )
    return {
        "code": 200,
        "message": "获取上传进度成功",
        "data": progress,
    }