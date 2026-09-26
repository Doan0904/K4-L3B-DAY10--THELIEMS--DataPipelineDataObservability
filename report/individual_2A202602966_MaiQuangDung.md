# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Mai Quang Dũng             |
| MSSV               | 2A202602966        |
| Khóa/Lớp         | Lớp K4-L3B                      |
| Tên nhóm         | TheLiems            |
| Vai trò chính    | Thành viên 3 (Observability owner) |
| Repository         | https://github.com/Doan0904/K4-L3B-DAY10--TenNhom--DataPipelineDataObservability |
| Ngày hoàn thành | 2026-09-26               |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Observability & Quality | `src/observability/quality.py` | `pd.DataFrame` (dữ liệu clean, corrupted, repaired) | Kết quả kiểm tra chất lượng (Quality Gate) và Freshness (Độ tươi mới) | Hoàn thành |
| Reporting | `src/observability/reporting.py` | Metrics RAG, kết quả Quality/Freshness | File báo cáo Markdown (`phase1_report.md`, `corruption_report.md`) | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Cấu hình OpenAI Embeddings | Tích hợp hệ thống chung | Giúp agent embedding ổn định và chất lượng thay cho local MiniLM. |
| Xử lý Unicode Encode Error trên Windows Console | Hỗ trợ quá trình Integration (TV4) | Pipeline chạy mượt mà, không văng lỗi khi in báo cáo tiếng Việt ra console. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Xây dựng Data Quality Gate | `quality.py` / `run_data_quality_checks` | `data/quality/*_quality_report.json` | Chạy lệnh pipeline, xem file JSON báo cáo. |
| Tính toán Data Freshness | `quality.py` / `build_freshness_report` | `data/quality/*_freshness_report.json` | Mở báo cáo Markdown hoặc kiểm tra giá trị `is_fresh` ở JSON. |
| Tổng hợp Báo cáo Markdown | `reporting.py` | `data/reports/phase1_report.md` và `corruption_report.md` | Mở thư mục `data/reports/` kiểm tra bảng biểu so sánh. |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Hệ thống RAG có thể chạy bình thường nhưng sinh ra câu trả lời "ảo" hoặc sai nếu dữ liệu đầu vào bị lỗi cấu trúc (thiếu title, trùng lặp paper_id) hoặc dữ liệu quá cũ (Stale Data). Nhiệm vụ của tôi là xây dựng "trạm kiểm dịch" (Quality Gate) và báo cáo để phát hiện "Silent Failure" này.

### Cách triển khai

1. **Quality Gate:** Sử dụng thư viện `great_expectations` ở chế độ `ephemeral` (trong RAM) để kiểm tra:
   - Các cột `paper_id`, `title`, `text_for_embedding` không bị `null`.
   - `paper_id` phải unique (không trùng lặp).
   - Số lượng dòng (row count) phải nằm trong khoảng cho phép.
2. **Freshness:** Dựa vào cột `age_days` do Thành viên 2 tính toán. Tôi đặt ngưỡng `threshold_days = 180`, đếm số lượng dòng cũ hơn ngưỡng này (stale_rows). Nếu tỉ lệ cũ vượt quá `max_stale_ratio = 0.25`, dữ liệu sẽ bị đánh dấu là hết hạn (`is_fresh = False`).
3. **Reporting:** Code hàm sinh ra Markdown so sánh tự động, parse từ điển dict của bundle metrics, làm tròn tỉ lệ thập phân (Float) và hiển thị kết quả "Khôi phục / Chưa khôi phục" trong Phase 2.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | `clean_df` hoặc `corrupted_df`, RAG Evaluation Bundle |
| Output                         | JSON lưu trữ kết quả và File báo cáo Markdown |
| Module phụ thuộc             | `core/config.py` (để lấy đường dẫn) |
| Module sử dụng output        | `phase1.py` và `corruption_flow.py` |
| Điều kiện lỗi cần xử lý | Lọc bỏ dữ liệu rác (không phải kiểu số) khi vẽ bảng báo cáo, xử lý lỗi Unicode trên console. |

