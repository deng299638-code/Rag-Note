import asyncio
from pathlib import Path

from langchain_community.document_loaders import TextLoader, PyPDFLoader, UnstructuredPowerPointLoader, \
    UnstructuredMarkdownLoader, UnstructuredWordDocumentLoader

from utils.MultiModal_PDF_Loader import MultiModalPDFLoader


async def txt_loader(file_path : str):
    path = Path(file_path)

    for encoding in ("utf-8","gbk"):
        try:
            loader = TextLoader(str(path),encoding = encoding,)
            return await asyncio.to_thread(loader.load)

        except UnicodeDecodeError:
            continue

    return []

def txt_loader_sync(file_path : str):
    path = Path(file_path)

    for encoding in ("utf-8", "gbk"):
        try:
            loader = TextLoader(str(path),encoding=encoding,)
            return loader.load()
        except UnicodeDecodeError:
            continue

    return []


async def pdf_loader(file_path:str,file_hash: str | None =None,user_id: str | None =None):
    loader = MultiModalPDFLoader()
    return await loader.load(file_path, file_hash, user_id)

def pdf_loader_sync(file_path:str,file_hash: str | None =None,user_id: str | None =None):
    loader = MultiModalPDFLoader()
    return loader.load_sync(file_path, file_hash, user_id)

async def markdown_loader(file_path):
    loader = UnstructuredMarkdownLoader(file_path,mode="single")
    return await asyncio.to_thread(loader.load)

def markdown_loader_sync(file_path):
    loader = UnstructuredMarkdownLoader(file_path,mode="single")
    return loader.load()

async def ppt_loader(file_path):
    loader = UnstructuredPowerPointLoader(file_path,mode="single")
    return await asyncio.to_thread(loader.load)

def ppt_loader_sync(file_path):
    loader = UnstructuredPowerPointLoader(file_path,mode="single")
    return loader.load()

async def word_loader(file_path: str) :
    loader = UnstructuredWordDocumentLoader(file_path)
    return await asyncio.to_thread(loader.load)


def word_loader_sync(file_path: str) :
    loader = UnstructuredWordDocumentLoader(file_path)
    return loader.load()