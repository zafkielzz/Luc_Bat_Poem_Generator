import json
import os
from typing import Dict, Any
from .tone_classifier import get_tone, is_bang, is_trac, is_duong_binh, is_am_binh
from .rhyme_checker import extract_rhyme

class VocabMapper:
    """
    Module pre-compute và lưu trữ thuộc tính âm vị học (Tone, Rhyme)
    cho từng Token ID trong từ điển của Tokenizer.
    """

    def __init__(self, tokenizer=None):
        self.tokenizer = tokenizer
        self.vocab_map: Dict[int, Dict[str, Any]] = {}

    def build_map(self) -> Dict[int, Dict[str, Any]]:
        """Duyệt qua tất cả tokens trong tokenizer và xây dựng bảng thuộc tính."""
        if self.tokenizer is None:
            raise ValueError("Tokenizer chưa được nạp!")

        vocab = self.tokenizer.get_vocab()
        print(f"Đang xây dựng bảng tra cho {len(vocab)} tokens...")

        for token_str, token_id in vocab.items():
            # Xử lý làm sạch token (loại bỏ ký tự đặc biệt của tokenizer như ' ', '##')
            cleaned_token = token_str.replace(" ", "").replace("##", "").strip()

            tone = get_tone(cleaned_token)
            rhyme = extract_rhyme(cleaned_token)

            self.vocab_map[token_id] = {
                "token": token_str,
                "clean_token": cleaned_token,
                "tone": tone.value,
                "is_bang": is_bang(cleaned_token),
                "is_trac": is_trac(cleaned_token),
                "is_duong_binh": is_duong_binh(cleaned_token),
                "is_am_binh": is_am_binh(cleaned_token),
                "rhyme": rhyme
            }

        return self.vocab_map

    def save_to_file(self, file_path: str):
        """Lưu bảng tra ra file JSON."""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.vocab_map, f, ensure_ascii=False, indent=2)
        print(f"✓ Đã lưu bảng tra VocabMapper vào: {file_path}")

    @classmethod
    def load_from_file(cls, file_path: str) -> "VocabMapper":
        """Nạp bảng tra đã tính toán từ file JSON."""
        instance = cls()
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            instance.vocab_map = {int(k): v for k, v in data.items()}
        print(f"✓ Đã nạp thành công {len(instance.vocab_map)} tokens từ: {file_path}")
        return instance
