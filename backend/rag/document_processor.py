from langchain_core.documents import Document

from rag.text_spliter import AsyncTextSplitter
from utils.file_handler import txt_loader, txt_loader_sync, pdf_loader, markdown_loader, ppt_loader, word_loader, \
    pdf_loader_sync, markdown_loader_sync, ppt_loader_sync, word_loader_sync


class DocumentProcessor:
    def __init__(self):
        self.splitter = AsyncTextSplitter()

    def split_documents_sync(self,documents:list[Document]):
        return self.splitter.split_documents_sync(documents)

    async def split_documents(self,documents: list[Document]):
        return await self.splitter.split_documents(documents)

    def get_file_document_sync(self,file_path:str):
        file_path = file_path.lower()

        if file_path.endswith(".txt"):
            return txt_loader_sync(file_path)

        if file_path.endswith(".pdf"):
            return pdf_loader_sync(file_path)

        if file_path.endswith(".md"):
            return markdown_loader_sync(file_path)

        if file_path.endswith(".pptx"):
            return ppt_loader_sync(file_path)

        if file_path.endswith(".docx"):
            return word_loader_sync(file_path)

        return []

    async def get_file_document(self,file_path:str):
        file_path = file_path.lower()

        if file_path.endswith(".txt"):
            return await txt_loader(file_path)

        if file_path.endswith(".pdf"):
            return await pdf_loader(file_path)

        if file_path.endswith(".md"):
            return await markdown_loader(file_path)

        if file_path.endswith(".pptx"):
            return await ppt_loader(file_path)

        if file_path.endswith(".docx"):
            return await word_loader(file_path)

        return []

    def process_file_sync(self,file_path: str):
        document = self.get_file_document_sync(file_path)

        if not document:
            return []

        return self.split_documents_sync(document)

    async def process_file(self, file_path: str):
        document = await self.get_file_document(file_path)

        if not document:
            return []

        return await self.split_documents(document)

