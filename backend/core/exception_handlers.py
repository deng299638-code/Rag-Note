from fastapi.responses import JSONResponse
from fastapi import Request
from exceptions.note_exceptions import NoteNotFoundError
from exceptions.note_template_exceptions import TemplateNotFoundError


async def note_not_found_handler(
        request:Request,
        exc:NoteNotFoundError,
):
    return JSONResponse(
        status_code= 404,
        content={
            "code": 404,
            "message": "笔记不存在",
            "data": None,
        }
    )





async def note_template_not_found_handler(
    request: Request,
    exc: TemplateNotFoundError,
):
    return JSONResponse(
        status_code=404,
        content={
            "code": 404,
            "message": "模板不存在",
            "data": None,
        },
    )