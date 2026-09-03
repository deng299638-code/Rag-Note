from fastapi.responses import JSONResponse
from fastapi import Request
from exceptions.note_exceptions import NoteNotFoundError


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