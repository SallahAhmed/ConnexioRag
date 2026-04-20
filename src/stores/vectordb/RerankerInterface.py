from abc import ABC, abstractmethod
from typing import List
from models.db_schemas import RetrievedDocument

class RerankerInterface(ABC):
    @abstractmethod
    async def rerank(self, query: str, documents: List[RetrievedDocument], top_k: int) -> List[RetrievedDocument]:
        """
        Reranks a list of retrieved documents based on the given query.
        
        Args:
            query (str): The search query.
            documents (List[RetrievedDocument]): The documents to rerank.
            top_k (int): Number of top results to return.
            
        Returns:
            List[RetrievedDocument]: The reranked list of documents, sorted by descending score.
        """
        pass
