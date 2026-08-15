# 🧭 PROJECT DIRECTION — Định Hình Lại Toàn Bộ Hướng Đi & Cách Tiếp Cận

> **Vai trò file này:** Đây là **file chiến lược DUY NHẤT** định hình lại toàn bộ hướng đi, triết lý
> và cách tiếp cận của dự án *Sinh thơ Lục Bát AI* sau đợt đánh giá chuyên gia (Review 1 & 2).
> Nó là "la bàn" — trả lời **tại sao** và **đi đâu**. Mọi quyết định kỹ thuật mới đều phải đối
> chiếu với file này trước khi thực hiện.
>
> - **Chi tiết kỹ thuật / hướng dẫn sử dụng** → `README.md`
> - **Nhật ký phát triển theo thời gian** → `DEVLOG.md`
> - **Luật lập trình cho AI agent** → `.gemini/rules/luc_bat_project.md`
> - **File này → ĐỊNH HƯỚNG (Why & Where), phần còn lại → Chi tiết (What & How)**

---

## 1. 🎯 Tuyên bố Vấn đề (Problem Statement)

Xây dựng hệ thống **tự động sáng tác thơ Lục Bát tiếng Việt** thoả mãn đồng thời hai yêu cầu
tưởng chừng mâu thuẫn:

| | Yêu cầu |
|---|---|
| **1. Hình thức (cấu trúc)** | **100% tuân thủ** luật Lục Bát: câu 6/8 tiếng, gieo vần lưng + vần chân, Bằng/Trắc ở vị trí 2-4-6-8, Trầm/Bổng tiếng 8. |
| **2. Nội dung (chất thơ)** | **Tự nhiên, có cảm xúc, đúng chủ đề** — không "thơ phèn" (gượng gạo, sáo rỗng, vần chết). |

Đây là bài toán *Neural-Symbolic* điển hình: mô hình ngôn ngữ giỏi ngữ nghĩa nhưng không đếm được
âm tiết; code đếm chính xác nhưng không biết làm thơ. **Mỗi bên làm việc mình giỏi nhất.**

**Tên đề tài học thuật:** *Hybrid Neural-Symbolic Constrained Generation for Vietnamese Regulated Poetry*
(Mô hình Qwen3-8B + Logits Engine can thiệp + N-Best Reranking).

---

## 2. 🏛️ Triết lý Thiết kế (Design Philosophy)

### 2.1. Phân định Trách nhiệm — Deterministic → Code, Probabilistic → LLM
- **Code xử lý deterministic tốt hơn → giao cho Code:** đếm 6/8 tiếng, ngắt dòng `\n`, chặn token
  vô nghĩa (trie/lexicon), dừng đúng số cặp câu. *Không bắt mô hình học thuộc lòng 100k mẫu chỉ để đếm từ.*
- **LLM làm tốt nhất → giao cho LLM:** cảm xúc, hình tượng thơ, mạch nối chủ đề, chọn từ tự nhiên.

### 2.2. Hard Constraint vs Soft Constraint (chống "thơ phèn")
- **Hard ($-\infty$)** — chỉ 3 thứ:
  1. **Số âm tiết** đúng 6 (Lục) / 8 (Bát) — không cho xuống dòng sớm, ép `\n` ngay sau tiếng cuối.
  2. **Xuống dòng `\n`** chỉ xuất hiện tại biên câu 6/8.
  3. **Well-formedness trie** — token ngoài từ điển âm tiết bị chặn (không cắt giữa âm tiết).
- **Soft ($-\lambda$ penalty)** — cho **Bằng/Trắc** và **gieo vần**:
  - `tone_penalty = 1.5`, `rhyme_penalty = 3.0` (trừ khỏi logits token vi phạm).
  - Lý do: nếu một từ cực hợp ngữ cảnh nhưng lệch nhẹ thanh điệu, ta **chỉ phạt nhẹ** để mô hình có
    "đường thoát", không bị ép chọn từ gượng gạo. Cho phép **Vần thông (slant rhyme)** bên cạnh vần chính.
  - **Nghiêm cấm ép cứng thanh/vần** ($-\infty$) — đó chính là nguồn gốc "thơ phèn".

