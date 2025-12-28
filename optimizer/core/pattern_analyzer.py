"""
Basic error pattern analysis.
"""

from typing import List, Dict
from collections import Counter, defaultdict
from loguru import logger

from autoeval.core.models import Evaluation


class PatternAnalyzer:
    """Analyze error patterns from evaluations"""

    def analyze(self, evaluations: List[Evaluation]) -> Dict:
        """
        Analyze evaluations to find patterns.

        Args:
            evaluations: List of Evaluation objects

        Returns:
            Analysis dictionary with patterns, gaps, and recommendations
        """
        logger.info(f"Analyzing {len(evaluations)} evaluations...")

        # Aggregate scores
        all_scores = defaultdict(list)
        for eval in evaluations:
            for dimension, score in eval.scores.items():
                all_scores[dimension].append(score)

        avg_scores = {dim: sum(scores) / len(scores) if scores else 0
                     for dim, scores in all_scores.items()}

        # Aggregate errors
        error_counts = Counter()
        error_examples = defaultdict(list)

        for eval in evaluations:
            for error in eval.errors:
                error_counts[error.type] += 1
                if len(error_examples[error.type]) < 3:  # Keep up to 3 examples
                    error_examples[error.type].append({
                        'question': eval.question.question,
                        'description': error.description,
                        'severity': error.severity
                    })

        # Aggregate knowledge gaps
        all_gaps = []
        for eval in evaluations:
            all_gaps.extend(eval.knowledge_gaps)

        gap_counts = Counter(all_gaps)

        # Calculate acceptance rate
        acceptable_count = sum(1 for eval in evaluations if eval.is_acceptable)
        acceptance_rate = acceptable_count / len(evaluations) if evaluations else 0

        # Generate recommendations
        recommendations = self._generate_recommendations(avg_scores, error_counts, gap_counts)

        analysis = {
            'total_evaluations': len(evaluations),
            'average_scores': avg_scores,
            'acceptance_rate': acceptance_rate,
            'error_breakdown': dict(error_counts),
            'error_examples': dict(error_examples),
            'knowledge_gaps': dict(gap_counts),
            'recommendations': recommendations
        }

        logger.info(f"Analysis complete. Overall score: {avg_scores.get('overall', 0):.2f}")
        return analysis

    def _generate_recommendations(
        self,
        avg_scores: Dict,
        error_counts: Counter,
        gap_counts: Counter
    ) -> List[str]:
        """Generate improvement recommendations"""
        recommendations = []

        # Score-based recommendations
        if avg_scores.get('accuracy', 5) < 4:
            recommendations.append("提高回答准确性：加强与参考资料的一致性")

        if avg_scores.get('completeness', 5) < 4:
            recommendations.append("增强回答完整性：确保覆盖问题的所有关键方面")

        if avg_scores.get('clarity', 5) < 4:
            recommendations.append("改善表达清晰度：使用更通俗易懂的语言")

        if avg_scores.get('safety', 5) < 4.5:
            recommendations.append("强化安全边界：明确不能替代专业医疗诊断")

        # Error-based recommendations
        total_errors = sum(error_counts.values())
        if total_errors > 0:
            if error_counts.get('incomplete', 0) > total_errors * 0.2:
                recommendations.append("针对信息不完整问题：在系统提示词中强调完整性要求")

            if error_counts.get('unclear', 0) > total_errors * 0.15:
                recommendations.append("针对表述不清问题：要求用简单语言解释专业术语")

        if error_counts.get('factual_error', 0) > 0:
            recommendations.append("针对事实错误：加强医学知识准确性训练")

        # Gap-based recommendations
        if gap_counts:
            top_gap = gap_counts.most_common(1)[0][0] if gap_counts else None
            if top_gap:
                recommendations.append(f"知识薄弱领域：{top_gap}")

        if not recommendations:
            recommendations.append("整体表现良好，继续保持")

        return recommendations
