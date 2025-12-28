#!/usr/bin/env python3
"""
Weakness Pattern Builder
Automatically builds weakness patterns from evaluation data
"""
import sys
import json
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime

# Add repo root to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

from optimizer.core.pattern_storage import PatternStorage
from loguru import logger


def extract_entity_weaknesses(pattern_storage: PatternStorage, min_frequency: int = 2) -> dict:
    """
    Extract entity-specific weakness patterns from pattern storage

    Groups patterns by inferred entity and identifies high-frequency weaknesses
    """
    logger.info("Extracting entity-specific weakness patterns...")

    patterns = pattern_storage.patterns

    # Group patterns by category and extract common themes
    entity_weaknesses = defaultdict(lambda: defaultdict(list))

    for pattern in patterns:
        category = pattern.get('category', 'general')
        description = pattern.get('description', '')
        frequency = pattern.get('frequency', 1)
        severity = pattern.get('severity', 'minor')

        # Skip low-frequency patterns
        if frequency < min_frequency:
            continue

        # Try to infer entity name from description
        entity_name = infer_entity_name(description, category)

        entity_weaknesses[category][entity_name].append({
            "description": description,
            "frequency": frequency,
            "severity": severity
        })

    return entity_weaknesses


def infer_entity_name(description: str, category: str) -> str:
    """Infer entity name from pattern description"""
    # Common entity keywords by category
    entity_keywords = {
        "diseases": [
            "糖尿病", "高血压", "半月板损伤", "类风湿", "痛风", "脂肪肝",
            "甲状腺结节", "过敏性鼻炎", "沙门氏菌", "破伤风"
        ],
        "examinations": [
            "CT检查", "PET-CT", "超声", "妇科超声", "胃镜", "心电图",
            "血常规", "核磁共振", "MRI"
        ],
        "surgeries": [
            "阑尾炎手术", "痔疮手术", "白内障手术", "剖腹产",
            "鼻翼缩窄", "胸膜腔穿刺"
        ],
        "vaccines": [
            "破伤风疫苗", "破伤风针", "HPV疫苗", "流感疫苗", "乙肝疫苗",
            "卡介苗"
        ]
    }

    keywords = entity_keywords.get(category, [])

    for keyword in keywords:
        if keyword in description:
            return keyword

    return "通用"


def generate_weakness_id(description: str) -> str:
    """Generate a weakness ID from description"""
    # Extract key concept
    if "禁忌" in description:
        return "contraindications"
    elif "准备" in description or "空腹" in description:
        return "preparation_requirements"
    elif "时间" in description or "时长" in description:
        return "timing_details"
    elif "剂量" in description or "用药" in description:
        return "dosage_administration"
    elif "并发症" in description or "合并" in description:
        return "complications_concurrent"
    elif "生活" in description or "饮食" in description or "运动" in description:
        return "lifestyle_details"
    elif "恢复" in description or "康复" in description:
        return "recovery_timeline"
    elif "疫苗" in description and "程序" in description:
        return "vaccination_schedule"
    elif "术语" in description or "概念" in description:
        return "terminology_clarity"
    else:
        # Generate hash-based ID
        import hashlib
        return "weakness_" + hashlib.md5(description.encode()).hexdigest()[:8]


