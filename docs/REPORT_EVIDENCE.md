# Sổ cái bằng chứng cho báo cáo đồ án

Đây là **điểm tổng hợp duy nhất** cho các số liệu và kết luận được dùng trong khoá luận. Không sao chép số liệu vào nhiều file; mỗi dòng chỉ trỏ tới artifact gốc có thể tái lập.

## Quy ước

- **Artifact gốc**: JSON, CSV, log, model adapter hoặc script sinh kết quả. Giữ nguyên để tái lập.
- **Bằng chứng báo cáo**: chỉ dùng các kết luận được ghi trong bảng bên dưới.
- **Chẩn đoán**: hữu ích để quyết định kỹ thuật, nhưng không tự động là claim chính thức của đồ án.
- Mỗi kết luận quan trọng mới: ghi `DEVLOG.md`, sau đó thêm hoặc cập nhật đúng một dòng trong file này.

## Bằng chứng hiện tại

| Claim / câu hỏi báo cáo | Kết luận hiện hành | Artifact gốc | Trạng thái dùng trong báo cáo |
|---|---|---|---|---|
| Symbolic engine có giữ cấu trúc 6–8 không? | Có. Held-out 30 prompt × 3 seed: SCR=100.0±0.0. | `experiments/evaluation_freeze_v1/` | Claim chính thức |
| Engine và reranker đóng góp riêng thế nào? | Development ablation: free 54.9 overall, engine-first 67.8, engine+rerank 83.3. | `experiments/evaluation_freeze_v1/ablation_stage0_seed42_n50.json` | Claim chính thức; ghi rõ development |
| Pilot SFT cải thiện metric luật? | Có: held-out overall 81.8±0.1 → 91.7±1.1; combined RMA 54.3±0.9 → 82.4±4.0. | `experiments/pilot_qlora_v1/seed42/`, `seed123/`, `seed2026/` | Claim tự động, không gọi là chất thơ |
| Pilot SFT có tự nhiên hơn theo người chấm? | Chưa: paired blind một rater, baseline 8/12, SFT 4/12. Không scale SFT. | `experiments/pilot_qlora_v1/human_eval_v1/paired_human_eval_summary_v1.md` | Limit/negative result chính thức |
| Model có năng lực tiếng Việt tổng quát không? | Chẩn đoán văn xuôi từ adapter được người dùng đánh giá xấp xỉ 8/10; ngôn ngữ nhìn chung tự nhiên, vẫn có lỗi hình ảnh cục bộ. | `data/evaluation/prose_sft_pilot_v1.csv`, `data/evaluation/prose_sft_pilot_v1.json` | Chẩn đoán định tính, không thay human-eval chính thức |
| Decoder có làm tăng lỗi ghép từ không? | Có tín hiệu: candidate engine có bigram chưa thấy 20.5% so với free-gen 18.1%. | `experiments/collocation_diagnostic_v1.json` | Chẩn đoán phát triển |
| Điểm collocation có khớp naturalness không? | Audit development một rater: chọn candidate điểm cao hơn 7/9 cặp không hòa; 3 hòa. | `experiments/collocation_audit_v1_summary.md` | Tín hiệu prototype, cần held-out trước claim cuối |
| Prototype collocation v1 có đổi held-out selection không? | Không; weight 0.05 không đổi top-1 ở 30 prompt × 3 seed. | `DEVLOG.md` Khoang 34 | Negative result; không dùng production |
| Tet4 adapter có cải thiện metric luật so với base? | Development 18 prompt × 3 seed: adapter overall 93.9 vs base 83.8; combined RMA 92.0 vs 64.2. | `experiments/tet4_v1/dev_automatic_comparison_v1.json` | Development automatic result, không suy ra naturalness |
| Tet4 adapter có tự nhiên hơn theo paired blind không? | Không đạt gate: base 3/7, adapter 1/7, tie 3/7; giữ base làm baseline Tet4. Có lỗi cắt cụm như “tri â” thay vì “tri ân”. | `experiments/tet4_v1/dev_human_base_vs_adapter_v1.json` | Negative result chính thức cho adapter rộng trong scope Tet4 |
| Lexical guard có loại lỗi từ cụt Tet4 không? | Audit 432 candidate: 8 lỗi chắc chắn; guard đổi 1/54 selection, loại bài “tri â”. Overall -0.23, RMA -0.62, trong gate tự động. | `experiments/tet4_v1/dev_lexical_audit_v1.json`, `dev_lexical_guard_offline_v1.json` | Development safeguard; bật cho Tet4, không áp hồi tố baseline rộng |
| Rank-collocation có đủ tác động để dùng Tet4 không? | Không: weight dev tốt nhất chỉ đổi 5/54 selection; không đủ 7 cặp khác nhau cho human gate. | `experiments/tet4_v1/dev_rank_collocation_v1.json` | Negative result; tắt trong production Tet4 |
| Pilot web-mined/nhập tay Tết có lọc được dữ liệu SFT đủ chuẩn không? | HTML/PDF/manual: 185 strict đầu vào → 168 unique sau exact dedup chéo; nhập tay còn có 25 review và 6 bài 2 dòng được cách ly. Chưa đủ mốc 300 để train. | `scripts/import_tet4_manual_paste.py`, `data/sft/archive/tet4_legacy_staging_v1/tet4_combined_staging_v1.jsonl`, `tet4_combined_audit_v1.json` | Chẩn đoán/pilot corpus; không dùng làm claim chất lượng model |

