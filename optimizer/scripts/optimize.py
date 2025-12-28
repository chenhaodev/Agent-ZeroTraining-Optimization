#!/usr/bin/env python3
"""
Optimizer - Convert LLM weaknesses into improved prompts

Takes evaluation results from autoeval and generates:
1. Improved prompt versions (v1.0 → v1.1 → v1.2...)
2. Hierarchical Pattern Storage index (when prompts get too long)
3. Weakness pattern storage
"""

import sys
import argparse
import json
from pathlib import Path
from loguru import logger
from datetime import datetime

# Add repo root to path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root))

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add("outputs/logs/optimizer.log", rotation="10 MB", level="DEBUG")

from optimizer.core.pattern_analyzer import PatternAnalyzer
from optimizer.core.pattern_storage import PatternStorage
from optimizer.core.prompt_optimizer import PromptOptimizer


def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Optimizer - Generate improved prompts from evaluation results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Optimize using latest evaluation report
  python optimizer/scripts/optimize.py

  # Optimize using specific evaluation report
  python optimizer/scripts/optimize.py --eval-report eval_20251228_001

  # Show statistics about current prompt versions
  python optimizer/scripts/optimize.py --stats

  # List all stored weakness patterns
  python optimizer/scripts/optimize.py --list-patterns
        """
    )

    parser.add_argument(
        '--eval-report',
        type=str,
        help='Specific evaluation report ID to use (e.g., eval_20251228_001)'
    )

    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics about prompt versions and patterns'
    )

    parser.add_argument(
        '--list-patterns',
        action='store_true',
        help='List all stored weakness patterns'
    )

    parser.add_argument(
        '--incremental',
        action='store_true',
        default=True,
        help='Generate incremental version (v1.0 → v1.1) instead of replacing'
    )

    return parser.parse_args()


def find_latest_report():
    """Find the most recent evaluation report"""
    reports_dir = Path("outputs/reports")
    if not reports_dir.exists():
        return None

    # Find all report directories
    report_dirs = [d for d in reports_dir.iterdir() if d.is_dir() and d.name.startswith('eval_')]
    if not report_dirs:
        return None

    # Sort by name (timestamp is in name) and get latest
    latest = sorted(report_dirs, key=lambda x: x.name, reverse=True)[0]
    return latest.name


def load_evaluation_report(report_id: str):
    """Load evaluation report"""
    report_path = Path(f"outputs/reports/{report_id}/report.json")

    if not report_path.exists():
        logger.error(f"Report not found: {report_path}")
        return None

    with open(report_path, 'r', encoding='utf-8') as f:
        report = json.load(f)

    logger.info(f"Loaded evaluation report: {report_id}")
    logger.info(f"  Total evaluations: {report['summary']['total_evaluations']}")
    logger.info(f"  Acceptance rate: {report['summary']['acceptance_rate']:.1%}")
    logger.info(f"  Average score: {report['summary']['average_scores']['overall']:.2f}/5.0")

    return report


def main():
    """Main optimization pipeline"""
    args = parse_args()

    logger.info("=" * 60)
    logger.info("Optimizer - Prompt Improvement System")
    logger.info("=" * 60)

    # Handle stats mode
    if args.stats:
        prompt_optimizer = PromptOptimizer()
        stats = prompt_optimizer.get_prompt_stats()

        logger.info("\n📊 Prompt Statistics:")
        logger.info(f"  Current version: {stats['current_version']}")
        logger.info(f"  Total versions: {stats['total_versions']}")
        logger.info(f"  Total patterns stored: {stats['pattern_storage']['total_patterns']}")

        if stats.get('versions'):
            logger.info("\n  Version history:")
            for version in stats['versions']:
                logger.info(f"    v{version['version']}: {version['patterns_count']} patterns")

        return

    # Handle list-patterns mode
    if args.list_patterns:
        pattern_storage = PatternStorage()
        patterns = pattern_storage.get_all_patterns()

        logger.info(f"\n📋 Stored Patterns ({len(patterns)} total):\n")

        for i, pattern in enumerate(patterns, 1):
            logger.info(f"{i}. [{pattern['severity'].upper()}] {pattern['description']}")
            logger.info(f"   Category: {pattern['category']} | Frequency: {pattern['frequency']}")
            if pattern.get('examples'):
                logger.info(f"   Example: {pattern['examples'][0][:100]}...")
            logger.info("")

        return

    # Find evaluation report
    if args.eval_report:
        report_id = args.eval_report
    else:
        logger.info("No report specified, finding latest...")
        report_id = find_latest_report()
        if not report_id:
            logger.error("No evaluation reports found in outputs/reports/")
            logger.info("Run autoeval first: python autoeval/scripts/evaluate.py")
            sys.exit(1)

    # Load evaluation report
    report = load_evaluation_report(report_id)
    if not report:
        sys.exit(1)

    # Initialize components
    logger.info("\n[Step 1/4] Analyzing error patterns...")
    analyzer = PatternAnalyzer()
    analysis = analyzer.analyze_from_report(report)

    logger.info(f"  Found {len(analysis.get('error_patterns', []))} error patterns")
    logger.info(f"  Identified {len(analysis.get('knowledge_gaps', []))} knowledge gaps")

    # Store patterns with pattern retrieval
    logger.info("\n[Step 2/4] Storing patterns in hierarchical pattern storage...")
    pattern_storage = PatternStorage()

    for pattern in analysis.get('error_patterns', []):
        pattern_storage.add_pattern(pattern)

    logger.info(f"  ✓ Stored {len(analysis.get('error_patterns', []))} patterns")

    # Generate improved prompt
    logger.info("\n[Step 3/4] Generating improved prompt...")
    prompt_optimizer = PromptOptimizer()

    new_version = prompt_optimizer.generate_updated_prompt(
        analysis,
        incremental=args.incremental
    )

    logger.info(f"  ✓ Generated prompt version: {new_version}")

    # Show improvements
    logger.info("\n[Step 4/4] Summarizing improvements...")

    # Get prompt stats
    stats = prompt_optimizer.get_prompt_stats()

    logger.info(f"\n📈 Optimization Summary:")
    logger.info(f"  Previous version: {float(new_version) - 0.1:.1f}")
    logger.info(f"  New version: {new_version}")
    logger.info(f"  Total patterns in pattern database: {stats['pattern_storage']['total_patterns']}")
    logger.info(f"  Pattern categories: {len(set(p.get('category', 'unknown') for p in analysis.get('error_patterns', [])))}")

    logger.info(f"\n💡 Top Improvements:")
    for i, pattern in enumerate(analysis.get('error_patterns', [])[:5], 1):
        logger.info(f"  {i}. {pattern.get('description', 'Unknown')}")
        logger.info(f"     Severity: {pattern.get('severity', 'unknown')} | Frequency: {pattern.get('frequency', 0)}")

    logger.info(f"\n📁 Output Files:")
    logger.info(f"  Prompt: outputs/prompts/deepseek_system_v{new_version}.yaml")
    logger.info(f"  Patterns: outputs/cache/error_patterns/patterns.json")
    logger.info(f"  Pattern Index: outputs/cache/error_patterns/patterns.index")

    logger.info("\n" + "=" * 60)
    logger.info("✅ Optimization Complete!")
    logger.info("=" * 60)

    logger.info(f"\nNext steps:")
    logger.info(f"  1. Review prompt: cat outputs/prompts/deepseek_system_v{new_version}.yaml")
    logger.info(f"  2. Test improvements: python autoeval/scripts/evaluate.py --prompt-version {new_version}")
    logger.info(f"  3. Compare: python autoeval/scripts/evaluate.py --compare-mode")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nOptimization interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
