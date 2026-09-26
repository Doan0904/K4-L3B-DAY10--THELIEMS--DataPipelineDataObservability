# Phân Công Công Việc — Nhóm 4 Người (Day 10: Data Pipeline & Data Observability)

> Tài liệu này là **kế hoạch làm việc nội bộ** của nhóm. Đọc hết mục 1–3 trước khi code.
> Khi xong bài, thông tin vai trò ở đây được chép sang [`TEAM.md`](TEAM.md) và `report/group_report.md`.

---

## 0. Tóm tắt nhanh

| TV | Vai trò | File sở hữu (code phải viết) | Bàn giao chính |
|:--:|---|---|---|
| **TV1** | Source & Corruption owner | `src/ingestion/crossref.py`, `src/ingestion/corruption.py` | 2 file raw JSON, `corruption_log.json`, 6 kịch bản lỗi |
| **TV2** | Data model & Test-set owner | `src/ingestion/cleaning.py`, `src/evaluation/testset.py` | Dataset sạch 24 dòng, `test_set.json` 10 câu |
| **TV3** | Observability & Reporting owner | `src/observability/quality.py`, `src/observability/reporting.py` | GX 1.x quality gate + freshness, 2 báo cáo markdown |
| **TV4** | Trưởng nhóm / Integration owner | `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py` | 2 pipeline chạy end-to-end, metrics 3 trạng thái, demo, nộp bài |

| Họ tên | MSSV | Email GitHub | TV |
|---|---|---|:--:|
| | | | TV1 |
| | | | TV2 |
| | | | TV3 |
| | | | TV4 |

**Vì sao chia như vậy?** Đây là cách chia 4 người mà [`report/README.md`](../report/README.md) khuyến nghị, có một chỗ chỉnh: `corruption.py` chuyển từ TV4 sang TV1. Lý do là `crossref.py` nhẹ, còn TV4 đã phải lo tích hợp, demo và nộp bài. `retrieval/` (embedding, ChromaDB, QA agent) và `evaluation/metrics.py` **đã có sẵn code, không có TODO**, nên không ai phải viết. Mọi người vẫn phải đọc hiểu để trả lời Q&A.

---

## 1. Cài môi trường (mỗi người tự làm trên máy mình, 15 phút đầu)

```bash
cd <thư mục repo>
python3 --version                 # cần 3.11 / 3.12 / 3.13

# Cách nhẹ (khuyên dùng): torch bản CPU (~200 MB thay vì ~3 GB bản CUDA)
uv venv .venv --python 3.11
source .venv/bin/activate         # Windows: .\.venv\Scripts\Activate.ps1
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install -e .
# (Không có uv: python -m venv .venv → activate → pip install torch --index-url ... → pip install -e .)

cp .env.example .env              # rồi điền GOOGLE_API_KEY=<key của bạn>, không dấu nháy, không khoảng trắng
python -c "import chromadb, great_expectations, sentence_transformers; print('Environment Ready!')"
```

- Nếu đã cài bằng cách nhẹ thì **không chạy `uv sync` / `uv run`**, vì `uv.lock` sẽ kéo lại torch CUDA. Chỉ cần activate `.venv` rồi gọi `python ...`.
- Đặt `git config user.email` **trùng email tài khoản GitHub**. Nếu không, commit sẽ không hiện trong Insights → Contributors, và **không commit = 0 điểm cá nhân**.
- **Tuyệt đối không commit `.env`** (bị trừ 20 điểm). File đã có trong `.gitignore`, nhưng vẫn phải kiểm tra `git status` trước mỗi lần commit.

---

## 2. Contract dùng chung (cả nhóm thống nhất trong 15 phút đầu, không đổi về sau)

Các module gọi chéo nhau, nên **sai tên cột hoặc kiểu dữ liệu là vỡ pipeline**. Mọi người code theo đúng contract này.

### 2.1. Raw schema: `PaperRecord` (đã định nghĩa trong `crossref.py`, không sửa)

