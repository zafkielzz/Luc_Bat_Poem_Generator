# Kỹ thuật Tet4 Agent — Plan, Keyword Coverage và Constrained Generation

Tài liệu này mô tả pipeline đang được triển khai và là nguồn giải thích kỹ thuật
cho báo cáo/slide. Trạng thái hiện tại là development prototype, chưa phải kết
quả chất lượng cuối.

## 1. Luồng agent hiện tại

```text
wish_intent
  -> retrieval + creative brief
  -> người dùng chọn đúng 2–3 keyword
  -> Qwen3-8B lập plan JSON bốn dòng (no-CoT)
  -> coverage contract + plan prompt
  -> sinh N ứng viên bằng logits processor
  -> evaluator + lexical guard + coverage gate
  -> accept, hoặc feedback có cấu trúc rồi retry
```

- **Creative brief**: bản định hướng ngắn gồm hình ảnh, giọng và hướng triển khai.
- **No-CoT**: không yêu cầu hoặc lưu chuỗi suy luận ẩn; Qwen chỉ xuất JSON plan ngắn.
- **Coverage gate**: cổng xác minh nội dung sau khi sinh, không phải một lớp huấn luyện.
- **Retry**: sinh lại có feedback cụ thể khi toàn bộ ứng viên trượt gate.

## 2. Keyword được đưa vào thơ bằng cách nào?

Keyword hiện **không bị ép bằng logits processor**. Pipeline dùng phương pháp
generate–verify–retry (sinh, kiểm tra, rồi sinh lại):

1. User chọn đúng 2–3 keyword; protocol chuẩn hóa Unicode, khoảng trắng và loại trùng.
2. Keyword được đưa nguyên văn vào prompt lập plan và prompt sinh thơ.
3. Ngay từ attempt đầu, prompt có content contract:
   - nhắc rõ người nhận nếu xác định được;
   - dùng nguyên văn ít nhất một keyword;
   - phủ nghĩa ít nhất `min(2, K)` trên tổng `K` keyword.
4. Model sinh nhiều ứng viên (`N=4` trong smoke test, thiết kế sản phẩm là best-of-8).
5. Verifier kiểm tra từng ứng viên bằng matching tất định.
6. Nếu không ứng viên nào qua toàn bộ gate, agent không trả bài; feedback được thêm
   vào prompt và model retry.

Phương pháp này giữ cho model còn quyền paraphrase, đồng thời không cho phép bỏ toàn
bộ keyword. Nó cũng tránh giả định sai rằng một từ tiếng Việt tương ứng đúng một token.

## 3. Exact coverage và semantic coverage

### 3.1 Exact coverage

Exact match yêu cầu các âm tiết của keyword xuất hiện **liên tiếp và đúng thứ tự**.
Ví dụ `con cháu` chỉ exact-match với `con cháu`, không phải khi `con` và `cháu`
nằm rời rạc ở hai dòng.

### 3.2 Semantic coverage

Semantic match hiện dùng alias có kiểm soát, dễ audit:

| Keyword | Alias được chấp nhận về nghĩa |
|---|---|
| `con cháu` | `cháu con`, `trẻ nhỏ`, `trẻ con`, `đàn trẻ`, `trẻ` |
| `sum vầy` | `quây quần`, `đoàn viên`, `tụ họp`, `đầm ấm` |
| `lộc xuân` | `lộc mới`, `lộc biếc`, `mầm lộc`, `chồi lộc` |
| `bình an` | `an lành`, `yên bình`, `an yên` |

Alias chỉ được tính là semantic hit, không thay thế yêu cầu có ít nhất một exact hit.
Ví dụ `trẻ` có thể gợi `con cháu`, nhưng một bài chỉ có paraphrase vẫn chưa đủ gate.

### 3.3 Công thức content gate

Với `K` keyword:

```text
content_pass = recipient_pass
               AND exact_keyword_count >= 1
               AND semantic_keyword_count >= min(2, K)
```

