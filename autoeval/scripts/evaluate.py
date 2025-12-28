#!/usr/bin/env python3
"""
Medical AI Evaluation Agent - Main CLI
"""

import sys
import argparse
import json
from datetime import datetime
from loguru import logger
from pathlib import Path

# Add repo root to path so we can import from autoeval
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root))

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add("outputs/logs/evaluation.log", rotation="10 MB", level="DEBUG")

from autoeval.core.loader import DataLoader
from autoeval.core.sampler import sample_data
from optimizer.rag.vector_store import get_vector_store
from autoeval.services.question_generator import QuestionGenerator
from autoeval.services.answer_generator import AnswerGenerator
from autoeval.services.evaluator import Evaluator
from optimizer.core.pattern_analyzer import PatternAnalyzer
from optimizer.core.prompt_optimizer import PromptOptimizer
from autoeval.utils.reporting.json_reporter import JSONReporter
from autoeval.utils.reporting.markdown_reporter import MarkdownReporter
from autoeval.config.settings import get_settings
from autoeval.config.tuning_presets import load_preset, list_presets


def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Medical AI Evaluation Agent - Build advanced prompts with TIERED RAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with defaults (balanced preset)
  python main.py

  # Disable RAG entirely (baseline)
  python main.py --no-rag

  # Custom RAG-k value
  python main.py --rag-k 3        # Cost-optimized
  python main.py --rag-k 8        # High accuracy

  # Use preset configuration
  python main.py --preset cost_optimized
  python main.py --preset high_accuracy

  # Disable category rules (Tier 2)
  python main.py --no-category-rules

  # Combine options
  python main.py --rag-k 8 --sample-size 50
  python main.py --preset balanced --questions-per-entity 5

  # Validation & Comparison
  python main.py --compare-mode              # Compare baseline vs optimized
  python main.py --prompt-version 1.1        # Use specific prompt version
  python main.py --baseline-only             # Establish baseline only
        """
    )

    # Prompt Optimization Configuration (RAG for AnswerGenerator, not Evaluator!)
    rag_group = parser.add_argument_group('Prompt Optimization Configuration')
    rag_group.add_argument(
        '--no-rag',
        action='store_true',
        help='Disable learned pattern retrieval (baseline mode - no prompt optimization)'
    )
    rag_group.add_argument(
        '--rag-k',
        type=int,
        help='Number of learned error patterns to retrieve for dynamic prompts (1-10). Note: Evaluator uses direct lookup, not RAG.'
    )
    rag_group.add_argument(
        '--no-category-rules',
        action='store_true',
        help='Disable Tier 2 category-specific rules'
    )

    # Preset Configuration
    preset_group = parser.add_argument_group('Preset Configuration')
    preset_group.add_argument(
        '--preset',
        type=str,
        choices=['baseline', 'cost_optimized', 'balanced', 'high_accuracy', 'maximum_quality', 'fast_iteration'],
        help='Use predefined configuration preset'
    )
    preset_group.add_argument(
        '--list-presets',
        action='store_true',
        help='List available presets and exit'
    )

    # Sampling Configuration
    sample_group = parser.add_argument_group('Sampling Configuration')
    sample_group.add_argument(
        '--sample-size',
        type=int,
        help='Number of entities to sample (default: 10 for testing, 100 for production)'
    )
    sample_group.add_argument(
        '--questions-per-entity',
        type=int,
        help='Number of questions to generate per entity (default: 3)'
    )

    # Vector Store Configuration
    vector_group = parser.add_argument_group('Vector Store Configuration')
    vector_group.add_argument(
        '--rebuild-index',
        action='store_true',
        help='Force rebuild of vector store index'
    )

    # Performance Configuration
    perf_group = parser.add_argument_group('Performance Configuration')
    perf_group.add_argument(
        '--max-workers',
        type=int,
        default=5,
        help='Maximum parallel workers for answer generation and evaluation (default: 5)'
    )

    # Validation & Comparison
    validation_group = parser.add_argument_group('Validation & Comparison')
    validation_group.add_argument(
        '--compare-mode',
        action='store_true',
        help='Run OOD validation comparing baseline vs optimized prompts'
    )
    validation_group.add_argument(
        '--prompt-version',
        type=str,
        help='Specific prompt version to use (e.g., "1.1", "1.2"). Uses latest if not specified.'
    )
    validation_group.add_argument(
        '--optimize-prompts',
        action='store_true',
        default=False,
        help='Generate optimized prompts after evaluation (disabled by default)'
    )
    validation_group.add_argument(
        '--baseline-only',
        action='store_true',
        default=True,
        help='Only run evaluation without optimization (DEFAULT behavior)'
    )
    validation_group.add_argument(
        '--load-qa-from',
        type=str,
        metavar='REPORT_ID',
        help='Load Q&A pairs from existing report (e.g., "eval_20251228_022927") - skip question/answer generation'
    )

    return parser.parse_args()


def apply_config(args, settings):
    """Apply command-line arguments to configuration"""
    config = {
        'use_rag': True,
        'rag_k': 5,
        'use_category_rules': True,
        'sample_size': 10,
        'questions_per_entity': 3,
        'rebuild_index': False,
        'max_workers': 5  # Parallel workers for answer gen & evaluation
    }

    # Apply preset first (if specified)
    if args.preset:
        logger.info(f"📋 Loading preset: {args.preset}")
        preset = load_preset(args.preset)
        config['rag_k'] = preset.get('rag_k', 5)
        config['use_category_rules'] = preset.get('use_category_rules', True)
        config['use_rag'] = (preset.get('rag_k', 0) > 0)

        logger.info(f"  RAG-k: {config['rag_k']}")
        logger.info(f"  Category rules: {config['use_category_rules']}")
        logger.info(f"  Estimated tokens: {preset.get('estimated_tokens', 'N/A')}")
        logger.info(f"  Estimated accuracy: {preset.get('estimated_accuracy', 'N/A')}/5.0")

    # Override with explicit flags
    if args.no_rag:
        config['use_rag'] = False
        config['rag_k'] = 0
        logger.info("🔕 RAG disabled (baseline mode)")

    if args.rag_k is not None:
        config['rag_k'] = args.rag_k
        config['use_rag'] = (args.rag_k > 0)
        logger.info(f"🔧 RAG-k set to: {args.rag_k}")

    if args.no_category_rules:
        config['use_category_rules'] = False
        logger.info("🔕 Category rules disabled (Tier 2 off)")

    if args.sample_size is not None:
        config['sample_size'] = args.sample_size

    if args.questions_per_entity is not None:
        config['questions_per_entity'] = args.questions_per_entity

    if args.rebuild_index:
        config['rebuild_index'] = True

    if args.max_workers:
        config['max_workers'] = args.max_workers
        logger.info(f"⚡ Parallel workers set to: {args.max_workers}")

    return config


def run_evaluation_workflow(config, settings, variant_name="default"):
    """
    Run the core evaluation workflow with given configuration.

    Returns:
        dict: Evaluation results including report_id, analysis, evaluations
    """
    sample_size = config['sample_size']
    questions_per_entity = config['questions_per_entity']

    # Step 1: Load data
    logger.info(f"\n[{variant_name}] Step 1/7: Loading medical data...")
    loader = DataLoader(settings.DATA_DIR)
    medical_data = loader.load_all()

    # Step 2: Sample data
    logger.info(f"\n[{variant_name}] Step 2/7: Sampling data (sample_size={sample_size})...")
    sampled_data = sample_data(medical_data, sample_size=sample_size, method="stratified")

    # Step 3: Build/load vector store
    logger.info(f"\n[{variant_name}] Step 3/7: Setting up vector store...")
    vector_store = get_vector_store()

    total_sampled = sum(len(entities) for entities in sampled_data.values())

    if config['rebuild_index'] or not vector_store.exists():
        logger.info("Building vector store for sampled data only...")
        vector_store.build(sampled_data, show_progress=True)
        vector_store.save()
        logger.info(f"✓ Vector store built ({total_sampled} entities)")
    else:
        logger.info("Loading existing vector store...")
        vector_store.load()

    # Step 4: Generate questions
    logger.info(f"\n[{variant_name}] Step 4/7: Generating questions ({questions_per_entity} per entity)...")
    question_gen = QuestionGenerator()
    all_questions = []

    for entity_type, entities in sampled_data.items():
        for entity in entities:
            questions = question_gen.generate(entity, num_questions=questions_per_entity)
            all_questions.extend(questions)

    logger.info(f"Total questions generated: {len(all_questions)}")

    # Step 5: Generate answers
    logger.info(f"\n[{variant_name}] Step 5/7: Generating answers with DeepSeek...")
    answer_gen = AnswerGenerator(
        use_dynamic_prompts=config['use_rag'],
        rag_k=config['rag_k'],
        use_category_rules=config['use_category_rules'],
        prompt_version=config.get('prompt_version', '1.0')
    )
    qa_pairs = []

    for question in all_questions:
        answer = answer_gen.generate(question)
        qa_pairs.append((question, answer))

    logger.info(f"Total answers generated: {len(qa_pairs)}")

    # Step 6: Evaluate with direct golden-ref lookup (no RAG!)
    logger.info(f"\n[{variant_name}] Step 6/7: Evaluating answers...")
    evaluator = Evaluator()
    evaluations = evaluator.evaluate_batch(qa_pairs)

    logger.info(f"Total evaluations completed: {len(evaluations)}")

    # Step 7: Analyze
    logger.info(f"\n[{variant_name}] Step 7/7: Analyzing results...")
    analyzer = PatternAnalyzer()
    analysis = analyzer.analyze(evaluations)

    return {
        'evaluations': evaluations,
        'analysis': analysis,
        'config': config,
        'variant_name': variant_name
    }


def run_comparison(config, settings):
    """
    Run OOD validation comparing baseline vs optimized prompts.

    Steps:
    1. Run baseline evaluation (no RAG, no category rules)
    2. Run optimized evaluation (with RAG + category rules + latest prompt)
    3. Generate comparison report
    """
    logger.info("="*80)
    logger.info("OOD VALIDATION: Baseline vs Optimized Comparison")
    logger.info("="*80)

    # Get latest prompt version
    prompt_optimizer = PromptOptimizer()
    latest_version = prompt_optimizer.current_version

    logger.info(f"\n📊 Comparison Setup:")
    logger.info(f"  Sample size: {config['sample_size']}")
    logger.info(f"  Questions per entity: {config['questions_per_entity']}")
    logger.info(f"  Latest prompt version: {latest_version}")

    # Configuration for baseline
    baseline_config = config.copy()
    baseline_config['use_rag'] = False
    baseline_config['rag_k'] = 0
    baseline_config['use_category_rules'] = False
    baseline_config['prompt_version'] = '1.0'

    # Configuration for optimized
    optimized_config = config.copy()
    optimized_config['use_rag'] = True
    optimized_config['rag_k'] = config.get('rag_k', 5)
    optimized_config['use_category_rules'] = True
    optimized_config['prompt_version'] = config.get('prompt_version', latest_version)

    # Run baseline evaluation
    logger.info("\n" + "="*80)
    logger.info("🔵 Running BASELINE evaluation (no RAG, no category rules, v1.0)")
    logger.info("="*80)
    baseline_results = run_evaluation_workflow(baseline_config, settings, variant_name="BASELINE")

    # Run optimized evaluation
    logger.info("\n" + "="*80)
    logger.info(f"🟢 Running OPTIMIZED evaluation (RAG-k={optimized_config['rag_k']}, category rules, v{optimized_config['prompt_version']})")
    logger.info("="*80)
    optimized_results = run_evaluation_workflow(optimized_config, settings, variant_name="OPTIMIZED")

    # Generate comparison report
    logger.info("\n" + "="*80)
    logger.info("📊 Generating Comparison Report")
    logger.info("="*80)

    baseline_analysis = baseline_results['analysis']
    optimized_analysis = optimized_results['analysis']

    # Calculate improvements
    baseline_score = baseline_analysis['average_scores']['overall']
    optimized_score = optimized_analysis['average_scores']['overall']
    score_improvement = ((optimized_score - baseline_score) / baseline_score) * 100

    baseline_acceptance = baseline_analysis['acceptance_rate']
    optimized_acceptance = optimized_analysis['acceptance_rate']
    acceptance_improvement = ((optimized_acceptance - baseline_acceptance) / baseline_acceptance) * 100

    # Print comparison
    logger.info("\n📊 COMPARISON RESULTS:")
    logger.info("="*80)
    logger.info(f"\n{'Metric':<30} {'Baseline':<15} {'Optimized':<15} {'Improvement':<15}")
    logger.info("-"*80)
    logger.info(f"{'Overall Score':<30} {baseline_score:<15.2f} {optimized_score:<15.2f} {score_improvement:+.1f}%")
    logger.info(f"{'Acceptance Rate':<30} {baseline_acceptance:<15.1%} {optimized_acceptance:<15.1%} {acceptance_improvement:+.1f}%")

    for dim in ['accuracy', 'completeness', 'relevance', 'clarity', 'safety']:
        b_score = baseline_analysis['average_scores'].get(dim, 0)
        o_score = optimized_analysis['average_scores'].get(dim, 0)
        improvement = ((o_score - b_score) / b_score * 100) if b_score > 0 else 0
        logger.info(f"{dim.capitalize():<30} {b_score:<15.2f} {o_score:<15.2f} {improvement:+.1f}%")

    logger.info("-"*80)
    logger.info(f"{'Error Count':<30} {sum(baseline_analysis['error_breakdown'].values()):<15} {sum(optimized_analysis['error_breakdown'].values()):<15}")

    # Save comparison report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    comparison_dir = Path(settings.REPORTS_DIR) / f"comparison_{timestamp}"
    comparison_dir.mkdir(parents=True, exist_ok=True)

    comparison_report = {
        'timestamp': timestamp,
        'sample_size': config['sample_size'],
        'questions_per_entity': config['questions_per_entity'],
        'baseline': {
            'config': baseline_config,
            'analysis': baseline_analysis,
            'prompt_version': '1.0'
        },
        'optimized': {
            'config': optimized_config,
            'analysis': optimized_analysis,
            'prompt_version': optimized_config['prompt_version']
        },
        'improvements': {
            'overall_score': {
                'baseline': baseline_score,
                'optimized': optimized_score,
                'improvement_pct': score_improvement
            },
            'acceptance_rate': {
                'baseline': baseline_acceptance,
                'optimized': optimized_acceptance,
                'improvement_pct': acceptance_improvement
            }
        }
    }

    report_file = comparison_dir / "comparison_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(comparison_report, f, indent=2, ensure_ascii=False)

    logger.info(f"\n📁 Comparison report saved to: {report_file}")
    logger.info("="*80)

    return comparison_report


def load_qa_pairs_from_report(report_id: str):
    """
    Load Q&A pairs from an existing evaluation report.

    Args:
        report_id: Report ID (e.g., "eval_20251228_022927")

    Returns:
        List of (Question, Answer) tuples

    Raises:
        FileNotFoundError: If report doesn't exist
        ValueError: If report format is invalid
    """
    from autoeval.core.models import Question, Answer

    report_path = Path(f"outputs/reports/{report_id}/report.json")

    if not report_path.exists():
        raise FileNotFoundError(
            f"Report not found: {report_path}\n"
            f"Available reports:\n" +
            "\n".join(f"  - {p.name}" for p in Path("outputs/reports").glob("eval_*") if p.is_dir())
        )

    logger.info(f"Loading Q&A pairs from: {report_path}")

    with open(report_path, 'r', encoding='utf-8') as f:
        report_data = json.load(f)

    if 'evaluations' not in report_data:
        raise ValueError(f"Invalid report format: missing 'evaluations' field")

    qa_pairs = []
    for i, eval_data in enumerate(report_data['evaluations']):
        # Reconstruct Question object
        q_data = eval_data['question']

        # Handle old format (text, source) vs new format (question, source_entity_name)
        question_text = q_data.get('question') or q_data.get('text', '')
        source_name = q_data.get('source_entity_name') or q_data.get('source', '')

        # Try to infer entity type from source name if not present
        # This is a best-effort approach for old reports
        if 'source_entity_type' not in q_data:
            # Default to 'disease' - most common type
            source_type = 'disease'
            source_id = i  # Use index as fallback ID
        else:
            source_type = q_data['source_entity_type']
            source_id = q_data.get('source_entity_id', i)

        question = Question(
            question=question_text,
            category=q_data.get('category', 'other'),
            difficulty=q_data.get('difficulty', 'medium'),
            source_entity_type=source_type,
            source_entity_id=source_id,
            source_entity_name=source_name
        )

        # Reconstruct Answer object
        # Handle both dict format and string format
        if isinstance(eval_data['answer'], dict):
            a_data = eval_data['answer']
            answer_text = a_data.get('answer', '')
            question_id = a_data.get('question_id', f'q-{i}')
            model = a_data.get('model', 'deepseek-chat')
            prompt_version = a_data.get('prompt_version', '1.0')
        else:
            # Old format: answer is just a string
            answer_text = eval_data['answer']
            question_id = f'q-{i}'
            model = 'deepseek-chat'
            prompt_version = '1.0'

        answer = Answer(
            question_id=question_id,
            answer=answer_text,
            model=model,
            prompt_version=prompt_version
        )

        qa_pairs.append((question, answer))

    logger.info(f"✓ Loaded {len(qa_pairs)} Q&A pairs from report")
    return qa_pairs


def main():
    """Main evaluation pipeline"""
    # Parse arguments
    args = parse_args()

    # Handle --list-presets
    if args.list_presets:
        print("\n📋 Available Presets:\n")
        preset_names = list_presets()
        for name, description in preset_names.items():
            print(f"{name}:")
            print(f"  {description}")
            # Load full preset to show details
            preset = load_preset(name)
            print(f"  RAG-k: {preset.get('rag_k', 'N/A')}")
            print(f"  Category rules: {'Yes' if preset.get('use_category_rules', False) else 'No'}")
            print(f"  Tokens: ~{preset.get('estimated_tokens', 'N/A')}")
            print(f"  Accuracy: ~{preset.get('estimated_accuracy', 'N/A')}/5.0")
            print()
        return

    settings = get_settings()
    config = apply_config(args, settings)

    # Add prompt_version to config if specified
    if args.prompt_version:
        config['prompt_version'] = args.prompt_version

    logger.info("=" * 60)
    logger.info("Medical AI Evaluation Agent")
    logger.info("Build Advanced Prompt + TIERED RAG")
    logger.info("=" * 60)

    # Handle comparison mode
    if args.compare_mode:
        logger.info("\n🔍 Mode: OOD Validation Comparison")
        run_comparison(config, settings)
        return

    # Handle baseline-only mode
    if args.baseline_only:
        logger.info("\n🔵 Mode: Baseline Evaluation Only")
        config['use_rag'] = False
        config['rag_k'] = 0
        config['use_category_rules'] = False
        config['prompt_version'] = '1.0'

    # Show configuration
    logger.info("\n📊 Configuration:")
    logger.info(f"  Sample size: {config['sample_size']}")
    logger.info(f"  Questions per entity: {config['questions_per_entity']}")
    logger.info(f"  RAG enabled: {config['use_rag']}")
    if config['use_rag']:
        logger.info(f"  RAG-k: {config['rag_k']}")
    logger.info(f"  Category rules (Tier 2): {config['use_category_rules']}")
    if 'prompt_version' in config:
        logger.info(f"  Prompt version: {config['prompt_version']}")

    sample_size = config['sample_size']
    questions_per_entity = config['questions_per_entity']

    # Check if loading from existing report
    if args.load_qa_from:
        logger.info(f"\n🔄 Loading Q&A pairs from existing report: {args.load_qa_from}")
        logger.info("⏩ Skipping steps 1-5 (data loading, sampling, Q&A generation)")

        try:
            qa_pairs = load_qa_pairs_from_report(args.load_qa_from)
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Failed to load Q&A pairs: {e}")
            return

        logger.info(f"✓ Loaded {len(qa_pairs)} Q&A pairs - jumping to evaluation")
    else:
        # Step 1: Load data
        logger.info("\n[Step 1/7] Loading medical data...")
        loader = DataLoader(settings.DATA_DIR)
        medical_data = loader.load_all()

        # Step 2: Sample data
        logger.info(f"\n[Step 2/7] Sampling data (sample_size={sample_size})...")
        sampled_data = sample_data(medical_data, sample_size=sample_size, method="stratified")

        # Step 3: Build/load vector store (ONLY for sampled entities - much faster!)
        logger.info("\n[Step 3/7] Setting up vector store...")
        logger.info("💡 Smart optimization: Only embedding sampled entities (not all 5,730)")
        vector_store = get_vector_store()

        # Calculate actual sample count
        total_sampled = sum(len(entities) for entities in sampled_data.values())
        logger.info(f"Building index for {total_sampled} sampled entities (~{total_sampled * 0.7:.0f} seconds)")

        if config['rebuild_index'] or not vector_store.exists():
            logger.info("Building vector store for sampled data only...")
            vector_store.build(sampled_data, show_progress=True)  # Only sample!
            vector_store.save()
            logger.info(f"✓ Vector store built ({total_sampled} entities)")
        else:
            logger.info("Loading existing vector store...")
            vector_store.load()

        # Step 4: Generate questions
        logger.info(f"\n[Step 4/7] Generating questions ({questions_per_entity} per entity)...")
        question_gen = QuestionGenerator()
        all_questions = []

        for entity_type, entities in sampled_data.items():
            logger.info(f"Processing {len(entities)} {entity_type}...")
            for entity in entities:
                questions = question_gen.generate(entity, num_questions=questions_per_entity)
                all_questions.extend(questions)

        logger.info(f"Total questions generated: {len(all_questions)}")

        # Step 5: Generate answers (with parallel processing)
        logger.info(f"\n[Step 5/7] Generating answers with DeepSeek...")
        answer_gen = AnswerGenerator(
            use_dynamic_prompts=config['use_rag'],
            rag_k=config['rag_k'],
            use_category_rules=config['use_category_rules'],
            prompt_version=config.get('prompt_version', '1.0')
        )

        # Use batch processing with parallel workers
        answers = answer_gen.generate_batch(all_questions, max_workers=config.get('max_workers', 5))
        qa_pairs = list(zip(all_questions, answers))

        logger.info(f"Total answers generated: {len(qa_pairs)}")

    # Step 6: Evaluate with direct golden-ref lookup (no RAG - parallel processing)
    step_num = "Re-Evaluation" if args.load_qa_from else "[Step 6/7]"
    logger.info(f"\n{step_num} Evaluating answers with GPT-5.1 (as judge)...")
    evaluator = Evaluator()
    evaluations = evaluator.evaluate_batch(qa_pairs, max_workers=config.get('max_workers', 5))

    logger.info(f"Total evaluations completed: {len(evaluations)}")

    # Step 7: Analyze and generate reports
    step_num = "Analysis" if args.load_qa_from else "[Step 7/7]"
    logger.info(f"\n{step_num} Analyzing results and generating reports...")

    analyzer = PatternAnalyzer()
    analysis = analyzer.analyze(evaluations)

    # JSON Report
    json_reporter = JSONReporter()
    report_id = json_reporter.generate(evaluations, analysis)

    # Markdown Report
    md_reporter = MarkdownReporter()
    md_file = md_reporter.generate(evaluations, analysis, report_id)
    logger.info(f"✓ Markdown report: {md_file}")

    # Step 7: Generate updated prompts (only if --optimize-prompts flag is set)
    new_version = None
    if args.optimize_prompts:
        logger.info(f"\n[Step 7/7] Optimizing prompts...")

        prompt_optimizer = PromptOptimizer()
        new_version = prompt_optimizer.generate_updated_prompt(analysis, incremental=True)

        # Show prompt stats
        prompt_stats = prompt_optimizer.get_prompt_stats()
        logger.info(f"✓ Generated prompt version: {new_version}")
        logger.info(f"  - Total patterns stored: {prompt_stats['pattern_storage']['total_patterns']}")
        logger.info(f"  - Prompt versions created: {prompt_stats['total_versions']}")
    else:
        logger.info(f"\n✓ Evaluation complete. To generate optimized prompts, use --optimize-prompts flag.")

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("EVALUATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Report ID: {report_id}")
    logger.info(f"Total Evaluations: {analysis['total_evaluations']}")
    logger.info(f"Acceptance Rate: {analysis['acceptance_rate']:.1%}")
    logger.info(f"\nAverage Scores:")
    for dim, score in analysis['average_scores'].items():
        logger.info(f"  - {dim}: {score:.2f}/5.0")

    logger.info(f"\nError Breakdown:")
    for error_type, count in analysis['error_breakdown'].items():
        logger.info(f"  - {error_type}: {count}")

    logger.info(f"\nRecommendations:")
    for i, rec in enumerate(analysis['recommendations'], 1):
        logger.info(f"  {i}. {rec}")

    logger.info(f"\n📊 Reports saved to: outputs/reports/{report_id}/")
    if new_version:
        logger.info(f"📝 Updated prompt: outputs/prompts/deepseek_system_v{new_version}.yaml")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nEvaluation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
