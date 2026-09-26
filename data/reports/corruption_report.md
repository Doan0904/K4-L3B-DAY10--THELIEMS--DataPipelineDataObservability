# Báo cáo So Sánh Sự Kiện Data Corruption

## Bảng so sánh 3 trạng thái

| Tiêu chí / Chỉ số | Baseline | Corrupted | Repaired | Δ (Corrupted - Baseline) | Mức khôi phục |
|---|---|---|---|---|---|
| judge_accuracy | 1.000 | 0.700 | 1.000 | -0.300 | [OK] Khôi phục hoàn toàn |
| mean_judge_score | 5.000 | 3.400 | 5.000 | -1.600 | [OK] Khôi phục hoàn toàn |
| mean_token_f1 | 1.000 | 0.640 | 1.000 | -0.360 | [OK] Khôi phục hoàn toàn |
| retrieval_hit_rate | 1.000 | 0.700 | 1.000 | -0.300 | [OK] Khôi phục hoàn toàn |
| samples | 10.000 | 10.000 | 10.000 | +0.000 | [OK] Khôi phục hoàn toàn |
| Quality Gate Success | True | False | True | - | [OK] |
| Freshness Check | True | False | True | - | [OK] |
| Stale Ratio | Chuẩn | 0.318 | 0.042 | - | - |

## Nhận xét chuyên sâu (Observability Insights)
- **Phát hiện lỗi thầm lặng (Silent Failure):** Khi dữ liệu bị tiêm lỗi (Corrupted), pipeline RAG vẫn chạy và sinh ra kết quả, nhưng chất lượng bị tụt giảm nghiêm trọng (thể hiện qua Hit Rate, F1). Tuy nhiên, **Data Quality Gate** đã bắt thành công các bất thường về cấu trúc và độ tươi mới, cảnh báo cờ `success = False`.
- **Khả năng phục hồi (Resilience):** Sau quá trình Repair, dữ liệu trở về trạng thái nguyên bản. Bảng số liệu cho thấy hệ thống khôi phục hoàn toàn 100% chỉ số Baseline.
