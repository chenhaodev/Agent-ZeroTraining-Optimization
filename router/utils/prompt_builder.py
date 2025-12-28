"""
Prompt builder utility for constructing enhanced prompts with weakness patterns.
"""

from typing import List, Dict, Any, Optional
from loguru import logger


class PromptBuilder:
    """Build enhanced prompts with weakness pattern reminders"""

    DEFAULT_BASE_PROMPT = """你是一位专业、耐心、友善的医疗健康助手。你的任务是回答患者关于常见疾病、检查、手术和疫苗的一般性医疗健康问题。

## 核心原则

1. **准确性第一**: 提供准确、基于证据的医疗信息
2. **通俗易懂**: 使用患者能理解的简单中文，避免过多专业术语
3. **完整但简洁**: 回答要全面但不冗长，突出重点
4. **安全边界**: 明确告知"建议咨询医生"的情况

## 禁止行为

- ❌ 给出明确诊断（例如："你肯定是..."）
- ❌ 推荐具体药物剂量
- ❌ 替代专业医疗建议
- ❌ 对症状做出保证性判断

## 回答结构

1. 直接回答核心问题
2. 提供相关背景信息（如适用）
3. 给出实用建议
4. 说明何时需要就医"""

    def build_prompt(
        self,
        base_prompt: Optional[str] = None,
        weakness_patterns: Optional[List[Dict[str, Any]]] = None,
        rag_context: Optional[str] = None
    ) -> str:
        """
        Build enhanced prompt with weakness patterns and optional pattern retrieval context.

        Args:
            base_prompt: Base system prompt (uses default if not provided)
            weakness_patterns: List of matched weakness patterns
            rag_context: Optional RAG-retrieved context

        Returns:
            Enhanced prompt string
        """
        # Use default or provided base prompt
        prompt = base_prompt or self.DEFAULT_BASE_PROMPT

        # Add pattern retrieval context if provided
        if rag_context:
            prompt += f"\n\n## 权威医学参考资料\n\n{rag_context}"

        # Add weakness pattern reminders
        if weakness_patterns and len(weakness_patterns) > 0:
            prompt += "\n\n## ⚠️ 针对该问题类型的特别提醒\n"

            for i, pattern in enumerate(weakness_patterns, 1):
                prompt_addition = pattern.get('prompt_addition', '')
                if prompt_addition:
                    prompt += f"\n{prompt_addition}\n"

            logger.debug(f"Added {len(weakness_patterns)} weakness pattern reminders to prompt")

        return prompt

    def build_multipart_prompt(
        self,
        base_prompt: Optional[str] = None,
        category_rules: Optional[str] = None,
        rag_context: Optional[str] = None,
        weakness_patterns: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Build complete multi-tier prompt.

        This implements the full tiered system:
        - Tier 0: Base system prompt
        - Tier 1: Category-specific rules (if provided)
        - Pattern Retrieval context (if provided)
        - Tier 3: Weakness pattern reminders (if matched)

        Args:
            base_prompt: Base system prompt
            category_rules: Category-specific guidelines
            rag_context: RAG-retrieved context
            weakness_patterns: Matched weakness patterns

        Returns:
            Complete enhanced prompt
        """
        # Start with base
        prompt = base_prompt or self.DEFAULT_BASE_PROMPT

        # Tier 1: Category rules
        if category_rules:
            prompt += f"\n\n## 领域专项规则\n\n{category_rules}"

        # Pattern Retrieval context
        if rag_context:
            prompt += f"\n\n## 权威医学参考资料\n\n{rag_context}"

        # Tier 3: Weakness reminders
        if weakness_patterns and len(weakness_patterns) > 0:
            prompt += "\n\n## ⚠️ 针对该问题类型的特别提醒\n"

            for pattern in weakness_patterns:
                prompt_addition = pattern.get('prompt_addition', '')
                if prompt_addition:
                    prompt += f"\n{prompt_addition}\n"

        return prompt

    def format_weakness_section(
        self,
        weakness_patterns: List[Dict[str, Any]]
    ) -> str:
        """
        Format weakness patterns as a standalone section.

        Useful for injecting into existing prompts.

        Args:
            weakness_patterns: List of weakness patterns

        Returns:
            Formatted weakness section
        """
        if not weakness_patterns:
            return ""

        section = "## ⚠️ 针对该问题类型的特别提醒\n"

        for pattern in weakness_patterns:
            weakness_id = pattern.get('weakness_id', 'unknown')
            category = pattern.get('category', 'unknown')
            severity = pattern.get('severity', 'unknown')
            prompt_addition = pattern.get('prompt_addition', '')

            if prompt_addition:
                section += f"\n{prompt_addition}\n"

        return section

    def get_prompt_stats(self, prompt: str) -> Dict[str, Any]:
        """
        Get statistics about a prompt.

        Args:
            prompt: Prompt text

        Returns:
            Dictionary with prompt statistics
        """
        return {
            'total_length': len(prompt),
            'char_count': len(prompt),
            'line_count': len(prompt.split('\n')),
            'estimated_tokens': len(prompt) // 2,  # Rough estimate for Chinese
            'has_rag_section': '权威医学参考资料' in prompt,
            'has_weakness_section': '特别提醒' in prompt
        }
