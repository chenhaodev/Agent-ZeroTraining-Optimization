"""
Retrieval for evaluation context.
"""

from typing import List, Dict
from loguru import logger

from optimizer.pattern_db.vector_store import get_vector_store
from autoeval.config.settings import get_settings


class Retriever:
    """Retriever for golden reference context"""

    def __init__(self):
        self.settings = get_settings()
        self.vector_store = get_vector_store()

    def retrieve(self, query: str, k: int = None, threshold: float = None) -> List[Dict]:
        """
        Retrieve relevant golden reference context with relevance filtering.

        Args:
            query: Query text (question)
            k: Number of results (defaults to settings.RETRIEVAL_TOP_K)
            threshold: Minimum similarity score (defaults to settings.PATTERN_RELEVANCE_THRESHOLD)

        Returns:
            List of relevant context dicts (may be empty if none meet threshold)
        """
        if k is None:
            k = self.settings.RETRIEVAL_TOP_K

        if threshold is None:
            threshold = getattr(self.settings, 'PATTERN_RELEVANCE_THRESHOLD', 0.0)

        logger.debug(f"Retrieving top-{k} results for query (threshold={threshold})")
        results = self.vector_store.search(query, k=k)

        # Filter by relevance threshold
        if threshold > 0:
            filtered_results = [r for r in results if r['similarity'] >= threshold]
            if len(filtered_results) < len(results):
                logger.info(
                    f"RAG relevance filter: {len(results)} → {len(filtered_results)} results "
                    f"(threshold={threshold:.2f})"
                )
            results = filtered_results

        return results

    def format_context(self, results: List[Dict]) -> str:
        """
        Format retrieval results as context string for evaluation.

        Args:
            results: List of retrieval results

        Returns:
            Formatted context string
        """
        if not results:
            return "未找到相关参考资料"

        context_parts = []

        for i, result in enumerate(results, 1):
            entity_type_zh = {
                'disease': '疾病',
                'examination': '检查',
                'surgery': '手术',
                'vaccine': '疫苗'
            }.get(result['entity_type'], result['entity_type'])

            part = f"""## 参考资料 {i}
来源: {entity_type_zh} - {result['name']}
相关度: {result['similarity']:.2f}

{result['content']}
"""
            context_parts.append(part)

        return "\n\n".join(context_parts)

    def retrieve_formatted(self, query: str, k: int = None, threshold: float = None) -> str:
        """
        Retrieve and format context in one call.

        Args:
            query: Query text
            k: Number of results
            threshold: Minimum similarity score

        Returns:
            Formatted context string (empty string if no relevant results)
        """
        results = self.retrieve(query, k, threshold)
        if not results:
            logger.warning(f"No relevant context found for query (threshold={threshold})")
            return ""
        return self.format_context(results)


# Singleton
_retriever = None

def get_retriever() -> Retriever:
    """Get global retriever instance"""
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever
