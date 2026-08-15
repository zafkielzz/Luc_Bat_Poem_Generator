import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import torch

from engine.evaluator import LucBatEvaluator
from engine.lucbat_engine import LucBatLogitsProcessor
from engine.vocab_assets import LucBatVocabAssets, SyllableTrie

# ---------------------------------------------------------------- fake tokenizer
NEWLINE_ID = 0
EOS_ID = 1
UNKNOWN_ID = 2
SPACE_ONLY_ID = 3

# Từ điển tổng hợp: line = token đầu dòng (CONTENT), mid = space-prefix.
# "trời"/"người" là multi-token ở đầu dòng (giống Qwen3: "trời" -> ['tr','ời']).
LINE_IDS = {
    "trời": [101, 301], "người": [102, 302], "thu": [103], "vàng": [104],
    "xanh": [105], "mưa": [106], "hoa": [107], "đẹp": [108], "ta": [109],
    "sáng": [110], "đêm": [111], "trăng": [112], "tối": [113], "sông": [114],
    "dài": [115], "mây": [116], "gió": [117], "lòng": [118], "tràn": [119],
}
MID_IDS = {
    "trời": [201], "người": [202], "thu": [203], "vàng": [204], "xanh": [205],
    "mưa": [206], "hoa": [207], "đẹp": [208], "ta": [209], "sáng": [210],
    "đêm": [211], "trăng": [212], "tối": [213], "sông": [214], "dài": [215],
    "mây": [216], "gió": [217], "lòng": [218], "tràn": [219],
}

SYLLABLES = sorted(set(LINE_IDS.keys()))
RHYME_GROUPS = {
    "ơi": ["trời"], "ươi": ["người"], "u": ["thu"], "ang": ["vàng", "sáng"],
    "anh": ["xanh"], "ưa": ["mưa"], "a": ["hoa", "ta"], "ep": ["đẹp"],
    "em": ["đêm"], "ăng": ["trăng"], "oi": ["tối"], "ong": ["sông", "lòng"],
    "ai": ["dài"], "ây": ["mây"], "o": ["gió"], "an": ["tràn"],
}


class FakeTokenizer:
    """Tokenizer tổng hợp: decode([i]) + encode(s) giả lập Qwen3 space-prefix."""

    def __init__(self):
        self._tok = {}
        self._tok[NEWLINE_ID] = "\n"
        self._tok[EOS_ID] = "<eos>"
        self._tok[UNKNOWN_ID] = "zzz"
        self._tok[SPACE_ONLY_ID] = " "
        for s, ids in LINE_IDS.items():
            if len(ids) == 1:
                self._tok[ids[0]] = s
        # multi-token line: "trời" = "tr"+"ời", "người" = "ng"+"ười"
        self._tok[101] = "tr"
        self._tok[301] = "ời"
        self._tok[102] = "ng"
        self._tok[302] = "ười"
        for s, ids in MID_IDS.items():
            self._tok[ids[0]] = " " + s
        self.vocab_size = max(self._tok) + 1
        self.eos_token_id = EOS_ID

    def decode(self, ids):
        return "".join(self._tok.get(i, "") for i in ids)

    def encode(self, text, add_special_tokens=False):
        if text.startswith(" "):
            return MID_IDS.get(text[1:], [])
        return LINE_IDS.get(text, [])


@pytest.fixture(scope="module")
def assets():
    return LucBatVocabAssets.build(FakeTokenizer(), SYLLABLES, RHYME_GROUPS)


# ---------------------------------------------------------------- helpers
def make_proc(assets, **kw):
    return LucBatLogitsProcessor(assets, **kw)


def run(proc, choices, seed=(NEWLINE_ID,)):
    """Cho từng token trong choices đi qua processor; trả về (ids, masks)
    với masks[i] = logits đã mask TRƯỚC khi chọn choices[i]."""
    ids = list(seed)
    masks = []
    V = proc.assets.vocab_size
    m = proc(torch.tensor([ids]), torch.zeros((1, V))).squeeze(0)
    for tok in choices:
        masks.append(m.clone())
        ids.append(tok)
        m = proc(torch.tensor([ids]), torch.zeros((1, V))).squeeze(0)
    masks.append(m.clone())
    return ids, masks


def blocked(mask, i):
    """Token i có bị chặn (hard mask) không."""
    return mask[i].item() < -1e20


# ---------------------------------------------------------------- tests
def test_build_classification(assets):
    assert assets.newline_id == NEWLINE_ID
    assert assets.eos_id == EOS_ID
    assert assets.vocab_size == FakeTokenizer().vocab_size
    # root_start: token đầu dòng (CONTENT), không có space-prefix
    rs = assets.root_children(True)
    assert rs[101].item() is True          # "tr" (bắt đầu "trời")
    assert rs[112].item() is True          # "trăng" đầu dòng
    assert rs[201].item() is False         # " trời" không phải đầu dòng
    assert rs[UNKNOWN_ID].item() is False
    # root_mid: space-prefix tokens
    rm = assets.root_children(False)
    assert rm[201].item() is True          # " trời"
    assert rm[101].item() is False
    # multi-token: ROOT_START -> 101 ("tr") -> 301 ("ời"); 101 không terminal
    node_tr = assets.children[SyllableTrie.ROOT_START][101]
    assert assets.is_complete[node_tr] is False
    node_troi = assets.children[node_tr][301]
    assert assets.is_complete[node_troi] is True


def test_first_step_blocks_invalid(assets):
    proc = make_proc(assets)
    _, masks = run(proc, [])
    m = masks[0]
    assert blocked(m, UNKNOWN_ID)          # token rác
    assert blocked(m, SPACE_ONLY_ID)       # space trần
    assert blocked(m, NEWLINE_ID)          # chưa tới cuối dòng
    assert blocked(m, EOS_ID)              # chưa đủ couplet
    assert blocked(m, 201)                 # space-prefix ở đầu dòng
    assert m[101].item() > -1e20           # token đầu dòng hợp lệ