| Trường | Lấy từ Crossref item | Quy tắc |
|---|---|---|
| `paper_id` | `DOI` | Giữ nguyên chuỗi DOI, chỉ `strip()`. Đây là **document ID** xuyên suốt pipeline |
| `title` | `title[0]` | Chuẩn hóa khoảng trắng |
| `summary` | `abstract` | **Bỏ thẻ JATS** (`<jats:p>`, …) bằng regex `<[^>]+>`, rồi chuẩn hóa khoảng trắng |
| `authors` | `author[]` | `list[str]` dạng `"given family"` |
| `categories` | `subject[]` | `list[str]`, thiếu thì `[]` |
| `primary_category` | `categories[0]` | Thiếu thì `""` |
| `published` | `published.date-parts[0]` | Chuỗi **`"YYYY-MM-DD"`** (thiếu tháng/ngày thì lấy 1) |
| `updated` | `created.date-time[:10]` | Thiếu thì bằng `published` |
| `abs_url`, `pdf_url` | `URL` | `pdf_url` lấy `link[0].URL` nếu có, không thì bằng `URL` |
| `comment` | — | `f"Crossref record {doi}"` |

Record thiếu DOI, title hoặc abstract thì **bỏ qua**. Snapshot có sẵn cho ra **24 record, 24 DOI duy nhất**.

### 2.2. Clean schema: DataFrame từ `build_clean_dataframe` (TV2 tạo, mọi người dùng)

`LocalEmbeddingIndex._build_documents` (file [`index.py`](../src/retrieval/index.py)) đọc **bắt buộc** các cột: `paper_id, title, text_for_embedding, published, authors_joined, categories_joined, summary, abs_url, pdf_url`.

| Cột | Kiểu | Ghi chú |
|---|---|---|
| Toàn bộ 11 trường của `PaperRecord` | như trên | `authors`, `categories` vẫn là list |
| `published` | **`str` `"YYYY-MM-DD"`** | **Không** đổi sang `Timestamp`, vì ChromaDB metadata chỉ nhận str/int/float/bool |
| `authors_joined` | `str` | `", ".join(authors)` |
| `categories_joined` | `str` | `", ".join(categories)` |
| `summary_chars` | `int` | `len(summary)` |
| `age_days` | `int` | `(run_date.date() - date.fromisoformat(published)).days` |
| `text_for_embedding` | `str` | Đúng 5 dòng: `Title: …\nAuthors: …\nPublished: …\nCategories: …\nSummary: …` |

- Khử trùng lặp theo `paper_id` (`keep="first"`), bỏ dòng có title hoặc summary rỗng, sort theo `published` giảm dần rồi `paper_id`, `reset_index(drop=True)`.
- **Cách lưu** (TV4 làm trong pipeline): `write_csv(df, paths.clean_csv)` và `write_json(paths.clean_json, df.to_dict(orient="records"))`.

### 2.3. Evaluation set: `data/eval/test_set.json` (TV2 tạo)

```json
{ "id": "eval_001", "question_type": "summary",
  "question": "What is the summary of the paper '<title>'?",
  "ground_truth": "<câu đầu của summary>", "ground_truth_doc_ids": ["<DOI>"] }
```

**Câu hỏi phải khớp đúng mẫu mà [`qa.py`](../src/retrieval/qa.py) nhận diện**, nếu không agent sẽ trả lời sai loại:

| `question_type` | Mẫu câu hỏi (bắt buộc có tiêu đề trong **dấu nháy đơn**) | `ground_truth` |
|---|---|---|
| `summary` | `What is the summary of the paper '<title>'?` | `first_sentence(summary)` (hàm trong `core.utils`) |
| `authors` | `Who authored the paper '<title>'?` | `authors_joined` |
| `date` | `When was the paper '<title>' published?` | `published` |
| `categories` | `What categories does the paper '<title>' belong to?` | `categories_joined` |

- Tiêu đề nằm trong `'…'` để `qa.py` tra cứu chính xác (`index.lookup`).
- Có 10 câu, phân bổ 3 `summary` + 3 `authors` + 2 `date` + 2 `categories`, dùng 10 bài báo khác nhau, chọn **cố định (deterministic)**. Không dùng random không seed.
- **Test set chỉ sinh một lần ở phase 1** và được dùng lại nguyên vẹn cho cả 3 trạng thái. Chỉ sinh lại khi file chưa tồn tại hoặc `REFRESH_TEST_SET=1`.

