"""Describing errors for logs and reports, and classifying API errors."""

import re

from ..exceptions.errors import DocumentationError

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


def describe_error(error: BaseException) -> str:
    """Describe an error in one line for a log message or an error report.

    codeatlas's own errors are described by their message. Other errors also
    name their type, since a message alone can be unclear (a KeyError's
    message is only the missing key).
    """
    if isinstance(error, DocumentationError):
        return str(error)
    message = str(error)
    return f"{type(error).__name__}: {message}" if message else type(error).__name__
