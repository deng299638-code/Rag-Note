import io
import re

from urllib.parse import quote
import zipfile
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import Response
from typing import Annotated

from db.db_config import get_db
from exceptions.note_exceptions import NoteNotFoundError
from models.note import Note
from schemas.common_schemas import ApiResponse, NoteStatsData
from schemas.note_schemas import NoteCreate, NoteListResponse, NoteResponse, NoteUpdate, BatchIdsRequest, \
    BatchPinRequest, BatchCategoryRequest, NoteQueryParams, SearchResponse
from schemas.writing_schemas import AutocompleteRequest
from services.note_service import NoteService, get_note_service
from services.writing_assistant_service import WritingAssistantService, get_writing_Service
from utils.JWT import get_current_user_id

note_router = APIRouter(prefix="/note", tags=["note"])


@note_router.post("/create", response_model=ApiResponse[NoteResponse], status_code=status.HTTP_201_CREATED)
async def create_note(
    payload: NoteCreate,
    user_id: int = Depends(get_current_user_id),
    service: NoteService = Depends(get_note_service),
):
    note = await service.create(user_id,payload)
    return {
        "code": 201,
        "message":"笔记创建成功",
        "data":note,
    }


@note_router.get("/list", response_model=ApiResponse[NoteListResponse])
async def list_notes(
    params: Annotated[
            NoteQueryParams,
            Query(),
        ],
    user_id: int = Depends(get_current_user_id),
    service: NoteService = Depends(get_note_service),

):
    result,total = await service.list(user_id,params)
    total_page = (
        total+params.page_size - 1
    )// params.page_size
    return {
        "code": 200,
        "message": "获取笔记列表成功",
        "data": {
            "notes":result,
            "total":total,
            "page":params.page,
            "page_size":params.page_size,
            "total_pages":total_page
        }
    }

@note_router.get("/search",response_model=ApiResponse[SearchResponse])
async def search_notes(
        q: str = Query(...,min_length=1,description="搜索标题或正文"),
        service: NoteService = Depends(get_note_service),
        user_id : int = Depends(get_current_user_id)
):

    notes,total = await service.search(user_id,q)
    return {
        "code": 200,
        "message": "获取笔记列表成功",
        "data": {
            "notes":notes,
            "total":total,
        }
    }

@note_router.delete("/batch")
async def batch_detete_notes(
        req:BatchIdsRequest,
        user_id : int = Depends(get_current_user_id),
        db : AsyncSession = Depends(get_db)
):
    result = await db.scalars(select(Note).where(
        Note.user_id == user_id,
        Note.id.in_(req.ids)
    ))

    notes = result.all()

    if not notes:
        return {
            "deleted_count": 0,
            "message": "没有找到可删除的笔记",
        }
    for i in notes:
        await db.delete(i)
    await db.commit()

    return {
        "deleted_count": len(notes),
        "message": f"成功删除 {len(notes)} 篇笔记",
    }


@note_router.patch("/batch/pin")
async def batch_pin_notes(
        payload:BatchPinRequest,
        db : AsyncSession = Depends(get_db),
        user_id : int = Depends(get_current_user_id)
):
    result = await db.scalars(
        select(Note).where(
            Note.user_id == user_id,
            Note.id.in_(payload.ids),
        )
    )

    notes = result.all()
    for i in notes:
        i.is_pinned = payload.is_pinned

    await db.commit()

    return {
        "updated_count":len(notes),
        "is_pinned": payload.is_pinned,
        "message": (
            f"成功置顶 {len(notes)} 篇笔记"
            if payload.is_pinned
            else f"成功取消置顶 {len(notes)} 篇笔记"
        ),
    }

@note_router.get("/stats",response_model=ApiResponse[NoteStatsData])
async def get_note_stats(
        user_id : int = Depends(get_current_user_id),
        service: NoteService = Depends(get_note_service),
):
    stats = await service.get_stats(user_id)
    return {
        "code": 200,
        "message": "获取笔记统计成功",
        "data": stats,
    }


async def _get_owned_note(note_id: int ,user_id:int,db:AsyncSession = Depends(get_db)):
    note = await db.scalar(select(Note).where(Note.id == note_id,Note.user_id == user_id))
    if not note:
        raise NoteNotFoundError

    return note



@note_router.patch("/batch/category")
async def BatchCategoryRequest(req:BatchCategoryRequest,service:NoteService = Depends(get_note_service),user_id:int = Depends(get_current_user_id)):

    count = await service.batch_update_category(req.ids,user_id,req.category)
    return {
        "updated_count":count,
        "category":req.category,
        "message":f"成功修改{count}篇笔记"
    }