### Cách xác minh

```bash
uv run python script/run_phase1.py
```

- **Kết quả mong đợi:** In ra báo cáo có Check dấu [PASS] hoặc [OK]. File `phase1_report.md` xuất hiện.
- **Kết quả thực tế:** Code in thành công. Báo cáo lưu thành công tại `data/reports/`.
- **Artifact/log:** `data/reports/phase1_report.md`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần vẽ bảng so sánh RAG Metrics (kiểu dữ liệu Float) ở báo cáo `corruption_report.md`.
- **Các phương án đã cân nhắc:** (1) Hardcode từng key metric; (2) Duyệt tự động toàn bộ dict.
- **Phương án đã chọn:** Chọn phương án 2 (Duyệt tự động) nhưng có bộ lọc `isinstance(float, int)` để bỏ qua dictionary của cấu hình Ragas.
- **Lý do:** Trade-off: tốn thêm tí dòng code filter nhưng pipeline linh hoạt, dù TV2 có đổi bộ metric RAG thì bảng Markdown vẫn vẽ đúng không bị văng lỗi.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f680' in position 0`
- **Nguyên nhân gốc:** Khi chạy code trên Console Windows (mã cp1252 mặc định), các ký tự Tiếng Việt hoặc Emoji (`🚀`, `✅`) không parse được.
- **Cách xử lý:** Bỏ emoji, thay bằng dạng text `[START]`, `[OK]`. Hỗ trợ đổi cấu hình biến môi trường `$env:PYTHONIOENCODING="utf-8"` để đọc tiếng Việt chuẩn xác.
- **Cách xác minh sau khi sửa:** Chạy lại `python script/run_phase1.py` không còn văng Exception.

## 7. Hiểu biết về luồng end-to-end

1. Dữ liệu từ Crossref API lấy về (TV1) -> Làm sạch bằng Pandas, tạo cột `text_for_embedding` (TV2) -> Nhúng bằng OpenAI Embeddings lưu vào ChromaDB -> Agent tra cứu vector.
2. Ground-truth list lưu danh sách Document IDs chứa câu trả lời chuẩn. Hệ thống đo xem Retrieval trả ra kết quả có khớp ID chuẩn đó không (Hit Rate).
3. Quality check kiểm tra định dạng/null (Cấu trúc). Freshness kiểm tra độ tươi mới thời gian (Logic nghiệp vụ).
4. Phải dùng cùng Test Set để hệ quy chiếu RAG là nhất quán, nếu khác test set sẽ không thể so sánh số liệu giữa Corrupted và Baseline.
5. Repair thành công khi Quality Gate báo PASS trở lại, Freshness báo YES, và `retrieval_hit_rate` hay `judge_accuracy` phục hồi về mức Baseline.

## 8. Phân tích kết quả

(Vui lòng mở file `data/reports/corruption_report.md` để xem bảng metrics và tự điền nhận xét của bạn vào đây sau khi flow 2 kết thúc)

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Hiểu rõ Data Observability:** Data Pipeline không chỉ là đổ dữ liệu từ A sang B, mà phải liên tục giám sát "Sức khỏe" của dòng chảy dữ liệu.
2. **Khái niệm "Silent Failure":** Dữ liệu có thể pass mọi Rule, không quăng lỗi Exception nào, nhưng model AI trả lời sai do dữ liệu Stale (Cũ/Hết hạn).
3. **Giá trị của Data Contract:** Contract giúp định nghĩa rõ ai gửi dữ liệu gì, schema thế nào, nếu vi phạm thì Quality Gate sẽ chặn đứng RAG.

### Nếu có thêm thời gian

Tôi sẽ viết thêm 1 rule Expectation check ngữ nghĩa của đoạn văn bản (ví dụ không chứa toàn ký tự đặc biệt) để Quality Gate chặt chẽ hơn nữa.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Mai Quang Dũng  
**Ngày xác nhận:** 2026-09-26