Người nhận có alias riêng nhưng thận trọng. Chẳng hạn `ông bà` có thể đổi trật tự
thành `bà ông`; `con cháu` chỉ được hiểu là người nhận nếu đứng sau `chúc` hoặc
`chúc cho`, tránh hiểu nhầm câu “chúc ông bà..., con cháu sum vầy”.

## 4. Acceptance gate đầy đủ

Một bài chỉ được trả cho user khi đồng thời đạt:

```text
accept = content_pass
         AND lexical_pass
         AND SCR == 100
         AND TCR >= 95
         AND combined_RMA >= 90
```

- **SCR**: điểm đúng cấu trúc/số âm tiết.
- **TCR**: điểm tuân thủ thanh điệu.
- **RMA**: điểm liên kết vần.
- **Lexical guard**: bộ chặn từ cụt/lỗi chắc chắn, ví dụ `tri â` thay vì `tri ân`.

Việc tách content gate khỏi reranker rất quan trọng: tăng trọng số keyword đơn thuần
có thể khiến một bài nhồi từ khóa nhưng hỏng vần thắng một bài tự nhiên hơn. Reranker
chỉ so chất lượng giữa các candidate; acceptance gate quyết định bài có đủ điều kiện
được trả hay không.

## 5. Logits processor đang làm gì?

Logits processor can thiệp phân phối token trong lúc decode:

- Hard constraint: nhịp 6–8, newline và đường đi hợp lệ trong `SyllableTrie`.
- Soft constraint: phạt token lệch thanh và lệch vần; retry hiện tăng rhyme penalty
  từ `3.0` lên `4.5`.
- Không hard-mask keyword, người nhận, vần hoặc thanh.

`SyllableTrie` xử lý một âm tiết có thể gồm nhiều token: state chỉ commit âm tiết ở
ranh giới space/newline. Vì vậy decoder không dùng giả định `một token = một từ`.

Không hard-mask keyword vì cụm tiếng Việt có thể gồm nhiều token và có nhiều cách
diễn đạt. Muốn hard-enforce an toàn cần automaton theo dõi toàn chuỗi keyword và trạng
thái coverage trên từng batch row; giải pháp này phức tạp và dễ làm câu thơ gượng.

## 6. Kết quả smoke test hiện tại

Input:

```text
wish_intent: Chúc ông bà năm mới bình an, vui khỏe, con cháu sum vầy
keywords: con cháu, sum vầy, lộc xuân
seed: 2026
2 attempts x 4 candidates
```

Một candidate có đủ 3 keyword:

```text
hoa đào rực rỡ giữa sân
ông bà ngồi ăn bánh chưng tròn đầy
con cháu cười đùa sum vầy
lộc xuân rực rỡ cửa ngõ đỏ thẫm
```

Candidate này chỉ là output chẩn đoán, **không được agent accept**. Nó đạt recipient,
exact `3/3`, semantic `3/3`, SCR `100`, nhưng TCR `64.29` và RMA `33.33`; câu cuối
cũng chưa tự nhiên.

Tổng kết trace:

- 8/8 candidate nhắc đúng `ông bà`.
- 8/8 phủ semantic ít nhất 2/3; đa số exact 3/3.
- 0/8 qua full acceptance gate vì TCR chỉ 57.14–78.57 và RMA 0–33.33.
- Agent trả trạng thái `failed_acceptance_gate`, không công bố candidate lỗi là kết quả.

Artifact: `outputs/agent_runs/ong_ba_adaptive_gate_v1.json`.

## 7. Bước tiếp theo trước fine-tune

