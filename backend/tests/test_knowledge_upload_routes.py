from fastapi.routing import APIRoute, APIRouter

from main import app


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
