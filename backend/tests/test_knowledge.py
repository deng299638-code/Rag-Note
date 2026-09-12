from fastapi.routing import APIRoute, APIRouter

from main import app


def test_knowledge_single_route_exists():
    routes = {
        (route.path, tuple(route.methods or ()))
        for route in app.routes
        if isinstance(route, APIRoute)
    }
    # FastAPI >= 0.140 惰性挂载：include_router 的路由在 app.routes 中
    # 表现为 _IncludedRouter 占位对象，需从其 original_router 展开
    for route in app.routes:
        router = getattr(route, "original_router", None)
        if isinstance(router, APIRouter):
            routes.update(
                (sub.path, tuple(sub.methods or ()))
                for sub in router.routes
                if isinstance(sub, APIRoute)
            )

    assert (
        "/knowledge/add/single",
        ("POST",),
    ) in routes
