"""
Precompute LucBatVocabAssets từ tokenizer Qwen3 thật (CPU, một lần).

Chạy:
  python scripts/precompute_assets.py \
      --tokenizer /media/zafkiel/WORK_SPACE2/models/Qwen3-8B \
      --syllables data/assets/syllables.json \
      --dict data/processed/clean_rhyme_dictionary.json \
      --out data/assets

Xuất ra:
  - data/assets/meta.json          (newline_id, eos_id, vocab_size, num_groups, ...)
  - data/assets/lucbat_assets.pt   (trie + dense masks)
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import torch
from transformers import AutoTokenizer

from engine.vocab_assets import LucBatVocabAssets

MODEL_PATH = "/media/zafkiel/WORK_SPACE2/models/Qwen3-8B"


def main():
    ap = argparse.ArgumentParser(description="Precompute assets cho LucBatLogitsProcessor")
    ap.add_argument("--tokenizer", default=MODEL_PATH, help="Đường dẫn tokenizer Qwen3")
    ap.add_argument("--syllables", default="data/assets/syllables.json")
    ap.add_argument("--dict", default="data/processed/clean_rhyme_dictionary.json")
    ap.add_argument("--out", default="data/assets")
    args = ap.parse_args()

    start = time.time()
    print(f"🚀 Precompute assets...")
    print(f"   tokenizer: {args.tokenizer}")

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, trust_remote_code=True)
    with open(args.syllables, "r", encoding="utf-8") as f:
        syllables = json.load(f)
    with open(args.dict, "r", encoding="utf-8") as f:
        rhyme_groups = json.load(f)["rhyme_groups"]

    print(f"   âm tiết: {len(syllables):,} | nhóm vần: {len(rhyme_groups):,}")

    assets = LucBatVocabAssets.build(tokenizer, syllables, rhyme_groups)
    assets.save(args.out)

    size_mb = os.path.getsize(os.path.join(args.out, "lucbat_assets.pt")) / 1e6
    print(f"\n================ BÁO CÁO ASSETS ================")
    print(f"📐 vocab_size      : {assets.vocab_size:,}  (max(vocab, eos+1))")
    print(f"🔚 eos_id          : {assets.eos_id}  |  newline_id: {assets.newline_id}")
    print(f"🌳 num_nodes trie  : {assets.num_nodes:,}")
    print(f"🎵 num_groups      : {assets.num_groups}")
    print(f"📦 num_syllables   : {len(assets.syllables):,}")
    print(f"🎭 tone_masks      : {tuple(assets.tone_masks.shape)}")
    print(f"🧩 group_masks     : {tuple(assets.group_masks.shape)} "
          f"({assets.group_masks.shape[0] * assets.group_masks.shape[1] / 1e6:.0f} MB)")
    print(f"🔹 root_masks      : {tuple(assets.root_masks.shape)}")
    print(f"⚪ is_space_start  : {assets.is_space_start.sum().item():,} token")
    print(f"💾 lucbat_assets.pt: {size_mb:.1f} MB")
    print(f"⏱️  Thời gian: {time.time() - start:.1f}s")

    # --- Verify nhanh (tương ứng checklist #2 của plan)
    assert assets.newline_id == 198, "newline_id phải là 198"
    assert assets.eos_id == 151645, "eos_id phải là 151645"
    assert assets.vocab_size == 151646, "vocab_size phải là 151646"
    # Vần "ơi" từ "trời" phải gieo được với nhóm "ươi" (Truyện Kiều: trời/người)
    gids = assets.rhyme_str_to_group_ids("ơi")
    assert any(assets.group_rhymes[g] == "ươi" for g in gids), "thiếu nhóm ươi"
    print("\n✓ Verify pass: newline=198, eos=151645, vocab=151646, vần ơi~ươi khớp")
    print("✅ Precompute hoàn tất!")


if __name__ == "__main__":
    main()
