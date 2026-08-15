import sys
import os
import re
import string

# Thêm thư mục gốc vào path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from phonetics import get_tone, is_bang, is_trac, extract_rhyme
from engine import LucBatState, LineType

def clean_word(word: str) -> str:
    """Loại bỏ dấu câu (phẩy, chấm, hỏi...) dính liền với từ."""
    # Loại bỏ các ký tự dấu câu ở đầu và cuối từ
    return word.strip(string.punctuation + "“”‘’…–—")

def process_text_block(text_block: str):
    """Xử lý một hoặc nhiều dòng thơ (đoạn thơ Lục Bát)."""
    lines = [line.strip() for line in text_block.strip().split('\n') if line.strip()]
    if not lines:
        return

    state = LucBatState()
    print(f"\n================ Phân tích {len(lines)} dòng thơ ================")

    for line_idx, line in enumerate(lines, 1):
        # Tách từ và làm sạch dấu câu
        raw_words = line.split()
        words = [clean_word(w) for w in raw_words if clean_word(w)]

        print(f"\n📍 Dòng {line_idx} ({state.line_type.value} - {len(words)} từ): \"{line}\"")
        print("-" * 65)

        line_constraints = []
        for idx, w in enumerate(words, 1):
            constraint = state.get_constraint()
            tone = get_tone(w)
            b_or_t = "BẰNG" if is_bang(w) else ("TRẮC" if is_trac(w) else "N/A")
            rhyme = extract_rhyme(w)

            # Kiểm tra tuân thủ luật
            req_info = ""
            if constraint.required_tone:
                req_info += f"[Cần Thanh: {constraint.required_tone}] "
            if constraint.required_rhyme:
                req_info += f"[Cần Vần: {constraint.required_rhyme}]"

            print(f"  Từ {idx:<2}: '{w:<8}' | Thanh: {tone.value:<7} ({b_or_t:<4}) | Vần: '{rhyme:<4}' | Ràng buộc: {req_info}")
            state.step(w)

        print("-" * 65)

def interactive_demo():
    print("==================================================")
    print("   DEMO TƯƠNG TÁC PHÂN TÍCH NGỮ ÂM & LUẬT LỤC BÁT   ")
    print("==================================================")
    print("💡 Hướng dẫn:")
    print("  - Bạn có thể dán (paste) 1 từ, 1 câu hoặc NGUYÊN ĐOẠN THƠ nhiều dòng.")
    print("  - Nhập 'exit' hoặc 'q' để thoát.\n")

    buffer = []
    while True:
        try:
            prompt_str = "👉 Dán đoạn thơ / câu thơ (Bấm Enter 2 lần để phân tích): " if not buffer else "... "
            line = input(prompt_str)

            if not buffer and line.strip().lower() in ["exit", "q"]:
                print("Tạm biệt!")
                break

            # Nếu dòng trống và đã có buffer -> Thực thi phân tích toàn bộ buffer
            if line.strip() == "" and buffer:
                text_block = "\n".join(buffer)
                process_text_block(text_block)
                buffer = []
            elif line.strip() != "":
                buffer.append(line)

        except (KeyboardInterrupt, EOFError):
            if buffer:
                process_text_block("\n".join(buffer))
            print("\nTạm biệt!")
            break

if __name__ == "__main__":
    interactive_demo()
