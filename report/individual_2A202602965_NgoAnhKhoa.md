# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Ngô Anh Khoa             |
| MSSV               | 2A202602965                     |
| Khóa/Lớp         | K4 — L3B              |
| Tên nhóm         | THE LIEMS     |
| Vai trò chính    | TV2 — Data model & Benchmark Test-set owner |
| Repository         | https://github.com/Doan0904/K4-L3B-DAY10--THELIEMS--DataPipelineDataObservability |
| Ngày hoàn thành | 2026-09-26               |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái |
| ------------------ | --------------------- | ---------------- | ----------------- | :---: |
| Data Cleaning & Modeling | `src/ingestion/cleaning.py`: `build_clean_dataframe`, `build_text_for_embedding` | Danh sách 24 `PaperRecord` từ `load_raw_records` + `run_date` (UTC) | Cleaned DataFrame 24 dòng, bảo toàn 11 cột gốc + 5 cột phái sinh, sẵn sàng nạp ChromaDB | Hoàn thành |
| Benchmark Test Set | `src/evaluation/testset.py`: `build_test_set` | Cleaned DataFrame | File `data/eval/test_set.json` gồm 10 câu hỏi chuẩn hóa phủ 4 dạng nghiệp vụ | Hoàn thành |

Tôi chịu trách nhiệm làm cầu nối trung tâm của Data Pipeline:
- Nhận dữ liệu thô từ **TV1** (`crossref.py`).
- Chuẩn hóa schema, tính toán trường thời gian `age_days` và định dạng văn bản embedding `text_for_embedding` làm đầu vào chuẩn cho **TV3** (Quality Gate & Freshness SLA) và **TV4** (ChromaDB Indexer).
- Tạo ra bộ testset chuẩn hóa dùng chung xuyên suốt 3 pha đánh giá (Baseline, Corrupted, Repaired).

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả và bằng chứng |
| --- | --- | --- |
| Triển khai hàm `load_raw_records` sớm trong `crossref.py` | Hỗ trợ TV1 và kiểm thử pipeline chung | Nạp dữ liệu offline snapshot `crossref_records.json` ngay cả khi API gặp rate-limit hoặc mất mạng |
| Xuất bản hàm `build_text_for_embedding` độc lập | TV1 (`src/ingestion/corruption.py`) | Giúp TV1 tái sử dụng logic sinh văn bản embedding đồng nhất khi thực hiện tiêm dữ liệu bẩn (Corruption) |
| Lưu tạm `data/clean/papers_clean.json` ở giai đoạn đầu | TV1 & TV3 | Giúp TV3 có dữ liệu sạch để kiểm thử sớm Great Expectations 1.x và Freshness SLA |

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Chuẩn hóa chuỗi, xử lý rác JATS/khoảng trắng, chuẩn hóa ngày tháng `YYYY-MM-DD` | `src/ingestion/cleaning.py` | 24 dòng dữ liệu sạch, không còn khoảng trắng thừa, `published`/`updated` dạng chuẩn | `df["title"].str.strip() != ""` |
| Tính toán `age_days` và cột `summary_chars` | `src/ingestion/cleaning.py` | Cột `age_days` kiểu số nguyên, phục vụ Freshness SLA kiểm tra ngưỡng 180 ngày | `df["age_days"] >= 0` |
| Xây dựng định dạng chuẩn 5 dòng `text_for_embedding` | `src/ingestion/cleaning.py::build_text_for_embedding` | Khối text chuẩn cấu trúc cho embedding model | In ra dòng đầu tiên kiểm tra 5 prefix: `Title:`, `Authors:`, `Published:`, `Categories:`, `Summary:` |
| Khử trùng lặp trên `paper_id` và lọc dòng rác | `src/ingestion/cleaning.py` | 24 bản ghi duy nhất, không trùng DOI | `df["paper_id"].nunique() == 24` |
| Sinh bộ 10 câu hỏi kiểm thử benchmark tất định (deterministic) | `src/evaluation/testset.py::build_test_set` | `data/eval/test_set.json` có đúng 10 câu hỏi, tiêu đề đặt trong `'...'` | `len(test_set) == 10` |

