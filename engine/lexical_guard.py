"""Kiểm tra lỗi từ/cụm từ chắc chắn trong thơ sinh trước khi rerank."""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable

_WORD_RE = re.compile(r"[a-zà-ỹđ]+", re.IGNORECASE)
# Các ký tự này không thể là một từ tiếng Việt độc lập; chúng thường là token bị cắt.
_ORPHAN_VOWELS = {"ă", "â", "ê", "ô", "ơ", "ư"}


def tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(unicodedata.normalize("NFC", text).lower())


def _keyword_prefix_matches(tokens: list[str], keywords: Iterable[str]) -> list[dict]:
    issues = []
    for keyword in keywords:
        expected = tokenize(keyword)
        if len(expected) < 2:
            continue
        width = len(expected)
        for start in range(len(tokens) - width + 1):
            actual = tokens[start:start + width]
            if actual[:-1] == expected[:-1] and actual[-1] != expected[-1] and expected[-1].startswith(actual[-1]):
                issues.append({
                    "type": "truncated_keyword",
                    "keyword": " ".join(expected),
                    "observed": " ".join(actual),
                })
    return issues


def assess(poem: str, keywords: Iterable[str] = ()) -> dict:
    """Trả issue chắc chắn; không phỏng đoán lỗi ở từ hiếm hoặc phong cách thơ."""
    tokens = tokenize(poem)
    issues = [
        {"type": "orphan_vowel", "token": token}
        for token in tokens if token in _ORPHAN_VOWELS
    ]
    issues.extend(_keyword_prefix_matches(tokens, keywords))
    hard_fail = bool(issues)
    return {"tokens": tokens, "issues": issues, "hard_fail": hard_fail}
