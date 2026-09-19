import asyncio
import hashlib
import json
import logging
import os
import shutil
import tempfile
from asyncio import tasks
from pathlib import Path

from redis import RedisError
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile, Depends
from uuid import uuid4
from db.redis_client import get_redis
from db.db_config import get_db
from rag.document_processor import DocumentProcessor
from rag.knowledge_vector_store import get_knowledge_Vector_Store
from utils.cache import cache_get_json, cache_set_json
from utils.image_extractor import delete_user_all_images, delete_image_directory
logger = logging.getLogger(__name__)
ALLOWED_SUFFIXES = {".txt",".pdf",".md",".pptx",".docx",}
UPLOAD_TERMINAL_STATUSES = {"completed","failed","cancelled",}
_UPLOAD_TASKS: set[asyncio.Task] = set()
UPLOAD_PROGRESS_TTL = 3600
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


        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(delete= False,suffix = suffix,) as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name

            return await self._ingest_saved_file(Path(temp_path),file_path.filename,user_id,content)

        finally:
            if temp_path:
                Path(temp_path).unlink(
                    missing_ok=True
                )

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
        task_id = await self.start_multiple_upload(files,user_id)

        yield self._see({
            "event": "start",
            "task_id": task_id,
        })
        last_processing_marker = None
        last_processed = 0
        while True:
            state = await self.get_upload_progress(user_id, task_id)

            processing_marker = (
                state["status"],
                state.get("current_filename"),
                state["progress"],
            )

            if (
                state["status"] == "processing"
                and processing_marker != last_processing_marker
            ):
                yield self._see({
                    "event_type": "processing",
                    "task_id": task_id,
                    "filename": state["current_filename"],
                    "progress": state["progress"],
                })

                last_processing_marker = processing_marker

            results = state.get("results", [])
            processed = min(state["processed"],len(results))

            while last_processed < processed:
                result = results[last_processed]
                item_index = last_processed + 1

                event_type = (
                    "error"
                    if result.get("status") == "failed"
                    else "completed"
                )

                yield self._see({
                    "event_type": event_type,
                    "task_id": task_id,
                    "filename": result["filename"],
                    "progress": int(
                        item_index / state["total"] * 100
                    ) if state["total"] else 100,
                    "result": result,
                })

                last_processed += 1

            if state["status"] in UPLOAD_TERMINAL_STATUSES:
                yield self._see({
                    "event_type": "finish",
                    "task_id": task_id,
                    "total": state["total"],
                    "succeeded": state["succeeded"],
                    "failed": state["failed"],
                    "status": state["status"],
                })
                return

            await asyncio.sleep(0.5)


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
        cache_key = self._document_cache_key(user_id, filename)
        cached = await cache_get_json(cache_key)
        if not cached:
            return cached
        result = await self._get_user_documents(user_id)
        chunks = []
        all_images = []
        for index,document in enumerate(result["documents"]):
            metadata = result["metadatas"][index]
            if metadata.get("original_filename") != filename:
                continue
            md5 = (metadata.get("md5") or metadata.get("file_hash"))
            image_paths = metadata.get("image_paths",[])
            images = [
                f"/knowledge/image/{md5}/{image_name}"
                for image_name in image_paths
            ]
            all_images.extend(images)
            chunks.append({
                "chunk_id": result["ids"][index],
                "index": metadata.get(
                    "chunk_index",
                    index,
                ),
                "content": document,
                "page": metadata.get("page", 0),
                "images": list(dict.fromkeys(images)),
            })

        if not chunks:
            raise ValueError("文档不存在")

        chunks.sort(key = lambda item : item["index"])

        detail =  {
            "filename":filename,
            "user_id":str(user_id),
            "content":"\n\n".join(
                item["content"]
                for item in chunks
            ),
            "images":all_images,
            "chunks":chunks,
        }

        await cache_set_json(cache_key,detail,ttl=300,)

        return detail
    async def delete_by_filename(self,filename:str,user_id:int):
        store = self._store()
        result = await self._get_user_documents(user_id)
        matched_md5s = set()
        matched_ids = []
        for index,metadata in enumerate(result["metadatas"]):
            if metadata.get("original_filename") != filename:
                continue
            matched_ids.append(result["ids"][index])
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

        await self._delete_document_cache(user_id, filename)
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
        await self._delete_user_document_cache(user_id)

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
    @staticmethod
    def _document_cache_key(user_id : int,filename :str):
        filename_hash = hashlib.sha256(filename.encode("utf-8")).hexdigest()
        return f"knowledge:detail:{user_id}:{filename_hash}"

    async def _delete_document_cache(self,user_id : int ,filename : str):
        redis = get_redis()
        await redis.delete(
            self._document_cache_key(user_id, filename)
        )

    async def _delete_user_document_cache(self,user_id):
        redis = get_redis()
        pattern = f"knowledge:detail:{user_id}:*"

        async for key in redis.scan_iter(match=pattern):
            await redis.delete(key)

    @staticmethod
    def _upload_progress_key(user_id : int,task_id :str):
        return f"knowledge:upload:{user_id}:{task_id}"

    async def _save_upload_progress(self,user_id:int,state:dict):
        redis = get_redis()
        await redis.set(
            self._upload_progress_key(user_id, state["task_id"]),
            json.dumps(
                state,
                ensure_ascii=False,
            ),
            ex=UPLOAD_PROGRESS_TTL,
        )

    async def get_upload_progress(self,user_id:int,task_id:str):
        redis = get_redis()
        cached = await redis.get(
            self._upload_progress_key(user_id, task_id)
        )

        if cached is None:
            raise ValueError("上传任务不存在或已过期")

        return json.loads(cached)

    async def _ingest_saved_file(self,file_path:str | Path,filename:str,user_id:int,content:bytes | None = None):
        file_path = Path(file_path)
        suffix =file_path.suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise ValueError(
                "仅支持 txt、pdf、md、pptx、docx 文件"
            )
        if content is None:
            content = await asyncio.to_thread(
                file_path.read_bytes
            )
        if not content:
            raise ValueError("上传文件不能为空")
        filehash = hashlib.md5(content).hexdigest()
        document_id = f"{user_id}:{filehash}"
        result = await self.processor.ingest_file( get_knowledge_Vector_Store().store,str(file_path),document_id=document_id,user_id=str(user_id),file_hash=filehash)
        await self._delete_user_document_cache(user_id)
        return {
            "filename": filename,
            "md5": filehash,
            "file_size": len(content),
            "file_type": suffix.removeprefix("."),
            **result,
        }

    async def _stage_upload_files(self,files:list[UploadFile],task_id:str,):
        temp_dir = Path(tempfile.mkdtemp(prefix=f"knowledge-upload-{task_id}-"))

        items = []
        try:
            for index,file in enumerate(files):
                filename = file.filename or f"file_{index}"
                suffix = Path(filename).suffix.lower()

                if suffix not in ALLOWED_SUFFIXES:
                    items.append({
                        "filename": filename,
                        "path": None,
                        "error": "不支持的文件类型",
                    })
                    continue

                try:
                    content = await file.read()

                except Exception:
                    items.append({
                        "filename": filename,
                        "path": None,
                        "error": "文件读取失败",
                    })
                    continue

                if not content:
                    items.append({
                        "filename": filename,
                        "path": None,
                        "error": "上传文件不能为空",
                    })
                    continue

                target = temp_dir / f"{index}{suffix}"

                await asyncio.to_thread(
                    target.write_bytes,
                    content
                )
                items.append({
                    "filename": filename,
                    "path": str(target),
                    "error": None,
                })
            return temp_dir,items

        except Exception:
            await asyncio.to_thread(
                shutil.rmtree,
                temp_dir,
                ignore_errors=True,
            )
            raise

    async def start_multiple_upload(self,files:list[UploadFile],user_id : int):
        task_id = uuid4().hex
        temp_dir,items = await self._stage_upload_files(files,task_id,)
        state = {
            "task_id": task_id,
            "user_id": str(user_id),
            "temp_dir":str(temp_dir),
            "status": "queued",
            "total": len(items),
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "progress": 0,
            "current_filename": None,
            "results": [],
        }

        await self._save_upload_progress(user_id, state)
        from db.arq_client import get_arq

        await get_arq().enqueue_job(
            "process_knowledge_upload",
            user_id,
            task_id,
            str(temp_dir),
            items,
            _job_id=task_id,
        )

        return task_id

    async def _run_upload_task(self,user_id:int,temp_dir:Path,items:list[dict],state:dict):
        try:
            total = state["total"]
            start_index = min(max(int(state.get("processed",0)),0),total)
            for index in range(start_index,total):
                item = items[index]
                filename = item["filename"]
                item_number = index + 1
                state.update({
                    "status": "processing",
                    "current_filename": filename,
                    "progress": int((index - 1) / total * 100) if total else 0,})

                await self._save_upload_progress(user_id, state,)
                try:
                    if item["error"]:
                        raise ValueError(item["error"])

                    result = await self._ingest_saved_file(
                        file_path=Path(item["path"]),
                        filename=filename,
                        user_id=user_id,
                    )

                except ValueError as exc:
                    state["failed"] += 1
                    result = {
                        "filename": filename,
                        "status": "failed",
                        "error": str(exc),
                    }

                except Exception:
                    state["failed"] += 1
                    result = {
                        "filename": filename,
                        "status": "failed",
                        "error": "文件处理失败",
                    }

                else:
                    state["succeeded"] += 1

                state["results"].append(result)
                state["processed"] = item_number
                state["progress"] = int(index / total * 100) if total else 100
                await self._save_upload_progress(
                    user_id,
                    state,
                )
            state.update({
                "status": "completed",
                "current_filename": None,
                "progress": 100 if total else 0,
            })

            await self._save_upload_progress(
                user_id,
                state,
            )
        except asyncio.CancelledError:
            state.update({
                "status": "cancelled",
                "current_filename": None,
            })

            try:
                await self._save_upload_progress(
                    user_id,
                    state,
                )
            except Exception:
                pass

            raise

        except Exception as exc:
            state.update({
                "status": "failed",
                "current_filename": None,
                "error": str(exc),
            })

            try:
                await self._save_upload_progress(
                    user_id,
                    state,
                )
            except Exception:
                pass

        finally:
            await asyncio.to_thread(
                shutil.rmtree,
                temp_dir,
                ignore_errors=True,
            )
    async def cancel_upload(self,user_id:int,task_id:str,):
        state = await self.get_upload_progress(user_id, task_id)

        if state["status"] in UPLOAD_TERMINAL_STATUSES:
            return state

        state.update({
            "status":"cancelled",
            "current_filename":None,
        })

        await self._save_upload_progress(user_id, state)

        from db.arq_client import get_arq

        job = await get_arq().job(task_id)

        if job is not None:
            await job.abort()

        if state["processed"] == 0:
            await asyncio.to_thread(
                shutil.rmtree,
                state["temp_dir"],
                ignore_errors=True,
            )

        return state



def get_knowledge_service(db: AsyncSession = Depends(get_db),):
    return KnowledgeService(db)
