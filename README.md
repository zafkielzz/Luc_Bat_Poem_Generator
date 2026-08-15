# Vietnamese Lục Bát Poetry Generator

Hệ thống sinh thơ Lục Bát tiếng Việt theo kiến trúc lai neural-symbolic: Qwen3-8B tạo nội dung, bộ luật xác định kiểm soát thể thơ, rồi chọn ứng viên tốt nhất từ một nhóm mẫu sinh.

> Đây là pet project nghiên cứu/kỹ thuật. Mục tiêu đã đạt là kiểm soát hình thức Lục Bát trong pipeline; chất lượng thơ tự nhiên vẫn là giới hạn chính.

## Kiến trúc

```text
Prompt có cấu trúc
      │
      ▼
Qwen3-8B (sinh ứng viên)
      │
      ▼
LucBatLogitsProcessor
  - hard: 6/8 tiếng, xuống dòng, âm tiết hợp lệ
  - soft: thanh điệu và vần
      │
      ▼
Evaluator + N-best reranker
      │
      ▼
Bài thơ Lục Bát 4 dòng
```

## Luồng agent cho lời chúc Tết 4 dòng

Luồng sản phẩm Tet4 có một bước lập kế hoạch trước khi sinh thơ:

```text
Người nhận + 2–3 từ khóa + tone
      → creative brief + plan JSON: ý/ảnh/vai trò cho từng dòng 1–4
      → sinh nhiều ứng viên có ràng buộc
      → kiểm tra người nhận, keyword, luật thơ và rerank/retry
```

Plan 4 dòng phân vai: dòng 1 mở bối cảnh/hình ảnh, dòng 2 phát triển mạch, dòng 3 đưa lời chúc hoặc tình cảm trọng tâm, dòng 4 khép lại. Plan là ràng buộc ngữ nghĩa mềm; nó không thay thế logits processor trong việc giữ luật 6–8/vần/thanh.

Các benchmark trong phần dưới **không dùng plan agent**: chúng so sánh trực tiếp base và adapter trên cùng metadata để cô lập ảnh hưởng của fine-tune và logits processor. Xem [`docs/TET4_AGENT_TECHNIQUES.md`](docs/TET4_AGENT_TECHNIQUES.md) để biết contract, verifier và retry.

Các thành phần chính:

- `phonetics/`: tách thanh, vần và kiểm tra vần thông.
- `engine/`: trie âm tiết, logits processor, evaluator, reranker và Tet4 agent.
- `scripts/generate_poem.py`: sinh thơ end-to-end.
- `scripts/benchmark_batch.py`: benchmark có ràng buộc.

## Kết quả cần diễn giải đúng

Bộ ràng buộc + hậu kiểm có thể bảo đảm đầu ra được chấp nhận đúng hình thức trong benchmark strict. Đây là đóng góp chính của dự án, không phải bằng chứng rằng base model tự biết luật Lục Bát.

Pilot QLoRA cuối dùng 117 candidate Tet4, 2 epoch (96 train / 21 dev). Re-evaluation dùng **đúng schema SFT** — người nhận + 2–3 từ khóa + tone, không có trường “Ý chúc” — trên 12 prompt held-out. Khi **bỏ** logits processor và reranker:

| Model | SCR | TCR | RMA | Overall | Đúng luật nghiêm ngặt |
|---|---:|---:|---:|---:|---:|
| Base Qwen3-8B | 43.8 | 45.0 | 2.8 | 31.8 | 0/12 |
| Adapter pilot | 43.8 | 56.7 | 2.8 | 35.3 | 0/12 |

Khi bỏ câu chỉ dẫn ở user prompt, adapter chỉ tăng nhẹ TCR/overall và cả hai vẫn 0/12 strict-valid. Vì vậy không có bằng chứng đáng tin rằng adapter tự giữ luật; vẫn không có claim cải thiện naturalness. Chi tiết kỹ thuật và evidence nằm trong [`docs/`](docs/).

### So sánh end-to-end có logits processor

Cùng 12 prompt held-out, seed 42, 8 ứng viên/prompt, logits processor strict + lexical guard + reranker:

| Model | SCR | TCR | RMA | Overall | Đúng luật nghiêm ngặt |
|---|---:|---:|---:|---:|---:|
| Base Qwen3-8B + processor | 100.0 | 100.0 | 100.0 | 100.0 | 12/12 |
| Adapter pilot + processor | 100.0 | 100.0 | 100.0 | 100.0 | 12/12 |

Processor và hậu kiểm là cơ chế kiểm soát hình thức chính; bảng này không đo naturalness và không chứng minh adapter tốt hơn.

### Hai ví dụ cùng prompt, output top-1 thực tế

Để README dễ đọc, chỉ giữ hai cặp minh họa; artifact benchmark giữ đủ 12 prompt. Các prompt dùng đúng schema SFT: `người nhận + keywords + tone`, không có trường “Ý chúc”. Output là top-1 từ seed 42, batch 8 ứng viên, logits processor strict + reranker.

#### 1. Chúc Tết ông bà

**Prompt**

```text
Viết một bài thơ Lục Bát 4 dòng để chúc Tết cho ông bà. Dùng tự nhiên các từ khóa: quất vàng, trường thọ. Giọng: Chân thành. Sáng tác trực tiếp bài thơ, không giải thích, không suy luận.
```

