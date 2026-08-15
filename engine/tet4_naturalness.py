"""Naturalness critic có cấu trúc cho strict-form candidates Tet4."""
from __future__ import annotations

import json
import re
from typing import Any


def build_critic_messages(poem: str, metadata: dict[str, Any]) -> list[dict[str, str]]:
    keywords = ", ".join(metadata.get("từ khoá", []))
    system = (
        "Bạn là biên tập viên tiếng Việt. Chỉ đánh giá độ tự nhiên của bài thơ, không sáng tác lại, "
        "không dùng <think>, không giải thích ngoài JSON. Phát hiện từ không tự nhiên, cụm ghép gượng, "
        "hoặc thiếu người nhận/keyword. Đừng coi văn phong thơ là lỗi chỉ vì ngắn."
    )
    user = (
        f"Ý chúc: {metadata.get('ý chúc', '')}\n"
        f"Keyword: {keywords}\n"
        f"Bài thơ:\n{poem}\n"
        "Trả JSON: {\"decision\":\"accept\" hoặc \"reject\", "
        "\"issues\":[\"...\"], \"repair_instruction\":\"một câu ngắn\"}."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_critic(raw: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", raw, re.S)
    if match:
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError:
            value = None
        if (isinstance(value, dict) and value.get("decision") in {"accept", "reject"}
                and isinstance(value.get("issues"), list)
                and all(isinstance(x, str) for x in value["issues"])
                and isinstance(value.get("repair_instruction"), str)):
            return value

    # Qwen đôi khi trích nguyên một câu thơ trong chuỗi JSON mà không escape
    # dấu ngoặc kép. Không đoán accept từ output hỏng; chỉ cứu được một reject
    # hiện diện rõ ràng để dùng như tín hiệu veto một chiều.
    decision = re.search(r'"decision"\s*:\s*"(accept|reject)"', raw)
    if not decision or decision.group(1) != "reject":
        return None
    issues_match = re.search(r'"issues"\s*:\s*\[(.*?)\]\s*,\s*"repair_instruction"', raw, re.S)
    issues_text = issues_match.group(1) if issues_match else "có từ hoặc cụm ghép không tự nhiên"
    issues_text = re.sub(r'\s+', ' ', issues_text).strip(' ,"')
    repair_match = re.search(r'"repair_instruction"\s*:\s*"(.*?)"\s*\}', raw, re.S)
    instruction = repair_match.group(1) if repair_match else "Dùng từ tiếng Việt thông dụng, tự nhiên."
    return {"decision": "reject", "issues": [issues_text], "repair_instruction": instruction}


def repair_feedback(poem: str, critic: dict[str, Any] | None) -> str | None:
    if not critic or critic.get("decision") != "reject":
        return None
    issues = "; ".join(critic.get("issues", [])[:4]) or "có từ/cụm không tự nhiên"
    instruction = critic.get("repair_instruction", "Dùng từ tiếng Việt thông dụng, tự nhiên.")
    return (
        "Bản strict trước bị biên tập viên từ chối. Giữ luật 6–8/vần/thanh và coverage, "
        f"nhưng sửa các lỗi: {issues}. Yêu cầu sửa: {instruction}. "
        f"Không lặp lại nguyên văn bản lỗi này:\n{poem}"
    )
