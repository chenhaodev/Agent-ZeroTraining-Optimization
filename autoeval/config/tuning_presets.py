"""
Helper module for loading and applying tuning presets.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger


def load_preset(preset_name: str = "balanced") -> Dict[str, Any]:
    """
    Load a tuning preset configuration.

    Args:
        preset_name: Name of preset (balanced, high_accuracy, cost_optimized, etc.)

    Returns:
        Preset configuration dictionary
    """
    preset_file = Path(__file__).parent / "tuning_presets.yaml"

    if not preset_file.exists():
        logger.warning(f"Preset file not found: {preset_file}, using defaults")
        return get_default_preset()

    try:
        with open(preset_file, 'r', encoding='utf-8') as f:
            presets = yaml.safe_load(f)

        if preset_name not in presets:
            logger.warning(f"Preset '{preset_name}' not found, using 'balanced'")
            preset_name = "balanced"

        preset = presets[preset_name]
        logger.info(f"Loaded tuning preset: {preset_name}")
        logger.info(f"  - RAG k={preset.get('rag_k', 5)}")
        logger.info(f"  - Min severity={preset.get('min_severity', 'minor')}")
        logger.info(f"  - Category rules={'enabled' if preset.get('use_category_rules', True) else 'disabled'}")
        logger.info(f"  - Estimated tokens: {preset.get('estimated_tokens', 'N/A')}")
        logger.info(f"  - Estimated accuracy: {preset.get('estimated_accuracy', 'N/A')}/5.0")

        return preset

    except Exception as e:
        logger.error(f"Failed to load preset: {e}")
        return get_default_preset()


def get_default_preset() -> Dict[str, Any]:
    """Get default balanced preset"""
    return {
        'description': '默认平衡配置',
        'use_dynamic_prompts': True,
        'rag_k': 5,
        'min_severity': 'minor',
        'use_category_rules': True,
        'estimated_tokens': 800,
        'estimated_accuracy': 4.6
    }


def list_presets() -> Dict[str, str]:
    """
    List all available presets with descriptions.

    Returns:
        Dict mapping preset names to descriptions
    """
    preset_file = Path(__file__).parent / "tuning_presets.yaml"

    if not preset_file.exists():
        return {"balanced": "默认平衡配置"}

    try:
        with open(preset_file, 'r', encoding='utf-8') as f:
            presets = yaml.safe_load(f)

        return {
            name: config.get('description', 'No description')
            for name, config in presets.items()
            if isinstance(config, dict) and 'description' in config
        }

    except Exception as e:
        logger.error(f"Failed to list presets: {e}")
        return {"balanced": "默认平衡配置"}


def compare_presets() -> str:
    """
    Generate a comparison table of all presets.

    Returns:
        Formatted comparison string
    """
    preset_file = Path(__file__).parent / "tuning_presets.yaml"

    if not preset_file.exists():
        return "Preset file not found"

    try:
        with open(preset_file, 'r', encoding='utf-8') as f:
            presets = yaml.safe_load(f)

        # Build comparison table
        lines = []
        lines.append("\n" + "="*80)
        lines.append("Tuning Preset Comparison")
        lines.append("="*80)
        lines.append(f"{'Preset':<20} {'Tokens':<10} {'Accuracy':<10} {'RAG-k':<8} {'Category':<12}")
        lines.append("-"*80)

        for name, config in presets.items():
            if not isinstance(config, dict) or 'estimated_tokens' not in config:
                continue

            tokens = config.get('estimated_tokens', 'N/A')
            accuracy = config.get('estimated_accuracy', 'N/A')
            rag_k = config.get('rag_k', 'N/A')
            category = 'Yes' if config.get('use_category_rules', False) else 'No'

            lines.append(f"{name:<20} {tokens:<10} {accuracy:<10} {rag_k:<8} {category:<12}")

        lines.append("="*80)
        return "\n".join(lines)

    except Exception as e:
        return f"Failed to generate comparison: {e}"


def apply_preset_to_config(preset_name: str, config_dict: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Apply preset settings to a configuration dictionary.

    Args:
        preset_name: Name of preset to apply
        config_dict: Existing config (will be updated), or None to create new

    Returns:
        Updated configuration dictionary
    """
    if config_dict is None:
        config_dict = {}

    preset = load_preset(preset_name)

    # Apply preset settings
    config_dict['use_dynamic_prompts'] = preset.get('use_dynamic_prompts', True)
    config_dict['rag_k'] = preset.get('rag_k', 5)
    config_dict['min_severity'] = preset.get('min_severity', 'minor')
    config_dict['use_category_rules'] = preset.get('use_category_rules', True)

    return config_dict


if __name__ == "__main__":
    # Demo usage
    print("Available Presets:")
    print("-" * 40)
    for name, desc in list_presets().items():
        print(f"  {name}: {desc}")

    print(compare_presets())

    print("\nLoading 'high_accuracy' preset:")
    preset = load_preset('high_accuracy')
    print(f"  Configuration: {preset}")