**Base không processor**

```text
Quất vàng rộn ràng xuân về
Chúc ông chúc bà sức vui khỏe thêm
Trường thọ như cây cổ thụ
Ngày càng an khang, phúc phần đầy dư.
```

**Base + processor**

```text
quat vang nho nhặt trên ngò
thoang thoang hương gió tết trô hời hờ
trường thơi dẫu có bao gờ
tương tư nhớ đến cội rơ tơ vừng
```

**Adapter pilot + processor**

```text
ễ ơi nhà vãn có nhiều
thơ ca bao nhớ thiết liều nay đi
dâu dông năm cũ qua đi
bài này xin gửi cho thì trời trăng
```

**Frontier model (bạn điền)**

```text
Model / version:
[Dán output ở đây]
```

#### 2. Chúc Tết bà con trong xóm

**Prompt**

```text
Viết một bài thơ Lục Bát 4 dòng để chúc Tết cho bà con trong xóm. Dùng tự nhiên các từ khóa: cổng làng, trống hội. Giọng: Chân thành. Sáng tác trực tiếp bài thơ, không giải thích, không suy luận.
```

**Base không processor**

```text
Cổng làng rộn rã tiếng trống,
Người quen người lạ đón nhau vui xuân.
Chào nhau năm mới lời thật thà,
Tâm tình gửi gửi giữa thôn quê thân thương.
```

**Base + processor**

```text
cổng làng rộn rã tiếng trung
trống hồi vang vọng giữa xung quanh người
tết về mang nắng sớm tươi
bà con sum vánh đón mời nụ hân
```

**Adapter pilot + processor**

```text
lời chia nhau tấu với lời
kính chia xuân đến mọi nơi xa gần
cổng làng nở bướm vàng đan
trống hồi đánh mộc hồn dân chung vầ
```

**Frontier model (bạn điền)**

```text
Model / version:
[Dán output ở đây]
```

Các cặp trên cố ý giữ nguyên output benchmark, không biên tập. Chúng cho thấy kiểm soát luật thơ không đồng nghĩa với chất lượng ngôn ngữ hay chất thơ.

## Hướng phát triển khả thi

- **Teacher LLM cho dữ liệu hiếm:** dùng model mạnh tạo thơ mới từ brief trừu tượng `người nhận + keywords + tone`, không đưa thơ nguồn vào prompt. Mỗi bài synthetic cần provenance, strict-form/lexical/copy guard, near-dedup và human review trước khi dùng train; không dùng synthetic làm held-out.
- **So sánh model top-tier:** dùng đúng 12 prompt schema-matched cố định ở trên. Báo cáo tách hai chế độ: raw generation để đo khả năng tự thân, và cùng logits processor để đo chất lượng end-to-end. Mỗi model cần lưu version, seed/temperature, latency, chi phí (nếu có) và blind human preference; không suy ra naturalness chỉ từ metric luật.
- **Plan agent:** tiếp tục dùng plan 4 dòng như ràng buộc ngữ nghĩa mềm; đánh giá riêng plan-assisted so với direct generation bằng cùng protocol.

## Yêu cầu

- Python 3.10+
- NVIDIA GPU có CUDA; cấu hình thử nghiệm dùng RTX 4060 Laptop 8GB
- Qwen3-8B đã tải cục bộ (không được chứa trong repository)
- Môi trường có PyTorch, Transformers, BitsAndBytes, PEFT và Unsloth

```bash
pip install -r requirements.txt
```

Đặt đường dẫn model bằng đối số `--model` khi script hỗ trợ, hoặc cập nhật `MODEL_PATH` trong `scripts/generate_poem.py` theo máy của bạn.

## Chạy thử

```bash
python -m pytest tests/ -q

python scripts/generate_poem.py \
  "viết bài lục bát 4 câu chúc Tết ông bà" \
  --num-samples 8
```

Lần chạy đầu cần các asset từ điển/trie. Asset precompute lớn không được commit; nếu cần tái tạo, chạy:

```bash
python scripts/precompute_assets.py
```

## Tài liệu

- [`PROJECT_DIRECTION.md`](PROJECT_DIRECTION.md): định hướng kiến trúc và các quyết định cốt lõi.
- [`docs/TET4_AGENT_TECHNIQUES.md`](docs/TET4_AGENT_TECHNIQUES.md): pipeline Tet4 plan → generate → verify → retry.
- [`docs/HUMAN_EVAL.md`](docs/HUMAN_EVAL.md): rubric đánh giá bằng người.
- [`docs/REPORT_EVIDENCE.md`](docs/REPORT_EVIDENCE.md): sổ cái bằng chứng và negative results.

## Giới hạn và trạng thái

- Logits processor chịu trách nhiệm chính cho luật 6–8/vần/thanh trong output strict.
- Fine-tune 117 bài chưa cải thiện đáng tin cậy chất lượng thơ tự thân.
- Raw corpus, checkpoint, adapter và output benchmark lớn được giữ cục bộ, không phát hành qua repository.

Dự án được đóng ở phạm vi cá nhân nhằm lưu lại một pipeline sinh thơ có ràng buộc, các thí nghiệm tái lập được và những kết quả âm có giá trị kỹ thuật.