| 168 khổ legacy có được đưa trở lại quy trình xây Gold không? | Có. Checkpoint 14/08: TET4-009 đã được reviewer chuyển sang `REJECT`, còn 127 `ACCEPT` và 41 `REJECT`. Importer sinh 117 candidate từ các bài ACCEPT có metadata hợp lệ, làm sạch ký tự trang trí và tạo prompt từ recipient + keywords_pipe + tone; không dùng `prompt_draft`; `chung chung` được chuẩn hóa thành `mọi nhà`; 32/117 recipient đại chúng (`mọi nhà` hoặc `mọi người`) được gắn `recipient_scope=general`. Còn phải loại bài chỉ tả Xuân–Tết không có ý chúc, audit near-dedup/group split, và audit 82 bất đồng thanh/vần (117/117 đã đúng cấu trúc 4 dòng) trước khi record nào trainable. | `data/evaluation/Review 168 bài để duyệt vào corpus - tet4_gold_review_v2.csv`; `scripts/import_tet4_gold_review_v2.py`; `data/sft/tet4_gold_candidates_v1_audit.json` | Human review/import T3; chưa Gold/trainable |

| Tet4 combined staging đã sạch để train chưa? | Chưa. 168/168 qua lexical guard nhưng chỉ 58/168 đạt is_valid_lucbat; chưa có nhãn phù hợp lời chúc cho toàn bộ corpus. Các cửa sổ 4 dòng cũ cũng chưa xác nhận ranh giới tác phẩm, nên chỉ dùng review/khám phá. | `data/sft/archive/tet4_legacy_staging_v1/tet4_review_sheet_v1.csv`; `tet4_combined_staging_v1.jsonl` | Decision gate T3; không train |

| Cửa sổ 4 dòng Tet4 có bảo toàn đơn vị thơ không? | Không đảm bảo. 168 record thuộc 11 nguồn, và importer/collector hiện dùng cửa sổ trượt; cần phân đoạn ranh giới bài trước SFT. | scripts/import_tet4_manual_paste.py; scripts/collect_tet4_web_corpus.py; `data/sft/archive/tet4_legacy_staging_v1/tet4_combined_staging_v1.jsonl` | Decision gate T3; không train |

| Phân đoạn bài dài từ source có nhãn có giữ được provenance không? | Có. Batch Điện Máy Xanh/AVAKids/Decathlon: 24 bài -> 31 block không chồng nhau, mỗi block lưu parent poem, vị trí và ngữ cảnh. Mới là review; chưa train. | scripts/import_tet4_labeled_source.py; tet4_dienmayxanh_batch1_review_v1_audit.json | Decision gate T3 |

