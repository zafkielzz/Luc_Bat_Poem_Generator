# Tet4 Teacher Prompt Catalog v1

## Mục đích

Dùng `gpt-5.6-sol` với `reasoning.effort=medium` như **teacher LLM** để tạo
candidate thơ Lục Bát 4 dòng cho corpus Tet4. Teacher tạo dữ liệu mới từ brief
trừu tượng; không nhận nguyên văn thơ nguồn và không được paraphrase thơ nguồn.

Mục tiêu là 360 **semantic group** (nhóm ý nghĩa độc lập), mỗi group sinh một
candidate trước. Chỉ retry group trượt automatic gate hoặc bị reviewer loại;
không tạo hai biến thể đại trà. Human review quyết định record nào có thể gắn
`training_eligible=true`.

Không sinh cứng 360 bài mới: 360 là sức chứa taxonomy để tránh thiếu chủ đề.
Trước hết review 168 khổ legacy; sau đó chỉ sinh teacher số bài cần bù để đạt tối
thiểu 300 Gold accept, ưu tiên các family còn thiếu và các group bị reject.

## Taxonomy 360 nhóm ý nghĩa

| Family | Slots | Biến thể bắt buộc để tránh lặp |
|---|---:|---|
| Ông bà | 30 | sức khỏe, quây quần, ông/bà riêng, cháu ở xa, bàn thờ gia tiên, mừng thọ, Tết quê |
| Cha mẹ và họ hàng | 30 | hiếu kính, gia đình nhỏ, anh chị em, họp mặt, cha mẹ làm việc vất vả, nếp nhà |
| Vợ chồng và người yêu | 30 | cùng vun vén, xa nhau, cưới đầu năm, giữ lời hẹn, sẻ chia việc nhà, yêu thương kín đáo |
| Trẻ em, học sinh, thầy cô | 30 | lì xì, chăm ngoan, thi cử, lớp học đầu xuân, tri ân thầy cô, cha mẹ chúc con |
| Bạn bè và hàng xóm | 30 | trà xuân, tình bạn cũ, láng giềng, đoàn tụ nhóm bạn, xóa hiểu lầm, giúp đỡ nhau |
| Đồng nghiệp và người dẫn dắt | 30 | mở việc đầu năm, teamwork, người mới đi làm, người nghỉ hưu, mentor, ca trực Tết |
| Đối tác, khách hàng, kinh doanh | 24 | tín nghĩa, khai trương, cửa hàng nhỏ, hợp tác dài lâu, khách quen, khởi nghiệp |
| Nông dân, công nhân, tiểu thương | 30 | mưa thuận, mùa màng, chợ Tết, chuyến xe, xưởng đêm, gánh hàng, bữa cơm đủ đầy |
| Xa quê và trở về | 30 | vé xe cuối năm, sân ga, cuộc gọi video, kiều bào, căn bếp cũ, mộ tổ, hẹn đoàn viên |
| Cộng đồng và người phục vụ | 24 | y bác sĩ trực Tết, chiến sĩ, tình nguyện viên, công nhân vệ sinh, tài xế, ngư dân |
| Cột mốc đời sống | 30 | em bé mới sinh, nhà mới, đám cưới, đỗ đạt, vượt bệnh, đổi nghề, khép năm khó khăn |
| Lời chúc gia đình/tự thân | 42 | bình an sau biến động, nếp sống mới, tiết kiệm, đọc sách, làm lành, chăm sức khỏe, hy vọng |

Tổng: **360**. Mỗi slot phải khác ít nhất hai trục: người nhận, hoàn cảnh,
hình ảnh, lời chúc trọng tâm, góc nhìn hoặc giọng điệu.

## Keyword bank

Danh sách keyword có thể copy/random theo đúng family ở
[`docs/TET4_KEYWORD_BANK.md`](TET4_KEYWORD_BANK.md). Mỗi brief dùng 2–3
keyword tương thích, không random lẫn các family.

## Cấu trúc một brief

Mỗi slot gồm:

```text
recipient: người nhận cụ thể
relationship: quan hệ và góc xưng hô
tet_situation: một khoảnh khắc Tết hữu hình
wish_intent: điều muốn chúc, chỉ một trọng tâm chính
imagery: 1–2 hình ảnh/cử chỉ đời thường, không phải danh sách sáo ngữ
keywords: đúng 2–3 keyword, ưu tiên một cụm cụ thể và một từ cảm xúc
tone: mộc mạc | ấm áp | hóm hỉnh nhẹ | trang trọng vừa | tha thiết
avoid: cliché/ý không được dùng; không sao chép nguồn
semantic_group_id: Tet4-Gxxx, không dùng lại
```

Không dùng prompt chỉ có dạng “chúc Tết + an khang thịnh vượng”. Một brief hợp
lệ luôn có: người nhận, hành động/bối cảnh Tết, lời chúc và ít nhất một hình ảnh
hoặc chi tiết quan hệ.

## Prompt teacher chuẩn

