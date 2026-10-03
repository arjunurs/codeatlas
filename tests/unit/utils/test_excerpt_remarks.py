"""Tests for finding remarks about the code excerpts a section was written from."""

import pytest

from docgen.utils.excerpt_remarks import find_excerpt_remarks


# The first six are sentences from the Flask sample run (2026-10-03)
@pytest.mark.parametrize(
    ("sentence", "phrase"),
    [
        (
            "This is the Flask web framework. The code shown covers these areas:",
            "The code shown",
        ),
        ("The code shows several pipelines.", "The code shows"),
        ("The patterns visible in this code are:", "visible in this code"),
        (
            "The context shows no API keys, OAuth or token handling.",
            "The context shows",
        ),
        ('| TagUUID | " u" | UUID | not shown |', "not shown"),
        ("The dotenv-related code is shown in two places:", "code is shown"),
        (
            "Based on the provided code, the app reads its config once.",
            "the provided code",
        ),
        ("The excerpts do not include the session interface.", "The excerpts"),
    ],
)
def test_remarks_about_the_excerpts_are_found(sentence, phrase):
    """Phrases that tell the reader about the excerpts are reported."""
    assert find_excerpt_remarks(sentence) == [phrase]


@pytest.mark.parametrize(
    "sentence",
    [
        "Pushing the application context sends `appcontext_pushed`.",
        "The request context is popped after the teardown functions run.",
        "`_cv_app` is the context variable that holds the current app context.",
        "This code shows how to register a blueprint:",
        "The example below shows a custom session interface.",
        "A message flashed in one request is shown in the next one.",
        "The name is visible in this code block as `app.name`.",
    ],
)
def test_ordinary_documentation_is_not_flagged(sentence):
    """A framework's own contexts and the section's own examples are not remarks."""
    assert find_excerpt_remarks(sentence) == []


def test_each_remark_is_reported_once():
    """A phrase repeated across a table is reported once."""
    text = "| TagUUID | not shown | not shown |\n| TagDict | Not shown | x |"

    assert find_excerpt_remarks(text) == ["not shown"]
