"""
JSON report generation.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict
from loguru import logger

from autoeval.core.models import Evaluation
from autoeval.config.settings import get_settings


class JSONReporter:
    """Generate JSON reports from evaluations"""

    def __init__(self):
        self.settings = get_settings()

    def generate(
        self,
        evaluations: List[Evaluation],
        analysis: Dict,
        report_id: str = None
    ) -> str:
        """
        Generate JSON report.

        Args:
            evaluations: List of Evaluation objects
            analysis: Analysis dictionary from PatternAnalyzer
            report_id: Optional report ID (generated if not provided)

        Returns:
            Report ID
        """
        if report_id is None:
            report_id = f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"Generating JSON report: {report_id}")

        # Create report directory
        report_dir = self.settings.get_report_dir(report_id)
        report_dir.mkdir(parents=True, exist_ok=True)

        # Build report data
        report = {
            'metadata': {
                'report_id': report_id,
                'timestamp': datetime.now().isoformat(),
                'evaluator_model': self.settings.EVALUATOR_MODEL,
                'generator_model': self.settings.ANSWER_GEN_MODEL,
                'sample_size': len(evaluations)
            },
            'summary': {
                'total_evaluations': analysis['total_evaluations'],
                'average_scores': analysis['average_scores'],
                'acceptance_rate': analysis['acceptance_rate'],
                'error_breakdown': analysis['error_breakdown']
            },
            'analysis': {
                'knowledge_gaps': analysis['knowledge_gaps'],
                'error_examples': analysis['error_examples'],
                'recommendations': analysis['recommendations']
            },
            'evaluations': []
        }

        # Add detailed evaluations
        for eval in evaluations:
            eval_data = {
                'question': {
                    'text': eval.question.question,
                    'category': eval.question.category,
                    'difficulty': eval.question.difficulty,
                    'source': eval.question.source_entity_name
                },
                'answer': eval.answer.answer,
                'scores': eval.scores,
                'errors': [
                    {
                        'type': err.type,
                        'severity': err.severity,
                        'description': err.description
                    }
                    for err in eval.errors
                ],
                'is_acceptable': eval.is_acceptable
            }
            report['evaluations'].append(eval_data)

        # Save full report
        report_path = report_dir / "report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"JSON report saved: {report_path}")

        # Save summary only
        summary_path = report_dir / "summary.json"
        summary = {
            'report_id': report_id,
            'timestamp': report['metadata']['timestamp'],
            'summary': report['summary'],
            'recommendations': analysis['recommendations']
        }
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        logger.info(f"Summary saved: {summary_path}")

        return report_id
