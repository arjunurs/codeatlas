"""Find remarks in a section about the code excerpts it was written from.

Readers never see the excerpts, so phrases such as "the code shown" or "not
shown" read as gaps in the documentation rather than facts about the code.
"""

from __future__ import annotations

import re

# "The context" alone is not a remark: Flask and other frameworks have
# application and request contexts. "This code shows" usually introduces the
# section's own example, so only "the code shows" counts.
_EXCERPT_REMARK = re.compile(
    r"\bthe code (?:shown|shows|provided)\b"
    r"|\bcode (?:is|are) shown\b"
    r"|\bvisible in (?:the|this) (?:code|context|excerpts?)\b(?! block| example)"
    r"|\b(?:the|these) (?:code )?excerpts?\b"
    r"|\bthe (?:provided|given|retrieved) (?:code|context)\b"
    r"|\b(?:the|this) context (?:shows?|shown|does not show)\b"
    r"|\bnot shown\b",
    re.IGNORECASE,
)


def find_excerpt_remarks(text: str) -> list[str]:
    """Find the phrases in a section that refer to its source excerpts.

    Args:
        text: Section Markdown

    Returns:
        Each phrase found, once, in order of first appearance
    """
    found: dict[str, str] = {}
    for match in _EXCERPT_REMARK.finditer(text):
        found.setdefault(match.group(0).lower(), match.group(0))
    return list(found.values())
