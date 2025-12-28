#!/usr/bin/env python3
"""
Threshold Optimization Tool
Tests different retrieval thresholds (0.3, 0.4, 0.5, 0.6) to find optimal precision/recall balance
"""
import sys
from pathlib import Path
from collections import defaultdict

# Add repo root to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

from optimizer.core.pattern_storage import PatternStorage
from loguru import logger


# Test questions covering all categories
TEST_QUESTIONS = [
    # Diseases
    {"question": "膝关节半月板损伤是什么病，会有什么影响？", "category": "diseases"},
    {"question": "糖尿病患者平时要注意什么饮食禁忌？", "category": "diseases"},
    {"question": "高血压病人可以运动吗？", "category": "diseases"},
    {"question": "痛风发作时应该怎么办？", "category": "diseases"},

    # Examinations
    {"question": "妇科超声检查是做什么的？检查的时候会疼吗？", "category": "examinations"},
    {"question": "做CT检查前需要注意什么？要空腹吗？", "category": "examinations"},
    {"question": "胃镜检查痛苦吗？", "category": "examinations"},

    # Surgeries
    {"question": "阑尾炎手术后多久可以正常饮食？", "category": "surgeries"},
    {"question": "痔疮手术后会复发吗？", "category": "surgeries"},

    # Vaccines
    {"question": "破伤风针和破伤风疫苗有什么区别？", "category": "vaccines"},
    {"question": "HPV疫苗打几针？间隔多久？", "category": "vaccines"},
    {"question": "流感疫苗每年都要打吗？", "category": "vaccines"},
]


def test_threshold(pattern_storage: PatternStorage, threshold: float, k: int = 3) -> dict:
    """Test a specific threshold across all test questions"""
    results_by_category = defaultdict(lambda: {"total": 0, "retrieved": 0, "avg_score": 0.0, "scores": []})

    for q_data in TEST_QUESTIONS:
        question = q_data["question"]
        category = q_data["category"]

        # Retrieve patterns
        patterns = pattern_storage.retrieve_relevant(
            question=question,
            category=category,
            k=k,
            threshold=threshold
        )

        # Record results
        results_by_category[category]["total"] += 1

        if patterns:
            results_by_category[category]["retrieved"] += 1
            # Get average score of retrieved patterns
            scores = [p.get('relevance_score', 0) for p in patterns]
            results_by_category[category]["scores"].extend(scores)
            if scores:
                results_by_category[category]["avg_score"] += sum(scores) / len(scores)

    # Calculate averages
    for category, stats in results_by_category.items():
        if stats["retrieved"] > 0:
            stats["avg_score"] = stats["avg_score"] / stats["retrieved"]
            stats["avg_patterns_per_q"] = len(stats["scores"]) / stats["retrieved"]
        else:
            stats["avg_patterns_per_q"] = 0

        stats["retrieval_rate"] = stats["retrieved"] / stats["total"] if stats["total"] > 0 else 0

    # Overall stats
    total_questions = len(TEST_QUESTIONS)
    total_retrieved = sum(s["retrieved"] for s in results_by_category.values())
    all_scores = []
    for s in results_by_category.values():
        all_scores.extend(s["scores"])

    return {
        "threshold": threshold,
        "overall": {
            "retrieval_rate": total_retrieved / total_questions,
            "questions_with_patterns": total_retrieved,
            "total_questions": total_questions,
            "avg_score": sum(all_scores) / len(all_scores) if all_scores else 0.0,
            "total_patterns_retrieved": len(all_scores)
        },
        "by_category": dict(results_by_category)
    }