### 2.4. Artifact paths

**Chỉ dùng `settings.paths.*`** trong [`config.py`](../src/core/config.py). Không hardcode `C:\...` hay `/home/...` (bị trừ 5 điểm). Ghi file bằng `core.utils.write_json / write_csv / write_text`, vì các hàm này tự tạo thư mục cha.

### 2.5. Quality result (TV3 trả về, TV4 dùng)

`run_data_quality_checks(df, settings, report_name)` trả về dict **tối thiểu** gồm:

```python
{"report_name": str, "success": bool, "row_count": int,
 "expectations": [{"name": str, "column": str | None, "success": bool, "observed": ...}],
 "freshness": {...}}   # payload của build_freshness_report
```

`success = (tất cả 4 expectation pass) AND freshness["is_fresh"]`. Đây là cách tích hợp Freshness vào Quality Gate. File kết quả ghi vào `settings.paths.quality_dir / f"{report_name}_quality_report.json"`.

### 2.6. Lưu ý chênh lệch giữa hướng dẫn LMS và code thật

| Hướng dẫn LMS nói | Code thật trong repo | Làm theo |
|---|---|---|
| `run_phase1_pipeline(settings)` | `phase1.main()` | **Code thật** (`script/run_phase1.py` gọi `main()`) |
| `run_corruption_flow_pipeline(settings)` | `corruption_flow.main()` | **Code thật** |
| `evaluate_freshness_sla()` | `build_freshness_report(df, settings, report_path)` | **Code thật** |
| `repair_from_raw_snapshot()` | chưa có | TV4 tự viết thành hàm helper trong `corruption_flow.py` |
| Báo cáo cá nhân ở `reports/individual_<MSSV>_<HoTen>.md` | thư mục `report/`, mẫu `individual_report.md` | **`report/<MSSV>_HoTen.md`** (theo `SUBMISSION.md`) |

**Không đổi chữ ký các hàm có sẵn**, vì module khác đang gọi chúng.

---

## 3. Quy trình Git

```bash
git checkout main && git pull origin main
git checkout -b feat/<tên-module>          # vd: feat/crossref, feat/cleaning, feat/quality, feat/pipelines
# ... code, tự chạy lệnh kiểm tra của mình ...
git add <chỉ file của mình>                 # KHÔNG dùng git add . (dễ dính .env / .venv)
git commit -m "feat(ingestion): implement parse_crossref_payload with JATS stripping"
git push -u origin feat/<tên-module>        # rồi mở Pull Request vào main, TV4 review + merge
```

- Mỗi người phải có **ít nhất 1 commit của chính mình trên `main`**. Nên commit nhỏ và nhiều lần.
- Thứ tự merge ưu tiên: **TV1 (`load_raw_records`) → TV2 (`cleaning`) → TV3 → TV2 (`testset`) → TV4**.
- Chỉ **TV4 commit các file trong `data/`** (artifact sinh ra từ lần chạy cuối), để tránh conflict.

---

## 4. Việc chi tiết từng người

### TV1: Source & Corruption owner