### 2.3. No-CoT — Không Chain-of-Thought (QUYẾT ĐỊNH ĐÃ CHỐT)
- **Bỏ R-CoT hoàn toàn** (quyết định 08/08): không `<think>`, không "reverse chain".
- **Lý do:** logits engine đã bảo đảm luật 100% lúc sinh; CoT chỉ tốn VRAM/token, nhiễu output
  (Qwen3 tự bật `<think>...</think>`), và rủi ro tiền xử lý dữ liệu.
- **Hệ quả cho SFT (lượt sau):** fine-tune dùng **instruction pairs** — input là block metadata có
  cấu trúc (chủ đề / số câu / từ khoá / vần gợi ý — đúng format `build_prompt`), output là bài thơ
  trực tiếp. SFT học **chất thơ**, không học luật.

### 2.4. Baseline-First (QUYẾT ĐỊNH ĐÃ CHỐT)
- **Đo baseline Qwen3 CHƯA train** (chỉ engine + reranker) trước khi đầu tư SFT.
- Mục đích: xác định **gap định lượng** (TCR/RMA) → quyết định SFT có cần không và cần cải thiện gì.

---

## 3. 🧩 Kiến trúc Hệ thống (System Architecture)

### 3.1. Kiến trúc Hybrid 3 Tầng
```
                          [ User Prompt ]
                                 │
                                 ▼
        ┌────────────────────────────────────┐
        │ TẦNG 1: NEURAL GENERATION          │  ← Qwen3-8B (nf4; sau này QLoRA SFT)
        │     sinh token tự do + soft logits │
        └──────────────────┬─────────────────┘
                           ▼
        ┌────────────────────────────────────┐
        │ TẦNG 2: SYMBOLIC INTERVENTION      │  ← LucBatLogitsProcessor
        │   Hard: 6/8 + \n + trie + EOS      │     (can thiệp lúc sinh)
        │   Soft: -λ Bằng/Trắc + vần         │
        └──────────────────┬─────────────────┘
                           ▼  N = 8 bài ứng viên
        ┌────────────────────────────────────┐
        │ TẦNG 3: CANDIDATE RERANKING        │  ← LucBatReranker (Poetry Critic)
        │   Chọn bài thơ tự nhiên nhất        │
        └──────────────────┬─────────────────┘
                           ▼
              [ Bài thơ Lục Bát hoàn chỉnh ]
```

### 3.2. Đếm Âm tiết qua SyllableTrie Subword (KHÔNG đếm token space)
- Tokenizer BPE Qwen3 tách khác nhau theo vị trí: `"trời"` (đầu dòng) → `['tr','ời']`
  (multi-token), còn `" trời"` (giữa dòng) → `[130868]` (1 token space-prefix). Đếm token `220`
  (space-only) là **sai**.
- **`SyllableTrie` 2 gốc:** `ROOT_START` (đầu dòng, token không space) + `ROOT_MID` (giữa dòng,
  token space-prefix và token `220` cho âm tiết bắt đầu nguyên âm). Mỗi âm tiết thêm 2 dạng `s` và `" "+s`.
- **Boundary-triggered `step()`:** `LucBatState.step(cur_syl)` chỉ gọi khi gặp **newline** hoặc
  **token space-prefix** — không cắt nhầm terminal node vừa là prefix (`"a"` vs `"ai"`).

### 3.3. Các Module
| Module | Vai trò |
|---|---|
| `phonetics/` | 6 thanh điệu (Bằng/Trắc, Ngang/Huyền), trích vần, **vần thông** `SLANT_RHYME_MAP`, bộ lọc âm tiết `is_lexicon_syllable`. |
| `engine/lucbat_state.py` | Trạng thái vị trí 1-6/1-8, vần anchor, Trầm/Bổng. |
| `engine/vocab_assets.py` | `LucBatVocabAssets` + `SyllableTrie` — precompute trie subword + dense masks (`tone_masks`/`group_masks`/`root_masks`). |
| `engine/lucbat_engine.py` | `LucBatLogitsProcessor` — hard (6/8+`\n`+trie+EOS) + soft (-λ thanh/vần), boundary-triggered. |
| `engine/evaluator.py` | `LucBatEvaluator` — SCR/TCR/RMA, `is_valid_lucbat`. |
| `engine/reranker.py` | `LucBatReranker` — best-of-N weighted. |
| `scripts/` | Pipeline data (extract → merge → filter → syllables → precompute) + `generate_poem.py` (sinh thơ end-to-end). |

