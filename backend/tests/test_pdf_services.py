from types import SimpleNamespace
from unittest.mock import Mock

from utils.ocr_service import OCRService
from utils.vision_service import VisionService


def test_ocr_extracts_lines_and_handles_failure():
    engine = Mock(
        return_value=(
            [
                [[], "第一行", 0.99],
                [[], "第二行", 0.98],
            ],
            None,
        )
    )
    service = OCRService(engine=engine)

    assert service.recognize_sync("unused.png") == "第一行\n第二行"

    engine.side_effect = RuntimeError("模拟识别失败")
    assert service.recognize_sync("unused.png") == ""


def test_vision_failure_does_not_repeat_original_text(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("VISION_ENABLED", "true")

    image = tmp_path / "page.png"
    image.write_bytes(b"fake-image")

    model = Mock()
    model.invoke.return_value = SimpleNamespace(
        content="表格中收入为 100 万元"
    )
    service = VisionService(model=model)

    assert service.describe_page_sync(
        str(image), "已有正文"
    ) == "表格中收入为 100 万元"

    model.invoke.side_effect = RuntimeError("模拟超时")
    assert service.describe_page_sync(
        str(image), "已有正文"
    ) == ""

    model.reset_mock()
    monkeypatch.setenv("VISION_ENABLED", "false")
    assert service.describe_page_sync(str(image)) == ""
    model.invoke.assert_not_called()