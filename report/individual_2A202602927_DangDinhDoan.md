# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin        | Nội dung |
| ---------------- | -------- |
| Họ và tên        | Đặng Đỉnh Đoàn |
| MSSV             | 2A202602927 |
| Khóa/Lớp         | K4 — L3B |
| Tên nhóm         | THE LIEMS |
| Vai trò chính    | TV1 — Source & Corruption owner; hỗ trợ tích hợp pipeline (TV4) |
| Repository       | https://github.com/Doan0904/K4-L3B-DAY10--TenNhom--DataPipelineDataObservability |
| Ngày hoàn thành  | 2026-09-26 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Raw ingestion | `src/ingestion/crossref.py`: `parse_crossref_payload`, `fetch_source_records`, `load_raw_records` | Crossref `/works` payload (live API hoặc snapshot `data/raw/crossref_response.json`) | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` (24 `PaperRecord`) | Hoàn thành (commit `d8c6391`) |
| Corruption suite | `src/ingestion/corruption.py`: `corrupt_clean_dataframe` | Clean DataFrame (schema do TV2 tạo) | DataFrame bị tiêm 6 loại lỗi + `data/results/corruption_log.json` | Hoàn thành (commit `f816e9f`) |
| Pipeline orchestration | `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py` (`main`, `_repair_from_raw_snapshot`) | Module của TV1–TV3 | 2 flow chạy end-to-end, metrics 3 trạng thái, 2 báo cáo markdown | Code hoàn thành và đã chạy được; commit sau lần chạy chính thức |

Phần của tôi nằm ở hai đầu pipeline. `crossref.py` là đầu vào của `cleaning.py` (TV2). `corruption.py` nhận output của TV2 và tạo dữ liệu bẩn cho quality gate (TV3) và bước đánh giá.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Soạn contract dùng chung (raw schema, clean schema, mẫu câu hỏi test, dict quality) | Cả nhóm (`docs/PHAN_CONG.md` mục 2) | TV2 và TV3 code theo cùng schema. Khi ghép không lỗi cột hay kiểu dữ liệu |
| Merge 3 nhánh `feat/tv1-ingestion`, `Khoa`, `QuangDung` vào `main` | TV2, TV3 | Giải conflict ở `crossref.py`. Chạy lại lệnh nghiệm thu CP0–CP4 trên `main` sau khi merge, tất cả đạt |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Parse Crossref, bỏ thẻ JATS, chuẩn hóa ngày `YYYY-MM-DD`, bỏ record thiếu trường / trùng DOI | `crossref.py::parse_crossref_payload` | 24 record, 24 DOI duy nhất, không summary nào còn `<jats:` | Lệnh CP0 → `Đã tải 24 bài báo` |
| Fetch có retry và fallback về snapshot | `crossref.py::fetch_source_records` | Mặc định đọc snapshot. `REFRESH_SOURCE=1` gọi API thật | Giả lập API trả 429 liên tục → fallback, vẫn ra 24 bài. Gọi API thật trên bản sao repo → 24 bài |
| Tiêm 6 kịch bản lỗi có thể tái lập | `corruption.py::corrupt_clean_dataframe` | 24 → 22 dòng; log ghi đủ 6 scenario kèm giá trị trước/sau | Lệnh CP4 → `Corrupted 22 dòng`. Chạy 2 lần cho kết quả giống hệt (`DataFrame.equals` = True) |
| Nối 2 pipeline và repair tự động | `phase1.py`, `corruption_flow.py` | Bảng 3 trạng thái trong `data/reports/corruption_report.md` | `python script/run_phase1.py` và `python script/run_corruption_flow.py` đều exit 0 |

Output cụ thể từ phần việc của tôi: `data/results/corruption_log.json`. File này ghi rõ bài nào bị lỗi gì, nên có thể truy từng câu hỏi test bị giảm điểm về đúng kịch bản gây ra (xem mục 8).

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

1. **Ingestion:** lấy metadata bài báo từ một nguồn bên ngoài, vốn không ổn định (rate limit 429, dữ liệu thay đổi theo ngày). Pipeline vẫn phải tái lập được và luôn giữ bản thô làm điểm tựa lineage.
2. **Corruption:** giả lập sự cố dữ liệu thật để chứng minh hai điều. Thứ nhất, RAG vẫn chạy nhưng trả lời sai mà không báo lỗi (silent failure). Thứ hai, quality gate phát hiện được sự cố đó.

### Cách triển khai

**`crossref.py`**
- Mỗi item Crossref được map sang `PaperRecord`:
  - DOI → `paper_id`.
  - `title[0]` → `title`.
  - `abstract` → `summary`, sau khi bỏ thẻ bằng regex `<[^>]+>` và chuẩn hóa khoảng trắng.
  - `author[]` → `"given family"`.
  - `subject[]` → `categories`.
  - Ngày: thử lần lượt các trường `published`, `published-online`, `published-print`, `issued`, `created`; thiếu tháng hoặc ngày thì lấy 1.
- Item thiếu DOI, tiêu đề, tóm tắt hoặc ngày thì bỏ qua. DOI trùng thì chỉ giữ lần xuất hiện đầu.
- `fetch_source_records`:
  - Mặc định đọc snapshot đã commit.
  - Khi `REFRESH_SOURCE=1` thì gọi `https://api.crossref.org/works` với `query`, `filter`, `rows` lấy từ `Settings`. Gặp lỗi 429 hoặc 5xx thì thử lại tối đa 4 lần, thời gian chờ tăng dần 1s, 2s, 4s. Hết lượt thử thì quay về snapshot.
  - Response thô được lưu nguyên vẹn, records được lưu riêng ra `crossref_records.json`.