**A. `src/ingestion/crossref.py`** (CP0, rubric #2: 15 điểm)

1. **`load_raw_records(path)`: làm và push TRƯỚC TIÊN (≤ 10 phút).** Đọc `read_json(path)` rồi trả về `[PaperRecord(**r) for r in data]`. TV2 cần hàm này ngay để bắt đầu code, vì `data/raw/crossref_records.json` đã có sẵn trong repo.
2. `parse_crossref_payload(payload)`: duyệt `payload["message"]["items"]` và map theo contract ở mục 2.1. Nhớ viết hàm nhỏ `_strip_jats(text)`.
3. `fetch_source_records(settings)`:
   - **Mặc định (`settings.refresh_source == False`) và file snapshot `paths.raw_api_response` đã tồn tại:** đọc snapshot, **không gọi API**. Cách này giữ kết quả tái lập được (luôn 24 bài) và không ghi đè snapshot gốc.
   - **Khi `REFRESH_SOURCE=1`:** gọi `GET https://api.crossref.org/works` với `params={"query": settings.source_query, "filter": settings.source_filter, "rows": settings.max_results}`, `timeout=30`. Retry có backoff (1s, 2s, 4s…) khi gặp 429/503. Hết retry hoặc lỗi mạng thì **fallback đọc snapshot**. Lưu JSON gốc nguyên vẹn vào `paths.raw_api_response`.
   - Luôn parse rồi ghi `[asdict(r) for r in records]` vào `paths.raw_records_json`, sau đó `return records`.
   - `print`/log rõ đang dùng nguồn nào (live API hay snapshot), để còn giải thích khi demo.

**Kiểm tra:**
```bash
python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"
# → Đã tải 24 bài báo ; summary không còn chữ "<jats:"
```

**B. `src/ingestion/corruption.py`** (CP4, rubric #8: 15 điểm, làm chung với TV4)

Viết `corrupt_clean_dataframe(df, output_log_path)`. Làm trên `df.copy()`, **cố định (deterministic)**: chọn dòng theo vị trí cố định hoặc `random_state=42`.

| # | Kịch bản | Cách làm gợi ý | Tác động kỳ vọng |
|---|---|---|---|
| 1 | Drop latest records | Sort `published` giảm dần, bỏ `ceil(20% × n)` dòng đầu (5 dòng) | Câu hỏi về bài bị mất → retrieval miss |
| 2 | Blank summary | Gán `summary = ""` cho 3 dòng. **Dùng `""`, không dùng `None`**, vì GX bỏ qua null khi đo độ dài | GX summary-length fail, F1 = 0 |
| 3 | Inject noise | **Chèn vào đầu** summary chuỗi rác không có dấu chấm, vd `"#### xq9 zz@@ noise ####  "` (3 dòng khác) | Câu đầu bị bẩn → token F1 giảm |
| 4 | Truncate title | `title = title[:7]` cho 3 dòng | Tra cứu tiêu đề chính xác thất bại → retrieval có thể miss |
| 5 | Stale date | Lùi `published` 365 ngày (sửa chuỗi) và `age_days += 365` cho **≥ 6 dòng** | Tỷ lệ stale > 25% → `is_fresh = False` |
| 6 | Duplicate rows | Nối thêm bản sao của 3 dòng (`pd.concat`) | GX unique `paper_id` fail |

Sau đó: **tính lại** `summary_chars` và `text_for_embedding` (cùng format 5 dòng; nên import helper từ `cleaning.py` của TV2 để khỏi lệch). Ghi log bằng `write_json(output_log_path, [...])`, mỗi phần tử có dạng `{"scenario": ..., "affected_paper_ids": [...], "affected_rows": n, "params": {...}}`, rồi return df bẩn.

**Kiểm tra:**
```bash
python -c "from core.config import load_settings; from ingestion.corruption import corrupt_clean_dataframe; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); c=corrupt_clean_dataframe(df, s.paths.corruption_log); print(f'Tín hiệu hoàn thành: Corrupted {len(c)} dòng')"
# → data/results/corruption_log.json có đủ 6 scenario
```
Sau khi TV2 có test set, kiểm tra xem **một số bài trong test set có bị tác động không** (nhất là kịch bản 1, 2, 4). Nếu không có bài nào bị ảnh hưởng thì metrics sẽ không giảm và phần phân tích sẽ yếu.

**Phần báo cáo nhóm TV1 viết:** §5 (Nguồn dữ liệu, raw schema) và §9 (bảng corruption scenarios).

---

### TV2: Data model & Test-set owner

**A. `src/ingestion/cleaning.py`** (CP1, rubric #3: 15 điểm). Bắt đầu ngay khi TV1 push `load_raw_records`.

Viết `build_clean_dataframe(records, run_date)` theo đúng contract ở mục 2.2:
1. `pd.DataFrame([asdict(r) for r in records])`.
2. Chuẩn hóa: `normalize_whitespace` cho title và summary (dùng lại hàm trong `core.utils`), strip từng phần tử trong authors và categories, bỏ phần tử rỗng.
3. Chuẩn hóa `published` và `updated` về `"YYYY-MM-DD"` (parse bằng `pd.to_datetime(...).dt.strftime("%Y-%m-%d")`), rồi tính `age_days` theo contract. `run_date` là datetime có timezone (UTC), nên chỉ lấy `.date()`.
4. Tạo `authors_joined`, `categories_joined`, `summary_chars`, `text_for_embedding`. **Tách phần ghép text thành hàm riêng**, vd `build_text_for_embedding(row)`, để TV1 dùng lại trong corruption.
5. Bỏ dòng thiếu title hoặc summary, `drop_duplicates("paper_id")`, sort, `reset_index(drop=True)`.

**Kiểm tra:**
```bash
python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print(f'Tín hiệu hoàn thành: Clean thành công {len(df)} dòng'); print(df.iloc[0]['text_for_embedding'])"
# → 24 dòng, in ra đủ 5 dòng Title/Authors/Published/Categories/Summary
```
Sau đó **tự lưu tạm** `data/clean/papers_clean.json` bằng `write_json(s.paths.clean_json, df.to_dict(orient="records"))` để TV1 và TV3 test sớm. Không commit file này (TV4 commit bản cuối).

**B. `src/evaluation/testset.py`** (CP2, rubric #6 phần test set)

Viết `build_test_set(df, output_path)` theo contract ở mục 2.3:
- Nếu `len(df) < 10` thì `raise ValueError`.
- Chọn 10 bài cố định, rải đều trên dataset (vd `df.iloc[::2].head(10)` sau khi đã sort). Như vậy test set có cả bài mới nhất (bị kịch bản drop-latest ảnh hưởng) và bài cũ hơn.
- Câu `categories` chỉ dùng bài có `categories_joined` khác rỗng.
- `id` đánh số `eval_001` … `eval_010`, rồi `write_json(output_path, items)` và `return items`.

**Kiểm tra:**
```bash
python -c "from core.config import load_settings; from evaluation.testset import build_test_set; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); ts=build_test_set(df, s.paths.eval_testset); print(f'Tín hiệu hoàn thành: Sinh được {len(ts)} câu hỏi test')"
# → 10 câu; mở data/eval/test_set.json kiểm tra từng câu có tiêu đề trong '...'
```

**Phần báo cáo nhóm TV2 viết:** §5 (Quy tắc cleaning; cách tạo `text_for_embedding`, `paper_id`, `age_days`) và §6 (Evaluation setup; vì sao giữ nguyên test set).

---

### TV3: Observability & Reporting owner

**A. `src/observability/quality.py`** (CP1, rubric #7: 15 điểm, **mục bị soi kỹ nhất**)

1. `build_freshness_report(df, settings, report_path)`:
   - `stale_rows = int((df["age_days"] > settings.freshness_threshold_days).sum())`, `stale_ratio = stale_rows / total_rows`.
   - Payload gồm `latest_published`, `oldest_published`, `stale_rows`, `total_rows`, `stale_ratio`, `threshold_days` (180), `max_stale_ratio` (0.25), `is_fresh = stale_ratio <= 0.25`.
   - `write_json(report_path, payload)` rồi return payload.
2. `run_data_quality_checks(df, settings, report_name)`, **đúng chuẩn GX 1.x**:
   ```python
   import great_expectations as gx
   import great_expectations.expectations as gxe

   context = gx.get_context(mode="ephemeral")
   data_source = context.data_sources.add_pandas(name="papers_source")
   data_asset = data_source.add_dataframe_asset(name="papers_asset")
   batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
   batch = batch_def.get_batch(batch_parameters={"dataframe": df})

   expectations = [
       gxe.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000),
       gxe.ExpectColumnValuesToNotBeNull(column="paper_id"),
       gxe.ExpectColumnValuesToNotBeNull(column="title"),
       gxe.ExpectColumnValuesToNotBeNull(column="text_for_embedding"),
       gxe.ExpectColumnValuesToBeUnique(column="paper_id"),
       gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30),
   ]
   for exp in expectations:
       result = batch.validate(exp)          # result.success, result.to_json_dict()
   ```
   - Có thể gom vào một `ExpectationSuite` rồi `batch.validate(suite)`, cách nào cũng được, miễn là **cú pháp 1.x**. **Cấm** dùng API cũ (`ge.from_pandas`, `df.expect_...`, `get_context()` dạng file-based cũ), vì bị trừ 10 điểm nếu crash.
   - Freshness: gọi `build_freshness_report(df, settings, settings.paths.quality_dir / f"{report_name}_freshness_report.json")`.
   - Trả về dict theo contract ở mục 2.5, ghi vào `quality_dir / f"{report_name}_quality_report.json"`.
   - **Lưu ý JSON:** kết quả GX có kiểu numpy. Dùng `result.to_json_dict()` hoặc ép về `int/float/bool` thuần trước khi `write_json`, nếu không sẽ gặp lỗi `TypeError: not JSON serializable`.
   - Có thể đặt `export GX_ANALYTICS_ENABLED=false` để GX bớt log hoặc gọi mạng.

**Kiểm tra:**
```bash
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'test'); print('Tín hiệu hoàn thành: Quality check status =', res['success'])"
# → True trên dữ liệu sạch. Tự thử thêm: nhân đôi 1 dòng → phải ra False (unique fail)
```
(Với snapshot hiện tại, tính đến 26/09/2026 chỉ 1/24 bài có `age_days > 180`, nên `is_fresh = True`. Số này tăng dần theo ngày chạy thật.)

**B. `src/observability/reporting.py`** (CP3 + CP5)

1. `generate_phase1_report(report_path, source_summary, metrics, quality, freshness)` viết markdown gồm: nguồn dữ liệu (API/snapshot, query, số record), bảng metrics (`retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy`, `mean_judge_score`), bảng từng expectation pass/fail, bảng freshness.
2. `generate_corruption_report(...)` viết **bảng 3 cột Baseline | Corrupted | Repaired**, thêm cột Δ (corrupted − baseline) và mức phục hồi, cho 4 metric + quality `success` + `is_fresh` + `stale_ratio`. Sau đó là mục "Nhận xét" ngắn.
   - Trường `ragas` trong metrics là dict (thường là `{"skipped": ...}`), nên **bỏ qua các giá trị không phải số** khi làm bảng.
   - Số liệu định dạng `f"{v:.3f}"`. **Không sửa tay số liệu** (bị trừ 20 điểm hoặc 0 điểm).
   - Ghi bằng `write_text(report_path, markdown)`.
   - Nên có thêm hàm helper `render_comparison_table(...) -> str` để TV4 `print` ra console khi demo.

**Phần báo cáo nhóm TV3 viết:** §8 (Data quality & freshness), và cùng TV4 viết §10 (so sánh 3 trạng thái).

---

### TV4: Trưởng nhóm / Integration owner

**A. Việc điều phối (xuyên suốt)**
- Chốt contract ở mục 2 trong 15 phút đầu. Tạo repo đúng tên `K4-L3B-DAY10-<TenNhom>-DataPipelineDataObservability` (**Public**), add 3 thành viên làm collaborator.
- Review và merge PR theo thứ tự ở mục 3. Nếu module của người khác lỗi thì **báo owner sửa**, không tự sửa hộ toàn bộ.

**B. `src/pipelines/phase1.py` → `main()`** (CP3). Trong lúc chờ các TV khác, viết khung trước:
```python
settings = load_settings()
records = fetch_source_records(settings)                          # TV1
df = build_clean_dataframe(records, now_utc())                    # TV2
write_csv(df, settings.paths.clean_csv)
write_json(settings.paths.clean_json, df.to_dict(orient="records"))
index = LocalEmbeddingIndex.build(df, settings)                   # collection papers-baseline
if settings.refresh_test_set or not settings.paths.eval_testset.exists():
    build_test_set(df, settings.paths.eval_testset)               # TV2
bundle = evaluate_pipeline(settings, index, settings.paths.eval_testset,
                           settings.paths.baseline_metrics, settings.paths.baseline_answers)
quality = run_data_quality_checks(df, settings, "baseline")       # TV3
freshness = build_freshness_report(df, settings, settings.paths.freshness_report)
generate_phase1_report(settings.paths.baseline_report, source_summary, bundle.summary, quality, freshness)
```
`source_summary` gồm `source_api`, `source_query`, `source_filter`, số raw record, số dòng sạch, thời điểm chạy. Phần demo agent (`build_agent` / `run_agent_question` → `paths.demo_answers`) là **tùy chọn**. Nếu làm thì bọc `try/except` để thiếu API key không làm hỏng pipeline.

**C. `src/pipelines/corruption_flow.py` → `main()`** (CP4 + CP5)
1. Đọc `baseline_metrics.json` và clean dataset (`pd.DataFrame(read_json(paths.clean_json))`). Nếu chưa có thì báo "chạy run_phase1.py trước".
2. `corrupted = corrupt_clean_dataframe(clean_df, paths.corruption_log)`, lưu `corrupted_clean_csv/json`.
3. `LocalEmbeddingIndex.build(corrupted, settings, paths.corrupted_embeddings_json)` sẽ tự dùng collection `papers-corrupted`. Sau đó `evaluate_pipeline(..., paths.eval_testset, paths.corrupted_metrics, paths.corrupted_answers)`. **Dùng cùng `test_set.json`**, không sinh lại.
4. Quality cho dữ liệu bẩn: `run_data_quality_checks(corrupted, settings, "corrupted")` (kỳ vọng `success=False`), cộng thêm freshness.
5. **`_repair_from_raw_snapshot(settings)`**: `build_clean_dataframe(load_raw_records(paths.raw_records_json), now_utc())`. Hàm này **không gọi API** và chạy bao nhiêu lần cũng cho cùng kết quả (idempotent). Lưu `repaired_clean_*`, build index `papers-repaired`, evaluate vào `repaired_metrics/answers`, quality `"repaired"` (kỳ vọng `True`).
6. `generate_corruption_report(...)` (TV3), rồi `print` bảng 3 trạng thái ra console.

**Kiểm tra cuối (CP3, CP5):**
```bash
python script/run_phase1.py            # exit 0; có papers_clean.csv, baseline_metrics.json, phase1_report.md
python script/run_corruption_flow.py   # exit 0; console in bảng 3 cột; có corruption_report.md
```

**D. Cấu hình LLM cho lần chạy chính thức:** `evaluate_pipeline` gọi LLM-judge 10 lần mỗi trạng thái. Gemini free tier có thể trả lỗi 429, khi đó code **tự rơi về heuristic judge** và `judge_accuracy` giữa các trạng thái sẽ không nhất quán. Chốt một cấu hình duy nhất cho lần chạy cuối: Gemini chạy ổn, hoặc `LLM_PROVIDER=mock` để dùng heuristic cho cả 3 trạng thái. Ghi cấu hình đó vào §4 báo cáo nhóm.

**Phần báo cáo nhóm TV4 viết:** §1–4, §7, §10–13 và ghép bản cuối. TV4 cũng điền [`TEAM.md`](TEAM.md).

---

## 5. Timeline (09:00 – 13:00; hạn nộp LMS 23:59:59 cùng ngày)

| Giờ | CP | TV1 | TV2 | TV3 | TV4 |
|---|---|---|---|---|---|
| 09:00–09:30 | CP0 | Cài env → **push `load_raw_records`** → `parse` + `fetch` | Cài env → đọc `index.py`/`qa.py` → bắt đầu `cleaning` | Cài env → đọc docs GX 1.x → viết `freshness` | Cài env, tạo repo, chốt contract, viết khung `phase1` |
| 09:30–10:05 | CP1 | Hoàn thiện + PR `crossref.py` | **PR `cleaning.py`**, lưu tạm `papers_clean.json` | `run_data_quality_checks` → test trên clean data | Review/merge, nối `phase1` đến bước index |
| 10:05–10:35 | CP2 | Bắt đầu `corruption.py` | `testset.py` → PR | PR `quality.py`, bắt đầu `reporting.py` | Chạy thử `run_phase1.py` từng phần |
| 10:35–11:00 | CP3 | Tiếp `corruption.py` | Hỗ trợ TV4 debug phase 1 | PR `generate_phase1_report` | **`run_phase1.py` chạy xanh** |
| 11:00–11:45 | CP4 | PR `corruption.py`, kiểm tra bài test bị ảnh hưởng | Viết §5–6 báo cáo | `generate_corruption_report` | `corruption_flow` bước 1–4 |
| 11:45–12:30 | CP5 | Viết §9 báo cáo | Kiểm tra repaired data khớp baseline | Viết §8, soát số liệu report | Repair + **`run_corruption_flow.py` chạy xanh**, commit `data/` |
| 12:30–13:00 | CP6 | Tập Q&A | Tập Q&A | Tập Q&A | Demo trên bảng, push cuối |
| Chiều/tối | — | Báo cáo cá nhân | Báo cáo cá nhân | Báo cáo cá nhân | Hoàn thiện `group_report.md`, `TEAM.md` |

**Nếu bị chậm:** ưu tiên để `run_phase1.py` chạy trước (40/100 điểm dựa vào nó), rồi mới làm corruption.

---

## 6. Checklist nộp bài (TV4 dẫn, cả nhóm cùng soát)

- [ ] `python script/run_phase1.py` và `python script/run_corruption_flow.py` đều exit 0 **trên bản code cuối**, chạy từ một máy vừa clone mới.
- [ ] Có đủ `data/raw/*`, `data/clean/*`, `data/eval/test_set.json`, `data/quality/*`, `data/results/{baseline,corrupted,repaired}_metrics.json`, `corruption_log.json`, `data/reports/{phase1,corruption}_report.md`.
- [ ] Metrics: corrupted **thấp hơn** baseline và repaired **quay về** mức baseline. Quality: baseline `True`, corrupted `False`, repaired `True`.
- [ ] Số liệu trong `group_report.md` và báo cáo cá nhân **khớp y hệt** file trong `data/results/`.
- [ ] `docs/TEAM.md` đã điền tên nhóm, họ tên, MSSV, vai trò theo bảng mục 0, phần tự khai từng người và **% đóng góp** được cả nhóm đồng ý.
- [ ] Mỗi người có `report/<MSSV>_HoTen.md` riêng (chép từ `report/individual_report.md`), **không copy của nhau**.
- [ ] `git status` sạch; không có `.env`, `.venv/`, `__pycache__/` trong commit; `git log -p | grep -i "api_key="` không lộ key thật.
- [ ] GitHub Insights → Contributors: **đủ 4 người** có commit trên `main`. Repo ở chế độ Public.
- [ ] **Từng người tự nộp link repo trên VLearn LMS** bằng tài khoản của mình (ai không nộp = 0 điểm).

---

## 7. Chuẩn bị Q&A (ai cũng phải trả lời được, không chỉ phần mình)

1. Dữ liệu đi thế nào từ Crossref → raw → clean → embedding MiniLM → ChromaDB → QA → metrics?
2. Vì sao phải giữ raw snapshot (lineage anchor, tránh rate limit, repair không cần gọi API)?
3. GX 1.x khác bản cũ ở đâu (ephemeral context, data source → asset → batch definition → batch)? Bốn expectation bắt lỗi gì?
4. Quality check khác freshness ở đâu? Vì sao dữ liệu cũ vẫn "hợp lệ" về schema nhưng nguy hiểm cho RAG?
5. **Silent failure** là gì? Kịch bản nào làm giảm hit rate, kịch bản nào chỉ làm giảm F1, kịch bản nào chỉ GX mới bắt được?
6. Vì sao 3 trạng thái phải dùng **cùng test set** và 3 collection ChromaDB **tách biệt**?
7. Repair **idempotent** nghĩa là gì? Chạy repair 2 lần có ra cùng kết quả không, và vì sao?

---

## 8. Bonus (chỉ khi phần bắt buộc đã xanh và còn thời gian)

- **B2 Auto-repair (+5, rẻ nhất):** TV4 sửa `corruption_flow` để khi quality gate của dữ liệu bẩn `success=False` thì **tự động** gọi repair, rồi log lý do (expectation nào fail).
- **B3 Pytest (+5):** TV2 và TV3 viết `tests/` cho parse, cleaning, quality và testset, kèm lệnh chạy one-click `pytest --cov=src`.
- **B1 Dashboard (+5):** Streamlit đọc `data/quality/*.json` và `data/results/*.json` để vẽ phân bố `age_days` và bảng 3 trạng thái.