---

## 4. 📐 Đánh giá Chất lượng (Evaluation)

### 4.1. Chỉ số định lượng tự động
- **SCR** (Structural Constraint Rate): % tuân thủ 6/8 + ngắt dòng. Hard-ép nên **luôn = 100**.
- **TCR** (Tone Constraint Rate): % đúng Bằng/Trắc + Trầm/Bổng. **Ngưỡng hợp lệ: TCR ≥ 95**.
- **RMA** (Rhyme Match Accuracy): % vần lưng + vần chân khớp (kể cả vần thông). **Ngưỡng: RMA ≥ 90**.
- **Overall = 0.4·SCR + 0.3·TCR + 0.3·RMA**.
- **`is_valid_lucbat`** = SCR=100 và TCR≥95 và RMA≥90 (cùng lúc).

### 4.2. Reranker (chọn best-of-N)
- Weighted sum (mỗi thành phần ~[0,1]): **evaluator overall .80** · **diversity (bigram distinct) .05**
  · **cliché penalty .10** (mỗi cụm `data/cliches.txt` = −0.25) · **keyword overlap .03** · **length .02**.
  *(08/08 tinh chỉnh bằng benchmark 10 prompt × 8 ứng viên — `tune_reranker_weights.py`: weight cũ
  0.35/0.20/0.15/0.20/0.10 → top1 40%/agg 73.0; bộ mới → top1 80%/agg 80.9/corr 0.91. Re-confirm trên
  50 prompt: top1 84%/agg 82.1/corr 0.95 — GIỮ NGUYÊN. KHÔNG dùng 0.90/0.02 — bị bài lặp `"liền liền"`
  đánh lừa; 0.85/0.03dv/0.07cl nhỉnh 2 prompt nhưng yếu lá chắn → cũng không dùng.)*

### 4.3. Human Eval (HOÃN — lượt sau)
- Rubric 5 tiêu chí, N=20 prompt, 2 variant, blind — tài liệu riêng `docs/HUMAN_EVAL.md`.

---

## 5. 🗂️ Dữ liệu (sau re-clean 08/08)

- **Nguồn:** Truyện Kiều + CSV `gender=="lục bát"` (exact match, 178,945 bài) + Parquet
  `the_loai=="luc_bat"` (87,609 bài). **Chống nhiễm song thất lục bát / các thể khác.**
- **Kết quả:** 2,040,269 cặp câu · 91,488 cặp vần (freq ≥ 2) · 415 nhóm vần · 3,264 từ vần.
- **Từ điển sinh (assets):** 10,745 âm tiết hợp lệ (`data/assets/syllables.json`) — qua
  `is_lexicon_syllable` (phải có nguyên âm, chuỗi phụ âm ≤ 2, chuỗi nguyên âm NFD ≤ 3) + lọc tần suất
  corpus ≥ 2 + **chặn chữ ngoại lai f/j/w/z + blocklist từ Anh** (3 lớp fix 08/08: fragment → English → rác nguyên âm).
- **Cảnh báo chất lượng (bài học 08/08, 3 lớp fix):**
  1. Fragment không nguyên âm `"n"`, `"b"` — bộ lọc cũ quá lỏng → `is_lexicon_syllable` (≥1 nguyên âm, phụ âm ≤ 2).
  2. Rò rỉ tiếng Anh `"just/from/the"` — alphabet regex không loại f/j/w/z → đã chặn + blocklist từ Anh.
  3. Rác nguyên âm `"thaoooooooo"`, `"ơiiiii"`, `"muười"` — chuỗi nguyên âm gốc NFD ≥ 4 → `vowel-run ≤ 3`.
  → **11,983 → 10,745 âm tiết.** Còn lại `"ượu"`-type chỉ là VẦN ĐÚNG (nucleus của `"rượu"`) model dùng sai
  vị trí — không phải lỗi lexicon nữa mà là lỗi TỪ NGỮ của model (đối tượng của SFT).

---

## 6. 🗺️ Lộ trình & Mốc chặn (Roadmap)

