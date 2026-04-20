from ..RerankerInterface import RerankerInterface
from models.db_schemas import RetrievedDocument
from typing import List
import logging
import asyncio
from sentence_transformers import CrossEncoder

class SentenceTransformerReranker(RerankerInterface):
    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        self.logger = logging.getLogger(__name__)
        self.model_name = model_name
        self.model = None
        self.logger.info(f"Reranker initialized (lazy-loading enabled for: {self.model_name})")

    async def rerank(self, query: str, documents: List[RetrievedDocument], top_k: int = 5) -> List[RetrievedDocument]:
        if not documents:
            return []

        # Lazy-load the model on first use to prevent startup timeouts
        if self.model is None:
            self.logger.info(f"Lazy-loading reranker model: {self.model_name}...")
            try:
                self.model = CrossEncoder(self.model_name)
            except Exception as e:
                self.logger.error(f"Failed to load reranker model: {str(e)}")
                return documents[:top_k]

        # Prepare pairs of (query, document_text) for the cross encoder
        pairs = [[query, doc.text] for doc in documents]
        
        try:
            # Predict similarity scores. We run this in a threadpool to not block asyncio
            scores = await asyncio.to_thread(self.model.predict, pairs)
            
            # Update the documents with new scores and sort them
            for doc, score in zip(documents, scores):
                doc.score = float(score)

            # Sort descending by score
            documents.sort(key=lambda x: x.score, reverse=True)
            
            # Return top-k
            return documents[:top_k]
            
        except Exception as e:
            self.logger.error(f"Error during reranking: {str(e)}")
            return documents[:top_k]
