#!/usr/bin/env python3
"""
Router Configuration Generator - Function 2

Generates smart routing configuration based on weakness patterns
and evaluation results. Decides when to use LLM-API, RAG, ReACT, etc.
"""

import sys
import json
import argparse
from pathlib import Path
from loguru import logger
from datetime import datetime

# Add repo root to path so we can import from both autoeval and router
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root))

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")

# Import from router
from router.core.weakness_matcher import get_weakness_matcher
# Note: simple_router might not exist - using decision_engine instead
from router.core.decision_engine import DecisionEngine as Router

# Import from autoeval for settings
from autoeval.config.settings import get_settings

def get_router():
    """Get router instance"""
    return Router()


def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Generate smart routing configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate router config
  python router_config.py

  # Test routing decisions on sample questions
  python router_config.py --test

  # Export router config as JSON
  python router_config.py --export router_config.json

  # Show router statistics
  python router_config.py --stats
        """
    )

    parser.add_argument(
        '--test',
        action='store_true',
        help='Test routing decisions on sample questions'
    )

    parser.add_argument(
        '--export',
        type=str,
        metavar='FILE',
        help='Export router configuration to JSON file'
    )

    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show router statistics and coverage'
    )

    parser.add_argument(
        '--min-confidence',
        type=float,
        default=0.70,
        help='Minimum confidence for RAG usage (default: 0.70)'
    )

    return parser.parse_args()


def generate_router_config(min_confidence=0.70):
    """
    Generate complete router configuration.

    Returns:
        dict: Router configuration with:
        - entity_coverage: Dict of entity names by category
        - weakness_patterns: List of weakness patterns
        - routing_rules: Decision rules for each tier
        - thresholds: Confidence and relevance thresholds
        - strategies: Available routing strategies
    """
    logger.info("=" * 60)
    logger.info("Router Configuration Generator")
    logger.info("=" * 60)

    # Initialize components
    router = get_router()
    weakness_matcher = get_weakness_matcher()
    settings = get_settings()

    # Get statistics
    router_stats = router.get_stats()
    weakness_stats = weakness_matcher.get_stats()

    logger.info(f"\n📊 Router Coverage:")
    logger.info(f"  Total entities: {router_stats['total_entities']}")
    logger.info(f"    - Diseases: {router_stats['diseases']}")
    logger.info(f"    - Examinations: {router_stats['examinations']}")
    logger.info(f"    - Surgeries: {router_stats['surgeries']}")
    logger.info(f"    - Vaccines: {router_stats['vaccines']}")

    logger.info(f"\n📋 Weakness Patterns:")
    logger.info(f"  Total patterns: {weakness_stats['total_weaknesses']}")
    logger.info(f"  By category:")
    for category, count in weakness_stats['by_category'].items():
        logger.info(f"    - {category}: {count}")
    logger.info(f"  By severity:")
    for severity, count in weakness_stats['by_severity'].items():
        logger.info(f"    - {severity}: {count}")

    # Build configuration
    config = {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'version': '2.0',
            'description': 'Smart routing configuration with three-tier decision logic'
        },
        'entity_coverage': {
            'total_entities': router_stats['total_entities'],
            'by_category': {
                'diseases': router_stats['diseases'],
                'examinations': router_stats['examinations'],
                'surgeries': router_stats['surgeries'],
                'vaccines': router_stats['vaccines']
            },
            'category_keywords': router_stats['category_keywords'],
            'ood_keywords': router_stats['ood_keywords']
        },
        'weakness_patterns': {
            'total_patterns': weakness_stats['total_weaknesses'],
            'by_category': weakness_stats['by_category'],
            'by_severity': weakness_stats['by_severity'],
            'avg_frequency': weakness_stats['avg_frequency']
        },
        'routing_tiers': {
            'tier_1': {
                'name': 'RAG Content Check',
                'description': 'Check if entity exists in database',
                'strategies': ['exact_match', 'category_match', 'partial_match'],
                'confidence_threshold': min_confidence,
                'action': 'use_rag' if True else 'skip_rag'
            },
            'tier_2': {
                'name': 'Weakness Pattern Match',
                'description': 'Match question to known weakness patterns',
                'min_frequency_threshold': 0.15,
                'top_k_patterns': 2,
                'action': 'add_weakness_reminders'
            },
            'tier_3': {
                'name': 'Baseline Fallback',
                'description': 'Use baseline prompt when no RAG or weakness match',
                'action': 'use_baseline_prompt'
            }
        },
        'thresholds': {
            'rag_confidence': min_confidence,
            'rag_relevance': settings.RAG_RELEVANCE_THRESHOLD,
            'weakness_frequency': 0.15,
            'weakness_top_k': 2
        },
        'strategies': {
            'LLM_API': {
                'enabled': True,
                'model': settings.ANSWER_GEN_MODEL,
                'description': 'Direct LLM-API call with enhanced prompts'
            },
            'RAG': {
                'enabled': settings.USE_SMART_ROUTING,
                'retrieval_k': settings.RETRIEVAL_TOP_K,
                'threshold': settings.RAG_RELEVANCE_THRESHOLD,
                'description': 'Retrieval-augmented generation from golden-refs'
            },
            'WEAKNESS': {
                'enabled': True,
                'top_k': 2,
                'min_frequency': 0.15,
                'description': 'Weakness-based targeted prompts'
            },
            'REACT': {
                'enabled': False,
                'description': 'ReACT-style reasoning (future enhancement)'
            }
        },
        'performance_targets': {
            'quality_improvement': '+10-15% on known weakness areas',
            'cost_savings': '15-25% via smart routing',
            'latency_overhead': '< 1ms for routing decision',
            'acceptance_rate_target': '>= 90%'
        }
    }

    return config


def test_routing_decisions():
    """Test routing decisions on sample questions"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Routing Decisions")
    logger.info("=" * 60)

    router = get_router()

    test_cases = [
        {"question": "糖尿病有哪些症状？", "entity_type": "diseases"},
        {"question": "高血压怎么治疗？", "entity_type": "diseases"},
        {"question": "CT检查需要注意什么？", "entity_type": "examinations"},
        {"question": "流感疫苗什么时候接种？", "entity_type": "vaccines"},
        {"question": "婴儿摇晃综合征如何预防？", "entity_type": "diseases"},  # OOD
        {"question": "感冒了怎么办？", "entity_type": "diseases"},  # Generic
    ]

    logger.info(f"\nTesting {len(test_cases)} questions:\n")

    for i, test_case in enumerate(test_cases, 1):
        question = test_case['question']
        entity_type = test_case['entity_type']

        logger.info(f"[{i}] {question}")

        decision = router.get_routing_decision(
            question=question,
            entity_type=entity_type
        )

        # Display decision
        rag_status = "✅ USE RAG" if decision['use_rag'] else "❌ SKIP RAG"
        logger.info(f"    RAG: {rag_status} (confidence: {decision['rag_confidence']:.2f})")
        logger.info(f"    Reason: {decision['rag_reason']}")

        if decision['has_weaknesses']:
            logger.info(f"    Weaknesses: {len(decision['weakness_patterns'])} patterns matched")
            for pattern in decision['weakness_patterns']:
                logger.info(f"      - {pattern['weakness_id']} (score: {pattern['match_score']:.2f})")
        else:
            logger.info(f"    Weaknesses: None matched")

        logger.info("")