```text
Bạn là teacher tạo dữ liệu nội bộ cho corpus lời chúc Tết Lục Bát tiếng Việt.
Hãy sáng tác MỘT bài thơ hoàn toàn mới, không trích, không mô phỏng sát, không
paraphrase bất kỳ thơ nguồn nào. Không giải thích, không có <think>.

Yêu cầu bắt buộc:
- đúng 4 dòng theo nhịp Lục–Bát–Lục–Bát; tự kiểm số tiếng, thanh và vần trước khi trả;
- phải là lời CHÚC TẾT rõ cho {recipient}, không chỉ tả mùa xuân;
- dùng tự nhiên ít nhất hai keyword, trong đó có ít nhất một keyword nguyên văn;
- có đúng một hình ảnh/cử chỉ cụ thể từ {imagery};
- không lặp một từ hoặc một vần chỉ để lấp nhịp; tránh {avoid}.

Brief:
- Quan hệ/góc xưng hô: {relationship}
- Hoàn cảnh Tết: {tet_situation}
- Ý chúc: {wish_intent}
- Keyword: {keywords}
- Giọng: {tone}

Chỉ trả JSON hợp lệ:
{"poem":"dòng 1\ndòng 2\ndòng 3\ndòng 4","used_keywords":[...],"semantic_group_id":"..."}
```

JSON chỉ phục vụ nhập liệu; evaluator, lexical guard và copy/near-dedup guard
quyết định automatic pass. Teacher không có quyền tự cho output pass.

## 12 brief mở đầu để calibration

| ID | Brief ngắn |
|---|---|
| G001 | Cháu ở xa chúc ông bà: cuộc gọi đêm giao thừa, sức khỏe và sớm đoàn viên; keyword `điện thoại`, `bình an`, `mái nhà`; giọng ấm. |
| G002 | Con chúc cha mẹ làm nông: mưa xuân, ruộng mạ, vụ mùa yên lành; keyword `mưa xuân`, `ruộng mạ`, `no ấm`; giọng mộc. |
| G003 | Vợ chồng mới cưới: cùng dọn căn bếp đầu năm, chúc bền lòng; keyword `bếp lửa`, `chung tay`, `tháng ngày`; giọng kín đáo. |
| G004 | Người yêu xa: đợi chuyến xe về quê, chúc giữ lời hẹn; keyword `sân ga`, `giao thừa`, `đợi nhau`; giọng tha thiết. |
| G005 | Cha mẹ chúc con nhỏ: nhận lì xì, chăm học và vui chơi; keyword `bao đỏ`, `trang vở`, `tiếng cười`; giọng tươi. |
| G006 | Học trò chúc cô giáo: lớp học mở đầu năm, tri ân người gieo chữ; keyword `sân trường`, `nét phấn`, `mùa mới`; giọng trang trọng vừa. |
| G007 | Bạn cũ gặp lại: ấm trà đầu xuân, chúc tình bạn bền; keyword `chén trà`, `đầu ngõ`, `bạn xưa`; giọng hóm hỉnh nhẹ. |
| G008 | Hàng xóm: cùng dựng cây nêu, chúc xóm nhỏ thuận hòa; keyword `cây nêu`, `ngõ nhỏ`, `thuận hòa`; giọng thân tình. |
| G009 | Đồng nghiệp trực Tết: ca trực đêm, chúc an toàn và gắn bó; keyword `ca trực`, `đèn sáng`, `bình yên`; giọng biết ơn. |
| G010 | Chủ quán chúc khách quen: mở cửa đầu năm, chúc làm ăn tử tế; keyword `mở hàng`, `khách quen`, `tín nghĩa`; giọng chân thành. |
| G011 | Người con xa quê: thắp hương tổ tiên, chúc gia đình đủ mặt; keyword `hương trầm`, `sân quê`, `đoàn viên`; giọng lắng. |
| G012 | Y bác sĩ trực Tết: lời chúc từ người dân, mong ca trực bình an; keyword `áo trắng`, `đêm xuân`, `an lành`; giọng trân trọng. |

## Quy trình scale

1. Chạy 12 brief calibration: terminal xử lý G001–G006, web xử lý G007–G012.
2. Chỉ khi human review cho thấy naturalness ổn định mới tạo batch 50 group/lần.
3. Sau khi biết số Gold accept từ 168 khổ legacy, chỉ lấy số group teacher cần bù đến tối thiểu 300 bài; phân terminal/web theo bảng bên dưới và ưu tiên family còn thiếu. Mỗi group sinh một candidate; retry có feedback chỉ cho group bị loại.
4. 360 group là reserve taxonomy, không phải lệnh phải sinh đủ 360 bài mới. Mỗi group chỉ giữ tối đa một bài.
5. Không đưa synthetic vào held-out; split theo `semantic_group_id`, không chỉ theo text hash.

## Phân công terminal và web

| Family | Terminal | Web | Tổng |
|---|---:|---:|---:|
| Ông bà | 18 | 12 | 30 |
| Cha mẹ và họ hàng | 18 | 12 | 30 |
| Vợ chồng và người yêu | 0 | 30 | 30 |
| Trẻ em, học sinh, thầy cô | 18 | 12 | 30 |
| Bạn bè và hàng xóm | 24 | 6 | 30 |
| Đồng nghiệp và người dẫn dắt | 24 | 6 | 30 |
| Đối tác, khách hàng, kinh doanh | 18 | 6 | 24 |
| Nông dân, công nhân, tiểu thương | 30 | 0 | 30 |
| Xa quê và trở về | 0 | 30 | 30 |
| Cộng đồng và người phục vụ | 18 | 6 | 24 |
| Cột mốc đời sống | 0 | 30 | 30 |
| Lời chúc gia đình/tự thân | 12 | 30 | 42 |
| **Tổng** | **180** | **180** | **360** |

Web nhận nhóm cần phán đoán cảm xúc/mạch quan hệ tinh tế; terminal nhận nhóm có bối cảnh rõ và dễ batch. Đây là phân công nguồn sinh, không phải thước đo độ khó.