### ✅ Đã hoàn thành (08/08)
- **Phase 0:** Phonetics + tests (vần thông, comparator idempotent).
- **Phase DATA:** Re-clean corpus (exact genre match, lọc rác).
- **Phase 1:** Precompute assets (trie 23,781 node, masks, ~64.5MB).
- **Phase 2:** Logits Engine (hard/soft, 0.84 ms/step, 11 test).
- **Phase 3:** Evaluator + Reranker (12 test).
- **Phase 4:** `generate_poem.py` end-to-end → **baseline đo được** (xem § Phase 4 bên dưới).
- **Phase 5:** Skills suite mới (6 skills × `.gemini`/`.claude`).
- **Ablation A3 (`ablation_pipeline.py`):** free-gen SCR=6.4 → engine-only 100 (71.3/22.7) → engine+reranker
  100 (79.1/61.3/82.1). Định lượng đóng góp engine vào cấu trúc + reranker vào vần.
- **Bonus:** 139 unit tests pass (thêm `tests/test_syllable_utils.py`, mở rộng cho 3 lớp fix lexicon + 2 regression test weight reranker + 6 test `extract_poem` cho ablation).

### ✅ Phase 4 — baseline đã đo (08/08)
- **Baseline thật (Qwen3-8B chưa train, engine + reranker, lexicon sạch 10,745 âm tiết):**
  SCR=100 (engine bảo đảm); single-run best-of-8 ≈ overall 64–76, best-of-16 ≈ **81.4** (variance cao).
  **Vấn đề cấu trúc đã hết: không còn tiếng Anh, không còn fragment, không còn rác nguyên âm.**
- Thử tăng penalty (tone 2.5, rhyme 5.0) → thơ **gượng hơn**, KHÔNG cải thiện → giữ default (1.5/3.0).
- **Gap còn lại = luận cứ quyết định SFT:** model ghép âm tiết thành TỪ/cụm không chuẩn
  (`"reo tời"`, `"úa nghèn ngà"`, `"hổng lẽ"`) dù mỗi âm tiết đều là tiếng Việt thật — đây là giới hạn
  *word-level* mà trie âm tiết không giải quyết được, model chưa biết ngữ nghĩa tiếng Việt.

### ✅ Task 5.1 — Benchmark batch (HOÀN THÀNH 08/08, `benchmark_batch.py`)
- **10 prompt × 8 ứng viên** → aggregate: **SCR=100 · TCR=75.7 · RMA=46.7 · overall=76.7 · valid 0/10**.
- **50 prompt × 8 ứng viên (A2, mở rộng theo expert review, seed=42, 283.7s):**
  **SCR=100 · TCR=79.1 · RMA=61.3 · overall=82.1 · valid 0/50 · top1_agree 84% · corr 0.95**
  → TCR 75.7→79.1, RMA 46.7→61.3, overall 76.7→82.1 (mẫu lớn hơn, đa chủ đề → ổn định hơn; VẪN 0/50 valid).
- Kèm **tinh chỉnh weight reranker** bằng `tune_reranker_weights.py` (CPU trên dump ứng viên):
  0.35/0.20 → top1 40%, agg 73.0; **0.80/0.05/0.10/0.03/0.02 → top1 80% (10p) / 84% (50p), agg 80.9/82.1, corr 0.91/0.95**.
  2 lệch chuẩn còn lại là CHỦ ĐÍCH: loại bài cliché dày + bài lặp `"liền liền"` dù overall cao.
  Cảnh báo: KHÔNG dùng 0.90/0.02 — overall bị bài lặp đánh lừa (đây là lý do giữ diversity/cliché).
- **Nhận xét:** dù chỉnh reranker tối ưu, aggregate overall vẫn ~82 — **model chưa biết tiếng Việt là
  rào chắn chính, reranker chỉ chọn được bài đỡ dở nhất. → SFT vẫn là bước quyết định.**

### ⏳ Hoãn lượt sau (đã thống nhất)
- **Task 2.1:** No-CoT SFT pipeline (`build_sft_dataset.py` — metadata→thơ, validate bằng evaluator).
- **Task 2.2:** Pilot finetune Unsloth QLoRA (500–1000 mẫu, 1 epoch) — so baseline cùng prompt/seed.
- **Task 5.2:** Human Eval protocol.

