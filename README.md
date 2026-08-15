# Vietnamese Lục Bát Poetry Generator

Hệ thống sinh lời chúc Tết Lục Bát 4 dòng theo hướng **neural-symbolic** (kết hợp mô hình ngôn ngữ với luật xác định): Qwen3-8B đề xuất nội dung, còn decoder và hậu kiểm giữ khuôn thơ.

> Trạng thái: dự án cá nhân đã khép lại sau pilot QLoRA cuối. Artifact, benchmark và các kết quả âm được giữ để tái lập; chất lượng thơ tự nhiên vẫn là giới hạn chính.

## Kết quả nhanh

| Hạng mục | Kết quả |
|---|---|
| Kiểm thử hồi quy | **195 passed** |
| Pilot cuối | QLoRA 2 epoch trên 117 candidate (96 train / 21 dev, tách theo nhóm nguồn) |
| Prompt held-out | 12 brief: người nhận + 2–3 từ khóa + tone |
| Strict pipeline | Base và adapter đều **12/12** bài hợp lệ theo kiểm tra luật |
| Sinh tự do | Base và adapter đều **0/12** bài hợp lệ nghiêm ngặt |

Con số strict 12/12 là bằng chứng cho decoder + hậu kiểm, **không** phải bằng chứng rằng model tự biết làm thơ hay.

## Kiến trúc

```text
Người nhận + keywords + tone
          │
          ▼
Creative brief → plan 4 dòng (ý, hình ảnh, vai trò từng dòng)
          │
          ▼
Qwen3-8B sinh N ứng viên
          │
          ▼
LucBatLogitsProcessor
  hard: 6/8 tiếng, biên xuống dòng, âm tiết hợp lệ
  soft: thanh điệu, vần
          │
          ▼
Verifier + lexical guard + N-best reranker
          │
          ▼
Bài Lục Bát 4 dòng hoặc REJECT
```

Plan chỉ hướng mạch ý. `LucBatLogitsProcessor` (bộ điều chỉnh điểm chọn token khi model đang sinh) và verifier mới là hai lớp kiểm soát luật thơ.

## Giao diện đầu vào

```text
Viết một bài thơ Lục Bát 4 dòng để chúc Tết cho ông bà.
Dùng tự nhiên các từ khóa: quất vàng, trường thọ.
Giọng: Chân thành.
```

User prompt chỉ chứa người nhận, keywords và tone. Chỉ dẫn không suy luận nằm ở system prompt; không lặp câu mệnh lệnh thừa ở user prompt.

## Đánh giá

### 1. Khả năng tự thân của model

Protocol: 12 prompt held-out, seed 42, 8 mẫu/prompt; không dùng logits processor và không reranker. Metric gồm SCR (đúng cấu trúc 6/8 và xuống dòng), TCR (đúng thanh), RMA (khớp vần), và Overall = 0.4×SCR + 0.3×TCR + 0.3×RMA.

| Model | SCR | TCR | RMA | Overall | Hợp lệ nghiêm ngặt |
|---|---:|---:|---:|---:|---:|
| Base Qwen3-8B | 43.8 | 45.0 | 2.8 | 31.8 | 0/12 |
| Adapter pilot | 43.8 | 56.7 | 2.8 | 35.3 | 0/12 |

Adapter tăng nhẹ điểm thanh/Overall trong deployment prompt, nhưng chưa tạo được bài hợp lệ nào và không có bằng chứng cải thiện độ tự nhiên.

### 2. Pipeline có ràng buộc

Cùng 12 prompt và seed; chạy strict processor, lexical guard, best-of-8 và reranker.

| Model | SCR | TCR | RMA | Overall | Hợp lệ nghiêm ngặt |
|---|---:|---:|---:|---:|---:|
| Base + processor | 100.0 | 100.0 | 100.0 | 100.0 | 12/12 |
| Adapter + processor | 100.0 | 100.0 | 100.0 | 100.0 | 12/12 |

Kết luận: pipeline kiểm soát **hình thức** đáng tin cậy; nó chưa giải quyết được hoàn toàn tính tự nhiên của từ ngữ khi model bị ép theo thanh/vần.

### 3. Đánh giá chất lượng thơ

Metric luật không đo “hay”. [Rubric human evaluation](docs/HUMAN_EVAL.md) có 5 tiêu chí: đúng luật, tự nhiên, hình ảnh/cảm xúc, đúng chủ đề và ít sáo ngữ (mỗi tiêu chí 1–5), với thiết kế blind comparison. Pilot cuối **chưa** có human evaluation, vì vậy README không chọn lọc hoặc biên tập một bài thơ đẹp để đại diện cho model.

Khi so sánh model frontier, dùng đúng 12 brief held-out, lưu model/version, sampling settings, latency và chi phí; báo cáo tách raw generation khỏi cùng pipeline có processor. Đó là cách tránh nhầm “đúng luật” với “thơ hay”.

## Chạy thử

Yêu cầu: Python 3.10+, CUDA GPU; Qwen3-8B được tải cục bộ (không nằm trong repository).

```bash
pip install -r requirements.txt
python -m pytest tests/ -q

python scripts/generate_poem.py \
  "viết bài lục bát 4 câu chúc Tết ông bà" \
  --num-samples 8
```

Với luồng có plan agent:

```bash
python scripts/run_tet4_agent.py \
  "Chúc Tết ông bà bình an, vui khỏe, con cháu sum vầy" \
  --keywords "con cháu" "sum vầy" "lộc xuân"
```

Lần đầu cần asset trie/từ điển đã precompute. Để tái tạo, chạy `python scripts/precompute_assets.py`.

## Cấu trúc repository

| Thành phần | Vai trò |
|---|---|
| `engine/` | logits processor, evaluator, reranker, agent và các guard |
| `phonetics/` | thanh điệu, vần và vần thông |
| `scripts/` | sinh thơ, benchmark, train và utility tái lập |
| `tests/` | regression tests cho luật thơ và pipeline |
| `docs/` | protocol agent, rubric human evaluation, sổ cái bằng chứng |

## Giới hạn và hướng tiếp theo

- 117 bài là quá ít và chưa đủ sạch để kết luận về fine-tune; pilot được lưu như negative result có ích.
- Data hiếm có thể mở rộng bằng teacher LLM, nhưng mỗi bài synthetic cần provenance, kiểm luật, copy/near-dedup guard và human review trước khi train.
- So sánh với model frontier nên ưu tiên blind human preference, không chỉ metric hình thức.

Tài liệu chi tiết: [định hướng dự án](PROJECT_DIRECTION.md), [pipeline Tet4](docs/TET4_AGENT_TECHNIQUES.md), [rubric human evaluation](docs/HUMAN_EVAL.md), [sổ cái bằng chứng](docs/REPORT_EVIDENCE.md).
