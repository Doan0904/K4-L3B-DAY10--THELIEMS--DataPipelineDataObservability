# Danh Sách Thành Viên & Báo Cáo Phân Công Nhóm

- **Tên Nhóm:** `THE LIEMS`
- **Mã Nhóm / Lớp:** `K4-L3B`
- **Tên Repository Nộp Bài:** `https://github.com/Doan0904/K4-L3B-DAY10--THELIEMS--DataPipelineDataObservability`

---

## # Thành viên

| STT | Họ và tên | MSSV | Email | Vai trò & Phân công công việc | Báo cáo cá nhân |
|---:|---|---|---|---|---|
| 1 | Đặng Đình Đoàn | 2A202602927 | dangnhatdoan@gmail.com | TV1 — Ingestion & Corruption owner; Hỗ trợ Pipeline Integration | `report/individual_2A202602927_DangDinhDoan.md` |
| 2 | Ngô Anh Khoa | 2A202602965 | khoaanhngo113@gmail.com | TV2 — Data Cleaning & Benchmark Test-set owner (`cleaning.py`, `testset.py`) | `report/individual_2A202602965_NgoAnhKhoa.md` |
| 3 | Mai Quang Dũng | 2A202602966 | maidung2005bk18@gmail.com | TV3 — Observability & Reporting owner (`quality.py`, `reporting.py`) | `report/individual_2A202602966_MaiQuangDung.md` |
| 4 | Lê Văn Việt | 2A202602504 | vanviet0611@gmail.com | TV4 — Pipeline Integration owner (`phase1.py`, `corruption_flow.py`) | `report/individual_2A202602504_LeVanViet.md` |

---

## # Cá nhân

### ## DangDinhDoan-2A202602927
- **Vai trò:** TV1 — Ingestion & Corruption owner; Hỗ trợ Pipeline Integration.
- **Công việc chi tiết đã hoàn thành:**
  - Xây dựng module thu thập Crossref API với cơ chế Retry & Fallback offline an toàn trong `src/ingestion/crossref.py`.
  - Triển khai kịch bản làm bẩn dữ liệu 6 scenarios trong `src/ingestion/corruption.py` và xuất `corruption_log.json`.
  - Hỗ trợ kết nối và chạy thực thi pipeline Baseline (`script/run_phase1.py`) và Corruption Flow (`script/run_corruption_flow.py`).
- **Điều học được / Đóng góp chính:**
  - Hiểu sâu sắc về cơ chế Data Lineage, bảo toàn snapshot dữ liệu thô phục vụ quy trình Idempotent Repair khôi phục 100% dữ liệu gốc.

### ## NgoAnhKhoa-2A202602965
- **Vai trò:** TV2 — Data Cleaning & Benchmark Test-set owner.
- **Công việc chi tiết đã hoàn thành:**
  - Chuẩn hóa schema, làm sạch khoảng trắng, lọc bỏ JATS XML tags và khử trùng lặp `paper_id` trong `src/ingestion/cleaning.py`.
  - Tính toán chính xác trường `age_days` phục vụ Freshness SLA và xây dựng hàm chuẩn hóa 5 dòng `build_text_for_embedding`.
  - Thiết kế bộ đánh giá chuẩn 10 câu hỏi tất định (`data/eval/test_set.json`) phủ 4 nhóm nghiệp vụ (`summary`, `authors`, `date`, `categories`) trong `src/evaluation/testset.py`.
- **Điều học được / Đóng góp chính:**
  - Tầm quan trọng của Data Contract trong việc liên kết các tầng dữ liệu (Pandas $\rightarrow$ ChromaDB $\rightarrow$ LLM Judge), hiểu cách thức bẫy lỗi Silent Failure thông qua các chốt kiểm dịch Data Quality Gate.

### ## MaiQuangDung-2A202602966
- **Vai trò:** TV3 — Data Observability & Reporting owner.
- **Công việc chi tiết đã hoàn thành:**
  - Thiết lập Data Quality Gate sử dụng Ephemeral Context theo chuẩn mới **Great Expectations 1.x** trong `src/observability/quality.py`.
  - Thiết lập công cụ giám sát Freshness SLA với ngưỡng `age_days > 180` và tỷ lệ cho phép tối đa 25%.
  - Tự động sinh báo cáo đối chiếu 3 trạng thái (Baseline, Corrupted, Repaired) dạng Markdown trong `src/observability/reporting.py`.
- **Điều học được / Đóng góp chính:**
  - Nắm vững cách xây dựng hệ thống giám sát chất lượng dữ liệu tự động, kịp thời ngăn chặn dữ liệu bẩn và dữ liệu quá hạn thâm nhập vào RAG vector store.

### ## LeVanViet-2A202602504
- **Vai trò:** TV4 — Pipeline Integration owner.
- **Công việc chi tiết đã hoàn thành:**
  - Nối pipeline baseline trong `src/pipelines/phase1.py`: ingest → clean → index → giữ nguyên test set → evaluate → quality gate → `phase1_report.md`.
  - Nối pipeline corruption trong `src/pipelines/corruption_flow.py`: làm bẩn → quality gate → đánh giá → repair từ `crossref_records.json` → đánh giá lại → bảng 3 trạng thái.
  - Kiểm tra repair bằng nội dung (không chỉ `paper_id`) và chạy repair hai lần cùng `run_date` để chứng minh idempotent.
  - Gắn từng câu trong `test_set.json` với kịch bản corruption tương ứng, ghi `data/results/question_impact.json`.
  - Ghi `judge_mode` vào báo cáo baseline để phân biệt điểm LLM với heuristic fallback.
- **Điều học được / Đóng góp chính:**
  - Hit rate và judge accuracy có thể cùng bằng 0.7 mà không phải cùng một tập câu. Quality gate bắt trùng ID, summary rỗng và dữ liệu cũ; riêng việc mất bài mới (`drop_latest_records`) chỉ lộ ra ở bộ đánh giá.
