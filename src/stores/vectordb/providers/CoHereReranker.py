import cohere
from typing import List
from ..RerankerInterface import RerankerInterface
from models.db_schemas import RetrievedDocument
import logging

logger = logging.getLogger(__name__)


class CoHereReranker(RerankerInterface):
    """
    Reranker using Cohere's rerank-multilingual-v3.0 model.
    Sorts PGVector retrieval results by relevance before they are fed to the LLM,
    dramatically improving answer accuracy especially for Arabic queries.
    """

    def __init__(self, api_key: str, model: str = "rerank-multilingual-v3.0"):
        self.client = cohere.AsyncClient(api_key=api_key)
        self.model = model

    async def rerank(self, query: str, documents: List[RetrievedDocument], top_k: int) -> List[RetrievedDocument]:
        if not documents:
            return []

        doc_texts = [d.text for d in documents]
        try:
            response = await self.client.rerank(
                model=self.model,
                query=query,
                documents=doc_texts,
                top_n=top_k,
            )

            reranked_docs = []
            for result in response.results:
                original_doc = documents[result.index]
                original_doc.score = result.relevance_score
                reranked_docs.append(original_doc)

            return reranked_docs

        except Exception as e:
            logger.error(f"[RAG] Cohere rerank failed, returning original order: {e}")
            # Graceful degradation: return top_k un-reranked results
            return documents[:top_k]
