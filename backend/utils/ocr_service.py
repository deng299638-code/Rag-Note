import asyncio
import logging
from threading import Lock

logger = logging.getLogger(__name__)

class OCRService:
    def __init__(self,engine=None):
        self._engine = engine
        self._lock = Lock()

    def recognize_sync(self,image_path: str):
        try:
            with self._lock:
                if self._engine is None:
                    from rapidocr_onnxruntime import RapidOCR

                    self._engine = RapidOCR()

                #[框坐标, 识别文本, 置信度]
                result,_ = self._engine(image_path)

            if not result:
                return ""

            return "\n".join(
                item[1].strip()
                for item in result
                if item[1].strip()
            )

        except Exception:
            logger.exception("OCR识别失败")
            return ""


    async def recognize(self,image_path:str):
        return await asyncio.to_thread(
            self.recognize_sync,
            image_path
        )