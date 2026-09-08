import asyncio
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from utils.config import milvus_config


class AsyncTextSplitter:
    def __init__(self,chunk_size : int | None = None,chunk_overlap : int | None =None,separators : list[str] | None = None):
        self.chunk_size = (chunk_size if chunk_size is not None else milvus_config["chunk_size"])
        self.chunk_overlap = (chunk_overlap if chunk_overlap is not None else milvus_config["chunk_overlap"])
        self.separators = (separators if separators is not None else milvus_config["separators"])

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size = self.chunk_size,
            chunk_overlap= self.chunk_overlap,
            separators = self.separators,
        )


    def split_text_sync(self,text : str):
        return self.splitter.split_text(text)


    async def split_text(self,text:str):
        return await asyncio.to_thread(
            self.split_text_sync,
            text
        )

    def split_documents_sync(self,documents : list[Any]):
        return self.splitter.split_documents(documents)


    async def split_documents(self,documents : list[Any]):
        return await asyncio.to_thread(
            self.split_documents_sync,
            documents
        )