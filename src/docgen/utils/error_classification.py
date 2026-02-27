"""API error classification utility.

This module classifies API errors based on common patterns,
extracted from providers.base for reusability.
"""

# Common error patterns for API error classification
ERROR_PATTERNS: list[tuple[tuple[str, ...], str]] = [
    (("rate", "limit"), "rate_limit"),
    (("api_key", "authentication", "unauthorized", "401"), "auth"),
    (("timeout", "timed out"), "timeout"),
    (("connection",), "connection"),
    (("quota", "billing"), "quota"),
    (("context", "length"), "context_length"),
]


def classify_api_error(error: Exception) -> str | None:
    """Classify an API error based on common patterns.

    Args:
        error: The exception to classify

    Returns:
        Error type string or None if no match
    """
    error_str = str(error).lower()
    for keywords, error_type in ERROR_PATTERNS:
        if any(kw in error_str for kw in keywords):
            return error_type
    return None