Nút thắt hiện tại không còn là bỏ keyword mà là phối hợp nội dung với vần/thanh.
Prototype **rhyme scaffold** đã được thêm: Qwen có thể đề xuất năm neo vần; validator
kiểm tra âm tiết đơn, thanh Bằng, quy tắc Bằng đối ở dòng Bát và ba quan hệ vần. Nếu
proposal sai, agent dùng fallback tất định `xuân → xuân`, `nhà → qua → ca` và lưu
provenance. Đây vẫn là soft planning, không biến vần thành hard token mask.

Smoke test seed 7 cho thấy prompt-only scaffold **chưa đủ**: Qwen đề xuất `nhà/nhà/ăn/vui/vui`
(sai cặp `ăn → vui`), agent dùng fallback hợp lệ nhưng candidate sinh ra không đặt anchor
đúng vị trí, TCR=78.57 và RMA=0. Đây là negative result; scaffold prompt-only không được
coi là cải tiến production.

Thí nghiệm tiếp theo cần được chọn rõ ràng giữa strict-rhyme retry (chỉ bật sau soft retry
thất bại, cần human gate) hoặc dùng model sinh mạnh hơn. Không tự đổi toàn bộ vần sang hard
mask vì điều đó trái quyết định baseline hiện tại và có nguy cơ làm câu thơ gượng.

Sau đó, strict-form retry đã được thử như một ablation có kiểm soát. Bản đầu của strict
mask chỉ lọc token đầu và không an toàn với subword; sau khi đổi sang lọc **subtree trie**
ở mọi token của âm tiết, GPU seed 123 đạt TCR=100 và RMA=100. Điều này xác nhận có thể
enforce luật vần/thanh với token tiếng Việt nhiều mảnh.

Tuy nhiên candidate strict có các cụm lỗi như `bàn thài`, `ông ơ`, `sum vờ`, đồng thời
không nhắc đủ `ông bà`; lexical/coverage gate đã từ chối nó. Kết luận thí nghiệm: strict
decode nên giữ như repair candidate sau soft failure, không phải output trực tiếp. Naturalness
critic hoặc model sinh mạnh hơn vẫn cần thiết để chọn/sửa câu trước khi công bố cho user.

Naturalness critic hiện là **veto một chiều**: `reject` sẽ chặn candidate và được đưa
vào feedback repair, còn `accept` không thể tự làm candidate pass. Lý do là cùng Qwen đã
từng accept nhầm thơ lỗi. Parser cũng chỉ phục hồi `reject` rõ ràng từ JSON lỗi nhẹ (ví dụ
Qwen chèn dấu ngoặc kép chưa escape khi trích thơ), tuyệt đối không suy đoán `accept`.
Strict decoder có fallback về hard baseline khi giao của trie với luật strict rỗng, ghi
`strict_relaxations` vào trace để không crash CUDA và không che giấu vi phạm strict.

Trace seed 2026 `ong_ba_naturalness_repair_v3.json`: candidate có SCR/TCR/RMA 100/100/100
nhưng chứa `bữa thơi` và `sum vắng` bị critic reject, nên runner trả
`failed_acceptance_gate`. Đây chứng minh chặn lỗi hoạt động; không chứng minh cùng Qwen
sửa được naturalness. 

Chỉ cân nhắc fine-tune sau khi:

1. agent flow được chạy trên 10–20 prompt phát triển;
2. failure rate được chia theo plan/content/form/naturalness;
3. prompt, scaffold, retry và reranker không còn cải thiện đáng kể;
4. dữ liệu fine-tune nhắm đúng failure còn lại thay vì bù lỗi orchestration.

## 8. Tệp triển khai và tái lập

- `engine/tet4_agent.py`: brainstorm, retrieval, keyword selection và plan messages.
- `engine/tet4_coverage.py`: recipient/keyword verifier, acceptance và retry feedback.
- `engine/lucbat_engine.py`: logits processor 6–8/trie cùng soft tone/rhyme.
- `scripts/run_tet4_agent.py`: runner Qwen plan → generate → verify → retry.
- `tests/test_tet4_coverage.py`: regression cho exact/paraphrase/recipient/form gate.