@note_router.get("/batch/export")
async def batch_export_notes(
    ids: str = Query(
        ...,
        description="笔记 ID，使用逗号分隔，例如 1,2,3",
    ),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):

    try:
        note_ids = [
            int(note_id.strip()) for note_id in ids.split(",") if note_id.strip()
        ]
    except ValueError:
        raise HTTPException(
            status_code= 400,
            detail="笔记 ID 必须是数字",
        )

    if not note_ids:
        raise HTTPException(
            status_code=400,
            detail="至少需要一个笔记 ID",
        )

    result = await db.scalars(
        select(Note).where(
            Note.id.in_(note_ids),
            Note.user_id == user_id
        )
    )

    notes = result.all()

    if not notes:
        raise HTTPException(
            status_code=404,
            detail="没有可导出的笔记",
        )
    zip_buffer = io.BytesIO()#内存缓冲区                              #压缩算法
    with zipfile.ZipFile (zip_buffer,'w',compression=zipfile.ZIP_DEFLATED ) as archive:
        used_name = set()
        for note in notes:
            if note.tags:
                tags = f"[{','.join(note.tags)}]\n"
            else:
                tags = ""

            markdown = (
                "---\n"
                f"title:{note.title}\n" 
                f"catrgory:{note.category or ''}\n"
                f"{tags if tags else ""}"
                f"create_time : {note.created_at}\n"
                f"update_time : {note.updated_at}\n"
                "---\n\n"
                f"#{note.title}\n"
                f"{note.content}"
            )
            safe_title = re.sub(r'[\\/:*?"<>|]','_',note.title).strip()

            if not safe_title:
                safe_title = f'note_{note.id}'

            file_name = f"{safe_title}.md"
            counter = 1

            while file_name in used_name:
                file_name = f"{safe_title}_{counter}.md"
                counter += 1

            used_name.add(file_name)

            archive.writestr(
                file_name,
                markdown.encode("utf-8")
            )
    zip_buffer.seek(0)

    file_name = "note.export.zip"

    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{quote(file_name)}"
            )
        },
    )

@note_router.get("/{note_id}", response_model=ApiResponse[NoteResponse])
async def get_note(note_id: int, user_id: int = Depends(get_current_user_id), service: NoteService = Depends(get_note_service),):
        note =  await service.get_owned(note_id,user_id)
        return {
            "code": 200,
            "message": "获取笔记详情成功",
            "data": note,
        }

@note_router.put("/{note_id}", response_model=ApiResponse[NoteResponse])
async def update_note(
    note_id: int,
    payload: NoteUpdate,
    user_id: int = Depends(get_current_user_id),
    service: NoteService = Depends(get_note_service),
):
    note = await service.update(
        note_id=note_id,
        user_id=user_id,
        payload=payload,
    )

    return {
        "code":200,
        "message":"笔记更新成功",
        "data":note,
    }



@note_router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(note_id: int, service:NoteService = Depends(get_note_service),user_id : int = Depends(get_current_user_id)):

    await service.delete(
        note_id=note_id,
        user_id=user_id,
    )



@note_router.put("/{note_id}/pin",response_model=ApiResponse[NoteResponse])
async def note_pin(
        note_id : int,
        user_id : int = Depends(get_current_user_id),
        service: NoteService = Depends(get_note_service),
):
    note =  await service.toggle_pin(
        note_id=note_id,
        user_id=user_id,
    )

    return {
        "code" : 200,
        "message":"笔记更新成功",
        "data":note
    }


@note_router.get("/{note_id}/export")
async def export_note(
        note_id : int,
        user_id : int = Depends(get_current_user_id),
        db : AsyncSession = Depends(get_db)
):
    note = await _get_owned_note(note_id,user_id,db)

    lines = [
        "--------",
        f"title : {note.title}"
    ]

    if note.category:
        lines.append(f"category:{note.category}")

    if note.tags:
        lines.append(f"tags : [{','.join(note.tags)}]")


    lines.extend(
        [
            f"created_at: {note.created_at}",
            f"updated_at: {note.updated_at}",
            "---",
            "",
            f"# {note.title}",
            "",
            note.content,
        ]
    )

    markdown = "\n".join(lines)
    filename = f"{note.title}.md"

    return Response(
        content=markdown.encode("utf-8"),
        media_type="text/markdown",
        headers={
            #不要直接展示作为附件下载
            "Content-Disposition":(
                #把文件名做 URL 编码
                f"attachment; filename*=UTF-8''{quote(filename)}"
            )
        }
    )

@note_router.post("/autocomplete",response_model=ApiResponse[dict])
async def autocomplete(payload:AutocompleteRequest,user_id : int = Depends(get_current_user_id),service:WritingAssistantService = Depends(get_writing_Service)):
    completion = await service.autocomplete(payload.context)

    return {
        "code":200,
        "message":"补全成功",
        "data":{
            "completion": completion,
        }
    }



