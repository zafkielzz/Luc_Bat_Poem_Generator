# SFT Data Audit — Stage 1.3

Mục tiêu là kiểm tra **chất lượng ngôn ngữ và an toàn sử dụng** của corpus trước SFT. Đây không phải human evaluation để so baseline với SFT.

## Tệp chấm

Mở `data/sft/quality_audit_form_v1.csv` trong LibreOffice/Google Sheets. Mỗi dòng là một bài được chọn ngẫu nhiên xác định từ quality subset.

## Cách chấm

- `naturalness_1_5`: 1 = gượng/vô nghĩa; 3 = hiểu được nhưng còn gượng; 5 = tự nhiên như thơ do người viết.
- `imagery_coherence_1_5`: 1 = rời rạc/mâu thuẫn; 3 = có ý nhưng mờ; 5 = hình ảnh và mạch ý rõ.
- `sensitive_or_unusable_0_1`: 1 nếu có nội dung tình dục thô, công kích, spam, lỗi chính tả nghiêm trọng hoặc không phù hợp để model học; ngược lại 0.
- `decision_accept_reject`: accept chỉ khi naturalness >= 3, imagery >= 3 và cột sensitive = 0; nếu lưỡng lự, reject và ghi notes.
- `notes`: ghi ngắn taxonomy lỗi: collocation, lặp ý, sáo ngữ, sai chính tả, nhạy cảm, lạc giọng, hoặc khác.

## Gate

Pilot chỉ tiếp tục nếu ít nhất 80/100 mẫu được accept. Nếu thấp hơn, không nới lỏng frozen form gate; thay vào đó lọc thêm theo taxonomy lỗi và audit lại.


## Phân tích sau khi chấm

Khi tất cả 100 dòng đã được điền, chạy:

```bash
python scripts/analyze_sft_audit.py
```

Kết quả ghi tại `data/sft/quality_audit_results_v1.json`. Pilot qua gate khi ít nhất 80% là `accept`.