| Có thể giữ thơ dài mà không trộn thẳng vào SFT 4 dòng không? | Có. Corpus nguồn hợp nhất giữ raw/full material và excerpt có provenance: 389 input -> 358 unique; toàn bộ gắn training_eligible=false cho plan-assisted pipeline. | scripts/build_tet4_source_material_corpus.py; tet4_source_material_corpus_v1_audit.json | Decision gate T3 |

| Qwen3-8B có thể lập plan có cấu trúc từ thơ Tết dài không? | Pilot 14 raw full poems (>=5 dòng), seed 42: 14/14 JSON parse hợp lệ gồm recipient, intent, imagery, tone và bốn vai trò dòng. Chất lượng plan còn chờ human review; chưa suy ra chất lượng thơ. | scripts/generate_tet4_plan_pilot.py; tet4_plan_pilot_v1.jsonl; tet4_plan_pilot_v1_audit.json | Chẩn đoán/pilot T3 |

| Agent-first A1/A2 đã kiểm tra được gì? | Coverage gate bắt người nhận + ≥1 exact + ≥2/3 semantic. Strict subtree retry seed 123 đạt SCR/TCR/RMA=100/100/100 nhưng sinh từ gượng. Seed 2026: naturalness critic phục hồi được reject từ JSON lỗi và chặn đúng bài “bữa thơi/sum vắng”; không có candidate nào được trả ra. | docs/TET4_AGENT_TECHNIQUES.md; engine/tet4_coverage.py; engine/tet4_naturalness.py; engine/lucbat_engine.py; scripts/run_tet4_agent.py; outputs/agent_runs/ong_ba_naturalness_repair_v3.json | Development smoke; verifier chặn lỗi, chưa chứng minh sửa được naturalness hay production |
| Web UI "Ông Đồ AI" có các tính năng tương tác nào? | Thiết kế giao diện hoàn chỉnh theo `UI_build.md`: Đơn xin chữ, Ông đồ mài mực + facts Tết, Thảo chữ nét bút lông + âm thanh, Thiệp 3D mực tàu giấy đỏ + con dấu triện cá nhân + pháo hoa, Cho chữ thư pháp, Mini-game Nối vần Lục Bát & Hái lộc đầu xuân. Bổ sung Canvas Editor tùy chỉnh thiệp thủ công, Kho lưu trữ thiệp (localStorage) & Hệ thống Template mở rộng. | `frontend/src/` | Giao diện sản phẩm hoàn chỉnh |

| Pilot synthetic assistant có đủ tự nhiên để tiếp tục không? | Không. Qua strict-form nhưng bị loại trước review vì người dùng nhận thấy naturalness kém; artifact và script đã xóa, không dùng train. | DEVLOG.md Khoang 96–97 | Negative result; chuyển sang teacher LLM mạnh hơn với cùng provenance/copy/human gate |

| Catalog prompt teacher Tet4 có giữ đúng product domain không? | Có protocol 360 semantic group, mọi group buộc có người nhận, hoàn cảnh Tết hữu hình, một ý chúc và chi tiết quan hệ/hình ảnh; cấm prompt chỉ liệt kê sáo ngữ. Chưa sinh candidate, nên chưa có claim naturalness. | `docs/TET4_TEACHER_PROMPT_CATALOG.md` | Protocol T3; chờ calibration |

## Quy trình viết báo cáo cuối

1. Dùng bảng này làm nguồn duy nhất để điền số cho chương Kết quả.
2. Mỗi bảng/hình trong báo cáo phải ghi đường dẫn artifact và protocol/seed tương ứng.
3. Tách rõ ba loại kết quả: **held-out chính thức**, **development**, và **chẩn đoán**.
4. Sau mỗi thí nghiệm mới, chỉ cập nhật dòng liên quan trong file này; không tạo thêm report tổng hợp độc lập.
5. Khi viết bản thảo, tạo `docs/final_report/` cho các chương văn bản; không chép JSON/CSV vào đó.

## Việc chờ

