import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.mark.asyncio
async def test_get_missing_note():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/notes/999999")

    assert response.status_code == 404
    assert response.json() == {
        "code": 404,
        "message": "笔记不存在",
        "data": None,
    }