def build_entity_names_json(entity_weaknesses: dict) -> dict:
    """Build entity_names.json structure"""
    entity_names = {
        "metadata": {
            "version": "1.0",
            "created": datetime.now().isoformat(),
            "description": "Auto-generated entity weakness patterns from evaluation data",
            "total_entities": 0,
            "total_weakness_patterns": 0
        },
        "entities": {}
    }

    total_entities = 0
    total_patterns = 0

    for category, entities in entity_weaknesses.items():
        entity_names["entities"][category] = {}

        for entity_name, patterns in entities.items():
            if entity_name == "通用":
                continue  # Skip generic patterns

            # Deduplicate and select top patterns
            unique_patterns = {}
            for p in patterns:
                weakness_id = generate_weakness_id(p["description"])
                if weakness_id not in unique_patterns or p["frequency"] > unique_patterns[weakness_id]["frequency"]:
                    unique_patterns[weakness_id] = p

            # Convert to weakness pattern format
            weakness_patterns = []
            for weakness_id, p in unique_patterns.items():
                # Calculate confidence based on frequency and severity
                severity_weight = {"critical": 1.0, "major": 0.85, "minor": 0.7}
                confidence = min(0.95, 0.5 + (p["frequency"] * 0.1) + severity_weight.get(p["severity"], 0.7) * 0.2)

                weakness_patterns.append({
                    "id": weakness_id,
                    "description": p["description"],
                    "severity": p["severity"],
                    "confidence": round(confidence, 2),
                    "frequency": p["frequency"]
                })

            if weakness_patterns:
                entity_names["entities"][category][entity_name] = {
                    "weakness_patterns": sorted(weakness_patterns, key=lambda x: -x["frequency"])
                }
                total_entities += 1
                total_patterns += len(weakness_patterns)

    entity_names["metadata"]["total_entities"] = total_entities
    entity_names["metadata"]["total_weakness_patterns"] = total_patterns

    return entity_names


def main():
    """Build weakness patterns from evaluation data"""
    logger.info("=" * 80)
    logger.info("Weakness Pattern Builder")
    logger.info("=" * 80)

    # Load pattern storage
    logger.info("\n[1/3] Loading pattern storage...")
    pattern_storage = PatternStorage()
    pattern_count = len(pattern_storage.patterns)
    logger.info(f"✓ Loaded {pattern_count} patterns")

    # Extract entity weaknesses
    logger.info("\n[2/3] Extracting entity-specific weaknesses (min_frequency=2)...")
    entity_weaknesses = extract_entity_weaknesses(pattern_storage, min_frequency=2)

    # Count results
    total_entities = sum(len(entities) for entities in entity_weaknesses.values())
    logger.info(f"✓ Found {total_entities} entities with weakness patterns")

    for category, entities in entity_weaknesses.items():
        logger.info(f"  - {category}: {len(entities)} entities")

    # Build entity_names.json
    logger.info("\n[3/3] Building entity_names.json...")
    entity_names = build_entity_names_json(entity_weaknesses)

    # Save to file
    output_file = Path("router/refs/entity_names.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(entity_names, f, ensure_ascii=False, indent=2)

    logger.info(f"✓ Saved to {output_file}")

    # Print summary
    print("\n" + "=" * 80)
    print("WEAKNESS PATTERN SUMMARY")
    print("=" * 80)

    metadata = entity_names["metadata"]
    print(f"\n📊 Statistics:")
    print(f"   Total entities: {metadata['total_entities']}")
    print(f"   Total weakness patterns: {metadata['total_weakness_patterns']}")
    print(f"   Average patterns per entity: {metadata['total_weakness_patterns'] / metadata['total_entities']:.1f}")

    print(f"\n🏷️  Entities by Category:")
    for category in ["diseases", "examinations", "surgeries", "vaccines"]:
        if category in entity_names["entities"]:
            count = len(entity_names["entities"][category])
            print(f"   - {category:15s}: {count} entities")

    print(f"\n⭐ Sample Entities with Weaknesses:")

    for category in ["diseases", "examinations", "surgeries", "vaccines"]:
        if category not in entity_names["entities"]:
            continue

        entities = entity_names["entities"][category]
        if not entities:
            continue

        print(f"\n   {category.upper()}:")

        # Show top 3 entities
        for i, (entity_name, data) in enumerate(list(entities.items())[:3], 1):
            patterns = data["weakness_patterns"]
            print(f"      {i}. {entity_name} ({len(patterns)} weaknesses):")

            for p in patterns[:2]:  # Show top 2 weaknesses
                print(f"         - [{p['severity']:8s}] {p['description'][:70]}...")
                print(f"           Confidence: {p['confidence']:.2f}, Frequency: {p['frequency']}")

    print(f"\n💡 Usage:")
    print(f"   The decision engine will now use these weakness patterns for smart routing.")
    print(f"   When a question matches an entity with known weaknesses, pattern retrieval will be triggered.")

    print(f"\n✅ Weakness patterns ready for production use!")
    print()


if __name__ == "__main__":
    main()
