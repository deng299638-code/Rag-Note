import asyncio
import hashlib
import json
import os
import tempfile
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile, Depends
from db.db_config import get_db
from rag.document_processor import DocumentProcessor
from rag.knowledge_vector_store import get_knowledge_Vector_Store
from utils.image_extractor import delete_user_all_images, delete_image_directory

ALLOWED_SUFFIXES = {".txt",".pdf",".md",".pptx",".docx",}

class KnowledgeService:
    def __init__(self,db:AsyncSession):
        self.db = db
        self.processor = DocumentProcessor()

    async def add_single(self,file_path:UploadFile,user_id : int):

        suffix = Path(file_path.filename or "").suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise ValueError(
                "仅支持 txt、pdf、md、pptx、docx 文件"
            )

        content = await file_path.read()

        if not content:
            raise ValueError("上传文件不能为空")

        file_hash = hashlib.md5(content).hexdigest()
        document_id = f"{user_id}:{file_hash}"
        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(delete= False,suffix = suffix,) as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name

            result = await self.processor.ingest_file(get_knowledge_Vector_Store().store,temp_path,document_id=document_id,user_id= str(user_id),file_hash = file_hash)

            return{
                "filename": file_path.filename,
                "md5":file_hash,
                "file_size":len(content),
                "file_type":suffix.removeprefix("."),
                **result,
            }

        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)#删除临时文件
                except OSError:
                    pass

    async def add_multiple(self,files: list[UploadFile],user_id : int):
        results = []

        for file in files:
            try:
                result = await self.add_single(file,user_id)

            except ValueError as exc:
                results.append({
                    "filename": file.filename,
                    "status": "failed",
                    "error": str(exc),
                })
            except Exception as exc:
                results.append({
                    "filename": file.filename,
                    "status": "failed",
                    "error": "文件处理失败",
                })

            else:
                results.append({
                    **result,
                    "status":result.get(
                        "status",
                        "success",
                    )
                })
        return results

    async def add_multiple_stream(self,files:list[UploadFile],user_id:int):
        total = len(files)
        yield self._see(
            {"event":"start",
             "total":total}
        )

        for index,file in enumerate(files,start=1):
            yield self._see(
                {
                    "event_type":"processing",
                    "filename":file.filename,
                    "progress": 0,
                }
            )

            try:
                result = await self.add_single(file,user_id)

            except ValueError as exc:
                yield self._see({
                    "event_type": "error",
                    "filename": file.filename,
                    "error_message": str(exc),
                })
            except Exception:
                yield self._see({
                    "event_type": "error",
                    "filename": file.filename,
                    "error_message": "文件处理失败",
                })
            else:
                yield self._see(
                    {
                        "event_type": "completed",
                        "filename": file.filename,
                        "progress": 100,
                        "result": result,
                    }
                )
        yield self._see(
            {
                "event_type":"finish",
                "total":total,
            }
        )

    async def list_documents(self,user_id: int):
        result = await self._get_user_documents(user_id)
        grouped = {}

        for index,content in enumerate(result.get("documents",[])):
            metadata = result["metadatas"][index]
            document_id = metadata.get("document_id")

            item = grouped.setdefault(
                document_id,
                {
                    "id": document_id,
                    "user_id":str(user_id),
                    "md5":metadata.get("file_hash",""),
                    "filename":metadata.get("original_filename",""),
                    "file_size":0,
                    "file_type":(
                        Path(
                            metadata.get("original_filename","")
                        ).suffix.removeprefix(".")
                    ),
                    "status":"completed",
                    "chunk_count":0,
                    "created_at":None,
                },
            )

            item["chunk_count"] += 1

        return list(grouped.values())
    async def _get_user_documents(self, user_id: int):
        store = self._store()
        exists =await asyncio.to_thread(
            store.client.has_collection,
            store.collection_name,
        )

        if not exists:
            return {
                "ids":[],
                "docuemnts":[],
                "metadatas":[],
            }

        return await asyncio.to_thread(
            store.get,
            include = ["documents","metadatas"],
            where={"user_id":str(user_id)}
        )

    async def get_document(self,filename:str,user_id : int):
        result = await self._get_user_documents(user_id)
        chunks = []

        for index,document in enumerate(result["documents"]):
            metadata = result["metadatas"][index]
            if metadata.get("original_filename") != filename:
                continue
            image_paths = metadata.get("image_paths",[])
            images = [
                f"/knowledge/image/{metadata.get('md5')}/{image_name}"
                for image_name in image_paths
            ]
            chunks.append({
                "chunk_id": result["ids"][index],
                "index": metadata.get(
                    "chunk_index",
                    index,
                ),
                "content": document,
                "page": metadata.get("page", 0),
                "images": images,
            })

        if not chunks:
            raise ValueError("文档不存在")

        chunks.sort(key = lambda item : item["index"])

        return {
            "filename":filename,
            "user_id":str(user_id),
            "content":"\n\n".join(
                item["content"]
                for item in chunks
            ),
            "images":[],
            "chunks":chunks,
        }

    async def delete_by_filename(self,filename:str,user_id:int):
        store = self._store()
        result = await self._get_user_documents(user_id)
        matched_md5s = set()
        matched_ids = []
        for index,metadata in enumerate(result["metadatas"]):
            if metadata.get("original_filename") != filename:
                continue
            matched_ids.append(result["ids"]["index"])
            md5 = (
                metadata.get("file_hash")
                or metadata.get("md5")
            )

            if md5:
                matched_md5s.add(md5)

        if not matched_ids:
            return None

        await asyncio.to_thread(
            store.delete,
            ids = matched_ids,

        )

        for md5 in matched_md5s:
            delete_image_directory(user_id,md5)
        return True

    async def delete_user_vectors(self,user_id:int):
        store = self._store()
        result = await self._get_user_documents(user_id)
        ids = [
            result["ids"][index]
            for index,metadata in enumerate(result.get("metadatas",[]))
            if metadata.get("user_id") == str(user_id)
        ]

        await asyncio.to_thread(
            store.delete,
            ids=ids,
        )

        delete_user_all_images(str(user_id))

        return len(ids)



    @staticmethod
    def _see(data:dict):
        return (
            "data: "
            + json.dumps(
            data,ensure_ascii=False,
            )
            +"\n\n"
        )

    def _store(self):
        return get_knowledge_Vector_Store().store


def get_knowledge_service(db: AsyncSession = Depends(get_db),):
    return KnowledgeService(db)