### 🎯 Mục tiêu con số (đích để so sánh)
- Baseline Qwen3 chưa train (**benchmark 08/08, lexicon sạch, 50 prompt × 8 mẫu, seed=42**):
  **SCR=100 · TCR=79.1 · RMA=61.3 · overall=82.1 · valid 0/50** (SCR=100 do engine; ablation cho SCR free-gen).
- Mục tiêu sau SFT (kỳ vọng): **đạt ngưỡng valid TCR≥95, RMA≥90**; cliché giảm, overall tăng.

---

## 7. ⚙️ Môi trường & Ràng buộc Hạ tầng

- **GPU:** NVIDIA RTX 4060 Laptop, **8 GB VRAM** — nf4 + bfloat16, VRAM ~5.2–6.5 GB.
- **Model:** `/media/zafkiel/WORK_SPACE2/models/Qwen3-8B` (USB mount — nạp weight 5–10 phút).
- **Env:** conda `capstone` (`/home/zafkiel/miniconda3/envs/capstone/bin/python`).
- **Ràng buộc:** không OOM trên 8GB → nf4 bắt buộc khi train; cần precompute lại assets mỗi khi
  đổi phonetics/tokenizer.

---

## 8. 🧠 Nhật ký Quyết định (Decision Log)

| Ngày | Quyết định | Lý do |
|---|---|---|
| 07/08 | PhoGPT-7B5 → **Qwen3-8B** + Unsloth | Reasoning/instruction-following vượt trội; dù tokenizer không 1:1 tiếng Việt (giải bằng trie subword). |
| 07/08 | **Bỏ R-CoT** → No-CoT SFT (metadata→thơ) | Engine đã bảo đảm luật; CoT tốn VRAM/nhiễu; SFT chỉ học chất thơ. |
| 07/08 | **Baseline-first** — đo Qwen3 chưa train trước | Xác định gap thật để quyết định SFT; tránh đầu tư mù. |
| 07/08 | **Hard chỉ 6/8 + `\n` + trie**; Bằng/Trắc & vần dùng **soft -λ** | Chống "thơ phèn"; cho mô hình đường thoát khi chọn từ tự nhiên. |
| 07/08 | Đếm âm tiết qua **SyllableTrie subword** | Token space thô (`220`) sai vì space-prefix là 1 token; boundary-triggered `step()` chống cắt giữa âm tiết. |
| 08/08 | Re-clean corpus: **exact genre match** (CSV/Parquet) | Lọc nhiễm song thất lục bát + 83k bài thể khác từ parquet. |
| 08/08 | Mở rộng **`SLANT_RHYME_MAP`** (au→âu, an→ân, e→ê, o→ô…) | Cần cho vần thông của Kiều (nhau/dâu); KHÔNG thêm `ang→âng` (trùng last-2 fallback, phá `anh→ang`). |
| 08/08 | **`is_lexicon_syllable`** + lọc tần suất corpus ≥ 2 | Bộ lọc cũ quá lỏng → fragment "n"/"b"/"ượu" làm vỡ baseline; nguyên âm bắt buộc + chuỗi phụ âm ≤ 2. |
| 08/08 | `stop_after_couplets` ép EOS đúng số cặp câu | Tránh thơ dài hơn yêu cầu; `LucBatLogitsProcessor` tự dừng. |

---

## 9. ⚠️ Rủi ro & Giới hạn đã biết (Known Risks)

1. **Fragment nucleus còn sót** trong lexicon (~"ượu"-type, không loại được bằng cấu trúc đơn giản).
   → Nếu baseline còn nhiễm: cài grammar onset/nucleus/coda đầy đủ hoặc dict-anchor cho lớp horn-vowel.
2. **Chất thơ của Qwen3 chưa train** hạn chế (cliché, vần ép) — chính là lý do cần SFT.
3. **Tốc độ nạp model từ USB** 5–10 phút — chỉ ảnh hưởng dev loop, không phải production.
4. **Dữ liệu nhiễm nguồn gốc** (OCR, thể loại sai) — đã giảm mạnh bằng exact match, nhưng không thể 100%.
5. **Reranker weights** là heuristic — cần benchmark batch để chỉnh.
