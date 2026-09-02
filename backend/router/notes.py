import io
import re
from urllib.parse import quote
import zipfile
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import Response
from db.db_config import get_db
from models.note import Note
from schemas.note_schemas import NoteCreate, NoteListResponse, NoteResponse, NoteUpdate,BatchIdsRequest,BatchPinRequest
from utils.JWT import get_current_user_id

note_router = APIRouter(prefix="/notes", tags=["notes"])


@note_router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    payload: NoteCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    note = Note(user_id=user_id, **payload.model_dump())
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


@note_router.get("", response_model=NoteListResponse)
async def list_notes(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str | None = Query(default= None),
    tags : str | None = Query(default=None)

):
    conditions = [Note.user_id == user_id]
    if category != None:
        conditions.append(Note.category == category)
    if tags != None:
        conditions.append(Note.tags == tags)
    base = select(Note).where(*conditions)
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    result = await db.scalars(
        base.order_by(Note.is_pinned.desc(),Note.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {"notes": result.all(), "total": total or 0}
@note_router.get("/search",response_model=NoteListResponse)
async def search_notes(
        q: str = Query(...,min_length=1,description="搜索标题或正文"),
        db:AsyncSession = Depends(get_db),
        user_id : int = Depends(get_current_user_id)
):
    patten = f"%{q}%"
    base = select(Note).where(
        Note.user_id == user_id,
        or_(
            Note.title.like(patten),
            Note.content.like(patten)
        )
    )

    total = await db.scalar(select(func.count()).select_from(base.subquery()))

    result = await db.scalars(
        base.order_by(
            Note.updated_at.desc()
        )
    )

    return {
        "notes": result,
        "total":total or 0,
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

@note_router.get("/stats")
async def get_note_stats(
        user_id : int = Depends(get_current_user_id),
        db : AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Note.category,func.count(Note.id).label("count"))
        .where(
            Note.user_id == user_id,
            Note.category.is_not(None),
        )
        .group_by(Note.category)
        .order_by(func.count(Note.id).desc())
    )

    categorys = [
        {
            "category":category,
            "count":count,
        }
        for category,count in result.all()
    ]

    total = await db.scalar(select(func.count(Note.id)).where(Note.user_id == user_id))

    uncategory = await db.scalar(select(func.count(Note.id)).where(Note.category.is_(None)))

    return {
        "total":total or 0,
        "categories" : categorys,
        "uncategorized" :  uncategory or 0,
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

            markdown = (
                "---\n"
                f"title:{note.title}\n" 
                f"catrgory:{note.category or ''}\n"
                f"{tags}"
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









async def _get_owned_note(note_id: int, user_id: int, db: AsyncSession) -> Note:
    note = await db.scalar(select(Note).where(Note.id == note_id, Note.user_id == user_id))
    if note is None:
        raise HTTPException(status_code=404, detail="笔记不存在")
    return note


@note_router.get("/{note_id}", response_model=NoteResponse)
async def get_note(note_id: int, user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    return await _get_owned_note(note_id, user_id, db)


@note_router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: int,
    payload: NoteUpdate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    note = await _get_owned_note(note_id, user_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(note, field, value)
    await db.commit()
    await db.refresh(note)
    return note


@note_router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(note_id: int, user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    note = await _get_owned_note(note_id, user_id, db)
    await db.delete(note)
    await db.commit()


@note_router.patch("/{note_id}/pin",response_model=NoteResponse)
async def note_pin(
        note_id : int,
        user_id : int = Depends(get_current_user_id),
        db:AsyncSession = Depends(get_db),
):
    note = await _get_owned_note(note_id,user_id,db)
    note.is_pinned = not note.is_pinned
    await db.commit()
    await db.refresh(note)
    return note



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