**`corruption.py`**
- Làm trên bản sao, sort theo `published` giảm dần để vị trí các dòng luôn cố định. Không dùng random nên chạy lại luôn ra cùng kết quả.
- Sau khi bỏ 20% bài mới nhất, 5 kịch bản còn lại tác động lên **các nhóm dòng không trùng nhau**. Nhờ vậy mỗi câu hỏi test bị ảnh hưởng chỉ do đúng một loại lỗi, dễ quy nguyên nhân.
- Có 2 chi tiết cố ý:
  - Summary bị xóa được gán `""` chứ không phải `None`, vì GX `ExpectColumnValueLengthsToBeBetween` bỏ qua giá trị null.
  - Chuỗi nhiễu được chèn **vào đầu** summary và không có dấu chấm. Như vậy nó dính vào câu đầu tiên, tức phần mà QA trả lời, nên ảnh hưởng thật tới F1.
- Cuối cùng tính lại `summary_chars` và `text_for_embedding` để phần embedding dùng đúng nội dung đã bị lỗi.

**Repair (`corruption_flow._repair_from_raw_snapshot`)**
- Không vá trên DataFrame bẩn. Thay vào đó, bỏ hẳn dữ liệu bẩn và cho `crossref_records.json` đi lại qua chính `build_clean_dataframe`.
- Cách này không gọi API và chạy bao nhiêu lần cũng ra cùng kết quả (idempotent).
- Repair được kích hoạt khi quality gate của dữ liệu bẩn trả `success=False`, và log in ra những check đã fail.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Crossref payload `{"message": {"items": [...]}}`; clean DataFrame theo contract mục 2.2 (`published` là chuỗi, có `authors_joined`, `categories_joined`, `age_days`) |
| Output | `list[PaperRecord]` + 2 file raw; DataFrame bẩn cùng schema + `corruption_log.json` |
| Module phụ thuộc | `core.config.Settings`, `core.utils` (`normalize_whitespace`, `read_json`, `write_json`) |
| Module sử dụng output | `ingestion/cleaning.py`, `pipelines/phase1.py`, `pipelines/corruption_flow.py` |
| Điều kiện lỗi cần xử lý | HTTP 429/5xx, timeout, JSON hỏng → fallback snapshot. Payload không có record hợp lệ → `ValueError`. Snapshot chưa tồn tại và API lỗi → raise. Dataset nhỏ hơn số vị trí cần tiêm lỗi → tự bỏ qua vị trí vượt kích thước |

### Cách xác minh

```bash
python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"
python -c "from core.config import load_settings; from ingestion.corruption import corrupt_clean_dataframe; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); c=corrupt_clean_dataframe(df, s.paths.corruption_log); print(f'Tín hiệu hoàn thành: Corrupted {len(c)} dòng')"
python script/run_phase1.py
python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** 24 bài; 22 dòng sau khi tiêm lỗi; log có 6 scenario; quality gate trên dữ liệu bẩn trả `False`.
- **Kết quả thực tế:** đúng như mong đợi. `crossref_records.json` sinh lại giống hệt bản đã commit (`git diff` rỗng).
- **Artifact/log:** `data/raw/`, `data/results/corruption_log.json`, `data/quality/corrupted_quality_report.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** hướng dẫn yêu cầu "gọi API Crossref, lỗi thì fallback về snapshot". Nhưng đề cũng yêu cầu tín hiệu nghiệm thu cố định (24 bài, 24 dòng sạch) và báo cáo phải tái lập được.
- **Các phương án đã cân nhắc:**
  - (A) Luôn gọi API thật, chỉ fallback khi lỗi.
  - (B) Mặc định đọc snapshot, chỉ gọi API khi bật `REFRESH_SOURCE=1`; khi gọi mà lỗi vẫn fallback.