### Output cụ thể do phần việc của tôi tạo ra:
- **`data/clean/papers_clean.csv` & `data/clean/papers_clean.json`**: Dataset sạch chuẩn hóa 24 bài báo khoa học.
- **`data/eval/test_set.json`**: Bộ 10 câu hỏi đánh giá chuẩn hóa được giữ cố định làm thước đo đối chứng cho cả 3 trạng thái.

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
1. **Schema Heterogeneity & Vector Compatibility:** Dữ liệu thô từ API bên ngoài chứa khoảng trắng thừa, định dạng ngày tháng không đồng nhất. Vector store ChromaDB chỉ chấp nhận metadata nguyên thủy (`str`, `int`, `float`, `bool`) và sẽ văng exception nếu gặp `pd.Timestamp`.
2. **Text Representation for Retrieval:** Embedding model cần một khối văn bản có cấu trúc rõ ràng để vừa nắm được ngữ cảnh tác giả, thời gian xuất bản, phân loại danh mục, vừa nắm được nội dung tóm tắt.
3. **Rigorous Benchmark Evaluation:** Để kiểm chứng khả năng phát hiện lỗi của hệ thống Observability và suy giảm chất lượng của RAG, bộ câu hỏi test phải được chọn một cách có chiến lược, phủ đều các nhóm nghiệp vụ và bắt buộc phải chịu tác động trực tiếp khi dữ liệu bị tiêm lỗi.

### Cách triển khai
* **Data Cleaning Pipeline (`build_clean_dataframe`):**
  1. Chuyển đổi danh sách `PaperRecord` sang `pd.DataFrame`.
  2. Dùng `normalize_whitespace` làm sạch khoảng trắng trong `title` và `summary`. Strip từng tác giả và phân loại danh mục, loại bỏ các phần tử rỗng.
  3. Chuẩn hóa `published` và `updated` sang chuỗi `"YYYY-MM-DD"`.
  4. Tính `age_days = (run_date.date() - date.fromisoformat(published)).days`.
  5. Tạo 4 cột helper: `authors_joined = ", ".join(authors)`, `categories_joined = ", ".join(categories)`, `summary_chars = len(summary)`, và `text_for_embedding` qua hàm độc lập.
  6. Lọc bỏ dòng thiếu title/summary, deduplicate theo `paper_id` (`keep="first"`), sắp xếp theo ngày công bố giảm dần (`published DESC, paper_id ASC`), reset index.
* **Benchmark Test-Set Generator (`build_test_set`):**
  1. Kiểm tra số lượng bản ghi tối thiểu $\ge 10$.
  2. Chọn tất định 10 bài trải đều trên tập dữ liệu đã sort (`df.iloc[::2].head(10)`).
  3. Phân bổ chính xác theo 4 nhóm nghiệp vụ:
     - 3 câu `summary`: *"What is the summary of the paper '<title>'?"* $\rightarrow$ Ground truth: câu đầu của summary (`first_sentence`).
     - 3 câu `authors`: *"Who authored the paper '<title>'?"* $\rightarrow$ Ground truth: `authors_joined`.
     - 2 câu `date`: *"When was the paper '<title>' published?"* $\rightarrow$ Ground truth: `published`.
     - 2 câu `categories`: *"What categories does the paper '<title>' belong to?"* $\rightarrow$ Ground truth: `categories_joined`.
  4. Tiêu đề bài báo bắt buộc bọc trong dấu nháy đơn `'...'` để regex trong `qa.py` (`re.search(r"'([^']+)'", question)`) bóc tách và tra cứu chính xác.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `records: list[PaperRecord]`, `run_date: datetime` |
| Output | `pd.DataFrame` 16 cột (11 gốc + 5 phái sinh), `data/eval/test_set.json` |
| Module phụ thuộc | `ingestion.crossref` (`PaperRecord`, `load_raw_records`), `core.utils` (`normalize_whitespace`, `first_sentence`, `write_json`) |
| Module sử dụng output | `retrieval.index` (`_build_documents`), `observability.quality` (`run_data_quality_checks`, `build_freshness_report`), `evaluation.metrics` (`evaluate_pipeline`), `ingestion.corruption` |
| Điều kiện lỗi cần xử lý | Bản ghi thiếu title/summary, `categories` rỗng, `len(df) < 10`, định dạng ngày sai lệch |

