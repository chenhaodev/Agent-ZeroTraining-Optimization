"""
Smart Router Decision Engine with Hot-Reload Capability.

This module provides:
1. Weakness pattern matching (Tier 1 - HIGHEST PRIORITY)
2. RAG decision-making for supplemental info (Tier 2)
3. Hot-reload when weakness catalog is updated
"""

import json
import os
from pathlib import Path
from typing import Tuple, Set, Optional, List, Dict, Any
from datetime import datetime
from loguru import logger

from router.core.weakness_matcher import WeaknessMatcher
from router.config.settings import get_router_settings


class DecisionEngine:
    """
    Smart routing decision engine with hot-reload capability.

    Features:
    - Fast rule-based RAG decisions
    - Weakness pattern matching
    - Auto-reload when weakness catalog updates
    """

    def __init__(
        self,
        entity_data_path: Optional[str] = None,
        weaknesses_path: Optional[str] = None
    ):
        """
        Initialize decision engine.

        Args:
            entity_data_path: Path to entity_names.json (optional)
            weaknesses_path: Path to deepseek_weaknesses.json (optional)
        """
        settings = get_router_settings()

        self.entity_data_path = Path(entity_data_path or settings.ENTITY_NAMES_PATH)
        self.weaknesses_path = Path(weaknesses_path or settings.WEAKNESSES_PATH)

        # Load entity names
        self.entities_by_category = self._load_entities()
        self.all_entities_set = self._build_entity_set()

        # Initialize weakness matcher
        self.weakness_matcher = WeaknessMatcher(str(self.weaknesses_path))

        # Track file modification times for hot-reload
        self._entity_mtime = self._get_mtime(self.entity_data_path)
        self._weakness_mtime = self._get_mtime(self.weaknesses_path)
        self._last_reload_check = datetime.now()

        # Define category keywords (learned from database)
        self.category_keywords = {
            'diseases': {
                '糖尿病', '高血压', '白血病', '肺结节', '半月板', '游走脾',
                '沙门氏菌', '卡波西肉瘤', '家族性高胆固醇血症', '类鼻疽',
                '疾病', '症状', '治疗', '病因'
            },
            'examinations': {
                '检查', '筛查', 'CT', 'MRI', 'X光', '超声', 'B超',
                '血常规', '尿检', '心电图', '胃镜', '肠镜', '活检'
            },
            'surgeries': {
                '手术', '术后', '操作', '切除', '置换', '移植',
                '微创', '开放', '腹腔镜', '穿刺'
            },
            'vaccines': {
                '疫苗', '接种', '注射', '免疫', '预防针',
                '乙肝', '流感', '肺炎', '狂犬', 'HPV'
            }
        }

        # Known out-of-database topics (learned from failed retrievals)
        self.ood_keywords = {
            '摇晃综合征', '婴儿摇晃', 'Shaken Baby',
            '念珠菌性龟头炎', '念珠菌龟头',
            '海绵状血管瘤', '血管瘤',
            '阴唇粘连', '外阴粘连',
            '先天性心脏病筛查',
            '单纯性甲状腺肿',
            '心脏性猝死预防',
            '变性手术', '性别肯定手术',
            '感染性疾病通用症状'
        }

        logger.info(
            f"DecisionEngine initialized: {len(self.all_entities_set)} entities, "
            f"{len(self.weakness_matcher.weaknesses)} weakness patterns"
        )

    def _get_mtime(self, filepath: Path) -> float:
        """Get file modification time"""
        try:
            return os.path.getmtime(filepath) if filepath.exists() else 0
        except Exception:
            return 0

    def _load_entities(self) -> dict:
        """Load entity names from JSON file"""
        if not self.entity_data_path.exists():
            logger.warning(f"Entity data not found: {self.entity_data_path}")
            return {'diseases': [], 'examinations': [], 'surgeries': [], 'vaccines': []}

        try:
            with open(self.entity_data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load entities: {e}")
            return {'diseases': [], 'examinations': [], 'surgeries': [], 'vaccines': []}

    def _build_entity_set(self) -> Set[str]:
        """Build a set of all entity names for fast lookup"""
        all_entities = set()
        for category, names in self.entities_by_category.items():
            all_entities.update(names)
        return all_entities

    def check_for_updates(self) -> bool:
        """
        Check if data files have been updated and reload if necessary.

        Returns:
            True if reloaded, False otherwise
        """
        reloaded = False

        # Check entity names
        current_entity_mtime = self._get_mtime(self.entity_data_path)
        if current_entity_mtime > self._entity_mtime:
            logger.info("Entity names updated, reloading...")
            self.entities_by_category = self._load_entities()
            self.all_entities_set = self._build_entity_set()
            self._entity_mtime = current_entity_mtime
            reloaded = True

        # Check weakness patterns
        current_weakness_mtime = self._get_mtime(self.weaknesses_path)
        if current_weakness_mtime > self._weakness_mtime:
            logger.info("Weakness patterns updated, reloading...")
            self.weakness_matcher = WeaknessMatcher(str(self.weaknesses_path))
            self._weakness_mtime = current_weakness_mtime
            reloaded = True

        if reloaded:
            logger.info(
                f"✓ Hot-reload complete: {len(self.all_entities_set)} entities, "
                f"{len(self.weakness_matcher.weaknesses)} weakness patterns"
            )

        self._last_reload_check = datetime.now()
        return reloaded

    def should_use_rag(
        self,
        question: str,
        min_confidence: float = 0.70
    ) -> Tuple[bool, str, float]:
        """
        Decide if RAG should be used for this question.

        Args:
            question: The question text
            min_confidence: Minimum confidence to use RAG (0.0-1.0)

        Returns:
            Tuple of (use_rag, reason, confidence)
        """
        question_lower = question.lower()

        # Strategy 1: Check exact entity name match (HIGH confidence)
        for entity_name in self.all_entities_set:
            if entity_name in question:
                return True, f"Exact match: '{entity_name}'", 0.95

        # Strategy 2: Check for known out-of-database topics (HIGH confidence)
        for ood_keyword in self.ood_keywords:
            if ood_keyword in question:
                return False, f"Known OOD topic: '{ood_keyword}'", 0.90

        # Strategy 3: Check category keywords (MEDIUM confidence)
        matched_categories = []
        for category, keywords in self.category_keywords.items():
            if any(kw in question for kw in keywords):
                matched_categories.append(category)

        if len(matched_categories) >= 2:
            categories_str = ', '.join(matched_categories)
            return True, f"Multiple category matches: {categories_str}", 0.75
        elif len(matched_categories) == 1:
            return True, f"Category match: {matched_categories[0]}", 0.65

        # Strategy 4: Check for partial entity matches
        for entity_name in self.all_entities_set:
            if len(entity_name) >= 3:
                prefix = entity_name[:min(3, len(entity_name))]
                if len(prefix) >= 2 and prefix in question and prefix not in ['检查', '手术', '疫苗']:
                    return True, f"Partial match: '{entity_name}'", 0.60

        # Strategy 5: Default - use RAG with threshold filtering
        return True, "Uncertain - defer to threshold filter", 0.50

    def get_routing_decision(
        self,
        question: str,
        entity_type: Optional[str] = None,
        min_confidence: float = 0.70,
        auto_reload: bool = True
    ) -> Dict[str, Any]:
        """
        Complete routing decision with CORRECT priority: weakness patterns first, then RAG.

        This implements the correct three-tier routing strategy:
        - Tier 1: Weakness pattern matching (check if hits known weakness - HIGHEST PRIORITY)
        - Tier 2: RAG retrieval for supplemental info (if no weakness match)
        - Tier 3: Baseline only (if neither applies)

        Args:
            question: The question text
            entity_type: Optional entity type ('diseases', 'vaccines', etc.)
            min_confidence: Minimum confidence for RAG usage
            auto_reload: Whether to auto-check for data updates

        Returns:
            Dictionary with routing decision and weakness patterns
        """
        # Hot-reload check
        if auto_reload:
            settings = get_router_settings()
            if settings.ENABLE_HOT_RELOAD:
                self.check_for_updates()

        # Step 1: Check for weakness patterns FIRST (highest priority)
        settings = get_router_settings()
        weakness_patterns = self.weakness_matcher.match_weaknesses(
            question=question,
            entity_type=entity_type,
            top_k=settings.WEAKNESS_TOP_K,
            min_frequency=settings.WEAKNESS_MIN_FREQUENCY
        )

        has_weaknesses = len(weakness_patterns) > 0

        # Step 2: If no weakness match, check RAG for supplemental info
        if not has_weaknesses:
            # No weakness pattern hit - check if RAG has golden-ref content
            use_rag, rag_reason, rag_confidence = self.should_use_rag(question, min_confidence)
        else:
            # Weakness pattern found - use updated prompt with inline reminders
            # RAG may still supplement with additional context
            use_rag = True  # Allow RAG to provide supplemental bad case examples
            rag_reason = f"Supplemental context for weakness: {weakness_patterns[0]['weakness_id']}"
            rag_confidence = 0.85  # High confidence when weakness is matched

        decision = {
            'use_rag': use_rag,
            'rag_reason': rag_reason,
            'rag_confidence': rag_confidence,
            'weakness_patterns': weakness_patterns,
            'has_weaknesses': has_weaknesses,
            'routing_tier': 'weakness' if has_weaknesses else ('rag' if use_rag else 'baseline'),
            'last_reload_check': self._last_reload_check.isoformat()
        }

        # Log routing decision
        if has_weaknesses:
            pattern_ids = [w['weakness_id'] for w in weakness_patterns]
            logger.debug(
                f"Routing: use_rag={use_rag}, weaknesses={pattern_ids}"
            )

        return decision

    def get_stats(self) -> dict:
        """Get statistics about the router configuration"""
        weakness_stats = self.weakness_matcher.get_stats()

        return {
            'total_entities': len(self.all_entities_set),
            'diseases': len(self.entities_by_category.get('diseases', [])),
            'examinations': len(self.entities_by_category.get('examinations', [])),
            'surgeries': len(self.entities_by_category.get('surgeries', [])),
            'vaccines': len(self.entities_by_category.get('vaccines', [])),
            'category_keywords': sum(len(kws) for kws in self.category_keywords.values()),
            'ood_keywords': len(self.ood_keywords),
            'weakness_patterns': weakness_stats['total_weaknesses'],
            'weakness_categories': weakness_stats['by_category'],
            'last_reload_check': self._last_reload_check.isoformat(),
            'entity_file_mtime': datetime.fromtimestamp(self._entity_mtime).isoformat() if self._entity_mtime else None,
            'weakness_file_mtime': datetime.fromtimestamp(self._weakness_mtime).isoformat() if self._weakness_mtime else None
        }


# Singleton instance
_decision_engine: Optional[DecisionEngine] = None


def get_decision_engine() -> DecisionEngine:
    """Get the global decision engine instance"""
    global _decision_engine
    if _decision_engine is None:
        _decision_engine = DecisionEngine()
    return _decision_engine


def reload_decision_engine() -> DecisionEngine:
    """Force reload the decision engine"""
    global _decision_engine
    logger.info("Force reloading decision engine...")
    _decision_engine = DecisionEngine()
    return _decision_engine
