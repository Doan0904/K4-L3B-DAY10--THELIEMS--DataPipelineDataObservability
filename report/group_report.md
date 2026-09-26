# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Khóa/Lớp         | K4-L3B              |
| Tên nhóm         | TheLiems |
| Repository         | https://github.com/Doan0904/K4-L3B-DAY10--THELIEMS--DataPipelineDataObservability |
| Ngày hoàn thành | 2026-09-26               |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Đặng Đình Đoàn | 2A202602927 | Ingestion & Corruption owner | `crossref.py`, `corruption.py` |
| 2 | Ngô Anh Khoa | 2A202602965 | Cleaning & Test-set owner | `cleaning.py`, `testset.py` |
| 3 | Mai Quang Dũng | 2A202602966 | Observability owner | `quality.py`, `reporting.py` |
| 4 | Lê Văn Việt | 2A202602504 | Integration owner | `phase1.py`, `corruption_flow.py` |

## 2. Tóm tắt kết quả

Nhóm đã triển khai thành công toàn bộ End-to-End Pipeline từ bước kéo dữ liệu (Ingestion) bằng Crossref API, cho đến việc làm sạch (Cleaning), lập chỉ mục (Embedding qua OpenAI) và đánh giá độ chính xác của RAG. Các công cụ theo dõi dữ liệu (Data Observability) bao gồm Quality Gate (dùng Great Expectations) và Freshness Check cũng được tích hợp thành công để phát hiện các dị thường (Silent Failures).

Baseline Pipeline đã sinh ra đầy đủ bộ artifacts: JSON raw, CSV sạch, Vector Index, metrics JSON và báo cáo Markdown.

Trong kịch bản Corruption, việc làm hỏng dữ liệu (như xóa một số bản ghi, sửa ngày tháng) đã khiến Quality Gate báo `FAIL` (Stale Ratio tăng lên 31.8% vượt ngưỡng 25%, trùng lặp ID, sai độ dài văn bản). Việc này lập tức làm giảm mạnh chất lượng của RAG (Hit Rate giảm từ 1.0 xuống 0.7, Score giảm từ 5.0 xuống 3.4).

Nhờ có hệ thống Observability, nhóm đã có căn cứ kích hoạt hàm Repair để khôi phục dữ liệu nguyên bản từ Raw Snapshot, lập tức đưa toàn bộ các chỉ số về lại trạng thái chuẩn 100% của Baseline. Không còn blocker nào cản trở.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref API
    -> raw response/raw records
    -> cleaning và data modeling
    -> embedding (OpenAI) + ChromaDB index
    -> evaluation baseline
    -> quality/freshness reports
    -> corruption
    -> re-index và re-evaluate
    -> repair từ dữ liệu nguồn
    -> comparison report
```

### Trách nhiệm của từng khối

| Khối             | Input          | Xử lý chính             | Output/artifact          | Owner          |
| ----------------- | -------------- | -------------------------- | ------------------------ | -------------- |
| Ingestion         | Crossref API | Lấy thông tin bài báo khoa học | `raw_records.json` | Đặng Đình Đoàn |
| Cleaning          | `raw_records.json` | Lọc Null, chuẩn hóa date, gộp authors | `papers_clean.json/csv` | Ngô Anh Khoa |
| Embedding/index   | `papers_clean.json` | OpenAI Embeddings, Chroma HNSW | `data/embeddings/` | Lê Văn Việt |
| Evaluation        | RAG answers | So sánh Ground truth với answers | `baseline_metrics.json` | Ngô Anh Khoa |
| Observability     | Clean DataFrame | GX validation, check age_days | `phase1_report.md` | Mai Quang Dũng |
| Corruption/repair | Clean DataFrame | Corrupt data và sau đó Repair | `corruption_log.json` / Repaired data | Đặng Đình Đoàn (Corrupt), Lê Văn Việt (Repair) |
| Orchestration     | Toàn bộ hệ thống | Điều phối 2 phases | Terminal / Log | Lê Văn Việt |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình             | Giá trị sử dụng |
| ---------------------------- | ------------------- |
| `LLM_PROVIDER`             | openai |
| `LLM_MODEL`                | gpt-4o-mini (OpenAI) |
| Embedding model              | text-embedding-3-small (OpenAI) |
| Số lượng Crossref records | 24 |
| Retrieval`top_k`           | 3 |
| Freshness threshold          | 180 days |

### Lệnh cài đặt

```bash
uv pip install -e .
```

### Lệnh chạy

Baseline:

```bash
uv run python script/run_phase1.py
```

Corruption flow:

```bash
uv run python script/run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh             | Trạng thái                                    | Bằng chứng                         |
| ----------------- | ----------------------------------------------- | ------------------------------------ |
| Baseline pipeline | Thành công | `data/reports/phase1_report.md` |
| Corruption flow   | Thành công | `data/reports/corruption_report.md` |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính                | Giá trị                             |
| --------------------------- | ------------------------------------- |
| Source                      | https://api.crossref.org/works |
| Query/filter                | machine learning, AI, RAG |
| Khối lượng lấy    | 24 records (Snapshot mode) |

