"""Unit tests for describing errors in reports and logs."""

from typing import TYPE_CHECKING

import anthropic
import openai
import pytest

from docgen.exceptions.errors import CodeParseError
from docgen.utils.error_classification import classify_api_error, describe_error

# The Anthropic and OpenAI SDKs build their errors from httpx2 objects; the
# releases at the dependency floors still use httpx. Type-check against httpx2,
# the version in uv.lock.
if TYPE_CHECKING:
    import httpx2 as httpx
else:
    try:
        import httpx2 as httpx
    except ImportError:
        import httpx


def test_documentation_error_is_described_by_its_message():
    """codeatlas's own errors already read as sentences."""
    assert describe_error(CodeParseError("bad.py does not parse")) == (
        "bad.py does not parse"
    )


def test_other_error_names_its_type():
    """A bare KeyError message is just the key, so the type is added."""
    assert describe_error(KeyError("name")) == "KeyError: 'name'"


def test_error_without_a_message_is_described_by_its_type():
    """No trailing colon when the error has no message."""
    assert describe_error(TimeoutError()) == "TimeoutError"


REQUEST = httpx.Request("POST", "https://api.example.com/v1")


def _status_error(error_class, status: int, error_type: str, message: str):
    """An SDK status error with the body and message the API sends."""
    body = {"type": "error", "error": {"type": error_type, "message": message}}
    return error_class(
        f"Error code: {status} - {body}",
        response=httpx.Response(status, request=REQUEST),
        body=body,
    )


@pytest.mark.parametrize(
    ("error", "summary"),
    [
        (
            _status_error(
                anthropic.AuthenticationError,
                401,
                "authentication_error",
                "invalid x-api-key",
            ),
            "Anthropic rejected the API key; check ANTHROPIC_API_KEY",
        ),
        (
            _status_error(
                openai.AuthenticationError,
                401,
                "invalid_request_error",
                "Incorrect API key provided: sk-...abcd.",
            ),
            "OpenAI rejected the API key; check OPENAI_API_KEY",
        ),
        (
            _status_error(
                anthropic.RateLimitError,
                429,
                "rate_limit_error",
                "Number of request tokens has exceeded your per-minute rate limit",
            ),
            "Anthropic rate limit reached; wait and run again",
        ),
        (
            _status_error(
                openai.RateLimitError,
                429,
                "insufficient_quota",
                "You exceeded your current quota, please check your plan.",
            ),
            "OpenAI reports no remaining quota or credit; check the account's billing",
        ),
        (
            _status_error(
                anthropic.APIStatusError, 529, "overloaded_error", "Overloaded"
            ),
            "Anthropic is overloaded; wait and run again",
        ),
        (
            _status_error(
                anthropic.NotFoundError, 404, "not_found_error", "model: claude-nope"
            ),
            "Anthropic does not recognize the model; check the model name",
        ),
        (
            _status_error(
                anthropic.BadRequestError,
                400,
                "invalid_request_error",
                "prompt is too long: 250000 tokens > 200000 maximum",
            ),
            "The request is too long for the Anthropic model",
        ),
        (
            anthropic.APITimeoutError(request=REQUEST),
            "Anthropic request timed out; run again",
        ),
        (
            openai.APIConnectionError(request=REQUEST),
            "Could not connect to OpenAI; check the network connection",
        ),
    ],
)
def test_provider_error_gets_a_summary_and_keeps_the_details(error, summary):
    """A known provider failure says what to do, then gives the SDK's own text."""
    assert describe_error(error) == f"{summary} ({error})"


def test_wrapped_provider_error_is_recognized():
    """LangChain raises subclasses of the SDK errors; they are still recognized."""

    class LangChainAuthenticationError(anthropic.AuthenticationError):
        pass

    error = _status_error(
        LangChainAuthenticationError, 401, "authentication_error", "invalid x-api-key"
    )

    assert describe_error(error).startswith("Anthropic rejected the API key")


def test_unrecognized_provider_error_names_its_type():
    """A provider error with no known cause is described like any other error."""
    error = _status_error(
        anthropic.InternalServerError, 500, "api_error", "Internal server error"
    )

    assert describe_error(error) == f"InternalServerError: {error}"


def test_error_from_elsewhere_gets_no_provider_summary():
    """Only provider SDK errors are classified, whatever their message says."""
    assert describe_error(RuntimeError("rate limit")) == "RuntimeError: rate limit"