def test_multitoken_continuation_forced(assets):
    proc = make_proc(assets)
    _, masks = run(proc, [101])            # chọn "tr" (prefix của "trời")
    m = masks[1]
    assert m[301].item() > -1e20           # bắt buộc "ời" để hoàn thành âm tiết
    assert blocked(m, NEWLINE_ID)          # không được cắt giữa âm tiết
    assert blocked(m, 201)                 # không bắt đầu âm tiết mới giữa chừng
    assert blocked(m, 216)


def test_tone_penalty_at_pos2(assets):
    proc = make_proc(assets, tone_penalty=1.5)
    _, masks = run(proc, [101, 301])       # trời xong, sắp chọn âm tiết 2 (B)
    m = masks[2]
    assert m[203].item() == pytest.approx(0.0)          # " thu" (Ngang=B) không phạt
    assert m[210].item() == pytest.approx(-1.5)         # " sáng" (Sắc=T) phạt -λ
    assert blocked(m, NEWLINE_ID)


def test_newline_forced_after_luc6(assets):
    proc = make_proc(assets)
    choices = [101, 301, 203, 216, 217, 211, 201]       # lục: trời thu mây gió đêm trời
    _, masks = run(proc, choices)
    m = masks[7]
    assert m[NEWLINE_ID].item() > -1e20                 # duy nhất newline
    assert blocked(m, 203)
    assert blocked(m, 112)                              # không bắt đầu dòng mới giữa dòng
    assert blocked(m, EOS_ID)


def test_rhyme_penalty_at_bat6(assets):
    proc = make_proc(assets, tone_penalty=1.5, rhyme_penalty=3.0)
    # Lục xong + xuống dòng + bát: trăng mây sông sáng hoa (đang ở tiếng 5)
    choices = [101, 301, 203, 216, 217, 211, 201, NEWLINE_ID,
               112, 216, 214, 210, 207]
    _, masks = run(proc, choices)
    m = masks[13]                                        # trước tiếng 6 bát (vần lưng = "ơi")
    assert m[202].item() == pytest.approx(0.0)           # " người" (ươi~ơi) đúng vần
    assert m[203].item() == pytest.approx(-3.0)          # " thu" sai vần -> -3.0
    assert m[210].item() == pytest.approx(-4.5)          # " sáng" sai thanh + sai vần


def test_full_couplet_valid_and_couplet_count(assets):
    proc = make_proc(assets)
    choices = [101, 301, 203, 216, 217, 211, 201, NEWLINE_ID,
               112, 216, 214, 210, 207, 202, 205, 212, NEWLINE_ID]
    ids, _ = run(proc, choices)
    assert proc._rows[0].couplets == 1
    assert proc._rows[0].last_line_was_bat is True
    # Decode ra bài thơ và đánh giá lại bằng LucBatEvaluator
    tok = FakeTokenizer()
    poem = "".join(tok.decode([i]) for i in ids[1:])
    res = LucBatEvaluator().evaluate(poem)
    assert res["scr"] == 100.0
    assert res["tcr"] == 100.0
    assert res["rma"] == 100.0
    assert res["is_valid_lucbat"] is True


def test_stop_after_couplets_forces_eos(assets):
    proc = make_proc(assets, stop_after_couplets=1)
    choices = [101, 301, 203, 216, 217, 211, 201, NEWLINE_ID,
               112, 216, 214, 210, 207, 202, 205, 212, NEWLINE_ID]
    _, masks = run(proc, choices)
    m = masks[-1]                                        # sau khi đủ 1 couplet
    assert m[EOS_ID].item() > -1e20
    assert blocked(m, NEWLINE_ID)
    assert blocked(m, 112)


def test_eos_blocked_mid_poem(assets):
    proc = make_proc(assets, stop_after_couplets=1)
    # Mới xong Lục (chưa đủ couplet) -> EOS phải bị chặn
    choices = [101, 301, 203, 216, 217, 211, 201, NEWLINE_ID]
    _, masks = run(proc, choices)
    assert blocked(masks[-1], EOS_ID)


def test_voluntary_stop_after_full_couplet(assets):
    proc = make_proc(assets)                             # stop_after_couplets=None
    choices = [101, 301, 203, 216, 217, 211, 201, NEWLINE_ID,
               112, 216, 214, 210, 207, 202, 205, 212, NEWLINE_ID]
    _, masks = run(proc, choices)
    m = masks[-1]                                        # đứng đầu dòng, mới hết 1 couplet
    assert m[EOS_ID].item() > -1e20                      # eos được phép (tự nguyện dừng)
    assert m[112].item() > -1e20                         # vẫn có thể viết tiếp couplet 2


def test_reset_allows_fresh_generation(assets):
    proc = make_proc(assets)
    run(proc, [101, 301, 203, 216, 217, 211, 201, NEWLINE_ID,
               112, 216, 214, 210, 207, 202, 205, 212, NEWLINE_ID])
    assert proc._rows[0].couplets == 1
    proc.reset()
    _, masks = run(proc, [])
    assert proc._rows[0].couplets == 0
    assert not blocked(masks[0], 101)                    # state mới như ban đầu


if __name__ == "__main__":
    import inspect
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for t in tests:
        t(assets=LucBatVocabAssets.build(FakeTokenizer(), SYLLABLES, RHYME_GROUPS))
        print(f"✓ {t.__name__}: PASSED")
    print("🎉 Tất cả test trong test_engine.py đều PASSED 100%!")
