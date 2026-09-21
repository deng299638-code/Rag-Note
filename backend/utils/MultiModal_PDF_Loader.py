import asyncio
import logging
import os
import re
import tempfile
from pathlib import Path
from langchain_core.documents import Document
from utils.image_extractor import extract_images_from_pdf
from utils.ocr_service import OCRService
from utils.vision_service import VisionService

logger = logging.getLogger(__name__)

# 高频英文词，用于判断文本层是否为乱码（字体 ToUnicode 映射损坏时整页字母被整体替换）
_COMMON_ENGLISH_WORDS = {
    "the", "and", "you", "that", "have", "for", "not", "with", "this",
    "from", "but", "they", "are", "was", "were", "been", "has", "had",
    "its", "it", "is", "to", "of", "in", "on", "we", "our", "their",
    "can", "will", "would", "which", "when", "what", "your", "more",
    "than", "into", "also", "such", "use", "used", "using", "show",
    "shown", "based", "between", "through", "where", "while", "during",
}

class MultiModalPDFLoader:
    def __init__(self,ocr_service=None,vision_service=None,text_threshold:int = 100,render_scale:float = 2.0):
        self.ocr = ocr_service or OCRService()
        self.vision = vision_service or VisionService()
        self.text_threshold =  text_threshold
        self.render_scale = render_scale
        self.ocr_enabled =(
            os.getenv("OCR_ENABLED","true").strip().lower() != "false"
        )


    @property
    def vision_enabled(self):
        enabled = getattr(self.vision,"enabled",True)
        return enabled if callable(enabled) else bool(enabled) #返回函数或者布尔值

    @staticmethod
    def _open_pdf(file_path : str):
        try:
            import fitz
            return fitz.open(file_path)
        except ImportError:
            logger.error("未安装 PyMuPDF，请先执行 uv add pymupdf")
            return None
        except Exception:
            logger.exception("打开PDF失败")
            return None

    @staticmethod
    def _page_text(page):
        try:
            return (page.get_text("text") or "").strip()
        except TypeError:
            return (page.get_text() or "" ).strip()

    @staticmethod
    def _text_looks_garbled(text: str) -> bool:
        """文本层存在但字体映射损坏时，字符会被整体替换（如整段字母位移），
        长度足够却没有任何正常英文单词。中文为主的文本不做此判定。"""
        sample = text[:3000]
        if len(sample) < 200:
            return False
        cjk = len(re.findall(r"[\u4e00-\u9fff]", sample))
        if cjk > 50:
            return False
        words = re.findall(r"[a-z']{3,}", sample.lower())
        if not words:
            return True
        hits = sum(1 for w in words if w in _COMMON_ENGLISH_WORDS)
        # 3000 字符的正常英文正文高频词命中通常 >= 5；乱码几乎为 0
        return hits < 2
    #判断PDF中是否有嵌入图片
    @staticmethod
    def _has_image(page):
        try:
            return bool(page.get_images(full=True))
        except Exception:
            return False

    #将PDF渲染成图片
    def _render_page(self,page):
        temp_path = None

        try:
            import fitz
            #构造缩放矩阵，控制图片分辨率
            matrix = fitz.Matrix(
                self.render_scale,
                self.render_scale,
            )
            #将PDF渲染成像素位图
            pixmap = page.get_pixmap(
                matrix = matrix,
                alpha=False,
            )

            with tempfile.NamedTemporaryFile(suffix=".png",delete=False) as temp_file:
                temp_path = temp_file.name
            #将位图保存到历史文件
            pixmap.save(temp_path)
            return temp_path

        except Exception:
            logger.exception("PDF 页面渲染失败")
            #报错清理临时文件
            if temp_path and Path(temp_path).exists():
                Path(temp_path).unlink()

            return None

    @staticmethod
    def _merge_text(native_text : str,ocr_text:str,vision_text:str,native_garbled: bool = False,):
        parts = []
        stages = []

        native_text = native_text.strip()
        ocr_text = ocr_text.strip()
        vision_text = vision_text.strip()

        # 文本层是乱码时，OCR 结果作为正文；OCR 失败才回退到乱码原文
        if native_text and not native_garbled:
            parts.append(native_text)
            stages.append("text")

        if ocr_text:
            stages.append("ocr")
            body = ocr_text if native_garbled else None
            if body:
                parts.append(body)
            else:
                parts.append(f"[OCR文本]:\n{ocr_text}")

        if native_garbled and native_text and not ocr_text:
            # OCR 未启用或失败，只能保留乱码原文，避免正文为空
            parts.append(native_text)
            stages.append("text-fallback")

        if vision_text:
            parts.append(f"[页面视觉描述]:\n{vision_text}")
            stages.append("vlm")

        return "\n\n".join(parts),"+".join(stages) or "empty"

    @staticmethod
    def _build_document(content:str,file_path:str,page_number:int,file_hash:str | None,user_id : str|None,processing_mode:str,has_images:bool,image_paths:list[str] | None =None):

        filename = Path(file_path).name
        metadata = {
            "original_filename":filename,
            "page":page_number,
            "source":filename,
            "processing_mode":processing_mode,
            "has_images":has_images,
            #后续图片提取时替换真实路径
            "image_paths":image_paths or []
        }

        if file_hash:
            metadata["md5"] = file_hash
            metadata["file_hash"] = file_hash

        if user_id:
            metadata["user_id"] = user_id

        return Document(
            page_content=content.strip(),
            metadata = metadata,
        )


    async def load(self,file_path :str,file_hash:str | None = None,user_id:str |None =None):

        image_map = {}
        if file_hash and user_id:
            image_map = await asyncio.to_thread(
                extract_images_from_pdf,
                pdf_path=file_path,
                user_id=user_id,
                md5=file_hash,
            )

        pdf = self._open_pdf(file_path)

        if pdf is None:
            return []

        documents = []

        try:
            for page_number in range(len(pdf)):
                page = pdf[page_number]
                native_text = self._page_text(page)
                native_garbled = self._text_looks_garbled(native_text)
                image_paths = image_map.get(page_number,[])
                has_images = self._has_image(page) or bool(image_paths)


                needs_ocr = (
                    self.ocr_enabled
                    and (
                        len(native_text) < self.text_threshold
                        or native_garbled
                    )
                )

                needs_vlm = (
                    self.vision_enabled
                    and(
                        has_images or len(native_text) < self.text_threshold
                    )
                )

                ocr_text = ""
                vision_text = ""
                temp_path = None

                if needs_ocr or needs_vlm:
                    temp_path = self._render_page(page)

                if temp_path:
                    try:
                        if needs_ocr:
                            try:
                                ocr_text = await self.ocr.recognize(temp_path)

                            except Exception:
                                logger.exception("OCR页面处理失败")

                        if needs_vlm:
                            try:
                                vision_text = await self.vision.describe_page(temp_path,ocr_text or native_text)
                            except Exception:
                                logger.exception("VLM 页面处理失败")


                    finally:
                        Path(temp_path).unlink(missing_ok=True)
                content,mode = self._merge_text(native_text, ocr_text, vision_text,native_garbled)

                documents.append(
                    self._build_document(
                        content,file_path,page_number + 1,file_hash,user_id,mode,has_images,image_paths
                    )
                )
        finally:
            pdf.close()

        return documents

    def load_sync(self,file_path:str,file_hash:str | None = None,user_id : str | None = None ):

        image_map = {}
        if file_hash and user_id:
            image_map = extract_images_from_pdf(file_path,user_id,file_hash)

        pdf = self._open_pdf(file_path)

        if pdf is None:
            return []

        documents = []

        try:
            for page_number in range(len(pdf)):
                page = pdf[page_number]
                native_text = self._page_text(page)
                native_garbled = self._text_looks_garbled(native_text)
                image_paths = image_map.get(page_number,[])
                has_images = self._has_image(page) or bool(image_paths)

                needs_ocr = (
                        self.ocr_enabled
                        and (
                            len(native_text) < self.text_threshold
                            or native_garbled
                        )
                )

                needs_vlm = (
                        self.vision_enabled
                        and (
                                has_images or len(native_text) < self.text_threshold
                        )
                )

                ocr_text = ""
                vision_text = ""
                temp_path = None

                if needs_ocr or needs_vlm:
                    temp_path = self._render_page(page)

                if temp_path:
                    try:
                        if needs_ocr:
                            try:
                                ocr_text = self.ocr.recognize_sync(temp_path)

                            except Exception:
                                logger.exception("OCR页面处理失败")

                        if needs_vlm:
                            try:
                                vision_text =  self.vision.describe_page_sync(temp_path, ocr_text or native_text)
                            except Exception:
                                logger.exception("VLM 页面处理失败")


                    finally:
                        Path(temp_path).unlink(missing_ok=True)
                content, mode = self._merge_text(native_text, ocr_text, vision_text, native_garbled)

                documents.append(
                    self._build_document(
                        content, file_path, page_number + 1, file_hash, user_id, mode, has_images,image_paths
                    )
                )
        finally:
            pdf.close()

        return documents
