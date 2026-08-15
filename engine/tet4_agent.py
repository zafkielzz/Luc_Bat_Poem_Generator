"""Lớp điều phối cho trải nghiệm Tet4 agent-first.

Agent không tự chọn từ khoá thay người dùng. Nó chỉ tra cứu corpus tư liệu,
gợi ý một creative brief (bản định hướng sáng tác), rồi đợi người dùng chọn
đúng 2--3 từ khoá trước khi chuyển sang bước lập plan và sinh thơ.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

from engine.tet4_protocol import normalize_metadata


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS = ROOT / "data" / "sft" / "tet4_source_material_corpus_v1.jsonl"
_WORD_RE = re.compile(r"[a-zA-ZÀ-ỹĐđ]+", re.UNICODE)


def _fold(value: str) -> str:
    """Chuẩn hoá để so khớp mềm tiếng Việt, không dùng làm đánh giá luật thơ."""
    normalized = unicodedata.normalize("NFD", value.casefold())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").replace("đ", "d")


def _terms(value: str) -> set[str]:
    return {_fold(word) for word in _WORD_RE.findall(value) if len(_fold(word)) > 1}


TOPIC_GUIDES: tuple[tuple[set[str], tuple[str, ...], str, str], ...] = (
    (
        {"ong", "ba", "cha", "me", "gia", "dinh", "con", "chau"},
        ("mai vàng", "chén trà", "sum vầy", "lộc xuân", "mái nhà", "con cháu"),
        "ấm áp, kính trọng",
        "Mở cảnh xuân ở nhà; gửi lời bình an; gợi sự quây quần; khép bằng niềm vui đầu năm.",
    ),
    (
        {"ban", "dong", "nghiep", "ban be"},
        ("nắng xuân", "nụ cười", "lộc mới", "đường xa", "tin vui", "chén trà"),
        "tươi sáng, thân tình",
        "Mở bằng dấu hiệu xuân; chúc hành trình thuận lợi; điểm một hình ảnh gần gũi; khép bằng tin vui.",
    ),
    (
        {"suc", "khoe", "binh", "an", "phuc", "loc", "thanh", "cong"},
        ("nắng xuân", "mai vàng", "lộc biếc", "an khang", "niềm vui", "đường mới"),
        "trang trọng, trong trẻo",
        "Mở bằng mùa xuân; triển khai điều chúc chính; thêm hình ảnh gợi Tết; khép lại bằng hy vọng năm mới.",
    ),
)
DEFAULT_GUIDE = (
    ("mai vàng", "nắng xuân", "chén trà", "lộc biếc", "sum vầy", "niềm vui"),
    "ấm áp, tươi sáng",
    "Mở bằng cảnh xuân; neo vào ý chúc; phát triển bằng một hình ảnh cụ thể; khép bằng dư âm vui lành.",
)


@dataclass(frozen=True)
class CreativeBrief:
    wish_intent: str
    suggested_keywords: list[str]
    imagery: list[str]
    tone: str
    four_line_direction: str
    source_refs: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Tet4Agent:
    """MVP điều phối A1: brainstorm và khoá input trước khi gọi model."""

    def __init__(self, corpus_path: Path | str = DEFAULT_CORPUS) -> None:
        self.corpus_path = Path(corpus_path)
        self.materials = self._load_corpus(self.corpus_path)

    @staticmethod
    def _load_corpus(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            raise FileNotFoundError(f"Không thấy source-material corpus: {path}")
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    @staticmethod
    def _guide(wish_intent: str) -> tuple[tuple[str, ...], str, str]:
        wanted = _terms(wish_intent)
        best = max(TOPIC_GUIDES, key=lambda item: len(item[0] & wanted))
        return best[1:] if best[0] & wanted else DEFAULT_GUIDE

    def _retrieve(self, wish_intent: str, limit: int = 3) -> list[dict[str, str]]:
        wanted = _terms(wish_intent)
        scored: list[tuple[int, str, dict[str, Any]]] = []
        for row in self.materials:
            text = str(row.get("text", ""))
            searchable = " ".join((text, str(row.get("author") or ""), str(row.get("url") or "")))
            overlap = len(wanted & _terms(searchable))
            # Ưu tiên tư liệu có nhãn rõ ràng khi cùng điểm; không coi điểm là chất lượng thơ.
            label_bonus = 1 if row.get("author") else 0
            scored.append((overlap + label_bonus, str(row.get("material_id", "")), row))
        scored.sort(key=lambda item: (-item[0], item[1]))
        refs = []
        for score, _, row in scored[:limit]:
            snippet = " ".join(str(row.get("text", "")).split())[:180]
            refs.append({
                "material_id": str(row.get("material_id", "")),
                "url": str(row.get("url") or ""),
                "unit_type": str(row.get("unit_type") or ""),
                "snippet": snippet,
                "match_score": str(score),
            })
        return refs

    def brainstorm(self, wish_intent: str) -> CreativeBrief:
        intent = " ".join(wish_intent.split())
        if not intent:
            raise ValueError("wish_intent không được để trống")
        suggested, tone, direction = self._guide(intent)
        return CreativeBrief(
            wish_intent=intent,
            suggested_keywords=list(suggested),
            imagery=list(suggested[:4]),
            tone=tone,
            four_line_direction=direction,
            source_refs=self._retrieve(intent),
        )

    @staticmethod
    def select_keywords(wish_intent: str, keywords: Iterable[str]) -> dict[str, Any]:
        """Khoá đúng schema Tet4 trước bước plan; lỗi 2--3 keyword được báo sớm."""
        return normalize_metadata({"wish_intent": wish_intent, "keywords": list(keywords)})

    @staticmethod
    def build_plan_messages(brief: CreativeBrief, selected_metadata: dict[str, Any]) -> list[dict[str, str]]:
        """Prompt JSON ngắn, không yêu cầu suy luận ẩn hay chép thơ nguồn."""
        keywords = ", ".join(selected_metadata["từ khoá"])
        refs = "\n".join(f"- {ref['snippet']}" for ref in brief.source_refs)
        system = (
            "Bạn là biên tập viên thơ Tết Lục Bát. Hãy lập dàn ý ngắn bằng JSON hợp lệ; "
            "không dùng <think>, không giải thích, không chép lại tư liệu. "
            "Dàn ý chỉ định ý/hình ảnh cho từng dòng và một khung neo vần, chưa viết thơ. "
            "Mỗi idea và image tối đa 12 từ; imagery phải là mảng tối đa 4 mục."
        )
        user = (
            f"Ý chúc: {selected_metadata['ý chúc']}\n"
            f"Từ khoá người dùng đã chọn: {keywords}\n"
            f"Giọng: {brief.tone}\n"
            f"Hướng 4 dòng: {brief.four_line_direction}\n"
            f"Tư liệu tham khảo (chỉ lấy cảm hứng, không sao chép):\n{refs}\n"
            "Trả JSON với khóa: recipient, wish_intent, keywords, imagery, tone, line_plan, rhyme_scaffold. "
            "line_plan là mảng đúng 4 object gồm line, role, idea, image. rhyme_scaffold là object đúng năm khóa "
            "line_1_end, line_2_sixth, line_2_end, line_3_end, line_4_sixth; mỗi giá trị đúng một âm tiết Bằng. "
            "Chúng phải gieo vần theo cặp 1_end~2_sixth, 2_end~3_end, 3_end~4_sixth; tiếng 6/8 dòng 2 là hai thanh Bằng đối nhau. "
            "Ví dụ hợp lệ, được phép dùng nguyên xi: {\"line_1_end\":\"xuân\",\"line_2_sixth\":\"xuân\",\"line_2_end\":\"nhà\",\"line_3_end\":\"qua\",\"line_4_sixth\":\"ca\"}."
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]