- T1 Tet4 đã hoàn tất: base model được giữ sau paired blind development.
- T2 lexical guard + collocation: audit từ cụt/lỗi chính tả trước, sau đó mới đánh giá collocation trên candidate pool Tet4.
- T3–T4 corpus/SFT Tet4: mở rộng web-mined nội bộ theo batch, lưu provenance; chỉ pilot khi đạt corpus sạch đủ lớn.
- T5–T6: human gate 7 cặp, sau đó demo, báo cáo, slides và video dự phòng.


## Scope sản phẩm hiện hành

Demo và các thí nghiệm phát triển mới tập trung vào **lời chúc Tết Lục Bát 4 dòng**. Người dùng đưa `wish_intent` (bao gồm người nhận nếu cần) và 2–3 `keywords`; hệ thống triển khai bài ngắn. Các benchmark đa chủ đề/4–6–8 dòng trước đó được giữ làm baseline nghiên cứu, không dùng để tune sản phẩm mới.

Dữ liệu Tet4 web-mined chỉ dùng nội bộ, không tái phân phối văn bản thô; bắt buộc lưu provenance, URL, tác giả/tác phẩm/ngày nếu có, khử trùng lặp và split theo nhóm trang/tác phẩm. License không phải điều kiện tuyển chọn theo quyết định phạm vi hiện hành, nhưng không được vượt robots.txt, paywall hay cơ chế chống truy cập.

Tracker của giai đoạn này là `COMPLETION_PLAN.md`; nhật kí chi tiết là `DEVLOG.md`.

| Strict-form gate của domain adaptation có được xác nhận chưa? | Development 18 prompt × 3 seed × 2 model: 108/108 output được chấp nhận, mọi output SCR/TCR/RMA=100/100/100. Decoder ghi strict relaxation ở 59/108 record, nên form được bảo đảm bởi hậu kiểm và reject, không phải hard-mask thuần. | `experiments/tet4_v1/domain_adapt_v2/{base,adapter}/seed*/benchmark_seed*_n18.json`; candidate JSON cùng thư mục | Development form result; chưa suy ra naturalness |
| Pha 1 domain adaptation có tự nhiên hơn sau strict-form không? | Không theo mini human gate một rater: baseline 4/7, adapter 1/7, hòa 2/7. Adapter không đạt ngưỡng >=5/7; không dùng làm adapter chất lượng hay demo. | `experiments/tet4_v1/domain_adapt_v2/human_eval_blind_strict_v1/paired_human_eval_strict_v1.json`; ratings và blind key cùng thư mục | Negative result chính thức; kết quả mô tả của một rater, không suy ra quần thể |
| Mốc 300 Gold có đồng nghĩa adapter sẽ dùng cho demo không? | Không. Đây chỉ là gate quy mô để mở một pilot QLoRA trên manifest đóng băng; adapter phải tiếp tục qua strict automatic gate và paired blind preference trước khi thay baseline trong README/demo. | `COMPLETION_PLAN.md`; `DEVLOG.md` Khoang 107 | Protocol T3; chưa có kết quả model |

| Micro-pilot kết thúc Tet4 có đủ điều kiện thay model demo không? | Không. Theo quyết định đóng dự án, chỉ freeze 14 mẫu strict có lời chúc rõ (11 train/3 dev, split theo `source_work_id`) để chạy một QLoRA exploratory 1 epoch; tập thấp hơn gate 300 Gold và chưa hoàn tất audit nội dung/prompt. | `data/sft/tet4_final_micro_pilot_v1/manifest.json` | Thí nghiệm kết thúc/pet project; không dùng làm claim chất lượng hay production. |


| Micro-pilot QLoRA kết thúc đạt kết quả gì? | Hoàn tất 1 epoch trên manifest frozen 14 record (11 train/3 dev), seed 42, r=16; 2 optimizer step, train loss 3.637756824493408, runtime train 12.4172 giây. Tet4 regression 3/3 pass. Không có dev metric/human gate và không thay baseline/demo vì tập dưới mốc 300 Gold. | `outputs/tet4_final_micro_pilot_v1/run_config.json`; `checkpoint-2/trainer_state.json`; `DEVLOG.md` Khoang 110 | Kết quả micro-pilot kết thúc, không phải claim chất lượng/naturalness. |

