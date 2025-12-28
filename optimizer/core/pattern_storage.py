"""
Pattern storage system using RAG for efficient error pattern retrieval.
Stores error patterns as embeddings and retrieves relevant ones based on question similarity.
"""

import json
import faiss
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger

from autoeval.config.settings import get_settings
from optimizer.rag.embedder import Embedder


class PatternStorage:
    """Store and retrieve error patterns using vector similarity search"""

    def __init__(self):
        self.settings = get_settings()
        self.embedder = Embedder()

        # Storage paths
        self.storage_dir = Path(self.settings.CACHE_DIR) / "error_patterns"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.patterns_file = self.storage_dir / "patterns.json"
        self.index_file = self.storage_dir / "patterns.index"

        # In-memory storage
        self.patterns: List[Dict[str, Any]] = []
        self.index: Optional[faiss.Index] = None

        # Load existing patterns
        self._load()

    def _load(self):
        """Load patterns and index from disk"""
        if self.patterns_file.exists() and self.index_file.exists():
            try:
                # Load patterns
                with open(self.patterns_file, 'r', encoding='utf-8') as f:
                    self.patterns = json.load(f)

                # Load FAISS index
                self.index = faiss.read_index(str(self.index_file))

                logger.info(f"Loaded {len(self.patterns)} error patterns from cache")
            except Exception as e:
                logger.warning(f"Failed to load patterns: {e}. Starting fresh.")
                self.patterns = []
                self.index = None
        else:
            logger.info("No existing error patterns found. Starting fresh.")

    def _save(self):
        """Save patterns and index to disk"""
        try:
            # Save patterns
            with open(self.patterns_file, 'w', encoding='utf-8') as f:
                json.dump(self.patterns, f, ensure_ascii=False, indent=2)

            # Save FAISS index
            if self.index is not None:
                faiss.write_index(self.index, str(self.index_file))

            logger.debug(f"Saved {len(self.patterns)} patterns to disk")
        except Exception as e:
            logger.error(f"Failed to save patterns: {e}")

    def add_pattern(self, pattern: Dict[str, Any]):
        """
        Add a new error pattern to storage.

        Args:
            pattern: Dict containing:
                - description: str (what went wrong)
                - guideline: str (how to fix it)
                - category: str (entity type: diseases, vaccines, etc.)
                - error_type: str (factual_error, incomplete, etc.)
                - severity: str (critical, major, minor)
                - frequency: int (how many times seen)
                - examples: List[str] (example questions/answers)
        """
        try:
            # Generate embedding for the pattern description
            embedding = self.embedder.embed(pattern['description'])

            # Initialize index if needed
            if self.index is None:
                dimension = len(embedding)
                self.index = faiss.IndexFlatL2(dimension)

            # Add to index
            embedding_np = np.array([embedding], dtype=np.float32)
            self.index.add(embedding_np)

            # Add to patterns list
            pattern_id = len(self.patterns)
            pattern['id'] = pattern_id
            self.patterns.append(pattern)

            # Save to disk
            self._save()

            logger.debug(f"Added pattern: {pattern['description'][:50]}...")

        except Exception as e:
            logger.error(f"Failed to add pattern: {e}")

    def add_patterns_batch(self, patterns: List[Dict[str, Any]]):
        """Add multiple patterns efficiently"""
        logger.info(f"Adding {len(patterns)} patterns to storage...")

        if not patterns:
            return

        try:
            # Generate all embeddings
            descriptions = [p['description'] for p in patterns]
            embeddings = self.embedder.embed_batch(descriptions, show_progress=False)

            # Initialize index if needed
            if self.index is None:
                dimension = len(embeddings[0])
                self.index = faiss.IndexFlatL2(dimension)

            # Add all embeddings to index
            embeddings_np = np.array(embeddings, dtype=np.float32)
            self.index.add(embeddings_np)

            # Add all patterns
            for i, pattern in enumerate(patterns):
                pattern['id'] = len(self.patterns) + i
                self.patterns.append(pattern)

            # Save to disk
            self._save()

            logger.info(f"Successfully added {len(patterns)} patterns")

        except Exception as e:
            logger.error(f"Failed to add patterns batch: {e}")

    def retrieve_relevant(
        self,
        question: str,
        k: int = 5,
        category: Optional[str] = None,
        min_severity: str = "minor",
        threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve top-k most relevant error patterns for a question.

        Args:
            question: The question to get patterns for
            k: Number of patterns to retrieve
            category: Optional filter by category (diseases, vaccines, etc.)
            min_severity: Minimum severity to include (critical > major > minor)
            threshold: Minimum relevance score (0-1, uses RAG_RELEVANCE_THRESHOLD if None)

        Returns:
            List of relevant patterns sorted by relevance (may be empty if none meet threshold)
        """
        if self.index is None or len(self.patterns) == 0:
            logger.debug("No patterns in storage yet")
            return []

        # Get threshold from settings if not provided
        if threshold is None:
            threshold = getattr(self.settings, 'RAG_RELEVANCE_THRESHOLD', 0.0)

        try:
            # Embed the question
            query_embedding = self.embedder.embed(question)
            query_np = np.array([query_embedding], dtype=np.float32)

            # Search for similar patterns (get more than k for filtering)
            search_k = min(k * 3, len(self.patterns))
            distances, indices = self.index.search(query_np, search_k)

            # Retrieve patterns
            results = []
            severity_order = {"critical": 3, "major": 2, "minor": 1}
            min_severity_level = severity_order.get(min_severity, 1)

            for idx, distance in zip(indices[0], distances[0]):
                if idx < len(self.patterns):
                    pattern = self.patterns[idx].copy()
                    pattern['relevance_score'] = float(1.0 / (1.0 + distance))  # Convert to similarity

                    # Apply relevance threshold filter
                    if threshold > 0 and pattern['relevance_score'] < threshold:
                        continue

                    # Apply category filter (allow 'general' to match all)
                    pattern_category = pattern.get('category', 'general')
                    if category and pattern_category != category and pattern_category != 'general':
                        continue

                    severity_level = severity_order.get(pattern.get('severity', 'minor'), 1)
                    if severity_level < min_severity_level:
                        continue

                    results.append(pattern)

                    if len(results) >= k:
                        break

            if threshold > 0 and len(results) < k:
                logger.info(
                    f"Pattern retrieval: Found {len(results)}/{k} patterns above threshold {threshold:.2f}"
                )
            logger.debug(f"Retrieved {len(results)} relevant patterns for question")
            return results

        except Exception as e:
            logger.error(f"Failed to retrieve patterns: {e}")
            return []

    def get_top_patterns(
        self,
        n: int = 10,
        category: Optional[str] = None,
        min_frequency: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Get top N most frequent error patterns.

        Args:
            n: Number of patterns to return
            category: Optional filter by category
            min_frequency: Minimum frequency to include

        Returns:
            List of patterns sorted by frequency
        """
        filtered = [
            p for p in self.patterns
            if p.get('frequency', 0) >= min_frequency
            and (category is None or p.get('category') == category)
        ]

        # Sort by frequency
        sorted_patterns = sorted(
            filtered,
            key=lambda x: x.get('frequency', 0),
            reverse=True
        )

        return sorted_patterns[:n]

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about stored patterns"""
        if not self.patterns:
            return {
                'total_patterns': 0,
                'by_category': {},
                'by_severity': {},
                'by_error_type': {}
            }

        stats = {
            'total_patterns': len(self.patterns),
            'by_category': {},
            'by_severity': {},
            'by_error_type': {}
        }

        for pattern in self.patterns:
            # Count by category
            category = pattern.get('category', 'unknown')
            stats['by_category'][category] = stats['by_category'].get(category, 0) + 1

            # Count by severity
            severity = pattern.get('severity', 'unknown')
            stats['by_severity'][severity] = stats['by_severity'].get(severity, 0) + 1

            # Count by error type
            error_type = pattern.get('error_type', 'unknown')
            stats['by_error_type'][error_type] = stats['by_error_type'].get(error_type, 0) + 1

        return stats