### Cách xác minh
```bash
# Kiểm tra Data Cleaning (Nhiệm vụ CP1)
python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print(f'Tín hiệu hoàn thành: Clean thành công {len(df)} dòng'); print(df.iloc[0]['text_for_embedding'])"

# Kiểm tra Benchmark Test Set (Nhiệm vụ CP2)
python -c "from core.config import load_settings; from evaluation.testset import build_test_set; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); ts=build_test_set(df, s.paths.eval_testset); print(f'Tín hiệu hoàn thành: Sinh được {len(ts)} câu hỏi test')"
```
- **Kết quả mong đợi:** In ra `Clean thành công 24 dòng` với đủ 5 dòng text template; in ra `Sinh được 10 câu hỏi test`.
- **Kết quả thực tế:** Cả 2 lệnh đều trả về chính xác như kỳ vọng, không lỗi runtime.

---

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Lựa chọn kiểu dữ liệu lưu trữ cột ngày tháng `published` trong cleaned DataFrame và cách chọn mẫu câu hỏi cho bộ testset.
- **Các phương án đã cân nhắc:**
  1. *Phương án A:* Đổi `published` sang kiểu `pd.Timestamp` để tiện tính toán ngày tháng và chọn 10 câu hỏi ngẫu nhiên bằng `random.sample`.
  2. *Phương án B:* Giữ `published` là kiểu chuỗi thuần `"YYYY-MM-DD"`, tính `age_days` bằng phép trừ `date` thông thường, và chọn 10 bài cố định (deterministic) với bước nhảy 2 (`iloc[::2].head(10)`).
- **Phương án đã chọn:** **Phương án B**.
- **Lý do:**
  1. ChromaDB chỉ hỗ trợ metadata kiểu `str, int, float, bool`. Nếu dùng `Timestamp`, khi nạp vào vector collection sẽ gây lỗi serializer crash toàn bộ pipeline.
  2. Việc chọn câu hỏi tất định (`iloc[::2].head(10)`) đảm bảo tính tái lập (reproducibility 100%). Đặc biệt, nó lấy cả những bài mới nhất ở đầu mảng (chính là những bài sẽ bị kịch bản "Drop latest 20% records" của TV1 xóa đi trong pha Corruption), giúp phản ánh trung thực sự sụp đổ của Retrieval Hit Rate.
- **Bằng chứng:** Baseline pipeline đạt Hit Rate 1.0, khi bị Corruption Hit Rate tụt ngay xuống 0.7 do câu hỏi trúng vào các bài bị drop.

---

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Môi trường ban đầu gặp lỗi thiếu công cụ CLI `uv` trên PowerShell:
  `uv : The term 'uv' is not recognized as the name of a cmdlet, function, script file, or operable program.`
- **Lệnh tái hiện:** `uv sync`
- **Nguyên nhân gốc:** Máy tính Windows chưa cài đặt `uv` trong PATH. Ngoài ra, file `uv.lock` của dự án đang khóa gói PyTorch CUDA rất nặng (~2.5 - 3 GB), nếu chạy `uv sync` sẽ tải bản GPU gây nghẽn băng thông và tốn thời gian.
- **Cách xử lý:** Kích hoạt virtual environment sẵn có và chuyển sang phương án cài đặt Torch CPU nhẹ (~200 MB) bằng lệnh:
  `pip install torch --index-url https://download.pytorch.org/whl/cpu`
  Sau đó cài đặt các gói phụ thuộc qua editable package `pip install -e .`.
- **Cách xác minh sau khi sửa:** Chạy kiểm tra `python -c "import chromadb, great_expectations, sentence_transformers; print('Environment Ready!')"` thành công.
- **Điều học được:** Luôn nắm rõ bản chất của virtualenv và package manager; ưu tiên các build tối ưu tài nguyên (CPU wheels) trong môi trường phòng lab thực chiến.

---

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index:** Crossref API trả về payload JSON thô $\rightarrow$ `crossref.py` lưu snapshot gốc và parse thành `PaperRecord` $\rightarrow$ `cleaning.py` loại bỏ rác, tính `age_days`, tạo khối 5 dòng `text_for_embedding` $\rightarrow$ `index.py` dùng Embedding model tạo vector và lập chỉ mục HNSW trong ChromaDB collection `papers-baseline`.
2. **Evaluation set và ground-truth document IDs:** File `test_set.json` lưu cặp `(question, ground_truth, ground_truth_doc_ids)`. Khi agent trả lời, hàm đánh giá so sánh IDs tài liệu do ChromaDB trả về với `ground_truth_doc_ids` để tính **Hit Rate**, và so sánh chuỗi câu trả lời với `ground_truth` để tính **Token F1** và **Judge Score**.
3. **Quality checks khác freshness monitoring ở điểm nào:**
   - **Quality checks:** Kiểm tra tính toàn vẹn cấu trúc và cú pháp của dữ liệu (Schema, Null check, Uniqueness, Min Length).
   - **Freshness monitoring:** Giám sát khía cạnh ngữ nghĩa theo thời gian. Dữ liệu cũ (ví dụ xuất bản cách đây nhiều năm) vẫn hoàn toàn đúng schema, không bị null, nhưng nếu dùng cho hệ sinh thái RAG đòi hỏi thông tin cập nhật sẽ dẫn đến câu trả lời lỗi thời.
