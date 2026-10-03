"""Unit tests for describing errors in reports and logs."""

from docgen.exceptions.errors import CodeParseError
from docgen.utils.error_classification import describe_error


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
