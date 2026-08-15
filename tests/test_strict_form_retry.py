import torch

from engine.lucbat_engine import LucBatLogitsProcessor
from scripts.run_tet4_agent import strict_repair_feedback
from engine.lucbat_state import Constraint


def test_strict_form_flags_default_to_soft_and_can_be_enabled():
    # Không cần assets/GPU: xác nhận API không đổi baseline mặc định.
    processor = LucBatLogitsProcessor(assets=None)
    assert processor.strict_tone is False
    assert processor.strict_rhyme is False
    processor.strict_tone = True
    processor.strict_rhyme = True
    assert processor.strict_tone and processor.strict_rhyme


class _SubtreeAssets:
    # Root có hai token đầu: token 1 dẫn đến subtree vần/than đúng, token 2 sai.
    children = [{1: 2, 2: 3}, {}, {}, {}]
    tone_bits = [0, 0, 1 << 0, 1 << 2]
    group_ids = [[], [], [7], [9]]

    @staticmethod
    def rhyme_str_to_group_ids(rhyme):
        return [7] if rhyme == "đúng" else []


def test_strict_mask_uses_subtree_group_and_tone_not_ambiguous_token_history():
    processor = LucBatLogitsProcessor(
        assets=_SubtreeAssets(), strict_tone=True, strict_rhyme=True
    )
    allowed = processor._strict_children_mask(
        0, Constraint(required_tone="NGANG", required_rhyme="đúng"), 4, "cpu"
    )
    assert allowed.tolist() == [False, True, False, False]


def test_strict_repair_feedback_keeps_deterministic_lexical_issue_when_critic_accepts():
    item = {
        "poem": "bàn thài ông ơ",
        "acceptance": {"coverage": {"pass": True}, "form_pass": False},
        "lexical": {"issues": [{"type": "orphan_vowel", "token": "ơ"}]},
        "naturalness_critic": {"result": {"decision": "accept", "issues": [], "repair_instruction": ""}},
    }
    feedback = strict_repair_feedback(item, {"ý chúc": "chúc ông bà", "từ khoá": ["sum vầy", "lộc xuân"]})
    assert "không dùng âm tiết đứng riêng: ơ" in feedback