def export_config(config, output_file):
    """Export configuration to JSON file"""
    output_path = Path(output_file)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    logger.info(f"\n✓ Configuration exported to: {output_path}")


def show_stats():
    """Show detailed router statistics"""
    logger.info("\n" + "=" * 60)
    logger.info("Router Statistics")
    logger.info("=" * 60)

    router = get_router()
    weakness_matcher = get_weakness_matcher()

    router_stats = router.get_stats()
    weakness_stats = weakness_matcher.get_stats()

    logger.info(f"\n📊 Entity Coverage:")
    logger.info(f"  Total: {router_stats['total_entities']}")
    logger.info(f"    - Diseases: {router_stats['diseases']} ({router_stats['diseases']/router_stats['total_entities']*100:.1f}%)")
    logger.info(f"    - Examinations: {router_stats['examinations']} ({router_stats['examinations']/router_stats['total_entities']*100:.1f}%)")
    logger.info(f"    - Surgeries: {router_stats['surgeries']} ({router_stats['surgeries']/router_stats['total_entities']*100:.1f}%)")
    logger.info(f"    - Vaccines: {router_stats['vaccines']} ({router_stats['vaccines']/router_stats['total_entities']*100:.1f}%)")

    logger.info(f"\n📋 Weakness Pattern Database:")
    logger.info(f"  Total patterns: {weakness_stats['total_weaknesses']}")
    logger.info(f"  Average frequency: {weakness_stats['avg_frequency']:.1%}")

    logger.info(f"\n  By Category:")
    for category, count in weakness_stats['by_category'].items():
        logger.info(f"    - {category}: {count}")

    logger.info(f"\n  By Severity:")
    for severity, count in weakness_stats['by_severity'].items():
        logger.info(f"    - {severity}: {count}")

    logger.info(f"\n🎯 Routing Coverage Estimate:")
    # Estimate how many questions will benefit from each tier
    logger.info(f"  Tier 1 (Weakness): ~15-25% of questions hit known weaknesses (HIGHEST PRIORITY)")
    logger.info(f"  Tier 2 (RAG supplement): ~70-80% of questions get supplemental context")
    logger.info(f"  Tier 3 (Baseline): ~5-10% of questions use base prompt only (fallback)")


def main():
    """Main entry point"""
    args = parse_args()

    # Generate router configuration
    config = generate_router_config(min_confidence=args.min_confidence)

    # Handle test mode
    if args.test:
        test_routing_decisions()

    # Handle export
    if args.export:
        export_config(config, args.export)
    else:
        # Default: show configuration summary
        logger.info("\n" + "=" * 60)
        logger.info("Router Configuration Summary")
        logger.info("=" * 60)

        logger.info(f"\n✅ Configuration generated successfully!")
        logger.info(f"\nRouter configuration includes:")
        logger.info(f"  - {config['entity_coverage']['total_entities']} entities indexed")
        logger.info(f"  - {config['weakness_patterns']['total_patterns']} weakness patterns")
        logger.info(f"  - 3-tier routing logic (Weakness → RAG supplement → Baseline)")
        logger.info(f"  - 4 routing strategies available")

        logger.info(f"\nThresholds:")
        logger.info(f"  - RAG confidence: {config['thresholds']['rag_confidence']}")
        logger.info(f"  - RAG relevance: {config['thresholds']['rag_relevance']}")
        logger.info(f"  - Weakness frequency: {config['thresholds']['weakness_frequency']}")

        logger.info(f"\nPerformance Targets:")
        for key, value in config['performance_targets'].items():
            logger.info(f"  - {key}: {value}")

    # Handle stats mode
    if args.stats:
        show_stats()

    # Show usage tip
    if not args.test and not args.export and not args.stats:
        logger.info(f"\n💡 Quick actions:")
        logger.info(f"  - Test routing: python router_config.py --test")
        logger.info(f"  - Show stats: python router_config.py --stats")
        logger.info(f"  - Export config: python router_config.py --export config.json")

    logger.info("\n" + "=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
