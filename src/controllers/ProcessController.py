from .BaseController import BaseController
from .ProjectController import ProjectController
import os
from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_community.document_loaders import Docx2txtLoader
from models import ProcessingEnum
from typing import List
from dataclasses import dataclass

@dataclass
class Document:
    page_content: str
    metadata: dict

class ProcessController(BaseController):

    def __init__(self, project_id: str):
        super().__init__()

        self.project_id = project_id
        self.project_path = ProjectController().get_project_path(project_id=project_id)

    def get_file_extension(self, file_id: str):
        return os.path.splitext(file_id)[-1]

    def get_file_loader(self, file_id: str):

        file_ext = self.get_file_extension(file_id=file_id)
        # Ensure the file path doesn't escape the project path (path traversal prevention)
        base_dir = os.path.abspath(self.project_path)
        file_path = os.path.abspath(os.path.join(base_dir, file_id))

        if not file_path.startswith(base_dir):
            raise ValueError(f"Invalid file_id path traversal detected: {file_id}")

        if not os.path.exists(file_path):
            return None

        if file_ext == ProcessingEnum.TXT.value or file_ext == ProcessingEnum.MD.value:
            return TextLoader(file_path, encoding="utf-8")

        if file_ext == ProcessingEnum.PDF.value:
            return PyMuPDFLoader(file_path)

        if file_ext == ProcessingEnum.DOCX.value:
            return Docx2txtLoader(file_path)

        return None

    def get_file_content(self, file_id: str):

        loader = self.get_file_loader(file_id=file_id)
        if loader:
            return loader.load()

        raise FileNotFoundError(f"File not found on disk: {file_id}")

    def process_file_content(self, file_content: list, file_id: str,
                            chunk_size: int=100, overlap_size: int=20):

        file_content_texts = [
            rec.page_content
            for rec in file_content
        ]

        file_content_metadata = [
            rec.metadata
            for rec in file_content
        ]

        # chunks = text_splitter.create_documents(
        #     file_content_texts,
        #     metadatas=file_content_metadata
        # )

        chunks = self.process_simpler_splitter(
            texts=file_content_texts,
            metadatas=file_content_metadata,
            chunk_size=chunk_size,
        )

        return chunks

    def process_simpler_splitter(self, texts: List[str], metadatas: List[dict], chunk_size: int, splitter_tag: str="\n"):
        """Sliding-window chunker with 150-char overlap for better RAG retrieval."""
        full_text = " ".join(texts)
        overlap = 150
        chunks = []
        start = 0
        text_len = len(full_text)

        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunk_text = full_text[start:end].strip()
            if len(chunk_text) > 5:
                chunks.append(Document(
                    page_content=chunk_text,
                    metadata={}
                ))
            if end == text_len:
                break
            start += (chunk_size - overlap)

        return chunks