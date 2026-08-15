from dataclasses import dataclass
from enum import Enum
from typing import Optional
from phonetics.tone_classifier import get_tone, ToneType
from phonetics.rhyme_checker import extract_rhyme

class LineType(str, Enum):
    LUC = "LUC"  # 6 chữ
    BAT = "BAT"  # 8 chữ

@dataclass
class Constraint:
    required_tone: Optional[str] = None  # 'B', 'T', 'NGANG', 'HUYEN', None
    required_rhyme: Optional[str] = None # Chuỗi vần cần gieo (VD: 'oi', 'anh')
    force_newline: bool = False

class LucBatState:
    """
    Máy trạng thái quản lý quy tắc thơ Lục Bát:
    - Quản lý thể dòng: Lục (6 chữ) / Bát (8 chữ).
    - Vị trí từ hiện tại (1 -> 6 hoặc 1 -> 8).
    - Ràng buộc Bằng/Trắc ở vị trí 2, 4, 6, 8.
    - Ràng buộc Trầm/Bổng ở câu Bát (tiếng 6 Ngang -> tiếng 8 Huyền và ngược lại).
    - Ràng buộc gieo vần lưng & vần chân.
    """

    def __init__(self):
        self.line_type: LineType = LineType.LUC
        self.word_pos: int = 1  # Vị trí từ 1-indexed (1..6 hoặc 1..8)
        self.rhyme_anchor_6: Optional[str] = None  # Vần của tiếng 6 câu Lục
        self.rhyme_anchor_8: Optional[str] = None  # Vần của tiếng 8 câu Bát
        self.tone_6_bat: Optional[ToneType] = None # Thanh điệu của tiếng 6 câu Bát (NGANG hay HUYEN)

    def get_constraint(self) -> Constraint:
        """Trả về đối tượng Constraint chứa điều kiện bắt buộc cho từ tiếp theo."""
        if self.line_type == LineType.LUC:
            if self.word_pos > 6:
                return Constraint(force_newline=True)

            # Quy tắc Bằng/Trắc câu Lục (6 chữ): 2-B, 4-T, 6-B
            if self.word_pos == 2:
                return Constraint(required_tone="B")
            elif self.word_pos == 4:
                return Constraint(required_tone="T")
            elif self.word_pos == 6:
                return Constraint(required_tone="B", required_rhyme=self.rhyme_anchor_8)

            return Constraint()  # Vị trí 1, 3, 5: Tự do

        else: # LineType.BAT (8 chữ)
            if self.word_pos > 8:
                return Constraint(force_newline=True)

            # Quy tắc Bằng/Trắc câu Bát (8 chữ): 2-B, 4-T, 6-B, 8-B
            if self.word_pos == 2:
                return Constraint(required_tone="B")
            elif self.word_pos == 4:
                return Constraint(required_tone="T")
            elif self.word_pos == 6:
                return Constraint(required_tone="B", required_rhyme=self.rhyme_anchor_6)
            elif self.word_pos == 8:
                if self.tone_6_bat == ToneType.NGANG:
                    req_t = "HUYEN"
                elif self.tone_6_bat == ToneType.HUYEN:
                    req_t = "NGANG"
                else:
                    req_t = "B"

                return Constraint(required_tone=req_t)

            return Constraint()  # Vị trí 1, 3, 5, 7: Tự do

    def step(self, syllable: str):
        """Cập nhật trạng thái sau khi 1 âm tiết/từ được sinh ra."""
        clean_syl = syllable.strip()
        if not clean_syl or clean_syl == "\n":
            return

        tone = get_tone(clean_syl)
        rhyme = extract_rhyme(clean_syl)

        if self.line_type == LineType.LUC:
            if self.word_pos == 6:
                self.rhyme_anchor_6 = rhyme  # Lưu vần tiếng 6 câu Lục

            self.word_pos += 1
            if self.word_pos > 6:
                self.line_type = LineType.BAT
                self.word_pos = 1

        else: # BAT
            if self.word_pos == 6:
                self.tone_6_bat = tone  # Lưu thanh điệu tiếng 6 câu Bát

            elif self.word_pos == 8:
                self.rhyme_anchor_8 = rhyme  # Lưu vần tiếng 8 câu Bát cho câu Lục tiếp theo

            self.word_pos += 1
            if self.word_pos > 8:
                self.line_type = LineType.LUC
                self.word_pos = 1
                self.tone_6_bat = None
