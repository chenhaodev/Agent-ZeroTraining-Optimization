"""
Test script for clustering-based prompt optimization.

Demonstrates the new clustering + LLM abstraction approach for
generating diverse, representative base prompts.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from optimizer.core.prompt_optimizer import PromptOptimizer
from optimizer.scripts.optimize import load_evaluation_report, find_latest_report
from optimizer.core.pattern_analyzer import PatternAnalyzer


def main():
    """Test clustering-based optimization"""

    logger.info("=" * 80)
    logger.info("Clustering-Based Prompt Optimization Test")
    logger.info("=" * 80)

    # Find latest evaluation report
    logger.info("\n[Step 1/5] Loading evaluation report...")
    report_id = find_latest_report()
    if not report_id:
        logger.error("No evaluation reports found!")
        logger.info("Run: python autoeval/scripts/evaluate.py first")
        return

    report = load_evaluation_report(report_id)
    if not report:
        return

    # Analyze patterns
    logger.info("\n[Step 2/5] Analyzing error patterns...")
    analyzer = PatternAnalyzer()

    from autoeval.core.models import Evaluation, Question, Answer, Error
    evaluations = []
    for i, eval_data in enumerate(report['evaluations']):
        q_data = eval_data['question']
        question = Question(
            question=q_data['text'],
            category=q_data['category'],
            difficulty=q_data['difficulty'],
            source_entity_type='unknown',
            source_entity_id=i,
            source_entity_name=q_data['source']
        )

        answer = Answer(
            question_id=f"q_{i}",
            answer=eval_data['answer'],
            model='deepseek-chat',
            prompt_version='1.0'
        )

        errors = []
        for e in eval_data.get('errors', []):
            errors.append(Error(
                type=e['type'],
                severity=e['severity'],
                description=e['description'],
                quote_from_answer=e.get('quote_from_answer', ''),
                correct_info_from_reference=e.get('correct_info_from_reference', '')
            ))

        evaluation = Evaluation(
            question=question,
            answer=answer,
            scores=eval_data['scores'],
            errors=errors,
            overall_score=eval_data['scores']['overall'],
            is_acceptable=eval_data['is_acceptable'],
            justification=eval_data.get('justification', ''),
            knowledge_gaps=eval_data.get('knowledge_gaps', []),
            suggestions=eval_data.get('suggestions', '')
        )
        evaluations.append(evaluation)

    analysis = analyzer.analyze(evaluations)

    # Merge in report-level analysis
    if 'analysis' in report:
        report_analysis = report['analysis']
        if 'knowledge_gaps' in report_analysis:
            analysis['knowledge_gaps'] = report_analysis['knowledge_gaps']
        if 'error_breakdown' not in analysis and 'error_breakdown' in report['summary']:
            analysis['error_breakdown'] = report['summary']['error_breakdown']

    # Convert error_examples to error_patterns
    if 'error_examples' in analysis:
        error_patterns = {}
        error_breakdown = analysis.get('error_breakdown', {})
        for error_type, examples in analysis['error_examples'].items():
            error_patterns[error_type] = [{
                'description': ex['description'],
                'severity': ex['severity'],
                'count': error_breakdown.get(error_type, 1),
                'examples': [ex],
                'category': 'general',
                'guideline': f"避免{error_type}错误：{ex['description']}"
            } for ex in examples]
        analysis['error_patterns'] = error_patterns

    logger.info(f"  Found {len(analysis.get('error_patterns', {}))} error types")
    logger.info(f"  Identified {len(analysis.get('knowledge_gaps', {}))} knowledge gaps")

    # Generate prompt with clustering
    logger.info("\n[Step 3/5] Generating prompt with clustering & abstraction...")
    optimizer = PromptOptimizer()

    new_version = optimizer.generate_updated_prompt_with_clustering(
        analysis,
        n_clusters=20,  # Create 20 clusters
        n_representatives=15,  # Select 15 representative patterns
        n_general_reminders=10,  # Generate 10 general reminders via LLM
        incremental=True
    )

    # Show results
    logger.info("\n[Step 4/5] Loading generated prompt...")
    import yaml
    prompt_file = optimizer.output_dir / f"deepseek_system_v{new_version}.yaml"
    with open(prompt_file, 'r', encoding='utf-8') as f:
        new_prompt = yaml.safe_load(f)

    logger.info("\n[Step 5/5] Summary of new prompt:")
    logger.info("=" * 80)
    logger.info(f"Version: {new_prompt['version']}")
    logger.info(f"Updated: {new_prompt['updated_at']}")

    memory = new_prompt.get('memory', {})

    if 'general_reminders' in memory:
        logger.info(f"\n📋 General Reminders ({len(memory['general_reminders'])} total):")
        for i, reminder in enumerate(memory['general_reminders'], 1):
            logger.info(f"  {i}. {reminder}")

    if 'representative_patterns' in memory:
        rep_patterns = memory['representative_patterns']
        if rep_patterns.get('mistakes'):
            logger.info(f"\n⚠️  Representative Mistakes ({len(rep_patterns['mistakes'])} total):")
            for i, mistake in enumerate(rep_patterns['mistakes'], 1):
                logger.info(f"  {i}. {mistake[:100]}...")

        if rep_patterns.get('guidelines'):
            logger.info(f"\n✅ Representative Guidelines ({len(rep_patterns['guidelines'])} total):")
            for i, guideline in enumerate(rep_patterns['guidelines'], 1):
                logger.info(f"  {i}. {guideline[:100]}...")

    if 'metadata' in memory:
        meta = memory['metadata']
        logger.info(f"\n📊 Clustering Metadata:")
        logger.info(f"  - Clusters created: {meta.get('n_clusters')}")
        logger.info(f"  - Representatives selected: {meta.get('n_representatives')}")
        logger.info(f"  - General reminders: {meta.get('n_general_reminders')}")
        logger.info(f"  - Total patterns in storage: {meta.get('total_patterns_in_storage')}")

    changes = new_prompt.get('changes', {})
    if 'clustering_stats' in changes:
        stats = changes['clustering_stats']
        logger.info(f"\n🔬 Clustering Statistics:")
        logger.info(f"  - Number of clusters: {stats.get('n_clusters')}")
        logger.info(f"  - Average cluster size: {stats.get('avg_cluster_size', 0):.1f}")
        logger.info(f"  - Abstractions generated: {stats.get('abstractions_generated')}")

    logger.info("\n" + "=" * 80)
    logger.info("✅ Clustering-based optimization complete!")
    logger.info("=" * 80)
    logger.info(f"\n📁 Output files:")
    logger.info(f"  Prompt: {prompt_file}")
    logger.info(f"  Metadata: {optimizer.output_dir / f'clustering_metadata_v{new_version}.json'}")
    logger.info(f"\nNext steps:")
    logger.info(f"  1. Review: cat {prompt_file}")
    logger.info(f"  2. Test: python autoeval/scripts/evaluate.py --prompt-version {new_version}")
    logger.info(f"  3. Compare: python autoeval/scripts/evaluate.py --compare-mode")


if __name__ == "__main__":
    main()
