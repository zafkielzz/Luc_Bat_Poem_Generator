"""
Assets tiền xử lý cho LucBatLogitsProcessor.

Precompute dựa trên tokenizer Qwen3 thật (CPU, một lần):
  - SyllableTrie: trie subword cho mọi âm tiết, 2 gốc:
      ROOT_START (đầu dòng — token KHÔNG space-prefix),
      ROOT_MID   (giữa dòng — token space-prefix, thêm token 220 "space trần"
                  cho các âm tiết bắt đầu nguyên âm mà tokenizer không có
                  dạng space-prefix, vd " ơi" -> [220, 124841]).
  - Dense masks: tone_masks[3, vocab] (NGANG/HUYEN/TRAC), group_masks[G, vocab],
    root_masks[2, vocab], is_space_start[vocab].

Đã kiểm chứng tokenizer Qwen3-8B (vocab 151,643; eos=151,645; newline=198):
  - "trời"   (đầu dòng) -> ['tr','ời']
  - " trời"  (giữa dòng) -> [130868] (1 token space-prefix)
  - Mask phải size = max(vocab_size, eos_id+1) = 151,646 (special ids nằm
    ngoài vocab_size nhưng vẫn là token hợp lệ của lm_head).
"""
import json
import os
from typing import Dict, List, Optional, Set

import torch

from phonetics import (
    ToneType,
    extract_rhyme,
    get_tone,
    is_valid_vietnamese_syllable,
    rhymes_match_extracted,
)

# Thứ tự 3 lớp thanh trong tone_masks (bit index).
TONE_NGANG = 0
TONE_HUYEN = 1
TONE_TRAC = 2  # SAC | HOI | NGA | NANG

_TRAC_TONES = {ToneType.SAC, ToneType.HOI, ToneType.NGA, ToneType.NANG}


def tone_bit(syllable: str) -> Optional[int]:
    """Trả về bit thanh (0=NGANG, 1=HUYEN, 2=TRAC) hoặc None nếu không xác định."""
    t = get_tone(syllable)
    if t == ToneType.NGANG:
        return TONE_NGANG
    if t == ToneType.HUYEN:
        return TONE_HUYEN
    if t in _TRAC_TONES:
        return TONE_TRAC
    return None


class SyllableTrie:
    """Trie lưu chuỗi token-id của từng âm tiết.

    - add(): gắn tone bit + group id cho MỌI node dọc đường đi ("subtree"),
      vì mask penalty áp lên token đầu âm tiết và một token-prefix có thể dẫn
      đến nhiều âm tiết khác tone/vần (ambiguous -> bit set -> không phạt).
    """

    ROOT_START = 0  # đầu dòng: token không space-prefix
    ROOT_MID = 1    # giữa dòng: token space-prefix (hoặc 220)

    def __init__(self):
        self.children: List[Dict[int, int]] = [{}, {}]
        self.is_complete: List[bool] = [False, False]
        self.tone_bits: List[int] = [0, 0]
        self.group_ids: List[Set[int]] = [set(), set()]
        # token-level accumulation (key: token id)
        self.token_tone_bits: Dict[int, int] = {}
        self.token_group_ids: Dict[int, Set[int]] = {}

    def add(self, token_ids, root: int, tbit: Optional[int], gid: Optional[int]):
        node = root
        bit = (1 << tbit) if tbit is not None else 0
        for tid in token_ids:
            nxt = self.children[node].get(tid)
            if nxt is None:
                nxt = len(self.children)
                self.children.append({})
                self.is_complete.append(False)
                self.tone_bits.append(0)
                self.group_ids.append(set())
                self.children[node][tid] = nxt
            node = nxt
            self.tone_bits[node] |= bit
            if gid is not None:
                self.group_ids[node].add(gid)
            # accumulate theo token id (1 token có thể xuất hiện ở nhiều node)
            self.token_tone_bits[tid] = self.token_tone_bits.get(tid, 0) | bit
            if gid is not None:
                self.token_group_ids.setdefault(tid, set()).add(gid)
        self.is_complete[node] = True

    def node_children_mask(self, node: int, vocab_size: int) -> torch.Tensor:
        m = torch.zeros(vocab_size, dtype=torch.bool)
        if self.children[node]:
            m[list(self.children[node].keys())] = True
        return m

    def root_mask(self, root: int, vocab_size: int) -> torch.Tensor:
        return self.node_children_mask(root, vocab_size)