def main():
    """Run threshold optimization analysis"""
    logger.info("=" * 80)
    logger.info("Threshold Optimization Analysis")
    logger.info("=" * 80)

    # Load pattern storage
    pattern_storage = PatternStorage()
    pattern_count = len(pattern_storage.patterns)
    logger.info(f"\n✓ Loaded {pattern_count} patterns from storage")

    # Show category distribution
    from collections import Counter
    category_counts = Counter([p['category'] for p in pattern_storage.patterns])
    logger.info(f"\nCategory distribution:")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        pct = count / pattern_count * 100
        logger.info(f"  {cat:15s}: {count:3d} patterns ({pct:5.1f}%)")

    # Test thresholds
    thresholds = [0.3, 0.4, 0.5, 0.6, 0.7]
    results = []

    logger.info(f"\n{'=' * 80}")
    logger.info(f"Testing {len(thresholds)} thresholds on {len(TEST_QUESTIONS)} questions")
    logger.info(f"{'=' * 80}\n")

    for threshold in thresholds:
        logger.info(f"Testing threshold={threshold}...")
        result = test_threshold(pattern_storage, threshold)
        results.append(result)

        overall = result["overall"]
        logger.info(f"  Retrieval rate: {overall['retrieval_rate']*100:.1f}% ({overall['questions_with_patterns']}/{overall['total_questions']} questions)")
        logger.info(f"  Avg similarity score: {overall['avg_score']:.3f}")
        logger.info(f"  Total patterns retrieved: {overall['total_patterns_retrieved']}")
        logger.info("")

    # Print comparison table
    print("\n" + "=" * 80)
    print("THRESHOLD COMPARISON")
    print("=" * 80)
    print()

    # Overall comparison
    print("Overall Performance:")
    print("-" * 80)
    print(f"{'Threshold':>10} | {'Retrieval Rate':>15} | {'Questions':>10} | {'Avg Score':>10} | {'Total Patterns':>15}")
    print("-" * 80)
    for result in results:
        threshold = result["threshold"]
        overall = result["overall"]
        print(f"{threshold:>10.1f} | {overall['retrieval_rate']*100:>14.1f}% | {overall['questions_with_patterns']:>4d}/{overall['total_questions']:<4d} | {overall['avg_score']:>10.3f} | {overall['total_patterns_retrieved']:>15d}")
    print()

    # Category-wise comparison
    print("\nCategory-wise Performance:")
    print("-" * 80)

    categories = ["diseases", "examinations", "surgeries", "vaccines"]
    for category in categories:
        print(f"\n{category.upper()}:")
        print(f"{'Threshold':>10} | {'Retrieval Rate':>15} | {'Retrieved':>10} | {'Avg Score':>10} | {'Patterns/Q':>12}")
        print("-" * 80)

        for result in results:
            threshold = result["threshold"]
            cat_stats = result["by_category"].get(category, {})

            if cat_stats:
                retrieval_rate = cat_stats["retrieval_rate"]
                retrieved = cat_stats["retrieved"]
                total = cat_stats["total"]
                avg_score = cat_stats["avg_score"]
                avg_patterns = cat_stats["avg_patterns_per_q"]

                print(f"{threshold:>10.1f} | {retrieval_rate*100:>14.1f}% | {retrieved:>4d}/{total:<4d} | {avg_score:>10.3f} | {avg_patterns:>12.1f}")

    # Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)

    # Find optimal threshold
    # Criteria: Good retrieval rate (>50%) with good quality scores (>0.5)
    optimal = None
    for result in results:
        threshold = result["threshold"]
        overall = result["overall"]

        if overall["retrieval_rate"] >= 0.5 and overall["avg_score"] >= 0.5:
            if optimal is None or overall["retrieval_rate"] > results[optimal]["overall"]["retrieval_rate"]:
                optimal = results.index(result)

    if optimal is not None:
        opt_result = results[optimal]
        opt_threshold = opt_result["threshold"]
        opt_overall = opt_result["overall"]

        print(f"\n✅ Recommended Threshold: {opt_threshold}")
        print(f"   - Retrieval rate: {opt_overall['retrieval_rate']*100:.1f}%")
        print(f"   - Average score: {opt_overall['avg_score']:.3f}")
        print(f"   - Patterns per retrieval: {opt_overall['total_patterns_retrieved']/opt_overall['questions_with_patterns']:.1f}")

        print(f"\n📊 Performance by Category:")
        for category in categories:
            cat_stats = opt_result["by_category"].get(category, {})
            if cat_stats:
                print(f"   - {category:15s}: {cat_stats['retrieval_rate']*100:5.1f}% retrieval ({cat_stats['avg_score']:.3f} avg score)")

    else:
        print("\n⚠️  No threshold meets optimal criteria (>=50% retrieval, >=0.5 score)")
        print("    Consider:")
        print("    - Lowering threshold for higher recall (may reduce precision)")
        print("    - Expanding pattern database with more evaluations")

    # Category-specific recommendations
    print(f"\n💡 Category-Specific Insights:")

    for category in categories:
        # Find best threshold for this category
        best_threshold = None
        best_retrieval = 0

        for result in results:
            cat_stats = result["by_category"].get(category, {})
            if cat_stats and cat_stats["retrieval_rate"] > best_retrieval:
                best_retrieval = cat_stats["retrieval_rate"]
                best_threshold = result["threshold"]

        if best_threshold is not None:
            print(f"   - {category:15s}: Best at threshold {best_threshold:.1f} ({best_retrieval*100:.1f}% retrieval)")

    print()


if __name__ == "__main__":
    main()
