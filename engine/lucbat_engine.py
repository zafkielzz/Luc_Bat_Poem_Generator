"""
LucBatLogitsProcessor — can thiệp logits theo luật Lục Bát (LogitsProcessor).

Hard constraints (cấm tuyệt đối):
  - Số âm tiết mỗi dòng đúng 6 (Lục) / 8 (Bát); xuống dòng BẮT BUỘC sau tiếng 6/8.
  - Không cắt giữa âm tiết: token phải đi theo đường trong SyllableTrie (subword).
  - Token ngoài lexicon bị chặn; EOS chỉ khi đủ số cặp câu (stop_after_couplets).

Soft penalties (-λ, chống "thơ phèn"):
  - tone_penalty  : lệch Bằng/Trắc/Trầm-Bổng ở vị trí 2, 4, 6, 8.
  - rhyme_penalty : lệch vần lưng (lục6-bát6) và vần chân (bát8-lục6 kế).
  Chỉ áp cho TOKEN BẮT ĐẦU âm tiết (root_start ∪ root_mid) — âm tiết multi-token
  có prefix ambiguous sẽ không bị phạt oan (bit set ở subtree).

Trạng thái mỗi row:
  - line_start : đang ở đầu dòng (ROOT_START) hay giữa dòng (terminal node).
  - trie_node  : node hiện tại trong trie.
  - cur_syl    : chuỗi token đã tích lũy của âm tiết đang xây (chưa step()).
  - lucbat     : LucBatState (word_pos, line_type, rhyme anchors, Trầm/Bổng).
  - couplets   : số cặp Lục-Bát đã hoàn thành (mỗi Bát kết thúc +1).

Bước âm tiết (boundary-triggered): step(cur_syl) chỉ được gọi khi gặp newline
hoặc token space-prefix bắt đầu âm tiết mới — tránh cut nhầm âm tiết khi một
node vừa terminal vừa là prefix của âm tiết dài hơn (vd "a" vs "ai").
"""
import copy
from typing import List, Optional

import torch
from transformers import LogitsProcessor

from engine.lucbat_state import LineType, LucBatState
from engine.vocab_assets import LucBatVocabAssets, SyllableTrie


class RowState:
    __slots__ = ("line_start", "trie_node", "cur_syl", "lucbat",
                 "couplets", "last_line_was_bat", "finished")

    def __init__(self):
        self.line_start = True
        self.trie_node = SyllableTrie.ROOT_START
        self.cur_syl = ""
        self.lucbat = LucBatState()
        self.couplets = 0
        self.last_line_was_bat = False
        self.finished = False