### Quy tắc cleaning

| Quy tắc                                 | Quality dimension liên quan |
| ---------------------------------------- | ---------------------------- |
| Loại bỏ dòng thiếu title hoặc abstract | Completeness  |
| Fill giá trị cho cột published date | Validity |

## 6. Evaluation setup

| Thành phần                             | Cấu hình thực tế          |
| ---------------------------------------- | ----------------------------- |
| Embedding model                          | OpenAI Embeddings (`langchain_openai`) |
| Vector store/collection                  | ChromaDB |
| Retrieval`top_k`                       | 3 |
| LLM provider/model                       | OpenAI (gpt-4o-mini) |

Test set được giữ nguyên qua 3 trạng thái để đảm bảo hệ quy chiếu không thay đổi. Nếu đổi câu hỏi hoặc ground truth, mọi sự so sánh điểm số bị lệch do lỗi hay do RAG sẽ không còn ý nghĩa.

## 7. Kết quả baseline

### Baseline metrics

| Metric                 |       Giá trị | Diễn giải                             |
| ---------------------- | --------------: | --------------------------------------- |
| `retrieval_hit_rate` |     1.000 | 100% trả về đúng Context |
| `mean_token_f1`      |     1.000 | Token F1 hoàn hảo |
| `judge_accuracy`     |     1.000 | RAG trả lời chính xác 100% |
| `mean_judge_score`   |     5.000 | Điểm judge tuyệt đối |

## 8. Data quality và freshness

| Check        | Cột | Kết quả baseline |
| ------------ | ----------------- | ----------------------- |
| Null check | `paper_id`, `title`, `text` | PASS |
| Unique check | `paper_id` | PASS |
| Length check | `summary` | PASS |

Freshness: Ngưỡng 180 ngày. Stale ratio = 0.042 (<= 0.25). Đạt tiêu chuẩn Fresh.

## 9. Corruption scenarios và repair

| Corruption         | Tác động thực tế | Cách repair   |
| ------------------ | --------------------- | -------------- |
| Gây trùng lặp ID, sửa đổi Date về xa hơn | Chất lượng RAG giảm rõ rệt, Stale ratio tăng lên 0.318 | Load lại snapshot từ Raw records (`data/raw/`) và clean lại từ đầu. |

## 10. So sánh baseline, corrupted và repaired

| Metric/signal            | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi |
| ------------------------ | -------: | --------: | -------: | -----------------------: | --------------: |
| `retrieval_hit_rate`   |      1.0 |       0.7 |      1.0 |                      -0.3 |             [OK] Khôi phục hoàn toàn |
| `mean_token_f1`        |      1.0 |       0.64 |      1.0 |                      -0.36 |             [OK] Khôi phục hoàn toàn |
| `judge_accuracy`       |      1.0 |       0.7 |      1.0 |                      -0.3 |             [OK] Khôi phục hoàn toàn |
| `mean_judge_score`     |      5.0 |       3.4 |      5.0 |                      -1.6 |             [OK] Khôi phục hoàn toàn |
| Quality checks pass/fail |      True |       False |      True |                      - |             [OK] |
| Freshness status         |      True |       False |      True |                      - |             [OK] |

**Quan hệ nhân quả:**
1. Khi tiêm dữ liệu bẩn (Corruption), các cột bị null, ID trùng lặp và Date trở nên cũ (Stale) -> Quality Gate phát hiện FAILED và Freshness báo FALSE -> Context do RAG truy xuất bị nhiễu (Hit Rate giảm 30%) -> Điểm trả lời (Judge Score) tụt từ 5.0 xuống 3.4.
2. Dựa vào cờ cảnh báo của Observability (TV3), hệ thống gọi lệnh Repair để khôi phục dữ liệu từ gốc -> Quality Gate báo PASS trở lại -> Agent truy xuất chuẩn xác như cũ (Score phục hồi 100%).

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Pipeline bị văng `UnicodeEncodeError` ở Windows Console khi in các Emoji và Tiếng Việt.
- **Nguyên nhân:** Console của hệ điều hành Windows dùng mã `cp1252` thay vì `utf-8`.
- **Cách xử lý:** Đã xóa bớt emoji, cấu hình chạy lệnh với `$env:PYTHONIOENCODING="utf-8"`.
- **Cách xác minh:** Chạy `python script/run_phase1.py` trơn tru không lỗi.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Hướng cải thiện |
| --------------------- | ----------------------------------------- |
| Dữ liệu Snapshot 24 records còn khá ít | Fetch thử dữ liệu hàng nghìn bài báo thật từ API để đo lường độ chịu tải của Indexer. |
| Chỉ kiểm tra cấu trúc | Tích hợp thêm các model NLP nhỏ để kiểm tra xem đoạn văn bản tiếng Anh có mang ý nghĩa học thuật không. |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [x] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng.
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