- **Phương án đã chọn:** (B).
- **Lý do:**
  - Crossref là nguồn sống. Khi tôi thử gọi API thật (`REFRESH_SOURCE=1`, chạy trên bản sao repo), kết quả là một bộ 24 bài hoàn toàn khác snapshot, có cả bài tiếng Nga.
  - Với (A), mỗi lần chạy sẽ ghi đè snapshot. Test set, metrics và báo cáo của cả nhóm sẽ lệch nhau giữa các máy, và không còn bản thô cố định để repair.
  - (B) vẫn giữ nguyên cơ chế retry và fallback theo đề, đổi lại được tính tái lập.
- **Bằng chứng:** chạy lại nhiều lần đều ra 24 record giống hệt bản đã commit. Dữ liệu sau repair có cùng tập `paper_id` với baseline (`same paper_ids as baseline=True` trong log).

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** khi merge nhánh `Khoa` vào `main` (sau khi đã merge nhánh của tôi), git báo `CONFLICT (content): Merge conflict in src/ingestion/crossref.py`.
- **Lệnh tái hiện:** `git merge --no-ff origin/Khoa`.
- **Nguyên nhân gốc:** TV2 cần `load_raw_records` để bắt đầu làm cleaning, nên đã tự viết hàm này trong nhánh của mình. Tôi cũng viết cùng hàm đó trong `crossref.py`. Hai bên sửa cùng vùng code.
- **Cách xử lý:**
  - So sánh 2 phiên bản: logic giống nhau (`PaperRecord(**row)` trên `read_json`), nhưng bản của tôi có thêm `parse` và `fetch`.
  - Giữ bản của tôi bằng `git checkout --ours src/ingestion/crossref.py`, rồi commit merge.
- **Cách xác minh:** chạy lại CP0 → CP4 trên `main` sau merge, tất cả đạt (24 / 24 / quality True / 10 câu / 22 dòng, quality dữ liệu bẩn False).
- **Điều học được:** hàm nào module khác cần sớm thì owner nên push trước. Trong kế hoạch, `load_raw_records` được đặt là việc đầu tiên, phải push trong 10 phút đầu. Nếu làm đúng như vậy thì đã tránh được làm trùng và conflict.

## 7. Hiểu biết về luồng end-to-end

1. **Crossref → vector index:**
   - Payload Crossref được lưu thô, rồi parse thành `PaperRecord`.
   - `cleaning.py` chuẩn hóa, tính `age_days` và ghép `text_for_embedding` 5 dòng.
   - `LocalEmbeddingIndex.build` embed bằng `all-MiniLM-L6-v2` và ghi vào ChromaDB (cosine) cùng metadata. Mỗi trạng thái có collection riêng: `papers-baseline`, `papers-corrupted`, `papers-repaired`.
2. **Evaluation set:**
   - Mỗi câu hỏi có `ground_truth_doc_ids` là DOI của bài chứa đáp án.
   - `retrieval_hit_rate`: tỷ lệ câu mà DOI đúng nằm trong top-k tài liệu truy xuất được.
   - `mean_token_f1`: mức trùng token giữa câu trả lời và ground truth.
   - `judge_*`: chấm bằng LLM, hoặc bằng heuristic khi không có LLM.
3. **Quality checks khác freshness ở đâu:**
   - Quality checks kiểm tra **tính hợp lệ của cấu trúc và nội dung**: số dòng, not-null, `paper_id` duy nhất, summary ≥ 30 ký tự.
   - Freshness kiểm tra **độ mới theo thời gian**: tỷ lệ bài có `age_days > 180` không được vượt 25%.
   - Dữ liệu có thể hợp lệ hoàn toàn về cấu trúc nhưng đã cũ. Khi đó RAG trả lời bằng thông tin lỗi thời.
4. **Vì sao dùng cùng test set:** nếu mỗi trạng thái dùng một bộ câu hỏi khác nhau thì chênh lệch metrics có thể đến từ độ khó của câu hỏi, không phải từ dữ liệu. Giữ nguyên `test_set.json` thì dữ liệu là biến duy nhất thay đổi.
5. **Repair thành công dựa trên:** metrics của trạng thái repaired quay về bằng baseline, quality gate repaired trả `success=True`, freshness `is_fresh=True`, và tập `paper_id` sau repair giống baseline.

## 8. Phân tích kết quả

