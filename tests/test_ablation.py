"""Test helper extract_poem của ablation_pipeline.py — chuẩn hoá output free-gen."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.ablation_pipeline import extract_poem
from scripts.generate_poem import render_chat_prompt


def test_strips_think_block_and_english_reasoning():
    raw = (
        "<think>\n"
        "Okay, let's tackle this request. The user wants a Lục Bát poem.\n"
        "First, I need to check the syllable structure.\n"
        "</think>\n"
        "Xuân sang rạng rỡ sắc màu\n"
        "Muôn hoa đua nở bên cầu gió reo\n"
    )
    poem = extract_poem(raw)
    assert poem.splitlines() == ["Xuân sang rạng rỡ sắc màu", "Muôn hoa đua nở bên cầu gió reo"]


def test_strips_think_tag_standing_alone():
    raw = (
        "<think>\n"
        "reasoning line\n"
        "</think>\n"
        "Xuân sang rạng rỡ sắc màu\n"
    )
    poem = extract_poem(raw)
    assert poem.splitlines() == ["Xuân sang rạng rỡ sắc màu"]


def test_drops_metadata_echo_lines():
    raw = (
        "BÀI THƠ LỤC BÁT\n"
        "Chủ đề: mùa xuân\n"
        "Số câu: 4 (mỗi câu Lục 6 âm tiết, Bát 8 âm tiết)\n"
        "Sáng tác trực tiếp bài thơ, không giải thích.\n"
        "Xuân sang rạng rỡ sắc màu\n"
        "Muôn hoa đua nở bên cầu gió reo\n"
    )
    poem = extract_poem(raw)
    lines = poem.splitlines()
    assert len(lines) == 2
    assert lines[0] == "Xuân sang rạng rỡ sắc màu"
    assert lines[1] == "Muôn hoa đua nở bên cầu gió reo"


def test_caps_at_8_lines():
    lines = [f"dòng thơ thứ {i} vần a" for i in range(1, 14)]
    raw = "\n".join(lines)
    poem = extract_poem(raw)
    assert len(poem.splitlines()) == 8


def test_drops_empty_lines_and_whitespace():
    raw = "  Xuân sang rạng rỡ sắc màu  \n\n\n   Muôn hoa đua nở bên cầu gió reo\n"
    poem = extract_poem(raw)
    assert poem.splitlines() == ["Xuân sang rạng rỡ sắc màu", "Muôn hoa đua nở bên cầu gió reo"]


class _ChatTemplateTokenizer:
    chat_template = "qwen3-template"

    def __init__(self):
        self.kwargs = None

    def apply_chat_template(self, messages, **kwargs):
        self.kwargs = kwargs
        return "rendered"


def test_render_chat_prompt_disables_thinking_explicitly():
    tokenizer = _ChatTemplateTokenizer()
    prompt = render_chat_prompt(tokenizer, [{"content": "s"}, {"content": "u"}])
    assert prompt == "rendered"
    assert tokenizer.kwargs["enable_thinking"] is False
    assert tokenizer.kwargs["add_generation_prompt"] is True


def test_render_chat_prompt_fallback_has_real_newlines():
    prompt = render_chat_prompt(object(), [{"content": "system"}, {"content": "user"}])
    assert chr(10) in prompt
    assert "system" in prompt and "user" in prompt


def test_empty_input():
    assert extract_poem("\n\n  \n") == ""
