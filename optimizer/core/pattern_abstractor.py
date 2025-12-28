"""
Pattern abstraction using LLM to generate general reminders.

Takes clusters of specific error patterns and abstracts them into
broader, more generalizable guidelines using LLM.
"""

from typing import List, Dict, Any
from loguru import logger
from autoeval.services.api_client import APIClient


class PatternAbstractor:
    """Abstract specific patterns into general reminders using LLM"""

    def __init__(self, api_client: APIClient = None):
        """
        Args:
            api_client: APIClient instance (creates new one if not provided)
        """
        self.api_client = api_client or APIClient()

    def abstract_cluster(
        self,
        cluster_patterns: List[Dict[str, Any]],
        cluster_id: int
    ) -> Dict[str, Any]:
        """
        Abstract a cluster of patterns into a general reminder.

        Args:
            cluster_patterns: List of patterns in the cluster
            cluster_id: ID of the cluster

        Returns:
            Dictionary with:
                - general_reminder: Abstracted guideline
                - cluster_id: Cluster ID
                - n_patterns: Number of patterns in cluster
                - example_patterns: Sample patterns (for reference)
                - category: Inferred category
                - error_types: List of error types in cluster
        """
        if not cluster_patterns:
            return None

        logger.info(f"Abstracting cluster {cluster_id} ({len(cluster_patterns)} patterns)...")

        # Prepare pattern summaries for LLM
        pattern_summaries = []
        for i, p in enumerate(cluster_patterns[:10], 1):  # Max 10 examples
            pattern_summaries.append(
                f"{i}. [{p.get('error_type')}] {p.get('description', '')[:150]}"
            )

        # Build prompt for abstraction
        prompt = f"""你是一个医疗AI系统的提示词优化专家。你的任务是从一组具体的错误模式中提取出通用的指导原则。

以下是{len(cluster_patterns)}个相似的错误模式（显示前{min(len(cluster_patterns), 10)}个）：

{chr(10).join(pattern_summaries)}

请分析这些错误模式的共同点，生成一个**简洁、通用、可操作**的提醒/指导原则。

要求：
1. **简洁**：1-2句话，不超过100字
2. **通用**：提取共性，而非重复具体细节
3. **可操作**：明确告诉AI应该做什么或避免什么
4. **医疗专业**：使用准确的医疗术语

输出格式（只输出指导原则，不要其他内容）：
"""

        try:
            # Call LLM to abstract
            response = self.api_client.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Use cheaper model for abstraction
                messages=[
                    {"role": "system", "content": "你是医疗AI提示词优化专家，擅长从具体错误中提取通用规律。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for consistency
                max_tokens=200
            )

            general_reminder = response.choices[0].message.content.strip()

            # Get cluster metadata
            categories = set(p.get('category', 'unknown') for p in cluster_patterns)
            error_types = set(p.get('error_type', 'unknown') for p in cluster_patterns)

            # Determine primary category (most common)
            category_counts = {}
            for p in cluster_patterns:
                cat = p.get('category', 'unknown')
                category_counts[cat] = category_counts.get(cat, 0) + 1
            primary_category = max(category_counts.items(), key=lambda x: x[1])[0]

            abstraction = {
                'general_reminder': general_reminder,
                'cluster_id': cluster_id,
                'n_patterns': len(cluster_patterns),
                'example_patterns': [
                    {
                        'description': p.get('description', '')[:200],
                        'error_type': p.get('error_type'),
                        'frequency': p.get('frequency', 0)
                    }
                    for p in cluster_patterns[:3]  # Keep top 3 examples
                ],
                'category': primary_category,
                'categories': list(categories),
                'error_types': list(error_types),
                'avg_frequency': sum(p.get('frequency', 0) for p in cluster_patterns) / len(cluster_patterns)
            }

            logger.info(f"  Generated reminder: {general_reminder[:80]}...")
            return abstraction

        except Exception as e:
            logger.error(f"Failed to abstract cluster {cluster_id}: {e}")
            # Fallback: use most common pattern as reminder
            sorted_patterns = sorted(
                cluster_patterns,
                key=lambda x: x.get('frequency', 0),
                reverse=True
            )
            return {
                'general_reminder': f"关于{primary_category}：{sorted_patterns[0].get('guideline', '')}",
                'cluster_id': cluster_id,
                'n_patterns': len(cluster_patterns),
                'example_patterns': [],
                'category': primary_category,
                'categories': list(categories),
                'error_types': list(error_types),
                'avg_frequency': 0,
                'abstraction_failed': True
            }

    def abstract_all_clusters(
        self,
        clusters: Dict[int, List[Dict[str, Any]]],
        min_cluster_size: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Abstract all clusters into general reminders.

        Args:
            clusters: Dictionary of cluster_id -> patterns
            min_cluster_size: Only abstract clusters with >= this many patterns

        Returns:
            List of abstraction results
        """
        abstractions = []

        # Filter clusters by size
        large_clusters = {
            cid: patterns for cid, patterns in clusters.items()
            if len(patterns) >= min_cluster_size
        }

        logger.info(
            f"Abstracting {len(large_clusters)} clusters "
            f"(with >= {min_cluster_size} patterns) out of {len(clusters)} total"
        )

        for cluster_id, patterns in sorted(large_clusters.items()):
            abstraction = self.abstract_cluster(patterns, cluster_id)
            if abstraction:
                abstractions.append(abstraction)

        logger.info(f"Generated {len(abstractions)} general reminders")

        return abstractions

    def format_for_prompt(
        self,
        abstractions: List[Dict[str, Any]],
        max_reminders: int = 10
    ) -> Dict[str, List[str]]:
        """
        Format abstractions for inclusion in base prompt.

        Args:
            abstractions: Output from abstract_all_clusters()
            max_reminders: Maximum number of reminders to include

        Returns:
            Dictionary with categorized reminders
        """
        # Sort by average frequency (cluster importance)
        sorted_abstractions = sorted(
            abstractions,
            key=lambda x: x.get('avg_frequency', 0),
            reverse=True
        )[:max_reminders]

        # Group by category
        by_category = {
            'diseases': [],
            'vaccines': [],
            'examinations': [],
            'surgeries': [],
            'general': []
        }

        for abs in sorted_abstractions:
            category = abs.get('category', 'general')
            reminder = abs['general_reminder']

            if category in by_category:
                by_category[category].append(reminder)
            else:
                by_category['general'].append(reminder)

        # Also create a flat list of all reminders
        all_reminders = [abs['general_reminder'] for abs in sorted_abstractions]

        return {
            'by_category': by_category,
            'all_reminders': all_reminders,
            'metadata': {
                'total_reminders': len(all_reminders),
                'clusters_abstracted': len(abstractions),
                'avg_cluster_size': sum(a['n_patterns'] for a in sorted_abstractions) / len(sorted_abstractions) if sorted_abstractions else 0
            }
        }
