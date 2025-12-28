#!/usr/bin/env python3
"""
Pattern Quality Analysis Tool
Identifies high-value patterns, duplicates, and unused patterns
"""
import sys
from pathlib import Path
from collections import defaultdict, Counter
import json

# Add repo root to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

from optimizer.core.pattern_storage import PatternStorage
from loguru import logger
import numpy as np


def find_duplicates(patterns: list, similarity_threshold: float = 0.95) -> list:
    """Find near-duplicate patterns using embeddings"""
    duplicates = []

    for i, p1 in enumerate(patterns):
        for j, p2 in enumerate(patterns[i+1:], i+1):
            # Check text similarity first (fast)
            desc1 = p1.get('description', '')
            desc2 = p2.get('description', '')

            if desc1 == desc2:
                duplicates.append({
                    "pattern1_id": i,
                    "pattern2_id": j,
                    "description1": desc1,
                    "description2": desc2,
                    "similarity": 1.0,
                    "type": "exact"
                })
            elif len(desc1) > 20 and len(desc2) > 20:
                # Check substring containment
                if desc1 in desc2 or desc2 in desc1:
                    duplicates.append({
                        "pattern1_id": i,
                        "pattern2_id": j,
                        "description1": desc1,
                        "description2": desc2,
                        "similarity": 0.98,
                        "type": "substring"
                    })

    return duplicates


def analyze_pattern_frequency(patterns: list) -> dict:
    """Analyze pattern frequency distribution"""
    freq_counter = Counter([p.get('frequency', 1) for p in patterns])
    severity_counter = Counter([p.get('severity', 'minor') for p in patterns])
    category_counter = Counter([p.get('category', 'general') for p in patterns])

    return {
        "frequency_distribution": dict(freq_counter),
        "severity_distribution": dict(severity_counter),
        "category_distribution": dict(category_counter)
    }


def identify_high_value_patterns(patterns: list) -> list:
    """Identify high-value patterns (high frequency + high severity)"""
    high_value = []

    severity_score = {"critical": 3, "major": 2, "minor": 1}

    for i, pattern in enumerate(patterns):
        frequency = pattern.get('frequency', 1)
        severity = pattern.get('severity', 'minor')
        category = pattern.get('category', 'general')
        description = pattern.get('description', '')

        # Calculate value score
        value_score = frequency * severity_score.get(severity, 1)

        if value_score >= 4:  # High-value threshold
            high_value.append({
                "pattern_id": i,
                "description": description[:100],
                "frequency": frequency,
                "severity": severity,
                "category": category,
                "value_score": value_score
            })

    return sorted(high_value, key=lambda x: x['value_score'], reverse=True)


def find_unused_patterns(patterns: list) -> list:
    """Find patterns with frequency = 1 (only seen once)"""
    unused = []

    for i, pattern in enumerate(patterns):
        frequency = pattern.get('frequency', 1)

        if frequency == 1:
            unused.append({
                "pattern_id": i,
                "description": pattern.get('description', '')[:100],
                "category": pattern.get('category', 'general'),
                "severity": pattern.get('severity', 'minor')
            })

    return unused


def recommend_patterns_to_remove(patterns: list, duplicates: list, unused: list) -> list:
    """Recommend patterns to remove"""
    to_remove = set()

    # Add duplicate patterns (keep first, remove rest)
    for dup in duplicates:
        to_remove.add(dup["pattern2_id"])

    # Add low-value unused patterns
    low_value_unused = [
        u for u in unused
        if u["severity"] == "minor"  # Only remove minor severity unused patterns
    ]

    # Keep top 80% of unused patterns, remove bottom 20%
    if len(low_value_unused) > 10:
        remove_count = len(low_value_unused) // 5  # Remove 20%
        for u in low_value_unused[-remove_count:]:
            to_remove.add(u["pattern_id"])

    return sorted(list(to_remove))