class LucBatVocabAssets:
    """Container runtime: trie + dense masks + metadata. Build rồi save/load."""

    def __init__(
        self,
        vocab_size: int,
        newline_id: int,
        eos_id: int,
        group_rhymes: List[str],
        num_nodes: int,
        children: List[Dict[int, int]],
        is_complete: List[bool],
        tone_bits: List[int],
        group_ids: List[List[int]],
        tone_masks: torch.Tensor,      # [3, vocab] bool
        group_masks: torch.Tensor,     # [G, vocab] bool
        root_masks: torch.Tensor,      # [2, vocab] bool
        is_space_start: torch.Tensor,  # [vocab] bool
        syllables: Optional[List[str]] = None,
        token_texts: Optional[Dict[int, str]] = None,
    ):
        self.vocab_size = vocab_size
        self.newline_id = newline_id
        self.eos_id = eos_id
        self.group_rhymes = group_rhymes
        self.num_nodes = num_nodes
        self.children = children
        self.is_complete = is_complete
        self.tone_bits = tone_bits
        self.group_ids = group_ids
        self.tone_masks = tone_masks
        self.group_masks = group_masks
        self.root_masks = root_masks
        self.is_space_start = is_space_start
        self.syllables = syllables or []
        self.token_texts = token_texts or {}
        self.num_groups = len(group_rhymes)

    def token_text(self, token: int) -> str:
        """Text token id (dùng để tích lũy cur_syl). Ngoài trie -> rỗng."""
        return self.token_texts.get(token, "")

    # ------------------------------------------------------------------ build
    @classmethod
    def build(cls, tokenizer, syllables: List[str],
              rhyme_groups: Dict[str, List[str]]) -> "LucBatVocabAssets":
        eos_id = tokenizer.eos_token_id if tokenizer.eos_token_id is not None else -1
        vocab_size = max(tokenizer.vocab_size, eos_id + 1)

        # --- Phân loại toàn bộ token bằng decode([i]) (key get_vocab() không
        # có space literal). eos/other specials để trống (sẽ bị chặn bởi hard mask).
        is_space_start = torch.zeros(vocab_size, dtype=torch.bool)
        newline_id = None
        for i in range(vocab_size):
            d = tokenizer.decode([i])
            if d == "\n":
                newline_id = i
            elif d.startswith(" ") and d != " ":
                is_space_start[i] = True
        if newline_id is None:
            raise RuntimeError("Không tìm thấy newline token (decode=='\\n')")

        # --- Gán group id cho các vần đã có trong từ điển
        group_rhymes = sorted(rhyme_groups.keys())
        gid_of_rhyme = {r: i for i, r in enumerate(group_rhymes)}

        def gid_of(syllable: str) -> Optional[int]:
            r = extract_rhyme(syllable)
            return gid_of_rhyme.get(r)

        trie = SyllableTrie()
        skipped = 0
        for s in syllables:
            s = s.strip()
            if not s or not is_valid_vietnamese_syllable(s):
                skipped += 1
                continue
            tbit = tone_bit(s)
            gid = gid_of(s)
            line_ids = tokenizer.encode(s, add_special_tokens=False)
            if line_ids:
                trie.add(line_ids, SyllableTrie.ROOT_START, tbit, gid)
            mid_ids = tokenizer.encode(" " + s, add_special_tokens=False)
            if mid_ids:
                trie.add(mid_ids, SyllableTrie.ROOT_MID, tbit, gid)

        num_nodes = len(trie.children)

        # --- Dense masks từ accumulation theo token id
        tone_masks = torch.zeros(3, vocab_size, dtype=torch.bool)
        for tid, bits in trie.token_tone_bits.items():
            if 0 <= tid < vocab_size:
                for b in range(3):
                    if bits & (1 << b):
                        tone_masks[b, tid] = True

        num_groups = len(group_rhymes)
        group_masks = torch.zeros(num_groups, vocab_size, dtype=torch.bool)
        for tid, gids in trie.token_group_ids.items():
            if 0 <= tid < vocab_size:
                for g in gids:
                    if g < num_groups:
                        group_masks[g, tid] = True

        root_masks = torch.zeros(2, vocab_size, dtype=torch.bool)
        root_masks[0] = trie.root_mask(SyllableTrie.ROOT_START, vocab_size)
        root_masks[1] = trie.root_mask(SyllableTrie.ROOT_MID, vocab_size)

        # Text của mọi token trong trie — engine cần để tích lũy cur_syl
        trie_tokens = set()
        for ch in trie.children:
            trie_tokens.update(ch.keys())
        token_texts = {t: tokenizer.decode([t]) for t in trie_tokens}

        return cls(
            vocab_size=vocab_size,
            newline_id=newline_id,
            eos_id=eos_id,
            group_rhymes=group_rhymes,
            num_nodes=num_nodes,
            children=trie.children,
            is_complete=trie.is_complete,
            tone_bits=trie.tone_bits,
            group_ids=[sorted(g) for g in trie.group_ids],
            tone_masks=tone_masks,
            group_masks=group_masks,
            root_masks=root_masks,
            is_space_start=is_space_start,
            syllables=sorted(syllables),
            token_texts=token_texts,
        )

    # ------------------------------------------------------------------ masks
    def root_children(self, line_start: bool) -> torch.Tensor:
        """Mask các token được phép BẮT ĐẦU một âm tiết (dòng mới / giữa dòng)."""
        return self.root_masks[0 if line_start else 1]

    def node_children_mask(self, node: int) -> torch.Tensor:
        m = torch.zeros(self.vocab_size, dtype=torch.bool)
        if self.children[node]:
            m[list(self.children[node].keys())] = True
        return m

    def tone_mask(self, required: str) -> torch.Tensor:
        """bool[vocab]: token có thể là một phần của âm tiết mang thanh required.
        'B' -> NGANG|HUYEN; 'T' -> TRAC; 'NGANG'/'HUYEN' -> đúng lớp. Không biết -> ones (không phạt)."""
        if required in ("B", "BANG"):
            return self.tone_masks[0] | self.tone_masks[1]
        if required == "T":
            return self.tone_masks[2]
        if required == "NGANG":
            return self.tone_masks[0]
        if required == "HUYEN":
            return self.tone_masks[1]
        return torch.ones(self.vocab_size, dtype=torch.bool)

    def rhyme_str_to_group_ids(self, rhyme: str) -> List[int]:
        """Các group id có vần gieo được với `rhyme` (vần chính + vần thông,
        KHÔNG gọi lại extract_rhyme — dùng rhymes_match_extracted)."""
        return [i for i, g in enumerate(self.group_rhymes) if rhymes_match_extracted(rhyme, g)]

    def rhyme_mask(self, rhyme: str) -> torch.Tensor:
        """bool[vocab]: token có thể kết thúc/đi cùng một âm tiết vần `rhyme`.
        Không có group nào khớp -> ones (không phạt, tránh phạt sạch vocab)."""
        ids = self.rhyme_str_to_group_ids(rhyme)
        if not ids:
            return torch.ones(self.vocab_size, dtype=torch.bool)
        m = self.group_masks[ids[0]].clone()
        for i in ids[1:]:
            m |= self.group_masks[i]
        return m

    # ------------------------------------------------------------------ io
    def save(self, save_dir: str):
        os.makedirs(save_dir, exist_ok=True)
        meta = {
            "vocab_size": self.vocab_size,
            "newline_id": self.newline_id,
            "eos_id": self.eos_id,
            "num_groups": self.num_groups,
            "num_nodes": self.num_nodes,
            "num_syllables": len(self.syllables),
            "group_rhymes": self.group_rhymes,
            "syllables": self.syllables,
        }
        with open(os.path.join(save_dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        torch.save({
            "children": self.children,
            "is_complete": self.is_complete,
            "tone_bits": self.tone_bits,
            "group_ids": self.group_ids,
            "tone_masks": self.tone_masks,
            "group_masks": self.group_masks,
            "root_masks": self.root_masks,
            "is_space_start": self.is_space_start,
            "token_texts": self.token_texts,
        }, os.path.join(save_dir, "lucbat_assets.pt"))

    @classmethod
    def load(cls, load_dir: str) -> "LucBatVocabAssets":
        with open(os.path.join(load_dir, "meta.json"), "r", encoding="utf-8") as f:
            meta = json.load(f)
        data = torch.load(os.path.join(load_dir, "lucbat_assets.pt"),
                          map_location="cpu", weights_only=False)
        return cls(
            vocab_size=meta["vocab_size"],
            newline_id=meta["newline_id"],
            eos_id=meta["eos_id"],
            group_rhymes=meta["group_rhymes"],
            num_nodes=meta["num_nodes"],
            children=data["children"],
            is_complete=data["is_complete"],
            tone_bits=data["tone_bits"],
            group_ids=data["group_ids"],
            tone_masks=data["tone_masks"],
            group_masks=data["group_masks"],
            root_masks=data["root_masks"],
            is_space_start=data["is_space_start"],
            syllables=meta.get("syllables", []),
            token_texts=data.get("token_texts", {}),
        )
