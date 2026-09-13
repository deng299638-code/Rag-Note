import asyncio
import os.path

from langchain_core.documents import Document

from rag.chunk_store import load_existing_chunks
from rag.text_spliter import AsyncTextSplitter
from utils.file_handler import txt_loader, txt_loader_sync, pdf_loader, markdown_loader, ppt_loader, word_loader, \
    pdf_loader_sync, markdown_loader_sync, ppt_loader_sync, word_loader_sync
from utils.hash_utils import hash_text, ChunkUpdatePlan, plan_update, supports_incremental, build_chunk_ids


class DocumentProcessor:
    def __init__(self):
        self.splitter = AsyncTextSplitter()

    def split_documents_sync(self,documents:list[Document]):
        return self.splitter.split_documents_sync(documents)

    async def split_documents(self,documents: list[Document]):
        return await self.splitter.split_documents(documents)

    def get_file_document_sync(self,file_path:str,file_hash: str | None =None,user_id: str | None =None):
        file_path = file_path.lower()

        if file_path.endswith(".txt"):
            return txt_loader_sync(file_path)

        if file_path.endswith(".pdf"):
            return pdf_loader_sync(file_path, file_hash, user_id)

        if file_path.endswith(".md"):
            return markdown_loader_sync(file_path)

        if file_path.endswith(".pptx"):
            return ppt_loader_sync(file_path)

        if file_path.endswith(".docx"):
            return word_loader_sync(file_path)

        return []

    async def get_file_document(self,file_path:str,file_hash: str | None =None,user_id: str | None =None):
        file_path = file_path.lower()

        if file_path.endswith(".txt"):
            return await txt_loader(file_path)

        if file_path.endswith(".pdf"):
            return await pdf_loader(file_path, file_hash, user_id)

        if file_path.endswith(".md"):
            return await markdown_loader(file_path)

        if file_path.endswith(".pptx"):
            return await ppt_loader(file_path)

        if file_path.endswith(".docx"):
            return await word_loader(file_path)

        return []

    def enrich_chunk_metadata(self, chunks: list[Document], *, file_path: str, user_id: str | None = None,file_hash: str | None = None,document_id :str):
        filename = os.path.basename(file_path)

        for index, chunk in enumerate(chunks):
            chunk.metadata = {
                **chunk.metadata,
                "document_id": document_id,
                "original_filename": filename,
                "chunk_index": index,
                "chunk_hash": hash_text(chunk.page_content)
            }

            if user_id is not None:
                chunk.metadata["user_id"] = user_id

            if file_hash is not None:
                chunk.metadata["file_hash"] =file_hash

        return chunks



    def process_file_sync(self,file_path: str,document_id: str,user_id : str | None = None,file_hash : str | None = None):
        documents = self.get_file_document_sync(file_path,file_hash, user_id)

        if not documents:
            return []

        chunks =  self.split_documents_sync(documents)

        return self.enrich_chunk_metadata(chunks,file_path=file_path, user_id=user_id, file_hash=file_hash,document_id = document_id)

    async def process_file(self, file_path: str,document_id: str,user_id : str | None = None,file_hash : str | None = None):
        documents = await self.get_file_document(file_path,file_hash, user_id)

        if not documents:
            return []

        chunks = await self.split_documents(documents)

        return self.enrich_chunk_metadata(chunks,file_path=file_path, user_id=user_id,file_hash = file_hash,document_id = document_id)



    async def ingest_file(self,store,file_path:str,document_id:str,user_id:str,file_hash:str):


        old_records = await asyncio.to_thread(
            load_existing_chunks,
            store,where={"document_id": document_id,"user_id": user_id,}
        )
        can_incremental = supports_incremental(old_records)
        old_file_hashes = {
            document.metadata.get("file_hash")
            for _,document in old_records
        }

        if can_incremental and old_records and old_file_hashes == {file_hash}:
            return {
                "status": "skipped",
                "added": 0,
                "deleted": 0,
                "kept": len(old_records),
            }


        new_chunks = await self.process_file(
            file_path,
            document_id=document_id,
            user_id=user_id,
            file_hash=file_hash,
        )
        if not new_chunks:
            raise ValueError("文件未解析出可索引文本，已保留原有切片")

        if not can_incremental:
            new_ids = build_chunk_ids(document_id,new_chunks)

            await asyncio.to_thread(
                store.upsert,
                documents = new_chunks,
                ids = new_ids
            )

            new_id_set = set(new_ids)
            delete_ids = [
                vector_id
                for vector_id, _ in old_records
                if vector_id not in new_id_set
            ]

            if delete_ids:
                await asyncio.to_thread(
                    store.delete,
                    ids=delete_ids,
                )

            return {
                "status": "rebuilt",
                "added": len(new_chunks),
                "deleted": len(delete_ids),
                "kept": 0,
            }
        plan = plan_update(old_records,new_chunks,document_id)

        new_ids = [chunk.metadata["chunk_id"] for chunk in new_chunks]
        collection_exists = await asyncio.to_thread(
            store.client.has_collection,
            store.collection_name,
        )
        write = (store.upsert if collection_exists else  store.add_documents)

        await asyncio.to_thread(
            write,
            documents = new_chunks,
            ids = new_ids,
        )

        if plan.delete_ids:
            await asyncio.to_thread(
                store.delete,
                ids = plan.delete_ids,
            )

        return {
            "status": "updated" if old_records else "created",
            "added": len(plan.add_documents),
            "deleted": len(plan.delete_ids),
            "kept": len(plan.kept_ids),
        }