| Pilot toàn bộ 117 candidate được chạy theo điều kiện nào? | Theo override rõ ràng của người dùng: QLoRA 2 epoch trên 117 candidate (93 train/24 dev, group-safe split). Chỉ 35/117 strict-valid; 82 còn lại chưa qua audit thanh/vần. | `data/sft/tet4_final_all_candidates_v1/manifest.json`; `DEVLOG.md` Khoang 111 | Artifact pet project theo quyết định người dùng; không phải Gold dataset hay claim chất lượng. |

| Pilot cuối 117 candidate đạt kết quả gì? | QLoRA 2 epoch hoàn tất trên 96 train/21 dev (group-safe), seed 42, r=16: 24 step, train loss 2.4423102736473083, runtime train 143.3149 giây; Tet4 regression 3/3 pass. Không có dev metric/human gate. | `outputs/tet4_final_all_candidates_v1/run_config.json`; `checkpoint-24/trainer_state.json`; `DEVLOG.md` Khoang 112 | Artifact pet project theo override người dùng; 82/117 record chưa strict-valid, không dùng làm claim chất lượng hoặc thay baseline/demo. |

| Adapter 117 candidate có tốt hơn base trên held-out không? | Về automatic strict-form: cả hai 12/12 accepted và SCR/TCR/RMA/overall=100/100/100/100; adapter exact-RMA 80.6 vs base 75.0. Nhưng inspection top-1 adapter còn cụm vô nghĩa (“nụ cười râu”, “bình vay tơ gầu”); không có human preference, nên không suy ra naturalness hoặc dùng adapter làm demo mặc định. | `experiments/tet4_v1/final_all117_{base,adapter}/seed42/benchmark_seed42_n12.json`; candidate dumps; `DEVLOG.md` Khoang 113 | Held-out automatic + qualitative negative result; form metric không thay human quality evaluation. |

| Fine-tune 117 candidate có giúp model tự tuân thủ Lục Bát khi bỏ logits processor không? | Không. Held-out 12 prompt × 8 sample, candidate-0: base SCR/TCR/RMA/overall = 62.5/59.9/0.0/43.0, 0/12 valid; adapter = 52.1/67.8/5.6/42.8, 0/12 valid. Trong toàn pool, base 0/96 valid, adapter 1/96 valid. | `experiments/tet4_v1/final_all117_freegen/{base,adapter}/freegen_seed42_n12.json`; `DEVLOG.md` Khoang 114 | Held-out negative result; logits processor+hậu kiểm, không adapter, bảo đảm form. |

| Re-evaluation đúng schema SFT có thay đổi kết luận pilot 117 không? | Có: với prompt `recipient + keywords + tone`, không wish_intent, adapter free-gen đạt SCR/TCR/RMA/overall 66.7/61.1/8.3/47.5 so với base 43.8/43.8/0.0/30.6; cả hai 0/12 strict-valid. Với processor, adapter accepted 12/12 vs base 11/12. Output vẫn có chuỗi từ vô nghĩa, nên chỉ là tín hiệu luật/format, không claim naturalness. | `experiments/tet4_v1/final_all117_schema_matched_v1/{base,adapter}/schema_matched_seed42_n12.json`; `DEVLOG.md` Khoang 115 | Held-out schema-matched; thay thế diễn giải benchmark prompt-mismatch trước đó. |

| Clean user prompt (không suffix chỉ dẫn) ảnh hưởng ra sao? | Trên 12 held-out prompt recipient+keywords+tone: free-gen base 43.8/45.0/2.8/31.8 vs adapter 43.8/56.7/2.8/35.3 (SCR/TCR/RMA/overall), cả hai 0/12 valid. Với processor, cả hai 12/12 và metric luật 100. | `experiments/tet4_v1/final_all117_clean_prompt_v1/{base,adapter}/clean_prompt_seed42_n12.json`; `DEVLOG.md` Khoang 116 | Deployment-schema test; adapter train với suffix cũ, không suy ra naturalness. |
