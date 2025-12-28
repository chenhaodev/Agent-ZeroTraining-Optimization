"""
Markdown report generator for human-readable evaluation results.
"""

from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from loguru import logger

from autoeval.config.settings import get_settings


class MarkdownReporter:
    """Generate human-readable markdown reports"""

    def __init__(self):
        self.settings = get_settings()

    def generate(
        self,
        evaluations: List[Dict[str, Any]],
        analysis: Dict[str, Any],
        report_id: str
    ) -> Path:
        """
        Generate markdown report.

        Args:
            evaluations: List of evaluation results
            analysis: Analysis from PatternAnalyzer
            report_id: Report identifier

        Returns:
            Path to generated markdown file
        """
        logger.info(f"Generating markdown report: {report_id}")

        report_dir = Path(self.settings.REPORTS_DIR) / report_id
        report_dir.mkdir(parents=True, exist_ok=True)

        report_file = report_dir / "report.md"

        # Build report sections
        content = self._build_report(evaluations, analysis, report_id)

        # Write to file
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"Markdown report saved: {report_file}")
        return report_file

    def _build_report(
        self,
        evaluations: List[Dict[str, Any]],
        analysis: Dict[str, Any],
        report_id: str
    ) -> str:
        """Build complete markdown report"""

        sections = [
            self._build_header(report_id, analysis),
            self._build_executive_summary(analysis),
            self._build_score_breakdown(analysis),
            self._build_error_analysis(analysis),
            self._build_recommendations(analysis),
            self._build_examples(evaluations, analysis),
            self._build_detailed_results(evaluations)
        ]

        return "\n\n".join(sections)

    def _build_header(self, report_id: str, analysis: Dict[str, Any]) -> str:
        """Build report header"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return f"""# Medical AI Evaluation Report

**Report ID:** `{report_id}`
**Generated:** {timestamp}
**Total Evaluations:** {analysis['total_evaluations']}
**Overall Score:** {analysis['average_scores']['overall']:.2f}/5.0
**Acceptance Rate:** {analysis['acceptance_rate']:.1%}

---"""

    def _build_executive_summary(self, analysis: Dict[str, Any]) -> str:
        """Build executive summary section"""

        overall = analysis['average_scores']['overall']

        # Determine quality level
        if overall >= 4.5:
            quality = "🟢 **Excellent**"
            summary = "系统回答质量优秀，达到部署标准。"
        elif overall >= 4.0:
            quality = "🟡 **Good**"
            summary = "系统回答质量良好，但仍有改进空间。"
        elif overall >= 3.0:
            quality = "🟠 **Acceptable**"
            summary = "系统回答质量可接受，建议优化后再部署。"
        else:
            quality = "🔴 **Needs Improvement**"
            summary = "系统回答质量需要显著提升。"

        # Top issues
        error_breakdown = analysis.get('error_breakdown', {})
        sorted_errors = sorted(error_breakdown.items(), key=lambda x: x[1], reverse=True)
        top_issues = sorted_errors[:3]

        issues_text = "\n".join([
            f"- **{error_type}**: {count} occurrences"
            for error_type, count in top_issues
        ])

        return f"""## Executive Summary

### Overall Quality: {quality}

{summary}

### Top Issues:
{issues_text}

### Key Metrics:
- **Accuracy**: {analysis['average_scores']['accuracy']:.2f}/5.0
- **Completeness**: {analysis['average_scores']['completeness']:.2f}/5.0
- **Relevance**: {analysis['average_scores']['relevance']:.2f}/5.0
- **Clarity**: {analysis['average_scores']['clarity']:.2f}/5.0
- **Safety**: {analysis['average_scores']['safety']:.2f}/5.0

---"""

    def _build_score_breakdown(self, analysis: Dict[str, Any]) -> str:
        """Build detailed score breakdown"""

        scores = analysis['average_scores']

        # Create ASCII bar chart
        def make_bar(score: float, max_score: float = 5.0) -> str:
            filled = int((score / max_score) * 20)
            empty = 20 - filled
            return f"{'█' * filled}{'░' * empty} {score:.2f}"

        return f"""## Score Breakdown

| Dimension | Score | Visualization |
|-----------|-------|---------------|
| **Accuracy** | {scores['accuracy']:.2f}/5.0 | `{make_bar(scores['accuracy'])}` |
| **Completeness** | {scores['completeness']:.2f}/5.0 | `{make_bar(scores['completeness'])}` |
| **Relevance** | {scores['relevance']:.2f}/5.0 | `{make_bar(scores['relevance'])}` |
| **Clarity** | {scores['clarity']:.2f}/5.0 | `{make_bar(scores['clarity'])}` |
| **Safety** | {scores['safety']:.2f}/5.0 | `{make_bar(scores['safety'])}` |
| **Overall** | {scores['overall']:.2f}/5.0 | `{make_bar(scores['overall'])}` |

---"""

    def _build_error_analysis(self, analysis: Dict[str, Any]) -> str:
        """Build error analysis section"""

        error_breakdown = analysis.get('error_breakdown', {})

        if not error_breakdown:
            return "## Error Analysis\n\n✅ No significant errors detected!\n\n---"

        total_errors = sum(error_breakdown.values())

        # Create error distribution
        error_rows = []
        for error_type, count in sorted(error_breakdown.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_errors * 100) if total_errors > 0 else 0
            bar_length = int(percentage / 5)  # Scale to 20 chars max
            bar = '█' * bar_length
            error_rows.append(f"| {error_type} | {count} | {percentage:.1f}% | `{bar}` |")

        error_table = "\n".join(error_rows)

        # Get error patterns
        patterns_section = self._build_error_patterns(analysis)

        return f"""## Error Analysis

