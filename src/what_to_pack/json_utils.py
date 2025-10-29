"""Utility functions for robust JSON extraction and validation from agent responses."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple


CODE_FENCE_PATTERN = re.compile(r"```(?:json)?(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_json_text(raw: str) -> str:
    """Extract JSON substring from raw LLM output.

    Strategy:
    1. If fenced code block present, grab inner text.
    2. Strip leading 'json' marker if present.
    3. Fallback: attempt to locate first '{' and last '}' and slice.
    """
    raw = raw.strip()
    match = CODE_FENCE_PATTERN.search(raw)
    if match:
        inner = match.group(1).strip()
        if inner.lower().startswith("json"):
            inner = inner[4:].strip()
        raw = inner
    # Fallback bracket slicing
    if not (raw.startswith("{") and raw.endswith("}")):
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            raw = raw[start : end + 1]
    return raw.strip()


def try_parse_json(raw: str) -> Tuple[Optional[Any], Optional[str]]:
    """Attempt JSON parsing returning (data, error)."""
    try:
        data = json.loads(raw)
        return data, None
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def validate_keys(obj: Any, required: List[str]) -> Tuple[bool, List[str]]:
    """Validate an object has required top-level keys."""
    if not isinstance(obj, dict):
        return False, required
    missing = [k for k in required if k not in obj]
    return len(missing) == 0, missing


def safe_load_validated(raw: str, required_keys: List[str]) -> Tuple[Dict[str, Any], List[str]]:
    """Extract, parse and validate JSON returning (data, warnings).

    Falls back to empty dict if parsing fails.
    Adds warnings for parse errors or missing keys.
    """
    warnings: List[str] = []
    json_text = extract_json_text(raw)
    data, err = try_parse_json(json_text)
    if err:
        warnings.append(f"JSON parse error: {err}")
        return {}, warnings
    ok, missing = validate_keys(data, required_keys)
    if not ok:
        warnings.append(f"Missing keys: {', '.join(missing)}")
    return data, warnings


__all__ = [
    "extract_json_text",
    "try_parse_json",
    "validate_keys",
    "safe_load_validated",
]
