from fastapi import APIRouter
from core.success_response import success_response
health_router = APIRouter(prefix="/health")

@health_router.get("/live")
async def get_health_application_status():
    """健康检查-存活"""
    return success_response(
        message="health application status",
        data={
            "status": "ok"
        }
    )