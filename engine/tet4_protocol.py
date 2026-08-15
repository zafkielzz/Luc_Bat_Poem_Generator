"""Protocol Tet4-v1 cho lời chúc Tết Lục Bát bốn dòng."""
from __future__ import annotations

import unicodedata
from typing import Any, Mapping

PROTOCOL_VERSION = "tet4-v1"
REQUIRED_FIELDS = ("wish_intent", "keywords")


def _clean_text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} phải là chuỗi")
    cleaned = " ".join(unicodedata.normalize("NFC", value).split())
    if not cleaned:
        raise ValueError(f"{field} không được để trống")
    return cleaned


def normalize_keywords(value: Any) -> list[str]:
    """Chuẩn hóa, loại trùng nhưng giữ nguyên thứ tự và cách viết của người dùng."""
    if not isinstance(value, list):
        raise ValueError("keywords phải là danh sách")
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        keyword = _clean_text(item, "mỗi keyword")
        key = keyword.casefold()
        if key not in seen:
            result.append(keyword)
            seen.add(key)
    if len(result) not in (2, 3):
        raise ValueError("keywords phải còn đúng 2 hoặc 3 mục sau khi loại trùng")
    return result


def normalize_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Đổi schema API Tet4 thành metadata tiếng Việt mà pipeline hiện dùng."""
    if not isinstance(metadata, Mapping):
        raise ValueError("metadata phải là object")
    wish_intent = _clean_text(metadata.get("wish_intent"), "wish_intent")
    # recipient là trường legacy; nếu có thì gộp vào ý chúc, không bắt buộc ở API Tet4.
    recipient = metadata.get("recipient")
    if recipient is not None:
        recipient = _clean_text(recipient, "recipient")
        wish_intent = f"Chúc {recipient}: {wish_intent}"
    keywords = normalize_keywords(metadata.get("keywords"))
    num_lines = metadata.get("num_lines", 4)
    if num_lines != 4:
        raise ValueError("Tet4-v1 chỉ hỗ trợ num_lines=4")
    version = metadata.get("protocol_version", PROTOCOL_VERSION)
    if version != PROTOCOL_VERSION:
        raise ValueError(f"protocol_version phải là {PROTOCOL_VERSION}")
    return {
        "ý chúc": wish_intent,
        "từ khoá": keywords,
        "số câu": 4,
        "protocol_version": PROTOCOL_VERSION,
    }


def validate_manifest(data: Mapping[str, Any], expected_split: str | None = None) -> list[dict[str, Any]]:
    """Kiểm tra manifest Tet4 và trả record đã chuẩn hóa metadata."""
    if data.get("version") != PROTOCOL_VERSION:
        raise ValueError(f"version manifest phải là {PROTOCOL_VERSION}")
    if expected_split is not None and data.get("split") != expected_split:
        raise ValueError(f"split manifest phải là {expected_split}")
    prompts = data.get("prompts")
    if not isinstance(prompts, list) or not prompts:
        raise ValueError("manifest phải có danh sách prompts không rỗng")
    ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for record in prompts:
        if not isinstance(record, Mapping):
            raise ValueError("mỗi prompt phải là object")
        prompt_id = _clean_text(record.get("id"), "id")
        if prompt_id in ids:
            raise ValueError(f"id prompt trùng: {prompt_id}")
        ids.add(prompt_id)
        prompt = _clean_text(record.get("prompt"), "prompt")
        normalized.append({"id": prompt_id, "prompt": prompt,
                           "metadata": normalize_metadata(record.get("metadata", {}))})
    return normalized
