from unittest.mock import AsyncMock, Mock

import fitz

from utils.MultiModal_PDF_Loader import (
    MultiModalPDFLoader,
)


def create_pdf(path):
    pdf = fitz.open()

    page = pdf.new_page()
    page.insert_textbox(
        fitz.Rect(50, 50, 545, 800),
        "这是一个足够长的原生文本。" * 20,
        fontname="china-s",
    )

    pdf.new_page()

    pdf.save(path)
    pdf.close()


async def test_pdf_uses_text_then_ocr_and_vlm(tmp_path):
    pdf_path = tmp_path / "demo.pdf"
    create_pdf(pdf_path)

    ocr = Mock()
    ocr.recognize = AsyncMock(
        return_value="扫描识别出的文字"
    )

    vision = Mock()
    vision.describe_page = AsyncMock(
        return_value="页面视觉描述"
    )

    documents = await MultiModalPDFLoader(
        ocr_service=ocr,
        vision_service=vision,
    ).load(
        str(pdf_path),
        file_hash="hash-1",
        user_id="u1",
    )

    assert len(documents) == 2

    # 长原生文本页不调用 OCR/VLM
    assert documents[0].metadata["page"] == 1
    assert documents[0].metadata["processing_mode"] == "text"

    # 空白页进入 OCR 和 VLM
    assert documents[1].metadata["page"] == 2
    assert "[OCR文本]" in documents[1].page_content
    assert "[页面视觉描述]" in documents[1].page_content

    assert ocr.recognize.await_count == 1
    assert vision.describe_page.await_count == 1

    rendered_path = ocr.recognize.call_args.args[0]
    assert not tmp_path.joinpath(rendered_path).exists()


async def test_vlm_failure_keeps_native_text(tmp_path):
    pdf_path = tmp_path / "demo.pdf"

    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "短文本", fontname="china-s")
    pdf.save(pdf_path)
    pdf.close()

    ocr = Mock()
    ocr.recognize = AsyncMock(return_value="")

    vision = Mock()
    vision.describe_page = AsyncMock(
        side_effect=RuntimeError("模拟 VLM 失败")
    )

    documents = await MultiModalPDFLoader(
        ocr_service=ocr,
        vision_service=vision,
    ).load(str(pdf_path))

    assert documents[0].page_content == "短文本"