def main():
    """Run pattern quality analysis"""
    logger.info("=" * 80)
    logger.info("Pattern Quality Analysis")
    logger.info("=" * 80)

    # Load patterns
    pattern_storage = PatternStorage()
    patterns = pattern_storage.patterns
    pattern_count = len(patterns)

    logger.info(f"\n✓ Loaded {pattern_count} patterns from storage")

    # Run analyses
    logger.info("\n[1/5] Analyzing pattern frequency distribution...")
    freq_analysis = analyze_pattern_frequency(patterns)

    logger.info("\n[2/5] Identifying high-value patterns...")
    high_value = identify_high_value_patterns(patterns)

    logger.info("\n[3/5] Finding duplicate patterns...")
    duplicates = find_duplicates(patterns)

    logger.info("\n[4/5] Finding unused patterns...")
    unused = find_unused_patterns(patterns)

    logger.info("\n[5/5] Generating recommendations...")
    to_remove = recommend_patterns_to_remove(patterns, duplicates, unused)

    # Print results
    print("\n" + "=" * 80)
    print("PATTERN QUALITY ANALYSIS RESULTS")
    print("=" * 80)

    # Overall stats
    print(f"\n📊 Overall Statistics:")
    print(f"   Total patterns: {pattern_count}")
    print(f"   High-value patterns: {len(high_value)} ({len(high_value)/pattern_count*100:.1f}%)")
    print(f"   Duplicate patterns: {len(duplicates)} ({len(duplicates)/pattern_count*100:.1f}%)")
    print(f"   Unused patterns (freq=1): {len(unused)} ({len(unused)/pattern_count*100:.1f}%)")

    # Frequency distribution
    print(f"\n📈 Frequency Distribution:")
    for freq, count in sorted(freq_analysis["frequency_distribution"].items()):
        pct = count / pattern_count * 100
        print(f"   Frequency {freq}: {count:4d} patterns ({pct:5.1f}%)")

    # Severity distribution
    print(f"\n⚠️  Severity Distribution:")
    for severity in ["critical", "major", "minor"]:
        count = freq_analysis["severity_distribution"].get(severity, 0)
        pct = count / pattern_count * 100 if pattern_count > 0 else 0
        print(f"   {severity:8s}: {count:4d} patterns ({pct:5.1f}%)")

    # Category distribution
    print(f"\n🏷️  Category Distribution:")
    for category, count in sorted(freq_analysis["category_distribution"].items(), key=lambda x: -x[1]):
        pct = count / pattern_count * 100
        print(f"   {category:15s}: {count:4d} patterns ({pct:5.1f}%)")

    # High-value patterns
    if high_value:
        print(f"\n⭐ Top 10 High-Value Patterns:")
        print(f"   (High frequency × High severity)")
        print("-" * 80)
        for i, p in enumerate(high_value[:10], 1):
            print(f"   {i:2d}. [Score: {p['value_score']:2d}] [{p['category']:12s}] {p['description'][:60]}...")
            print(f"       Frequency: {p['frequency']}, Severity: {p['severity']}")

    # Duplicates
    if duplicates:
        print(f"\n🔄 Duplicate Patterns Found: {len(duplicates)}")
        print("-" * 80)
        for i, dup in enumerate(duplicates[:5], 1):
            print(f"   {i}. [{dup['type'].upper()}] Similarity: {dup['similarity']:.2f}")
            print(f"      Pattern {dup['pattern1_id']}: {dup['description1'][:70]}...")
            print(f"      Pattern {dup['pattern2_id']}: {dup['description2'][:70]}...")
            print()

        if len(duplicates) > 5:
            print(f"   ... and {len(duplicates) - 5} more duplicates")

    # Unused patterns
    if unused:
        print(f"\n📦 Unused Patterns (frequency=1): {len(unused)}")
        print(f"   These patterns have only been seen once in evaluations.")
        print(f"   Consider:")
        print(f"   - Running more evaluations to validate usefulness")
        print(f"   - Removing low-severity unused patterns to reduce noise")

        # Show breakdown by severity
        unused_by_severity = defaultdict(int)
        for u in unused:
            unused_by_severity[u["severity"]] += 1

        print(f"\n   Unused by Severity:")
        for severity in ["critical", "major", "minor"]:
            count = unused_by_severity.get(severity, 0)
            if count > 0:
                print(f"   - {severity:8s}: {count:4d} patterns")

    # Recommendations
    print(f"\n" + "=" * 80)
    print("💡 RECOMMENDATIONS")
    print("=" * 80)

    if to_remove:
        print(f"\n✂️  Recommend removing {len(to_remove)} patterns ({len(to_remove)/pattern_count*100:.1f}%):")
        print(f"   - {len([d['pattern2_id'] for d in duplicates])} duplicate patterns")
        print(f"   - {len(to_remove) - len(duplicates)} low-value unused patterns")

        print(f"\n   This will reduce pattern count from {pattern_count} to {pattern_count - len(to_remove)}")

        # Save recommendations
        output_file = Path("outputs/cache/error_patterns/cleanup_recommendations.json")
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "total_patterns": pattern_count,
                "patterns_to_remove": len(to_remove),
                "pattern_ids_to_remove": to_remove,
                "duplicates": duplicates,
                "reason": "Duplicates and low-value unused patterns"
            }, f, ensure_ascii=False, indent=2)

        print(f"\n   💾 Cleanup recommendations saved to: {output_file}")
    else:
        print(f"\n✅ No patterns recommended for removal")
        print(f"   Pattern database quality looks good!")

    # Quality score
    quality_score = 100 - (len(duplicates) / pattern_count * 50) - (len(unused) / pattern_count * 20)
    quality_score = max(0, min(100, quality_score))

    print(f"\n🎯 Overall Pattern Database Quality Score: {quality_score:.1f}/100")

    if quality_score >= 80:
        print(f"   ✅ Excellent quality!")
    elif quality_score >= 60:
        print(f"   ⚠️  Good, but room for improvement")
    else:
        print(f"   ❌ Needs cleanup - many duplicates or unused patterns")

    print()


if __name__ == "__main__":
    main()
