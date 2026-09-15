import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute, APIRouter

from main import app
from router.knowledge import cancel_multiple_upload


def route_methods(path: str):
    routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute)
    ]
    # FastAPI >= 0.140 惰性挂载：include_router 的路由在 app.routes 中
    # 表现为 _IncludedRouter 占位对象，需从其 original_router 展开
    for route in app.routes:
        router = getattr(route, "original_router", None)
        if isinstance(router, APIRouter):
            routes.extend(
                sub
                for sub in router.routes
                if isinstance(sub, APIRoute)
            )

    return {
        method
        for route in routes
        if route.path == path
        for method in (route.methods or set())
    }


def test_knowledge_upload_routes_exist():
    assert route_methods(
        "/knowledge/add/single"
    ) == {"POST"}

    assert route_methods(
        "/knowledge/add/multiple"
    ) == {"POST"}

    assert route_methods(
        "/knowledge/add/multiple/stream"
    ) == {"POST"}

    assert route_methods(
        "/knowledge/add/multiple/{task_id}"
    ) == {"DELETE"}


@pytest.mark.asyncio
async def test_cancel_multiple_upload_cancels_task():
    state = {"task_id": "task-1", "status": "cancelled"}

    class Service:
        async def cancel_upload(self, user_id, task_id):
            assert (user_id, task_id) == (7, "task-1")
            return state

    response = await cancel_multiple_upload("task-1", 7, Service())

    assert response == {
        "code": 200,
        "message": "上传任务已取消",
        "data": state,
    }


@pytest.mark.asyncio
async def test_cancel_multiple_upload_returns_404_for_missing_task():
    class Service:
        async def cancel_upload(self, user_id, task_id):
            raise ValueError("上传任务不存在或已过期")

    with pytest.raises(HTTPException) as exc_info:
        await cancel_multiple_upload("missing", 7, Service())

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "上传任务不存在或已过期"
