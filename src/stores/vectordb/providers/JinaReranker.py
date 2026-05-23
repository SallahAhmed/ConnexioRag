import httpx
from typing import List
from ..RerankerInterface import RerankerInterface
from models.db_schemas import RetrievedDocument
import logging

logger = logging.getLogger(__name__)


class JinaReranker(RerankerInterface):
    def __init__(self, api_key: str, model: str = "jina-reranker-v2-base-multilingual"):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.jina.ai/v1/rerank"

    async def rerank(self, query: str, documents: List[RetrievedDocument], top_k: int) -> List[RetrievedDocument]:
        if not documents:
            return []

        doc_texts = [
            (d.text if d.text and d.text.strip() else "[empty]")
            for d in documents
        ]

        if all(text == "[empty]" for text in doc_texts):
            return documents[:top_k]

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "query": query,
                        "documents": doc_texts,
                        "top_n": top_k,
                    },
                )
                response.raise_for_status()
                data = response.json()

            reranked_docs = []
            for result in data.get("results", []):
                original_doc = documents[result["index"]]
                original_doc.score = result["relevance_score"]
                reranked_docs.append(original_doc)

            return reranked_docs

        except Exception as e:
            logger.error(f"[RAG] Jina rerank failed, returning original order: {e}")
            return documents[:top_k]
