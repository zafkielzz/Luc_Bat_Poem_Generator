# 🔬 Human Evaluation Protocol — Sinh thơ Lục Bát

> Trạng thái: **BẢN THẢO (drafted 08/08)** — Task 5.2 đang HOÃN theo quyết định chung;
> tài liệu soạn sẵn để dùng khi SFT xong, so baseline vs SFT.
> Nguồn: khuyến nghị E1/E2 từ `expert_review.md` — "human eval bắt buộc phải có với đề tài thơ".

## 1. Mục đích

Đo chất lượng **cảm nhận** của thơ sinh ra — thứ mà SCR/TCR/RMA không đo được
(đúng luật ≠ hay). Dùng để trả lời câu hỏi quyết định: **bài thơ sau SFT có hay hơn
baseline không**, ngoài các chỉ số tự động.

## 2. Thiết kế (cỡ mẫu khuyến nghị)

| Yếu tố | Giá trị |
|---|---|
| Số prompt | **N = 20** (chọn từ 50 prompt đa chủ đề của benchmark) |
| Variant | **2**: `baseline` (Qwen3-8B chưa train + engine + reranker) vs `sft` (sau SFT, cùng engine + reranker) |
| Số người chấm | **2–3** (tối thiểu 2 để tính agreement) |
| Cách trình bày | **Blind**: người chấm không biết bài nào của variant nào |
| Thứ tự | **Ngẫu nhiên hoá + counterbalance**: mỗi người chấm thấy 40 bài (20 prompt × 2) xáo trộn; thứ tự khác nhau giữa các người chấm |

## 3. Rubric — 5 tiêu chí (thang 1–5)

Chấm **từng bài**, mỗi tiêu chí 1–5 (1 = rất kém, 5 = xuất sắc):

| # | Tiêu chí | Mô tả | Neo điểm |
|---|---|---|---|
| 1 | **Đúng luật** | 6/8 âm tiết, vần lưng/chân, bằng/trắc đúng vị trí | 5 = chuẩn mọi dòng; 3 = lệch 1–2 chỗ; 1 = sai nhiều |
| 2 | **Tự nhiên** | Đọc trôi chảy như thơ thật, không gượng ép, không ghép từ lạ | 5 = trôi tự nhiên; 3 = hơi gượng; 1 = vô nghĩa |
| 3 | **Hình ảnh & cảm xúc** | Có hình ảnh, có mạch cảm xúc, không khô khan | 5 = hình ảnh gợi, xúc động; 1 = liệt kê khô |
| 4 | **Đúng chủ đề** | Bám sát yêu cầu prompt (chủ đề, đối tượng, lời chúc) | 5 = đúng trọng tâm; 3 = lạc đề nửa chừng; 1 = sai hẳn |
| 5 | **Ít sáo ngữ** | Không lạm dụng cụm mòn (`long lanh`, `đong đầy`, `hanh thông`…) | 5 = 0 cụm mòn; 3 = 1–2; 1 = chất đống |

**Điểm tổng mỗi bài** = trung bình 5 tiêu chí (hoặc trung bình có trọng số nếu nhóm quyết định,
vd tiêu chí 1–2 nặng hơn cho mục tiêu "đúng luật + tự nhiên").

## 4. Dữ liệu đầu vào cho mỗi bài chấm

Mỗi mục trong phiếu chấm:
```
Prompt gốc: viết bài thơ lục bát 4 câu về mùa thu
Bài thơ:     [thơ sinh ra, 8 dòng]
---
Đúng luật (1-5): __    Tự nhiên (1-5): __    Hình ảnh & cảm xúc (1-5): __
Đúng chủ đề (1-5): __  Ít sáo ngữ (1-5): __
```

## 5. Quy trình thực hiện

1. `scripts/run_human_eval.py` (chưa viết — Task 5.2) sinh bộ 40 bài:
   - Đọc 20 prompt chung; sinh baseline (model chưa train) và SFT (sau khi finetune);
   - Với mỗi variant, giữ **best-of-8 sau reranker** (thống nhất như pipeline production);
   - Randomise thứ tự, đánh ID ẩn (`H01`…`H40`), không lộ variant.
2. Export phiếu chấm (CSV / Google Form) cho 2–3 người.
3. Thu kết quả → `scripts/analyze_human_eval.py` (chưa viết) tổng hợp:
   - **Inter-annotator agreement**: Fleiss' kappa (nhiều người) hoặc Cohen's kappa (2 người);
   - **So sánh baseline vs SFT**: paired (Wilcoxon signed-rank — không giả định chuẩn) trên
     điểm trung bình mỗi prompt, hoặc t-test paired nếu dữ liệu xấp xỉ chuẩn;
   - Báo cáo per-tiêu-chí: SFT thắng đều hay chỉ thắng tiêu chí nào.

## 6. Ngưỡng diễn giải (đề xuất)

- **SFT được coi là cải thiện** nếu: thắng ở ≥ 3/5 tiêu chí và ≥ 2/3 số prompt,
  hoặc difference trung bình ≥ 0.5 điểm (thang 1–5) có ý nghĩa thống kê (p < 0.05).
- **Không kết luận** nếu kappa < 0.4 (agreement yếu → chỉ số không đáng tin).

## 7. Lưu ý

- Người chấm nên đọc 5–10 bài mẫu trước khi chấm thật để ổn định thang điểm (anchor calibration).
- Giữ cùng seed giữa lần sinh baseline và SFT để chỉ thay đổi đúng 1 biến (model weights).
- Nếu ngân sách hạn chế, có thể chấm chỉ N=10 prompt × 2 (20 bài/người) — giảm thời gian
  nhưng báo cáo rõ cỡ mẫu.
