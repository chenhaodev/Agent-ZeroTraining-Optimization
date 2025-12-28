"""
JSON parsing utilities for handling LLM responses.
"""

import json
import re
from loguru import logger
from typing import Any, Dict, List, Union


def extract_json_from_markdown(text: str) -> Union[Dict, List]:
    """
    Extract JSON from a markdown-formatted response.

    Handles cases where the LLM wraps JSON in markdown code blocks:
    ```json
    {...}
    ```

    Args:
        text: Raw text response from LLM

    Returns:
        Parsed JSON object (dict or list)

    Raises:
        ValueError: If JSON cannot be extracted or parsed
    """
    if not text or not text.strip():
        raise ValueError("Empty response")

    # Try to extract from markdown code block first
    markdown_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
    matches = re.findall(markdown_pattern, text, re.DOTALL)

    if matches:
        # Use the first code block found
        json_str = matches[0].strip()
    else:
        # No markdown blocks, assume the whole text is JSON
        json_str = text.strip()

    # Try to parse JSON
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        # Log the error with truncated response
        logger.error(f"JSON parsing failed: {e}")
        safe_log_response(json_str, "JSON parse error")
        raise ValueError(f"Failed to parse JSON: {e}")


def safe_log_response(response: str, context: str = "Response", max_length: int = 500):
    """
    Safely log a response, truncating if too long.

    Args:
        response: The response text to log
        context: Context string to prepend to log message
        max_length: Maximum characters to log (default: 500)
    """
    if not response:
        logger.warning(f"{context}: <empty response>")
        return

    # Truncate if too long
    if len(response) > max_length:
        truncated = response[:max_length] + f"... (truncated, total: {len(response)} chars)"
        logger.debug(f"{context}: {truncated}")
    else:
        logger.debug(f"{context}: {response}")