### Error Distribution

**Total Errors:** {total_errors}

| Error Type | Count | Percentage | Distribution |
|------------|-------|------------|--------------|
{error_table}

{patterns_section}

---"""

    def _build_error_patterns(self, analysis: Dict[str, Any]) -> str:
        """Build error patterns section"""

        error_patterns = analysis.get('error_patterns', {})

        if not error_patterns:
            return ""

        sections = []

        for error_type, patterns in error_patterns.items():
            if not patterns:
                continue

            sections.append(f"### {error_type.replace('_', ' ').title()} Patterns\n")

            for i, pattern in enumerate(patterns[:5], 1):  # Top 5 patterns
                severity_emoji = {
                    'critical': '🔴',
                    'major': '🟡',
                    'minor': '🟢'
                }.get(pattern.get('severity', 'minor'), '⚪')

                sections.append(f"""**{i}. {severity_emoji} {pattern.get('description', 'N/A')}**
- **Frequency**: {pattern.get('count', 0)} times
- **Category**: {pattern.get('category', 'N/A')}
- **Guideline**: {pattern.get('guideline', 'N/A')}
""")

                # Add examples
                examples = pattern.get('examples', [])
                if examples:
                    sections.append("- **Examples**:")
                    for ex in examples[:2]:
                        question = ex.get('question', 'N/A')[:80]
                        sections.append(f"  - \"{question}...\"")

                sections.append("")

        return "\n".join(sections)

    def _build_recommendations(self, analysis: Dict[str, Any]) -> str:
        """Build recommendations section"""

        recommendations = analysis.get('recommendations', [])

        if not recommendations:
            return "## Recommendations\n\n✅ No specific recommendations at this time.\n\n---"

        # Categorize recommendations
        immediate = []
        short_term = []
        long_term = []

        for rec in recommendations:
            if '立即' in rec or '紧急' in rec:
                immediate.append(rec)
            elif '知识薄弱' in rec or '加强' in rec:
                long_term.append(rec)
            else:
                short_term.append(rec)

        sections = ["## Recommendations\n"]

        if immediate:
            sections.append("### 🔴 Immediate Actions\n")
            for rec in immediate:
                sections.append(f"- {rec}")
            sections.append("")

        if short_term:
            sections.append("### 🟡 Short-term Improvements\n")
            for rec in short_term:
                sections.append(f"- {rec}")
            sections.append("")

        if long_term:
            sections.append("### 🟢 Long-term Enhancements\n")
            for rec in long_term:
                sections.append(f"- {rec}")
            sections.append("")

        sections.append("---")

        return "\n".join(sections)

    def _build_examples(self, evaluations: List[Any], analysis: Dict[str, Any]) -> str:
        """Build examples section showing best and worst answers"""

        # Sort by overall score (evaluations are Pydantic models, not dicts)
        sorted_evals = sorted(evaluations, key=lambda x: x.scores['overall'], reverse=True)

        best = sorted_evals[:2]  # Top 2
        worst = sorted_evals[-2:]  # Bottom 2

        sections = ["## Example Cases\n"]

        # Best answers
        sections.append("### ✅ Excellent Answers\n")
        for i, eval_data in enumerate(best, 1):
            score = eval_data.scores['overall']
            question = eval_data.question.question[:100]
            answer = eval_data.answer.answer[:300]

            sections.append(f"""**Example {i}** (Score: {score:.1f}/5.0)

**Q:** {question}...

**A:** {answer}...

**Why it's good:** {eval_data.suggestions[:200] if eval_data.suggestions else 'Well-structured and accurate'}

""")

        # Worst answers
        sections.append("### ⚠️ Answers Needing Improvement\n")
        for i, eval_data in enumerate(worst, 1):
            score = eval_data.scores['overall']
            question = eval_data.question.question[:100]
            answer = eval_data.answer.answer[:300]

            sections.append(f"""**Example {i}** (Score: {score:.1f}/5.0)

**Q:** {question}...

**A:** {answer}...

**Issues:**
""")
            for error in eval_data.errors[:3]:
                sections.append(f"- {error.type}: {error.description}")

            sections.append("")

        sections.append("---")

        return "\n".join(sections)

    def _build_detailed_results(self, evaluations: List[Any]) -> str:
        """Build detailed results section"""

        sections = ["## Detailed Results\n"]

        sections.append("### All Evaluations\n")
        sections.append("| # | Question | Overall | Accuracy | Completeness | Errors |")
        sections.append("|---|----------|---------|----------|--------------|--------|")

        for i, eval_data in enumerate(evaluations, 1):
            question = eval_data.question.question[:50]
            overall = eval_data.scores['overall']
            accuracy = eval_data.scores['accuracy']
            completeness = eval_data.scores['completeness']
            error_count = len(eval_data.errors)

            sections.append(
                f"| {i} | {question}... | {overall:.1f} | {accuracy:.1f} | {completeness:.1f} | {error_count} |"
            )

        sections.append("")
        sections.append("---")
        sections.append("\n*End of Report*")

        return "\n".join(sections)
