"""
Pattern clustering for representative selection.

Uses k-means clustering on pattern embeddings to ensure diverse,
representative pattern selection for the base prompt.
"""

from typing import List, Dict, Any, Optional
import numpy as np
from sklearn.cluster import KMeans
from collections import defaultdict
from loguru import logger


class PatternClusterer:
    """Cluster patterns for diverse representation"""

    def __init__(self, embedder, pattern_storage):
        """
        Args:
            embedder: Embedder instance for generating embeddings
            pattern_storage: PatternStorage instance with patterns and embeddings
        """
        self.embedder = embedder
        self.pattern_storage = pattern_storage

    def cluster_patterns(
        self,
        n_clusters: int = 20,
        min_cluster_size: int = 3
    ) -> Dict[int, List[Dict[str, Any]]]:
        """
        Cluster patterns using k-means on embeddings.

        Args:
            n_clusters: Number of clusters to create
            min_cluster_size: Minimum patterns per cluster (merge small clusters)

        Returns:
            Dictionary mapping cluster_id -> list of patterns
        """
        if len(self.pattern_storage.patterns) < n_clusters:
            logger.warning(
                f"Not enough patterns ({len(self.pattern_storage.patterns)}) "
                f"for {n_clusters} clusters. Reducing to {len(self.pattern_storage.patterns) // 2}"
            )
            n_clusters = max(1, len(self.pattern_storage.patterns) // 2)

        logger.info(f"Clustering {len(self.pattern_storage.patterns)} patterns into {n_clusters} clusters...")

        # Get embeddings from FAISS index
        # Note: We need to reconstruct embeddings or store them separately
        # For now, we'll re-embed the pattern descriptions
        descriptions = [p['description'] for p in self.pattern_storage.patterns]
        embeddings = self.embedder.embed_batch(descriptions, show_progress=True)
        embeddings_np = np.array(embeddings, dtype=np.float32)

        # Perform k-means clustering
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(embeddings_np)

        # Group patterns by cluster
        clusters = defaultdict(list)
        for pattern, cluster_id in zip(self.pattern_storage.patterns, cluster_labels):
            pattern['cluster_id'] = int(cluster_id)
            clusters[int(cluster_id)].append(pattern)

        # Log cluster statistics
        logger.info(f"Clustering complete. Created {len(clusters)} clusters")
        for cluster_id, patterns in sorted(clusters.items()):
            logger.debug(f"  Cluster {cluster_id}: {len(patterns)} patterns")

        # Merge small clusters into nearest larger cluster if needed
        if min_cluster_size > 1:
            clusters = self._merge_small_clusters(
                clusters,
                embeddings_np,
                cluster_labels,
                kmeans.cluster_centers_,
                min_cluster_size
            )

        return dict(clusters)

    def _merge_small_clusters(
        self,
        clusters: Dict[int, List[Dict]],
        embeddings: np.ndarray,
        cluster_labels: np.ndarray,
        cluster_centers: np.ndarray,
        min_size: int
    ) -> Dict[int, List[Dict]]:
        """Merge clusters smaller than min_size into nearest cluster"""

        small_clusters = [cid for cid, patterns in clusters.items() if len(patterns) < min_size]

        if not small_clusters:
            return clusters

        logger.info(f"Merging {len(small_clusters)} small clusters (< {min_size} patterns)...")

        for small_cid in small_clusters:
            # Find nearest cluster center
            small_center = cluster_centers[small_cid]
            distances = np.linalg.norm(cluster_centers - small_center, axis=1)
            distances[small_cid] = np.inf  # Don't merge with self
            nearest_cid = int(np.argmin(distances))

            # Merge patterns
            clusters[nearest_cid].extend(clusters[small_cid])

            # Update cluster_id in patterns
            for pattern in clusters[small_cid]:
                pattern['cluster_id'] = nearest_cid

            # Remove small cluster
            del clusters[small_cid]

            logger.debug(f"  Merged cluster {small_cid} -> {nearest_cid}")

        return clusters

    def select_representatives(
        self,
        clusters: Dict[int, List[Dict[str, Any]]],
        per_cluster: int = 1,
        strategy: str = "highest_frequency"
    ) -> List[Dict[str, Any]]:
        """
        Select representative patterns from each cluster.

        Args:
            clusters: Output from cluster_patterns()
            per_cluster: Number of representatives per cluster
            strategy: Selection strategy
                - "highest_frequency": Pick most frequent patterns
                - "highest_severity": Pick most severe patterns
                - "balanced": Mix of frequency and severity

        Returns:
            List of representative patterns
        """
        representatives = []

        for cluster_id, patterns in clusters.items():
            if strategy == "highest_frequency":
                # Sort by frequency, then severity
                sorted_patterns = sorted(
                    patterns,
                    key=lambda x: (x.get('frequency', 0), self._severity_score(x.get('severity', 'minor'))),
                    reverse=True
                )
            elif strategy == "highest_severity":
                # Sort by severity, then frequency
                sorted_patterns = sorted(
                    patterns,
                    key=lambda x: (self._severity_score(x.get('severity', 'minor')), x.get('frequency', 0)),
                    reverse=True
                )
            else:  # balanced
                # Combined score
                sorted_patterns = sorted(
                    patterns,
                    key=lambda x: (
                        self._severity_score(x.get('severity', 'minor')) * 0.5 +
                        min(x.get('frequency', 0) / 10, 1.0) * 0.5
                    ),
                    reverse=True
                )

            # Select top N from this cluster
            selected = sorted_patterns[:per_cluster]
            for pattern in selected:
                pattern['representative_of_cluster'] = cluster_id
            representatives.extend(selected)

        logger.info(
            f"Selected {len(representatives)} representative patterns "
            f"({per_cluster} per cluster, strategy={strategy})"
        )

        return representatives

    def _severity_score(self, severity: str) -> float:
        """Convert severity to numeric score"""
        severity_map = {
            'critical': 3.0,
            'major': 2.0,
            'minor': 1.0,
            'unknown': 0.5
        }
        return severity_map.get(severity, 0.5)

    def get_cluster_statistics(self, clusters: Dict[int, List[Dict]]) -> Dict[str, Any]:
        """Get statistics about clusters"""
        stats = {
            'n_clusters': len(clusters),
            'total_patterns': sum(len(patterns) for patterns in clusters.values()),
            'cluster_sizes': {},
            'clusters_by_category': defaultdict(lambda: defaultdict(int)),
            'clusters_by_error_type': defaultdict(lambda: defaultdict(int))
        }

        for cluster_id, patterns in clusters.items():
            stats['cluster_sizes'][cluster_id] = len(patterns)

            for pattern in patterns:
                category = pattern.get('category', 'unknown')
                error_type = pattern.get('error_type', 'unknown')
                stats['clusters_by_category'][cluster_id][category] += 1
                stats['clusters_by_error_type'][cluster_id][error_type] += 1

        return stats
