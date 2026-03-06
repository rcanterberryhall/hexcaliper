import re

# Patterns that typically signal a copyright or licensing notice.
# Each pattern captures a single line (up to 300 chars) starting at the keyword.
_PATTERNS = [
    r'©[^\n]{0,300}',
    r'Copyright\s[^\n]{0,300}',
    r'All rights reserved[^\n]{0,200}',
    r'Reproduction[^\n]{0,250}',
    r'No part of this[^\n]{0,250}',
    r'This (?:document|publication|standard)[^\n]{0,250}',
    r'Licensed under[^\n]{0,250}',
    r'Permission is (?:hereby )?granted[^\n]{0,250}',
    r'Proprietary[^\n]{0,200}',
    r'NOTICE:[^\n]{0,250}',
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _PATTERNS]
_MAX_NOTICES = 6
_MAX_NOTICE_LEN = 250


def extract(text: str) -> list[str]:
    """
    Return up to _MAX_NOTICES unique copyright/licensing notices found in text.
    Scans the full document but weights the first 6 000 chars (where copyright
    blocks typically appear in standards and technical documents).
    """
    # Prioritise front matter, then scan the rest
    head = text[:6000]
    tail = text[6000:] if len(text) > 6000 else ""
    search_text = head + ("\n" + tail if tail else "")

    candidates: list[str] = []

    for pattern in _COMPILED:
        for m in pattern.finditer(search_text):
            notice = m.group().strip()[:_MAX_NOTICE_LEN]
            candidates.append(notice)

    # Remove duplicates and notices that are substrings of a longer captured notice
    candidates = list(dict.fromkeys(candidates))  # dedupe exact
    notices: list[str] = []
    for candidate in candidates:
        c_lower = candidate.lower()
        # Skip if this is a substring of something already kept
        if any(c_lower in kept.lower() for kept in notices):
            continue
        # Replace any previously kept notice that is a substring of this one
        notices = [k for k in notices if k.lower() not in c_lower]
        notices.append(candidate)
        if len(notices) >= _MAX_NOTICES:
            break

    return notices
