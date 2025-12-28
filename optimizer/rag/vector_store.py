"""
FAISS-based vector store for medical entities.
"""

import faiss
import numpy as np
import pickle
from pathlib import Path
from typing import List, Dict, Tuple
from loguru import logger

from optimizer.rag.embedder import get_embedder
from autoeval.core.models import MedicalEntity
from autoeval.config.settings import get_settings


class VectorStore:
    """FAISS vector store with persistence"""

    def __init__(self):
        self.settings = get_settings()
        self.embedder = get_embedder()
        self.dimension = self.settings.EMBEDDING_DIMENSION

        self.index = None
        self.metadata: List[Dict] = []
        self.texts: List[str] = []

        self.index_path = Path(self.settings.CACHE_DIR) / "vector_store" / "index.faiss"
        self.metadata_path = Path(self.settings.CACHE_DIR) / "vector_store" / "metadata.pkl"
        self.texts_path = Path(self.settings.CACHE_DIR) / "vector_store" / "texts.pkl"

    def build(self, entities_dict: Dict[str, List[MedicalEntity]], show_progress: bool = True):
        """
        Build vector store from medical entities.

        Args:
            entities_dict: Dictionary with entity types and lists
            show_progress: Whether to show progress
        """
        logger.info("Building vector store...")

        # Flatten all entities
        all_entities = []
        for entity_type, entities in entities_dict.items():
            all_entities.extend(entities)

        logger.info(f"Total entities to index: {len(all_entities)}")

        # Extract texts and metadata
        texts = []
        metadata = []

        for entity in all_entities:
            text = entity.to_text()
            meta = entity.get_metadata()

            texts.append(text)
            metadata.append(meta)

        logger.info(f"Generating embeddings for {len(texts)} entities...")
        embeddings = self.embedder.embed_batch(texts, show_progress=show_progress)

        # Convert to numpy array
        embeddings_np = np.array(embeddings, dtype='float32')

        # Create FAISS index
        logger.info(f"Creating FAISS index (dimension={self.dimension})...")
        self.index = faiss.IndexFlatL2(self.dimension)
        self.index.add(embeddings_np)

        self.metadata = metadata
        self.texts = texts

        logger.info(f"Vector store built: {self.index.ntotal} vectors indexed")

    def search(self, query: str, k: int = 5) -> List[Dict]:
        """
        Search for similar entities.

        Args:
            query: Query text
            k: Number of results to return

        Returns:
            List of results with metadata and scores
        """
        if self.index is None:
            raise RuntimeError("Vector store not built or loaded")

        # Get query embedding
        query_embedding = self.embedder.embed(query)
        query_np = np.array([query_embedding], dtype='float32')

        # Search
        distances, indices = self.index.search(query_np, k)

        # Format results
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < len(self.metadata):
                result = {
                    **self.metadata[idx],
                    'content': self.texts[idx],
                    'distance': float(dist),
                    'similarity': 1 / (1 + float(dist))  # Convert L2 distance to similarity
                }
                results.append(result)

        return results

    def save(self):
        """Save vector store to disk"""
        logger.info("Saving vector store...")

        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        # Save FAISS index
        faiss.write_index(self.index, str(self.index_path))
        logger.info(f"Index saved to {self.index_path}")

        # Save metadata
        with open(self.metadata_path, 'wb') as f:
            pickle.dump(self.metadata, f)
        logger.info(f"Metadata saved to {self.metadata_path}")

        # Save texts
        with open(self.texts_path, 'wb') as f:
            pickle.dump(self.texts, f)
        logger.info(f"Texts saved to {self.texts_path}")

    def load(self):
        """Load vector store from disk"""
        logger.info("Loading vector store from disk...")

        if not self.index_path.exists():
            raise FileNotFoundError(f"Index file not found: {self.index_path}")

        # Load FAISS index
        self.index = faiss.read_index(str(self.index_path))
        logger.info(f"Index loaded: {self.index.ntotal} vectors")

        # Load metadata
        with open(self.metadata_path, 'rb') as f:
            self.metadata = pickle.load(f)
        logger.info(f"Metadata loaded: {len(self.metadata)} entries")

        # Load texts
        with open(self.texts_path, 'rb') as f:
            self.texts = pickle.load(f)
        logger.info(f"Texts loaded: {len(self.texts)} entries")

    def exists(self) -> bool:
        """Check if saved vector store exists"""
        return (self.index_path.exists() and
                self.metadata_path.exists() and
                self.texts_path.exists())


# Singleton
_vector_store = None

def get_vector_store() -> VectorStore:
    """Get global vector store instance"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
