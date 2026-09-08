import asyncio
from pathlib import Path

from langchain_community.document_loaders import TextLoader, PyPDFLoader, UnstructuredPowerPointLoader, \
    UnstructuredMarkdownLoader, UnstructuredWordDocumentLoader


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


async def pdf_loader(file_path):
    loader = PyPDFLoader(file_path,mode="single")
    return await asyncio.to_thread(loader.load)

def pdf_loader_sync(file_path):
    loader = PyPDFLoader(file_path,mode="single")
    return loader.load()

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