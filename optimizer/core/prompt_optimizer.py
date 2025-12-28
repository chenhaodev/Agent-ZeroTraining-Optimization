"""
Prompt optimization system with dynamic pattern-based guideline retrieval.
Generates improved prompts based on error analysis and builds runtime prompts with relevant patterns.
"""

import yaml
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import Counter
from loguru import logger

from autoeval.config.settings import get_settings
from optimizer.core.pattern_storage import PatternStorage
from optimizer.core.pattern_clustering import PatternClusterer
from optimizer.core.pattern_abstractor import PatternAbstractor
from router.core.weakness_matcher import get_weakness_matcher
from autoeval.services.api_client import APIClient


class PromptOptimizer:
    """Optimize prompts based on evaluation results and build dynamic prompts at runtime"""

    def __init__(self):
        self.settings = get_settings()
        self.pattern_storage = PatternStorage()
        self.weakness_matcher = get_weakness_matcher()

        # Initialize clustering and abstraction components
        self.api_client = APIClient()
        self.clusterer = PatternClusterer(
            embedder=self.pattern_storage.embedder,
            pattern_storage=self.pattern_storage
        )
        self.abstractor = PatternAbstractor(api_client=self.api_client)

        # Prompt paths
        self.prompt_dir = Path(self.settings.PROMPT_DIR)
        self.output_dir = Path(self.settings.PROMPTS_OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Load base prompts
        self.base_prompt = self._load_base_prompt()
        self.current_version = self._get_latest_version()

        # Load category-specific rules (Tier 2)
        self.category_rules = self._load_category_rules()

    def _load_base_prompt(self) -> Dict[str, Any]:
        """Load the base DeepSeek system prompt"""
        prompt_file = self.prompt_dir / "deepseek_system.yaml"

        if not prompt_file.exists():
            logger.warning(f"Base prompt file not found: {prompt_file}")
            return self._create_default_prompt()

        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load base prompt: {e}")
            return self._create_default_prompt()

    def _create_default_prompt(self) -> Dict[str, Any]:
        """Create a default prompt structure"""
        return {
            'version': '1.0',
            'system_prompt': """你是专业、耐心、友善的医疗健康助手。

## 核心原则
1. 准确性第一 - 基于循证医学提供信息
2. 通俗易懂 - 用患者能理解的语言解释
3. 完整但简洁 - 全面覆盖要点，避免冗余
4. 安全边界 - 明确助手的局限性

## 禁止行为
- 给出明确诊断（只能说"可能"、"建议就医确诊"）
- 推荐具体药物剂量
- 替代专业医疗建议""",
            'memory': {
                'common_mistakes': [],
                'knowledge_gaps': [],
                'improvement_guidelines': []
            }
        }

    def _load_category_rules(self) -> Dict[str, Any]:
        """Load category-specific rules (Tier 2)"""
        rules_file = self.prompt_dir / "category_rules.yaml"

        if not rules_file.exists():
            logger.warning(f"Category rules file not found: {rules_file}")
            return self._create_default_category_rules()

        try:
            with open(rules_file, 'r', encoding='utf-8') as f:
                rules = yaml.safe_load(f)
                logger.info(f"Loaded category rules: {len(rules.get('diseases', {}).get('rules', []))} disease rules, "
                           f"{len(rules.get('vaccines', {}).get('rules', []))} vaccine rules, "
                           f"{len(rules.get('examinations', {}).get('rules', []))} exam rules, "
                           f"{len(rules.get('surgeries', {}).get('rules', []))} surgery rules")
                return rules
        except Exception as e:
            logger.error(f"Failed to load category rules: {e}")
            return self._create_default_category_rules()

    def _create_default_category_rules(self) -> Dict[str, Any]:
        """Create default category rules if file not found"""
        return {
            'diseases': {'rules': []},
            'vaccines': {'rules': []},
            'examinations': {'rules': []},
            'surgeries': {'rules': []},
            'general': {'rules': []}
        }

    def _get_latest_version(self) -> str:
        """Get the latest prompt version from outputs/prompts/"""
        version_files = list(self.output_dir.glob("deepseek_system_v*.yaml"))

        if not version_files:
            return "1.0"

        # Extract version numbers
        versions = []
        for f in version_files:
            try:
                version_str = f.stem.split('_v')[1]  # "deepseek_system_v1.2.yaml" -> "1.2"
                versions.append(version_str)
            except:
                continue

        if not versions:
            return "1.0"

        # Sort and return latest
        versions.sort(key=lambda v: [int(x) for x in v.split('.')])
        return versions[-1]

    def _increment_version(self, version: str) -> str:
        """Increment version number (1.0 -> 1.1 -> 1.2, etc.)"""
        parts = version.split('.')
        major, minor = int(parts[0]), int(parts[1])
        return f"{major}.{minor + 1}"

    def _infer_category_from_keywords(self, description: str) -> str:
        """Infer entity category from pattern description using keywords"""
        desc_lower = description.lower()

        # Disease keywords
        if any(kw in desc_lower for kw in [
            '疾病', '症状', '病因', '治疗', '并发症', '诊断', '病理',
            '临床表现', '发病', '预后', '康复', '用药', '药物', '病变',
            '糖尿病', '高血压', '损伤', '炎症', '感染'
        ]):
            return 'diseases'

        # Examination keywords
        elif any(kw in desc_lower for kw in [
            '检查', '超声', 'ct', 'mri', 'x线', 'x光', '影像', '化验',
            'b超', '彩超', '心电图', '血常规', '尿检', '内窥镜', '穿刺'
        ]):
            return 'examinations'

        # Surgery keywords
        elif any(kw in desc_lower for kw in [
            '手术', '术后', '麻醉', '切除', '切开', '缝合', '植入',
            '关节镜', '微创', '开放性', '术前', '手术方式', '手术指征'
        ]):
            return 'surgeries'

        # Vaccine keywords
        elif any(kw in desc_lower for kw in [
            '疫苗', '接种', '免疫', '注射', '预防接种', '抗体',
            '破伤风针', 'hpv', '流感', '肺炎', '乙肝', '甲肝'
        ]):
            return 'vaccines'

        return 'general'

    def extract_patterns_from_analysis(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract error patterns from evaluation analysis.

        Args:
            analysis: Analysis results from PatternAnalyzer

        Returns:
            List of error patterns suitable for storage
        """
        patterns = []

        # Extract from error patterns
        for error_type, pattern_list in analysis.get('error_patterns', {}).items():
            for pattern_data in pattern_list:
                # Infer category from pattern data
                category = pattern_data.get('category')
                if not category or category == 'general':
                    category = self._infer_category_from_keywords(
                        pattern_data.get('description', '')
                    )

                pattern = {
                    'description': pattern_data.get('description', ''),
                    'guideline': pattern_data.get('guideline', ''),
                    'category': category,
                    'error_type': error_type,
                    'severity': pattern_data.get('severity', 'minor'),
                    'frequency': pattern_data.get('count', 1),
                    'examples': pattern_data.get('examples', [])[:2]  # Keep 2 examples
                }
                patterns.append(pattern)

        # Extract from knowledge gaps
        # knowledge_gaps is a dict mapping gap_description (str) -> count (int)
        for gap_description, count in analysis.get('knowledge_gaps', {}).items():
            # Infer category from description
            category = self._infer_category_from_keywords(gap_description)

            pattern = {
                'description': gap_description,
                'guideline': f"加强关于 {gap_description} 的知识准确性和完整性",
                'category': category,
                'error_type': 'knowledge_gap',
                'severity': 'major' if count >= 3 else 'minor',
                'frequency': count,
                'examples': []
            }
            patterns.append(pattern)

        logger.info(f"Extracted {len(patterns)} error patterns from analysis")
        return patterns

    def generate_updated_prompt(
        self,
        analysis: Dict[str, Any],
        incremental: bool = True
    ) -> str:
        """
        Generate updated prompt version based on error analysis.

        Args:
            analysis: Analysis results from PatternAnalyzer
            incremental: If True, builds on previous version; if False, starts fresh

        Returns:
            New version number
        """
        logger.info("Generating updated prompt based on error analysis...")

        # Extract and store patterns
        new_patterns = self.extract_patterns_from_analysis(analysis)
        if new_patterns:
            self.pattern_storage.add_patterns_batch(new_patterns)

        # Get top patterns for base prompt
        top_patterns = self.pattern_storage.get_top_patterns(n=10, min_frequency=2)

        # Build new prompt
        new_version = self._increment_version(self.current_version)

        if incremental:
            # Build on previous version
            new_prompt = self.base_prompt.copy()
        else:
            # Start fresh
            new_prompt = self._create_default_prompt()

        # Update memory section with top patterns
        new_prompt['version'] = new_version
        new_prompt['updated_at'] = datetime.now().isoformat()

        # Group patterns by type
        mistakes = [p['guideline'] for p in top_patterns if p['error_type'] == 'incomplete']
        gaps = [p['description'] for p in top_patterns if p['error_type'] == 'knowledge_gap']
        guidelines = [p['guideline'] for p in top_patterns if p['error_type'] == 'factual_error']

        new_prompt['memory'] = {
            'common_mistakes': mistakes[:5],
            'knowledge_gaps': gaps[:3],
            'improvement_guidelines': guidelines[:5]
        }

        # Add change summary
        new_prompt['changes'] = {
            'from_version': self.current_version,
            'patterns_added': len(new_patterns),
            'total_patterns_in_storage': len(self.pattern_storage.patterns),
            'improvements': [
                f"Added {len(mistakes)} completeness guidelines",
                f"Addressed {len(gaps)} knowledge gaps",
                f"Fixed {len(guidelines)} accuracy issues"
            ]
        }

        # Save to file
        output_file = self.output_dir / f"deepseek_system_v{new_version}.yaml"
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(new_prompt, f, allow_unicode=True, sort_keys=False)

        logger.info(f"Generated prompt version {new_version} -> {output_file}")
        logger.info(f"  - {len(mistakes)} common mistakes")
        logger.info(f"  - {len(gaps)} knowledge gaps")
        logger.info(f"  - {len(guidelines)} improvement guidelines")

        # Update current version
        self.current_version = new_version

        return new_version

    def build_dynamic_prompt(
        self,
        question: str,
        entity_type: str = "general",
        use_patterns: bool = True,
        num_patterns: int = 5,
        use_category_rules: bool = True
    ) -> str:
        """
        Build dynamic prompt for answer generation with pattern retrieval-retrieved patterns.

        Args:
            question: The question being answered
            entity_type: Type of entity (diseases, vaccines, examinations, surgeries)
            use_patterns: Whether to use pattern retrieval for dynamic prompts
            num_patterns: Number of patterns to retrieve
            use_category_rules: Whether to include Tier 2 category-specific rules

        Returns:
            Complete system prompt
        """
        # Start with base prompt
        base_text = self.base_prompt.get('system_prompt', '')

        # Add memory section from base prompt
        memory = self.base_prompt.get('memory', {})
        if memory.get('common_mistakes') or memory.get('improvement_guidelines'):
            base_text += "\n\n## 重点提醒\n"

            if memory.get('common_mistakes'):
                base_text += "\n**常见问题需避免：**\n"
                for mistake in memory['common_mistakes'][:3]:
                    base_text += f"- {mistake}\n"

            if memory.get('improvement_guidelines'):
                base_text += "\n**准确性要求：**\n"
                for guideline in memory['improvement_guidelines'][:3]:
                    base_text += f"- {guideline}\n"

        # Tier 2: Add category-specific rules (if enabled)
        if use_category_rules and entity_type and entity_type != "general" and entity_type in self.category_rules:
            category_info = self.category_rules[entity_type]
            rules = category_info.get('rules', [])

            if rules:
                category_name = {
                    'diseases': '疾病',
                    'vaccines': '疫苗',
                    'examinations': '检查',
                    'surgeries': '手术操作'
                }.get(entity_type, entity_type)

                base_text += f"\n\n## {category_name}类问题专项要求\n"
                for rule in rules:
                    base_text += f"• {rule}\n"

        # Tier 3: Add dynamically retrieved patterns if enabled
        if use_patterns:
            relevant_patterns = self.pattern_storage.retrieve_relevant(
                question=question,
                k=num_patterns,
                category=entity_type if entity_type != "general" else None,
                min_severity="minor"
            )

            if relevant_patterns:
                base_text += "\n\n## 针对此类问题的特别注意\n"
                for i, pattern in enumerate(relevant_patterns[:5], 1):
                    guideline = pattern.get('guideline', '')
                    severity = pattern.get('severity', 'minor')
                    relevance = pattern.get('relevance_score', 0)

                    # Only show high-relevance patterns
                    if relevance > 0.5:
                        emoji = "🔴" if severity == "critical" else "🟡" if severity == "major" else "🟢"
                        base_text += f"{emoji} {guideline}\n"

        # Tier 4: Add weakness pattern reminders (NEW!)
        # These are added regardless of pattern retrieval availability
        weakness_additions = self.weakness_matcher.get_prompt_additions(
            question=question,
            entity_type=entity_type,
            top_k=2  # Maximum 2 weakness patterns
        )

        if weakness_additions:
            base_text += weakness_additions
            logger.debug(f"Added weakness-based prompt reminders for question: {question[:50]}...")

        return base_text

    def generate_updated_prompt_with_clustering(
        self,
        analysis: Dict[str, Any],
        n_clusters: int = 20,
        n_representatives: int = 15,
        n_general_reminders: int = 10,
        incremental: bool = True
    ) -> str:
        """
        Generate updated prompt using clustering and LLM abstraction.

        This is an enhanced version of generate_updated_prompt() that:
        1. Clusters patterns for diversity
        2. Selects representative patterns from each cluster
        3. Uses LLM to abstract clusters into general reminders
        4. Creates a three-tier base prompt:
           - Tier 1: General reminders (LLM-abstracted)
           - Tier 2: Representative specific patterns (diverse)
           - Tier 3: All patterns in FAISS (runtime retrieval)

        Args:
            analysis: Analysis results from PatternAnalyzer
            n_clusters: Number of clusters to create
            n_representatives: Number of representative patterns for base prompt
            n_general_reminders: Number of general reminders to generate
            incremental: If True, builds on previous version

        Returns:
            New version number
        """
        logger.info("Generating updated prompt with clustering and abstraction...")

        # Step 1: Extract and store patterns (same as before)
        new_patterns = self.extract_patterns_from_analysis(analysis)
        if new_patterns:
            self.pattern_storage.add_patterns_batch(new_patterns)
            logger.info(f"Added {len(new_patterns)} new patterns to storage")

        # Check if we have enough patterns for clustering
        total_patterns = len(self.pattern_storage.patterns)
        if total_patterns < 10:
            logger.warning(
                f"Not enough patterns ({total_patterns}) for clustering. "
                "Using simple frequency-based selection."
            )
            return self.generate_updated_prompt(analysis, incremental)

        # Step 2: Cluster patterns
        logger.info(f"Clustering {total_patterns} patterns...")
        clusters = self.clusterer.cluster_patterns(n_clusters=n_clusters)

        # Step 3: Select representative patterns
        logger.info("Selecting representative patterns from clusters...")
        representatives = self.clusterer.select_representatives(
            clusters,
            per_cluster=1,
            strategy="balanced"
        )[:n_representatives]

        # Step 4: Abstract clusters into general reminders
        logger.info("Generating general reminders using LLM abstraction...")
        abstractions = self.abstractor.abstract_all_clusters(
            clusters,
            min_cluster_size=5  # Only abstract clusters with 5+ patterns
        )

        # Format reminders for prompt
        formatted_reminders = self.abstractor.format_for_prompt(
            abstractions,
            max_reminders=n_general_reminders
        )

        # Step 5: Build new prompt
        new_version = self._increment_version(self.current_version)

        if incremental:
            new_prompt = self.base_prompt.copy()
        else:
            new_prompt = self._create_default_prompt()

        new_prompt['version'] = new_version
        new_prompt['updated_at'] = datetime.now().isoformat()

        # Build memory section with three tiers
        # Tier 1: General reminders (LLM-abstracted)
        general_reminders = formatted_reminders.get('all_reminders', [])

        # Tier 2: Representative specific patterns
        representative_mistakes = []
        representative_guidelines = []
        for rep in representatives:
            if rep['error_type'] == 'incomplete':
                representative_mistakes.append(rep['guideline'])
            elif rep['error_type'] in ['factual_error', 'misleading']:
                representative_guidelines.append(rep['guideline'])

        new_prompt['memory'] = {
            'general_reminders': general_reminders[:n_general_reminders],
            'representative_patterns': {
                'mistakes': representative_mistakes[:5],
                'guidelines': representative_guidelines[:5]
            },
            'metadata': {
                'clustering_used': True,
                'n_clusters': len(clusters),
                'n_representatives': len(representatives),
                'n_general_reminders': len(general_reminders),
                'total_patterns_in_storage': total_patterns
            }
        }

        # Add change summary
        new_prompt['changes'] = {
            'from_version': self.current_version,
            'patterns_added': len(new_patterns),
            'total_patterns_in_storage': total_patterns,
            'improvements': [
                f"Generated {len(general_reminders)} general reminders via LLM abstraction",
                f"Selected {len(representatives)} representative patterns from {len(clusters)} clusters",
                f"Improved diversity and coverage across medical domains"
            ],
            'clustering_stats': {
                'n_clusters': len(clusters),
                'avg_cluster_size': sum(len(p) for p in clusters.values()) / len(clusters),
                'abstractions_generated': len(abstractions)
            }
        }

        # Save to file
        output_file = self.output_dir / f"deepseek_system_v{new_version}.yaml"
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(new_prompt, f, allow_unicode=True, sort_keys=False)

        logger.info(f"Generated clustered prompt version {new_version} -> {output_file}")
        logger.info(f"  - {len(general_reminders)} general reminders (LLM-abstracted)")
        logger.info(f"  - {len(representatives)} representative patterns (clustered)")
        logger.info(f"  - {total_patterns} total patterns in storage (for runtime retrieval)")

        # Save clustering metadata
        metadata_file = self.output_dir / f"clustering_metadata_v{new_version}.json"
        metadata = {
            'version': new_version,
            'timestamp': datetime.now().isoformat(),
            'clusters': {
                cid: {
                    'size': len(patterns),
                    'patterns': [
                        {'description': p['description'][:100], 'frequency': p.get('frequency', 0)}
                        for p in patterns[:3]
                    ]
                }
                for cid, patterns in list(clusters.items())[:10]  # Save first 10 clusters
            },
            'abstractions': abstractions[:20],  # Save top 20 abstractions
            'representatives': [
                {'description': r['description'][:100], 'cluster_id': r.get('cluster_id')}
                for r in representatives
            ]
        }
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved clustering metadata -> {metadata_file}")

        # Update current version
        self.current_version = new_version

        return new_version

    def get_prompt_stats(self) -> Dict[str, Any]:
        """Get statistics about prompt versions and patterns"""
        pattern_stats = self.pattern_storage.get_stats()

        # Count versions
        version_files = list(self.output_dir.glob("deepseek_system_v*.yaml"))

        return {
            'current_version': self.current_version,
            'total_versions': len(version_files),
            'pattern_storage': pattern_stats
        }

    def compare_versions(self, version1: str, version2: str) -> Dict[str, Any]:
        """
        Compare two prompt versions.

        Args:
            version1: First version (e.g., "1.0")
            version2: Second version (e.g., "1.2")

        Returns:
            Comparison dict with differences
        """
        file1 = self.output_dir / f"deepseek_system_v{version1}.yaml"
        file2 = self.output_dir / f"deepseek_system_v{version2}.yaml"

        if not file1.exists() or not file2.exists():
            return {'error': 'One or both versions not found'}

        with open(file1, 'r', encoding='utf-8') as f:
            prompt1 = yaml.safe_load(f)
        with open(file2, 'r', encoding='utf-8') as f:
            prompt2 = yaml.safe_load(f)

        return {
            'version1': version1,
            'version2': version2,
            'changes': prompt2.get('changes', {}),
            'mistakes_added': len(prompt2.get('memory', {}).get('common_mistakes', [])) -
                            len(prompt1.get('memory', {}).get('common_mistakes', [])),
            'guidelines_added': len(prompt2.get('memory', {}).get('improvement_guidelines', [])) -
                              len(prompt1.get('memory', {}).get('improvement_guidelines', []))
        }