class LucBatLogitsProcessor(LogitsProcessor):
    def __init__(self, assets: LucBatVocabAssets, tone_penalty: float = 1.5,
                 rhyme_penalty: float = 3.0, stop_after_couplets: Optional[int] = None,
                 device: str = "cpu", strict_tone: bool = False,
                 strict_rhyme: bool = False):
        self.assets = assets
        self.tone_penalty = tone_penalty
        self.rhyme_penalty = rhyme_penalty
        self.stop_after_couplets = stop_after_couplets
        self.device = device
        # Mặc định soft để tái lập baseline. Agent chỉ bật cả hai ở retry cuối.
        self.strict_tone = strict_tone
        self.strict_rhyme = strict_rhyme
        self._rows: Optional[List[RowState]] = None
        self._V: Optional[int] = None
        self._root_start = None
        self._root_mid = None
        self._tone_cache = {}
        self._rhyme_cache = {}
        # Strict tone/vần có thể không có nhánh trie nào thỏa đồng thời ở một
        # bước hiếm. Khi đó hạ *riêng bước đó* về hard baseline để sampler
        # không nhận phân phối rỗng; trace bên ngoài phải coi đây là vi phạm.
        self.strict_relaxations = 0

    # ------------------------------------------------------------------ public
    def reset(self):
        """Bắt đầu một lượt generate mới (rows cũ được xóa)."""
        self._rows = None
        self._V = None
        self._root_start = None
        self._root_mid = None
        self._tone_cache = {}
        self._rhyme_cache = {}
        self.strict_relaxations = 0

    def __call__(self, input_ids, scores):
        if self._rows is None:
            self._rows = [RowState() for _ in range(input_ids.shape[0])]
        else:
            # Advance mỗi row theo token mới nhất (token vừa được sample ở bước trước)
            for i, row in enumerate(self._rows):
                if row.finished:
                    continue
                if input_ids.shape[1] > 0:
                    self._advance(row, int(input_ids[i, -1].item()))

        V = scores.size(-1)
        self._V = V
        dev = scores.device
        if self._root_start is None:
            self._root_start = self._pad(self.assets.root_children(True), V, dev, fill=False)
            self._root_mid = self._pad(self.assets.root_children(False), V, dev, fill=False)

        for i, row in enumerate(self._rows):
            scores[i] = self._apply(row, scores[i], V, dev)
        return scores

    # ------------------------------------------------------------------ advance
    def _advance(self, row: RowState, token: int):
        assets = self.assets
        if token == assets.eos_id:
            row.finished = True
            return
        if token == assets.newline_id:
            if row.cur_syl:
                was_bat = (row.lucbat.line_type == LineType.BAT and row.lucbat.word_pos == 8)
                row.lucbat.step(row.cur_syl)
                row.cur_syl = ""
                row.couplets += 1 if was_bat else 0
                row.last_line_was_bat = was_bat
            row.line_start = True
            row.trie_node = SyllableTrie.ROOT_START
            return

        ch = assets.children[row.trie_node]
        if row.trie_node in (SyllableTrie.ROOT_START, SyllableTrie.ROOT_MID):
            # Bắt đầu âm tiết mới (token space-prefix có thể là 220 + content)
            row.cur_syl = assets.token_text(token).lstrip()
            row.trie_node = ch.get(token, row.trie_node)
            return

        nxt = ch.get(token)
        if nxt is not None:
            row.cur_syl += assets.token_text(token)
            row.trie_node = nxt
            return

        if assets.is_complete[row.trie_node]:
            # Hoàn tất âm tiết hiện tại + bắt đầu âm tiết mới (space-prefix)
            if row.cur_syl:
                was_bat = (row.lucbat.line_type == LineType.BAT and row.lucbat.word_pos == 8)
                row.lucbat.step(row.cur_syl)
                row.cur_syl = ""
                row.couplets += 1 if was_bat else 0
                row.last_line_was_bat = was_bat
            row.cur_syl = assets.token_text(token).lstrip()
            row.trie_node = assets.children[SyllableTrie.ROOT_MID].get(token, SyllableTrie.ROOT_MID)
            return
        # Token bị mask chặn — không nên tới đây (bỏ qua)

    # ------------------------------------------------------------------ apply
    def _must_newline(self, row: RowState) -> bool:
        """Bắt buộc xuống dòng: âm tiết đang ở tiếng 6 (Lục) / 8 (Bát) và đã hoàn chỉnh."""
        if not self.assets.is_complete[row.trie_node]:
            return False
        st = row.lucbat
        if st.line_type == LineType.LUC:
            return st.word_pos == 6
        if st.line_type == LineType.BAT:
            return st.word_pos == 8
        return False

    def _apply(self, row: RowState, logits, V: int, dev):
        assets = self.assets
        neg = torch.finfo(logits.dtype).min

        if row.finished:
            return self._only(logits, assets.eos_id, V, dev)

        if self._must_newline(row):
            return self._only(logits, assets.newline_id, V, dev)

        stop = self.stop_after_couplets
        if stop is not None and row.couplets >= stop:
            return self._only(logits, assets.eos_id, V, dev)

        at_root = row.trie_node in (SyllableTrie.ROOT_START, SyllableTrie.ROOT_MID)
        strict_hard = None
        if at_root:
            base = self._root_start if row.line_start else self._root_mid
            first = base
            constraint = row.lucbat.get_constraint()
            if self.strict_tone or self.strict_rhyme:
                strict_hard = self._strict_children_mask(
                    row.trie_node, constraint, V, dev
                )
        else:
            base = self._pad(self.assets.node_children_mask(row.trie_node), V, dev, fill=False)
            if assets.is_complete[row.trie_node]:
                base = base | self._root_mid
                first = self._root_mid
                current_constraint = row.lucbat.get_constraint()
                # Constraint cho âm tiết KẾ TIẾP (giả lập step âm tiết vừa xong)
                nxt = copy.copy(row.lucbat)
                if row.cur_syl:
                    nxt.step(row.cur_syl)
                constraint = nxt.get_constraint()
                if self.strict_tone or self.strict_rhyme:
                    # Nhánh tiếp tục âm tiết cũ phải giữ constraint cũ; nhánh
                    # space-prefix bắt đầu âm tiết mới dùng constraint sau step().
                    strict_hard = (
                        self._strict_children_mask(row.trie_node, current_constraint, V, dev)
                        | self._strict_children_mask(SyllableTrie.ROOT_MID, constraint, V, dev)
                    )
            else:
                first = None
                constraint = None
                if self.strict_tone or self.strict_rhyme:
                    strict_hard = self._strict_children_mask(
                        row.trie_node, row.lucbat.get_constraint(), V, dev
                    )

        hard = base
        if strict_hard is not None:
            constrained = base & strict_hard
            if bool(constrained.any().item()):
                hard = constrained
            else:
                # Không được mask toàn bộ vocabulary: `torch.multinomial` sẽ
                # nhận NaN/Inf và CUDA dừng. Giữ luật cấu trúc/trie của
                # baseline, đồng thời ghi nhận để candidate không thể được xem
                # là strict-form thành công một cách im lặng.
                self.strict_relaxations += 1
        if first is not None and constraint is not None:
            if constraint.required_tone:
                tm = self._tone_mask(constraint.required_tone, V, dev)
                if not self.strict_tone:
                    logits = logits - self.tone_penalty * (first & ~tm).to(logits.dtype)
            if constraint.required_rhyme:
                rm = self._rhyme_mask(constraint.required_rhyme, V, dev)
                if not self.strict_rhyme:
                    logits = logits - self.rhyme_penalty * (first & ~rm).to(logits.dtype)

        if stop is None and row.last_line_was_bat and row.trie_node == SyllableTrie.ROOT_START:
            # Cho phép kết thúc tự nguyện sau 1 cặp câu hoàn chỉnh (không set stop)
            eos_hot = torch.zeros(V, dtype=torch.bool, device=dev)
            if assets.eos_id < V:
                eos_hot[assets.eos_id] = True
            hard = hard | eos_hot

        return logits.masked_fill(~hard, neg)

    # ------------------------------------------------------------------ helpers
    def _only(self, logits, tok_id: int, V: int, dev) -> torch.Tensor:
        """Toàn -inf trừ token `tok_id` (0.0)."""
        neg = torch.finfo(logits.dtype).min
        m = torch.full((V,), neg, dtype=logits.dtype, device=dev)
        if tok_id < V:
            m[tok_id] = 0.0
        return m

    def _pad(self, mask: torch.Tensor, V: int, dev, fill: bool = False) -> torch.Tensor:
        if mask.shape[0] == V:
            return mask.to(dev)
        out = torch.full((V,), fill, dtype=torch.bool, device=dev)
        n = min(mask.shape[0], V)
        out[:n] = mask[:n].to(dev)
        return out

    def _tone_mask(self, required: str, V: int, dev) -> torch.Tensor:
        key = (required, V)
        if key not in self._tone_cache:
            self._tone_cache[key] = self._pad(self.assets.tone_mask(required), V, dev, fill=True)
        return self._tone_cache[key]

    def _rhyme_mask(self, rhyme: str, V: int, dev) -> torch.Tensor:
        key = (rhyme, V)
        if key not in self._rhyme_cache:
            self._rhyme_cache[key] = self._pad(self.assets.rhyme_mask(rhyme), V, dev, fill=True)
        return self._rhyme_cache[key]

    def _strict_children_mask(self, node: int, constraint, V: int, dev) -> torch.Tensor:
        """Giữ child token có *toàn bộ subtree* còn khả năng đạt tone/vần.

        Dense token mask không đủ cho strict decoding: một token subword có thể
        xuất hiện trong cả âm tiết hợp và không hợp vần. Trie node đã tích lũy
        tone_bits/group_ids của mọi hậu duệ, nên lọc ở đây an toàn với multi-token.
        """
        allowed = torch.zeros(V, dtype=torch.bool, device=dev)
        rhyme_groups = None
        if self.strict_rhyme and constraint.required_rhyme:
            group_ids = self.assets.rhyme_str_to_group_ids(constraint.required_rhyme)
            rhyme_groups = set(group_ids) if group_ids else None
        for token, child in self.assets.children[node].items():
            if token >= V:
                continue
            if self.strict_tone and constraint.required_tone:
                bits = self.assets.tone_bits[child]
                if constraint.required_tone in ("B", "BANG"):
                    tone_ok = bool(bits & ((1 << 0) | (1 << 1)))
                elif constraint.required_tone == "T":
                    tone_ok = bool(bits & (1 << 2))
                elif constraint.required_tone == "NGANG":
                    tone_ok = bool(bits & (1 << 0))
                elif constraint.required_tone == "HUYEN":
                    tone_ok = bool(bits & (1 << 1))
                else:
                    tone_ok = True
                if not tone_ok:
                    continue
            if rhyme_groups is not None and not (set(self.assets.group_ids[child]) & rhyme_groups):
                continue
            allowed[token] = True
        return allowed
