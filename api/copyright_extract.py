"""
copyright_extract.py — Copyright and licensing notice detection.

Scans document text for common copyright, licensing, and proprietary
markers and returns a deduplicated list of the most representative notices.
These are surfaced to the model so it can acknowledge document restrictions
when answering questions about uploaded files.
"""

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

# Pre-compiled regex objects for performance.
_COMPILED = [re.compile(p, re.IGNORECASE) for p in _PATTERNS]

# Maximum number of unique notices to return.
_MAX_NOTICES = 6
# Notices are truncated to this length to keep prompt injection size bounded.
_MAX_NOTICE_LEN = 250


# ── Public API ─────────────────────────────────────────────────

def extract(text: str) -> list[str]:
    """
    Return up to ``_MAX_NOTICES`` unique copyright/licensing notices found in *text*.

    Scans the full document but prioritises the first 6 000 characters, where
    copyright blocks typically appear in standards and technical documents.
    Exact duplicates are removed, and shorter notices that are substrings of a
    longer already-captured notice are also suppressed to avoid redundancy.

    :param text: The full text of the uploaded document.
    :type text: str
    :return: A deduplicated list of copyright/licensing notice strings.
    :rtype: list[str]
    """
    # Prioritise front matter, then append the remainder for a full scan.
    head = text[:6000]
    tail = text[6000:] if len(text) > 6000 else ""
    search_text = head + ("\n" + tail if tail else "")

    candidates: list[str] = []

    for pattern in _COMPILED:
        for m in pattern.finditer(search_text):
            notice = m.group().strip()[:_MAX_NOTICE_LEN]
            candidates.append(notice)

    # Remove exact duplicates while preserving first-seen order.
    candidates = list(dict.fromkeys(candidates))

    notices: list[str] = []
    for candidate in candidates:
        c_lower = candidate.lower()
        # Skip if this candidate is already covered by a longer kept notice.
        if any(c_lower in kept.lower() for kept in notices):
            continue
        # Replace any previously kept notice that is a substring of this one.
        notices = [k for k in notices if k.lower() not in c_lower]
        notices.append(candidate)
        if len(notices) >= _MAX_NOTICES:
            break

    return notices
