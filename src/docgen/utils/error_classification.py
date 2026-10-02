"""API error classification utility.

This module classifies API errors based on common patterns,
extracted from providers.base for reusability.
"""

import re

# Common error patterns for API error classification. Each entry is a regex
# alternation matched as whole words against the lowercased error message,
# with "_" and "-" read as spaces so "rate_limit_error" matches "rate limit".
# Order matters: quota comes before rate_limit because OpenAI reports an
# exhausted quota as HTTP 429.
ERROR_PATTERNS: list[tuple[str, str]] = [
    (r"quota|billing", "quota"),
    (r"rate limit(?:s|ed)?|too many requests|429", "rate_limit"),
    (r"api key|authentication|unauthorized|401", "auth"),
    (r"timeout|timed out", "timeout"),
    (r"connection", "connection"),
    (r"context length|maximum context|max(?:imum)? length|too long", "context_length"),
]

_COMPILED_PATTERNS = [
    (re.compile(rf"\b(?:{pattern})\b"), error_type)
    for pattern, error_type in ERROR_PATTERNS
]


def classify_api_error(error: Exception) -> str | None:
    """Classify an API error based on common patterns.

    Args:
        error: The exception to classify

    Returns:
        Error type string or None if no match
    """
    error_str = re.sub(r"[_-]", " ", str(error).lower())
    for pattern, error_type in _COMPILED_PATTERNS:
        if pattern.search(error_str):
            return error_type
    return None