class TestClassifyApiError:
    """Test cases for classify_api_error function."""

    def test_rate_limit_match(self):
        """Test that rate limit errors are classified correctly."""
        assert classify_api_error(Exception("rate limit exceeded")) == "rate_limit"
        assert classify_api_error(Exception("Rate Limit hit")) == "rate_limit"

    def test_rate_or_limit_alone_is_not_rate_limit(self):
        """Test that "rate" or "limit" on its own does not mean a rate limit."""
        assert classify_api_error(Exception("rate exceeded")) is None
        assert classify_api_error(Exception("limit reached")) is None

    def test_auth_errors(self):
        """Test authentication error classification."""
        assert classify_api_error(Exception("api_key invalid")) == "auth"
        assert classify_api_error(Exception("authentication failed")) == "auth"
        assert classify_api_error(Exception("unauthorized access")) == "auth"
        assert classify_api_error(Exception("401 error")) == "auth"

    def test_timeout_errors(self):
        """Test timeout error classification."""
        assert classify_api_error(Exception("request timeout")) == "timeout"
        assert classify_api_error(Exception("timed out")) == "timeout"

    def test_connection_errors(self):
        """Test connection error classification."""
        assert classify_api_error(Exception("connection refused")) == "connection"

    def test_quota_errors(self):
        """Test quota error classification."""
        assert classify_api_error(Exception("quota exceeded")) == "quota"
        assert classify_api_error(Exception("billing issue")) == "quota"

    def test_context_length_errors(self):
        """Test context length error classification."""
        assert classify_api_error(Exception("context too long")) == "context_length"
        assert classify_api_error(Exception("max length exceeded")) == "context_length"

    def test_no_match(self):
        """Test that unrecognized errors return None."""
        assert classify_api_error(Exception("some random error")) is None
        assert classify_api_error(Exception("")) is None

    @pytest.mark.parametrize(
        "message",
        [
            "Failed to generate documentation section",
            "Could not separate the input",
            "Inaccurate response format",
            "Delimiter missing in output",
            "Contextual information missing",
            "Invalid wavelength value",
        ],
    )
    def test_keyword_inside_longer_word_does_not_match(self, message):
        """Keywords only match as whole words, not inside longer words."""
        assert classify_api_error(Exception(message)) is None

    @pytest.mark.parametrize(
        ("message", "expected"),
        [
            ("Rate limit exceeded", "rate_limit"),
            ("429 Too Many Requests", "rate_limit"),
            (
                "Error code: 429 - {'type': 'error', 'error': {'type': "
                "'rate_limit_error', 'message': 'Number of request tokens has "
                "exceeded your per-minute rate limit'}}",
                "rate_limit",
            ),
            (
                "Error code: 401 - {'type': 'error', 'error': {'type': "
                "'authentication_error', 'message': 'invalid x-api-key'}}",
                "auth",
            ),
            (
                "Error code: 401 - {'error': {'message': 'Incorrect API key "
                "provided', 'code': 'invalid_api_key'}}",
                "auth",
            ),
            (
                "Error code: 429 - {'error': {'message': 'You exceeded your "
                "current quota, please check your plan and billing details.', "
                "'code': 'insufficient_quota'}}",
                "quota",
            ),
            ("Request timed out.", "timeout"),
            ("Connection error.", "connection"),
            (
                "Error code: 400 - {'error': {'message': \"This model's maximum "
                "context length is 8192 tokens.\", 'code': "
                "'context_length_exceeded'}}",
                "context_length",
            ),
            ("prompt is too long: 215000 tokens > 200000 maximum", "context_length"),
            (
                "Error code: 529 - {'type': 'error', 'error': {'type': "
                "'overloaded_error', 'message': 'Overloaded'}}",
                "overloaded",
            ),
            (
                "Error code: 404 - {'type': 'error', 'error': {'type': "
                "'not_found_error', 'message': 'model: claude-nope'}}",
                "not_found",
            ),
            (
                "Error code: 404 - {'error': {'message': 'The model `nope` does not "
                "exist or you do not have access to it.', 'code': 'model_not_found'}}",
                "not_found",
            ),
        ],
    )
    def test_provider_style_messages(self, message, expected):
        """Messages shaped like real provider errors map to the right type."""
        assert classify_api_error(Exception(message)) == expected
