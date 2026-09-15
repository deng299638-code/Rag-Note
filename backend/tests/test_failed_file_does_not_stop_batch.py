from tests.test_upload_task import FakeUploadFile, wait_for_state


@pytest.mark.asyncio
async def test_failed_file_does_not_stop_batch(
    monkeypatch,
):
    redis = FakeRedis()

    monkeypatch.setattr(
        service_module,
        "get_redis",
        lambda: redis,
    )

    service = KnowledgeService(db=None)

    async def fake_ingest(
        file_path,
        filename,
        user_id,
        content=None,
    ):
        if filename == "bad.txt":
            raise ValueError("文件解析失败")

        return {
            "filename": filename,
            "status": "created",
        }

    service._ingest_saved_file = fake_ingest

    task_id = await service.start_multiple_upload(
        [
            FakeUploadFile("good.txt", b"good"),
            FakeUploadFile("bad.txt", b"bad"),
        ],
        user_id=1,
    )

    state = await wait_for_state(
        redis,
        service,
        user_id=1,
        task_id=task_id,
        status="completed",
    )

    assert state["processed"] == 2
    assert state["succeeded"] == 1
    assert state["failed"] == 1
    assert len(state["results"]) == 2