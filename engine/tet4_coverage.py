"""Content coverage contract cho Tet4 agent.

Coverage là cổng sau generation, không phải hard mask token. Vì vậy model vẫn
có thể paraphrase tự nhiên, nhưng agent không được trả bài bỏ quên người nhận
hoặc toàn bộ keyword người dùng đã chọn.
"""
from __future__ import annotations

from typing import Any, Iterable

from engine.evaluator import _line_syllables


RECIPIENT_ALIASES: dict[str, tuple[str, ...]] = {
    "ông bà": ("ông bà", "bà ông"),
    "cha mẹ": ("cha mẹ", "mẹ cha", "ba mẹ", "mẹ ba", "bố mẹ", "mẹ bố"),
    "bố mẹ": ("bố mẹ", "mẹ bố", "ba mẹ", "mẹ ba", "cha mẹ", "mẹ cha"),
    "ba mẹ": ("ba mẹ", "mẹ ba", "bố mẹ", "mẹ bố", "cha mẹ", "mẹ cha"),
    "thầy cô": ("thầy cô", "cô thầy"),
    "anh chị": ("anh chị", "chị anh"),
    "con cháu": ("con cháu", "cháu con"),
}

# Alias phải đủ cụ thể để reviewer có thể giải thích vì sao được tính.
# Từ đơn "trẻ" chỉ là semantic hit yếu, không bao giờ thay exact-hit bắt buộc.
KEYWORD_ALIASES: dict[str, tuple[str, ...]] = {
    "con cháu": ("cháu con", "trẻ nhỏ", "trẻ con", "đàn trẻ", "trẻ"),
    "sum vầy": ("quây quần", "đoàn viên", "tụ họp", "đầm ấm"),
    "lộc xuân": ("lộc mới", "lộc biếc", "mầm lộc", "chồi lộc"),
    "bình an": ("an lành", "yên bình", "an yên"),
    "vui khỏe": ("khỏe vui", "mạnh khỏe", "khỏe mạnh"),
    "mai vàng": ("hoa mai", "mai nở", "cành mai"),
}


def _tokens(value: str) -> list[str]:
    return _line_syllables(value)


def _contains_phrase(haystack: list[str], phrase: str) -> bool:
    needle = _tokens(phrase)
    if not needle or len(needle) > len(haystack):
        return False
    return any(haystack[index:index + len(needle)] == needle
               for index in range(len(haystack) - len(needle) + 1))


def extract_recipients(wish_intent: str) -> list[str]:
    """Chỉ rút các đối tượng gia đình/nhóm rõ nghĩa; không ép đại từ mơ hồ."""
    tokens = _tokens(wish_intent)
    recipients = []
    for name in RECIPIENT_ALIASES:
        if not _contains_phrase(tokens, name):
            continue
        # "con cháu" thường là nội dung quây quần trong lời chúc ông bà.
        # Chỉ coi đây là người nhận khi nó đứng ngay sau động từ chúc.
        if name == "con cháu" and not (
            _contains_phrase(tokens, "chúc con cháu")
            or _contains_phrase(tokens, "chúc cho con cháu")
        ):
            continue
        recipients.append(name)
    return recipients


def evaluate_coverage(poem: str, wish_intent: str,
                      keywords: Iterable[str]) -> dict[str, Any]:
    poem_tokens = _tokens(poem)
    required_recipients = extract_recipients(wish_intent)
    recipient_details = []
    for recipient in required_recipients:
        matched_as = next((alias for alias in RECIPIENT_ALIASES[recipient]
                           if _contains_phrase(poem_tokens, alias)), None)
        recipient_details.append({"recipient": recipient, "matched": matched_as is not None,
                                  "matched_as": matched_as})

    keyword_details = []
    for raw_keyword in keywords:
        keyword = " ".join(_tokens(str(raw_keyword)))
        exact = _contains_phrase(poem_tokens, keyword)
        alias = None if exact else next(
            (candidate for candidate in KEYWORD_ALIASES.get(keyword, ())
             if _contains_phrase(poem_tokens, candidate)), None)
        keyword_details.append({"keyword": raw_keyword, "exact": exact,
                                "semantic": exact or alias is not None,
                                "matched_as": keyword if exact else alias})

    exact_count = sum(item["exact"] for item in keyword_details)
    semantic_count = sum(item["semantic"] for item in keyword_details)
    minimum_semantic = min(2, len(keyword_details))
    recipient_pass = all(item["matched"] for item in recipient_details)
    exact_pass = exact_count >= 1
    semantic_pass = semantic_count >= minimum_semantic
    reasons = []
    if not recipient_pass:
        reasons.append("missing_recipient")
    if not exact_pass:
        reasons.append("no_exact_keyword")
    if not semantic_pass:
        reasons.append("insufficient_semantic_keywords")
    return {
        "pass": not reasons,
        "reasons": reasons,
        "recipient_pass": recipient_pass,
        "recipients": recipient_details,
        "exact_keyword_count": exact_count,
        "semantic_keyword_count": semantic_count,
        "minimum_semantic_keywords": minimum_semantic,
        "keywords": keyword_details,
    }


def evaluate_acceptance(ranked_item: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    """Gate sản phẩm: content + lexical + cấu trúc/vần-thanh tối thiểu."""
    coverage = evaluate_coverage(
        ranked_item["poem"], metadata.get("ý chúc", ""), metadata.get("từ khoá", ()))
    evaluation = ranked_item["eval"]
    lexical_pass = not ranked_item.get("lexical", {}).get("hard_fail", False)
    form_pass = (
        evaluation.get("scr", 0) == 100
        and evaluation.get("tcr", 0) == 100
        and evaluation.get("combined_rma", evaluation.get("rma", 0)) == 100
    )
    reasons = list(coverage["reasons"])
    if not lexical_pass:
        reasons.append("lexical_hard_fail")
    if not form_pass:
        reasons.append("form_below_gate")
    return {"pass": not reasons, "reasons": reasons, "coverage": coverage,
            "lexical_pass": lexical_pass, "form_pass": form_pass}


def coverage_instruction(metadata: dict[str, Any]) -> str:
    """Contract ngắn đưa vào prompt từ attempt đầu tiên."""
    recipients = extract_recipients(metadata.get("ý chúc", ""))
    keywords = metadata.get("từ khoá", [])
    parts = []
    if recipients:
        parts.append("phải nhắc rõ " + ", ".join(recipients))
    parts.append("phải dùng nguyên văn ít nhất một từ khoá: " + ", ".join(keywords))
    parts.append(f"phải phủ ít nhất {min(2, len(keywords))}/{len(keywords)} ý từ khoá; phần còn lại được paraphrase")
    return "Ràng buộc nội dung: " + "; ".join(parts) + "."


def retry_feedback(assessments: list[dict[str, Any]], metadata: dict[str, Any]) -> str:
    """Biến failure trace thành yêu cầu sửa ngắn cho lượt generation kế tiếp."""
    content_passed = any(item.get("coverage", {}).get("pass") for item in assessments)
    form_failed = any(not item.get("form_pass", False) for item in assessments)
    parts = [coverage_instruction(metadata)]
    if content_passed:
        parts.append("Đã có ứng viên đúng nội dung; giữ nguyên coverage, đừng nhồi thêm từ khoá")
    else:
        parts.append("Lượt trước thiếu coverage; phân bố người nhận và từ khoá sang các dòng khác nhau")
    if form_failed:
        parts.append("ưu tiên sửa toàn bộ vị trí bằng–trắc và đủ ba liên kết vần Lục Bát, tránh thêm ý mới")
    return "Lượt trước không qua gate. " + "; ".join(parts) + "."
