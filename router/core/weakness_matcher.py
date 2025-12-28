"""
Weakness pattern matcher for identifying DeepSeek API weaknesses.
Used by router to add targeted prompts even when pattern retrieval doesn't match.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger


class WeaknessMatcher:
    """
    Matches questions to known DeepSeek weakness patterns.

    Strategy:
    1. Load weakness patterns from JSON
    2. Match question to patterns using keywords and patterns
    3. Return relevant weakness reminders for prompt augmentation
    """

    def __init__(self, weakness_data_path: str = "optimizer/config/deepseek_weaknesses.json"):
        """
        Initialize weakness matcher.

        Args:
            weakness_data_path: Path to deepseek_weaknesses.json (default: optimizer/config/)
        """
        self.weakness_data_path = Path(weakness_data_path)
        self.weaknesses = self._load_weaknesses()

        logger.info(f"WeaknessMatcher initialized with {len(self.weaknesses)} weakness patterns")

    def _load_weaknesses(self) -> List[Dict[str, Any]]:
        """Load weakness patterns from JSON file"""
        if not self.weakness_data_path.exists():
            logger.warning(f"Weakness data not found: {self.weakness_data_path}")
            return []

        try:
            with open(self.weakness_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('weaknesses', [])
        except Exception as e:
            logger.error(f"Failed to load weaknesses: {e}")
            return []

    def match_weaknesses(
        self,
        question: str,
        entity_type: Optional[str] = None,
        top_k: int = 2,
        min_frequency: float = 0.15
    ) -> List[Dict[str, Any]]:
        """
        Find weakness patterns that match the question.

        Args:
            question: The question text
            entity_type: Optional entity type filter ('diseases', 'vaccines', etc.)
            top_k: Maximum number of patterns to return
            min_frequency: Minimum frequency threshold (0.0-1.0)

        Returns:
            List of matched weakness patterns with scores
        """
        matches = []

        for weakness in self.weaknesses:
            # Skip if frequency too low
            if weakness.get('frequency', 0) < min_frequency:
                continue

            # Calculate match score
            score = self._calculate_match_score(question, weakness, entity_type)

            if score > 0:
                matches.append({
                    'weakness_id': weakness['weakness_id'],
                    'category': weakness['category'],
                    'subcategory': weakness['subcategory'],
                    'description': weakness['description'],
                    'severity': weakness['severity'],
                    'frequency': weakness['frequency'],
                    'prompt_addition': weakness['prompt_addition'],
                    'match_score': score
                })

        # Sort by match score (descending) and take top_k
        matches.sort(key=lambda x: (x['match_score'], x['frequency']), reverse=True)
        top_matches = matches[:top_k]

        if top_matches:
            logger.info(
                f"Matched {len(top_matches)} weakness patterns for question: "
                f"{[m['weakness_id'] for m in top_matches]}"
            )

        return top_matches

    def _calculate_match_score(
        self,
        question: str,
        weakness: Dict[str, Any],
        entity_type: Optional[str] = None
    ) -> float:
        """
        Calculate how well a weakness pattern matches the question.

        Returns:
            Match score (0.0 = no match, 1.0 = perfect match)
        """
        score = 0.0
        question_lower = question.lower()

        triggers = weakness.get('triggers', {})

        # Check entity type match (30% weight)
        entity_types = triggers.get('entity_types', [])
        if entity_type and entity_types:
            if entity_type in entity_types:
                score += 0.30

        # Check keyword match (40% weight)
        keywords = triggers.get('keywords', [])
        if keywords:
            matched_keywords = sum(1 for kw in keywords if kw in question)
            if matched_keywords > 0:
                keyword_score = min(1.0, matched_keywords / len(keywords))
                score += 0.40 * keyword_score

        # Check question pattern match (30% weight)
        patterns = triggers.get('question_patterns', [])
        if patterns:
            matched_patterns = sum(1 for pat in patterns if pat in question)
            if matched_patterns > 0:
                pattern_score = min(1.0, matched_patterns / len(patterns))
                score += 0.30 * pattern_score

        return score

    def get_prompt_additions(
        self,
        question: str,
        entity_type: Optional[str] = None,
        top_k: int = 2
    ) -> str:
        """
        Get formatted prompt additions for matched weaknesses.

        Args:
            question: The question text
            entity_type: Optional entity type filter
            top_k: Maximum number of patterns to include

        Returns:
            Formatted prompt additions (empty string if no matches)
        """
        matches = self.match_weaknesses(question, entity_type, top_k=top_k)

        if not matches:
            return ""

        # Build prompt additions
        additions = []
        for match in matches:
            additions.append(match['prompt_addition'])

        # Format as a section
        if additions:
            formatted = "\n\n## ⚠️ 针对该问题类型的特别提醒\n"
            formatted += "\n".join(additions)
            return formatted

        return ""

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about weakness patterns"""
        categories = {}
        severities = {}

        for w in self.weaknesses:
            cat = w.get('category', 'unknown')
            sev = w.get('severity', 'unknown')

            categories[cat] = categories.get(cat, 0) + 1
            severities[sev] = severities.get(sev, 0) + 1

        return {
            'total_weaknesses': len(self.weaknesses),
            'by_category': categories,
            'by_severity': severities,
            'avg_frequency': sum(w.get('frequency', 0) for w in self.weaknesses) / len(self.weaknesses) if self.weaknesses else 0
        }


# Singleton instance
_weakness_matcher: Optional[WeaknessMatcher] = None


def get_weakness_matcher() -> WeaknessMatcher:
    """Get the global weakness matcher instance"""
    global _weakness_matcher
    if _weakness_matcher is None:
        _weakness_matcher = WeaknessMatcher()
    return _weakness_matcher