4. **Vì sao phải dùng cùng test set cho 3 trạng thái:** Để đảm bảo tính khách quan trong phương pháp thực nghiệm khoa học. Test set là "thước đo cố định". Nếu thay đổi câu hỏi giữa các pha, sự thay đổi điểm số không thể xác định là do chất lượng dữ liệu hay do độ khó/dễ của câu hỏi mới.
5. **Repair được xem là thành công khi:**
   - Quality Gate: chuyển từ `False` về lại `True` (100% expectations pass).
   - Freshness SLA: `is_fresh = True` (tỷ lệ cũ quay về $\le 25\%$).
   - RAG Metrics: `retrieval_hit_rate` và `mean_token_f1` phục hồi 100% về mức Baseline ban đầu.

---

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.000 | 0.700 | 1.000 | Giảm 30% do các bài mới nhất trong testset bị kịch bản drop xóa mất; phục hồi hoàn toàn sau Repair. |
| `mean_token_f1` | 1.000 | 0.640 | 1.000 | Sụt giảm do nhiễu tiêm vào tóm tắt và mất tài liệu; khôi phục hoàn hảo 1.0 sau Repair. |
| `judge_accuracy` | 1.000 | 0.700 | 1.000 | RAG Agent không còn trích xuất đúng đáp án khi context bị thiếu hụt; hồi phục 1.0. |
| `mean_judge_score` | 5.000 | 3.400 | 5.000 | Điểm đánh giá giảm từ 5.0 xuống 3.4 trên dữ liệu bẩn; trở lại 5.0 tuyệt đối sau Repair. |
| Quality checks | True | False | True | Great Expectations 1.x bắt chính xác lỗi độ dài summary và trùng lặp ID. |
| Freshness status | True | False | True | Bắt thành công lỗi dữ liệu hết hạn khi Stale Ratio tăng vọt lên 31.8%. |

### Kết luận từ số liệu
1. **Chuỗi sự cố:** Dữ liệu bị tiêm lỗi $\rightarrow$ Quality Gate báo `False` & Freshness báo `False` $\rightarrow$ RAG Hit Rate giảm 30%, Mean Judge Score tụt từ 5.0 xuống 3.4 (Minh chứng cho hiện tượng **Silent Failure**).
2. **Chuỗi phục hồi:** Kích hoạt Idempotent Repair từ raw snapshot $\rightarrow$ Quality Gate và Freshness phục hồi `True` $\rightarrow$ Toàn bộ RAG metrics khôi phục hoàn toàn 100% về mức Baseline.

---

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất
1. **Data Contract là cốt lõi:** Trong pipeline đa tầng, việc thống nhất schema, kiểu dữ liệu nguyên thủy (đặc biệt cho vector store) và định dạng embedding quyết định tính ổn định của toàn hệ thống.
2. **Tầm quan trọng của Observability:** Silent Failure nguy hiểm hơn System Crash vì hệ thống vẫn trả về HTTP 200 nhưng câu trả lời sai lệch hoàn toàn. Data Quality Gate đóng vai trò như chốt kiểm dịch bảo vệ mô hình AI.
3. **Tính Idempotent trong Data Engineering:** Luôn bảo tồn raw data snapshot nguyên bản làm điểm tựa lineage để có thể tự phục hồi hệ thống bất kỳ lúc nào mà không phụ thuộc vào kết nối mạng bên ngoài.

### Nếu có thêm thời gian
Tôi sẽ xây dựng một bộ Dynamic Test Set Generator tích hợp kỹ thuật Semantic Perturbation để tự động sinh hàng trăm câu hỏi kiểm thử phức tạp hơn (Multi-hop reasoning), giúp đánh giá độ bền bỉ của RAG Agent ở quy mô lớn.

---

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Ngô Anh Khoa  
**Ngày xác nhận:** 2026-09-26  
