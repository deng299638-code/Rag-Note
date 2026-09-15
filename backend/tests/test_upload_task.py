import asyncio
import hashlib
import json
from types import SimpleNamespace

import pytest

import services.knowledge_service as service_module
from services.knowledge_service import KnowledgeService


class FakeRedis:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ex=None):
        self.values[key] = value

    async def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)

    async def scan_iter(self, match):
        for key in list(self.values):
            if fnmatch.fnmatch(key, match):
                yield key


class FakeUploadFile:
    def __init__(self, filename, content):
        self.filename = filename
        self.content = content

    async def read(self):
        return self.content


async def wait_for_state(
    redis,
    service,
    user_id,
    task_id,
    status,
):
    key = service._upload_progress_key(
        user_id,
        task_id,
    )

    for _ in range(100):
        value = redis.values.get(key)

        if value is not None:
            state = json.loads(value)

            if state["status"] == status:
                return state

        await asyncio.sleep(0.01)

    raise AssertionError(
        f"任务没有进入状态: {status}"
    )


@pytest.mark.asyncio
async def test_background_task_finishes_after_sse_disconnect(
    monkeypatch,
):
    redis = FakeRedis()

    monkeypatch.setattr(
        service_module,
        "get_redis",
        lambda: redis,
    )

    service = KnowledgeService(db=None)

    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_ingest(
        file_path,
        filename,
        user_id,
        content=None,
    ):
        started.set()
        await release.wait()

        return {
            "filename": filename,
            "status": "created",
        }

    service._ingest_saved_file = fake_ingest

    stream = service.add_multiple_stream(
        [
            FakeUploadFile(
                "demo.txt",
                b"hello",
            )
        ],
        user_id=1,
    )

    start_event = await anext(stream)

    payload = json.loads(
        start_event.removeprefix("data: ").strip()
    )

    task_id = payload["task_id"]

    await started.wait()

    # 模拟客户端断开 SSE
    await stream.aclose()

    # 后台任务继续
    release.set()

    state = await wait_for_state(
        redis,
        service,
        user_id=1,
        task_id=task_id,
        status="completed",
    )

    assert state["processed"] == 1
    assert state["succeeded"] == 1
    assert state["failed"] == 0

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


@pytest.mark.asyncio
async def test_ingest_saved_file_uses_string_path_and_md5(
    monkeypatch,
    tmp_path,
):
    redis = FakeRedis()

    monkeypatch.setattr(
        service_module,
        "get_redis",
        lambda: redis,
    )

    monkeypatch.setattr(
        service_module,
        "get_knowledge_Vector_Store",
        lambda: SimpleNamespace(
            store=object()
        ),
    )

    class FakeProcessor:
        async def ingest_file(
            self,
            store,
            file_path,
            **kwargs,
        ):
            assert isinstance(file_path, str)
            return {"status": "created"}

    service = KnowledgeService(db=None)
    service.processor = FakeProcessor()

    file_path = tmp_path / "demo.txt"
    content = b"hello"
    file_path.write_bytes(content)

    result = await service._ingest_saved_file(
        file_path=file_path,
        filename="demo.txt",
        user_id=1,
    )

    assert result["md5"] == hashlib.md5(
        content
    ).hexdigest()

@pytest.mark.asyncio
async def test_worker_resumes_from_processed(monkeypatch, tmp_path):
    redis = FakeRedis()
    monkeypatch.setattr(service_module, "get_redis", lambda: redis)

    service = KnowledgeService(db=None)
    called = []

    async def fake_ingest(file_path, filename, user_id, content=None):
        called.append(filename)
        return {"filename": filename, "status": "created"}

    service._ingest_saved_file = fake_ingest

    task_id = "resume-task"
    temp_dir = tmp_path
    items = [
        {"filename": "a.txt", "path": str(tmp_path / "a.txt"), "error": None},
        {"filename": "b.txt", "path": str(tmp_path / "b.txt"), "error": None},
    ]

    state = {
        "task_id": task_id,
        "status": "processing",
        "total": 2,
        "processed": 1,
        "succeeded": 1,
        "failed": 0,
        "progress": 50,
        "current_filename": "a.txt",
        "results": [
            {"filename": "a.txt", "status": "created"}
        ],
    }

    await service._save_upload_progress(1, state)

    await service._run_upload_task(
        user_id=1,
        temp_dir=temp_dir,
        items=items,
        state=state,
    )

    assert called == ["b.txt"]
    assert state["processed"] == 2
    assert state["status"] == "completed"

@pytest.mark.asyncio
async def test_start_upload_enqueues_arq_job(
    monkeypatch,
    tmp_path,
):
    redis = FakeRedis()
    monkeypatch.setattr(
        service_module,
        "get_redis",
        lambda: redis,
    )

    calls = []

    class FakeArq:
        async def enqueue_job(self, function_name, *args, **kwargs):
            calls.append((function_name, args, kwargs))
            return "arq-job"

    monkeypatch.setattr(
        "db.arq_client.get_arq",
        lambda: FakeArq(),
    )

    service = KnowledgeService(db=None)

    async def fake_stage(files, task_id):
        return tmp_path, [
            {
                "filename": "demo.txt",
                "path": str(tmp_path / "0.txt"),
                "error": None,
            }
        ]

    service._stage_upload_files = fake_stage

    task_id = await service.start_multiple_upload(
        [FakeUploadFile("demo.txt", b"hello")],
        user_id=7,
    )

    assert task_id
    assert len(calls) == 1

    function_name, args, kwargs = calls[0]

    assert function_name == "process_knowledge_upload"
    assert args[0] == 7
    assert args[1] == task_id
    assert args[2] == str(tmp_path)
    assert kwargs["_job_id"] == task_id