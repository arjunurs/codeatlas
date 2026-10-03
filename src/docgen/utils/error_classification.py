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
    (r"overloaded|529", "overloaded"),
    (r"not found|404", "not_found"),
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


# Provider SDKs, by the top-level package their errors are defined in:
# the provider's name and the variable that holds its API key
_PROVIDERS = {
    "anthropic": ("Anthropic", "ANTHROPIC_API_KEY"),
    "openai": ("OpenAI", "OPENAI_API_KEY"),
}

# What each kind of provider failure means, and what to do about it
_SUMMARIES = {
    "auth": "{name} rejected the API key; check {key_variable}",
    "quota": "{name} reports no remaining quota or credit; check the account's billing",
    "rate_limit": "{name} rate limit reached; wait and run again",
    "overloaded": "{name} is overloaded; wait and run again",
    "not_found": "{name} does not recognize the model; check the model name",
    "context_length": "The request is too long for the {name} model",
    "timeout": "{name} request timed out; run again",
    "connection": "Could not connect to {name}; check the network connection",
}


def _provider(error: Exception) -> tuple[str, str] | None:
    """Find the provider whose SDK raised an error, from the error's classes.

    LangChain raises its own subclasses of the SDK errors, so every class the
    error inherits from is checked, not only its own.
    """
    for cls in type(error).__mro__:
        provider = _PROVIDERS.get(cls.__module__.split(".")[0])
        if provider:
            return provider
    return None


def describe_error(error: Exception) -> str:
    """Describe an error in one line for a log message or an error report.

    codeatlas's own errors are described by their message. A recognized
    provider failure, such as a rejected API key, starts with what it means
    and what to do, followed by the SDK's message. Other errors also name
    their type, since a message alone can be unclear (a KeyError's message
    is only the missing key).
    """
    if isinstance(error, DocumentationError):
        return str(error)
    message = str(error)
    provider = _provider(error)
    error_type = classify_api_error(error) if provider else None
    if provider and error_type:
        name, key_variable = provider
        summary = _SUMMARIES[error_type].format(name=name, key_variable=key_variable)
        return f"{summary} ({message})"
    return f"{type(error).__name__}: {message}" if message else type(error).__name__
