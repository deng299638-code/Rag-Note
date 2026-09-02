from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse


def success_response(message : str = "成功", data = None):
    response = {
        "code": 200,
        "message": message,
        "data": data
    }

    return JSONResponse(content=jsonable_encoder(response))