> Số liệu dưới đây lấy từ lần chạy đầy đủ cả 2 script ngày 2026-09-26 (khoảng 03:10 UTC). Lúc đó chưa có API key, nên `judge_*` dùng **heuristic dự phòng** (dựa trên token F1), không phải LLM. **Cần cập nhật bảng này sau lần chạy chính thức cuối cùng của nhóm.**

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.000 | 0.600 | 1.000 | 4/10 câu mất DOI đúng khỏi top-k: 3 do `drop_latest_records`, 1 do `truncate_title` |
| `mean_token_f1` | 1.000 | 0.640 | 1.000 | Giảm do mất bài, tiêu đề hỏng và ngày sai |
| `judge_accuracy` | 1.000 | 0.700 | 1.000 | Heuristic judge khá dễ dãi: 2 câu có F1 0.68–0.72 vẫn được tính là đúng |
| `mean_judge_score` | 5.000 | 3.400 | 5.000 | |
| Quality checks | Pass | Fail | Pass | Fail ở `expect_column_values_to_be_unique(paper_id)` và `expect_column_value_lengths_to_be_between(summary)` |
| Freshness status | Fresh (stale 1/24 = 0.042) | Stale (7/22 = 0.318 > 0.25) | Fresh (0.042) | `stale_date` đẩy tỷ lệ bài cũ vượt ngưỡng |

### Kết luận từ số liệu

1. `drop_latest_records` (bỏ 5 bài mới nhất) → freshness gần như không đổi, GX cũng không bắt được vì 22 dòng vẫn nằm trong ngưỡng 5–5000 → nhưng 3 câu summary eval_001–003 mất tài liệu đúng, hit rate giảm từ 1.0 xuống 0.6 cùng với câu bị `truncate_title`. **Đây là silent failure thật sự**: không check nào của quality gate phát hiện việc mất bài, chỉ bộ đánh giá mới thấy.
2. `stale_date` → freshness chuyển thành `is_fresh=False` (0.318) → câu eval_008 vẫn truy xuất **đúng** tài liệu (hit=True) nhưng trả lời ngày `2025-06-04` thay vì ngày thật, F1 = 0. Retrieval tốt không có nghĩa là câu trả lời đúng.
3. Repair từ `crossref_records.json` → 4 expectation đều pass, freshness quay về 0.042 → cả 4 metrics quay về đúng bằng baseline (1.000).

**Corruption nào ảnh hưởng rõ nhất và vì sao?** `drop_latest_records` gây sụt giảm lớn nhất: 3/4 lần miss retrieval. Nó cũng nguy hiểm nhất vì đi qua quality gate mà không bị phát hiện: số dòng vẫn hợp lệ, không có null, không trùng. Muốn bắt được loại lỗi này cần thêm check so sánh số dòng với lần chạy trước (volume drift) hoặc so với ngày xuất bản mới nhất.

**Kết quả nào khác với kỳ vọng ban đầu?**
- `blank_summary` và `inject_noise` **không làm giảm điểm** ở các câu test bị ảnh hưởng (eval_004, 006, 009). Tôi kiểm tra lại thì thấy các câu đó thuộc loại `authors` hoặc `categories`. QA lấy đáp án từ metadata `authors_joined` / `categories_joined`, không từ summary, nên không bị ảnh hưởng. Như vậy tác động của corruption phụ thuộc loại câu hỏi. Chúng làm GX fail nhưng không làm agent sai trên bộ test này.
- Câu eval_003 bị trả lời bằng đoạn summary có chuỗi nhiễu `#### xq9 ...`, lấy từ một bài khác có nội dung gần giống. Điều này cho thấy nhiễu vẫn lan vào câu trả lời, kể cả khi câu hỏi không nhắm vào bài bị nhiễu.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Data pipeline:** bản thô phải được lưu nguyên vẹn và tách khỏi bước làm sạch. Nhờ `crossref_records.json`, repair chỉ là chạy lại cùng hàm cleaning trên dữ liệu đáng tin, không cần gọi lại API.
2. **Observability:** quality gate chỉ bắt được những gì đã được định nghĩa thành rule. Dữ liệu bị mất một phần (drop latest) vẫn đi qua cả 4 expectation. Các check về số lượng, độ mới và lỗi cấu trúc bổ sung cho nhau chứ không thay thế nhau.
3. **Tác động lên RAG:** agent không báo lỗi khi dữ liệu bẩn mà vẫn trả lời tự tin. Nó có thể lấy đúng tài liệu mà trả lời sai (ngày bị đổi), hoặc lấy sai tài liệu mà câu trả lời trông vẫn hợp lý.

### Nếu có thêm thời gian

Tôi sẽ thêm expectation về volume: so số dòng hiện tại với số dòng của baseline gần nhất, fail nếu giảm hơn 10%. Cách đo cải thiện: chạy lại `run_corruption_flow.py` và kiểm tra rằng kịch bản `drop_latest_records` giờ làm quality gate fail, dù đã tắt 4 kịch bản còn lại.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Đặng Đỉnh Đoàn
**Ngày xác nhận:** 2026-09-26
