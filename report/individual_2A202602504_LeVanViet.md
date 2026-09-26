# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Lê Văn Việt |
| MSSV | 2A202602504 |
| Khóa/Lớp | K4-L3B |
| Tên nhóm | THE LIEMS |
| Vai trò chính | TV4 — Pipeline Integration owner |
| Repository | https://github.com/Doan0904/K4-L3B-DAY10--THELIEMS--DataPipelineDataObservability |
| Ngày hoàn thành | 2026-09-26 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Baseline orchestration | `src/pipelines/phase1.py`: `main`, `_ensure_test_set`, `_judge_mode` | Raw snapshot, cleaning, index, test set, quality gate | `papers_clean.*`, `baseline_metrics.json`, `baseline_answers.json`, `phase1_report.md` | Hoàn thành |
| Corruption orchestration và repair | `src/pipelines/corruption_flow.py`: `main`, `_repair_from_raw_snapshot`, `build_question_impact` | Clean dataset, `test_set.json`, baseline metrics | Dataset corrupted/repaired, metrics 3 trạng thái, `corruption_report.md`, `question_impact.json` | Hoàn thành |

Tôi không viết `crossref.py`, `cleaning.py`, `testset.py`, `quality.py` hay `reporting.py`. Những module đó là của TV1–TV3. Phần của tôi là nối chúng theo đúng contract và chứng minh ba trạng thái so sánh được với nhau. TV1 hỗ trợ merge nhánh và lần chạy trên máy Windows.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Giữ một test set cho cả ba lần đánh giá | TV2 (`testset.py`) | `corruption_flow.py` không gọi `build_test_set`. Ba file answers cùng 10 id `eval_001`–`eval_010` |
| Tách collection Chroma theo trạng thái | Index có sẵn | Baseline, corrupted, repaired ghi vào `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Đối chiếu câu hỏi với `corruption_log.json` | TV1 (6 kịch bản), TV3 (bảng metrics) | `data/results/question_impact.json` |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Chạy baseline end-to-end | `script/run_phase1.py` | 24 dòng sạch, hit rate 1.0, quality `success=true` | `data/results/baseline_metrics.json`, `data/quality/baseline_quality_report.json` |
| Chạy corrupt → repair | `script/run_corruption_flow.py` | Hit rate 1.0 → 0.7 → 1.0; quality true → false → true | `corrupted_metrics.json`, `repaired_metrics.json`, `corruption_report.md` |
| Repair từ raw, không vá dataframe bẩn | `_repair_from_raw_snapshot` | 24 dòng repaired trùng nội dung baseline | So `papers_clean.json` với `papers_clean_repaired.json` |
| Gắn câu test với kịch bản lỗi | `build_question_impact` | 10 dòng, mỗi câu có scenario và hit/F1 ba pha | `data/results/question_impact.json` |

Output trực tiếp của phần tích hợp là cặp metrics và file `question_impact.json`. File này không chấm lại RAG. Nó chỉ nối log của TV1 với answers đã có, để chỉ ra câu nào đổi điểm vì kịch bản nào.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Các module đúng từng khúc vẫn chưa thành một bài làm. Baseline phải sinh artifact mà corruption flow đọc lại. Ba lần chấm phải dùng cùng câu hỏi và cùng ground-truth document id. Repair phải bỏ dataframe bẩn và làm sạch lại từ snapshot, không sửa từng ô. Sau đó phải chỉ ra silent failure ở mức từng câu, vì một hit rate 0.7 không nói được kịch bản nào gây ra.

### Cách triển khai

`phase1.main` đi một lượt: `fetch_source_records` → `build_clean_dataframe` → ghi CSV/JSON → `LocalEmbeddingIndex.build` vào collection `papers-baseline` → đọc `test_set.json` nếu file đã có và mọi `ground_truth_doc_ids` còn nằm trong dataset. Chỉ gọi `build_test_set` khi file chưa có, khi `REFRESH_TEST_SET=1`, hoặc khi test set trỏ tới paper id lạ. Sau đó `evaluate_pipeline` ghi metrics và answers, `run_data_quality_checks(..., "baseline")` gắn freshness vào cờ `success`, rồi `generate_phase1_report`.

`_judge_mode` đọc `reasoning` của từng câu. Nếu mọi câu đều là `Fallback heuristic judge used because the LLM evaluator was unavailable.` thì báo cáo ghi `judge_mode=heuristic fallback`, kể cả khi `.env` vẫn để một LLM provider. Demo agent bọc `try/except`: thiếu key thì bỏ qua, không làm fail baseline.

`corruption_flow.main` dừng ngay nếu thiếu raw records, clean JSON, test set hoặc baseline metrics. Nó không sinh test set mới. Sau `corrupt_clean_dataframe` vẫn index và chấm trên dữ liệu bẩn, vì đó là cách đo silent failure: pipeline không crash. Nếu quality gate `success=false` thì log nêu số check fail rồi mới repair. Repair là `build_clean_dataframe(load_raw_records(...), run_date)`, không gọi API. Hàm được gọi lần hai với cùng `run_date`; hai dataframe phải cùng signature thì `idempotent=true`. So với baseline chỉ trên `paper_id`, `title`, `summary`, `published`, `authors_joined`, `categories_joined`. `age_days` cố ý không nằm trong phép so đó vì nó đổi theo ngày chạy.

`build_question_impact` map `affected_paper_ids` trong `corruption_log.json` sang `ground_truth_doc_ids` của từng câu, rồi lấy hit và token F1 từ ba file answers.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `PaperRecord` từ TV1, DataFrame sạch từ TV2, test set 10 câu, dict quality có `success`, `expectations`, `freshness` từ TV3 |
| Output | Ba bộ metrics/answers, hai báo cáo markdown, `question_impact.json`, ba collection Chroma |
| Module phụ thuộc | `ingestion.crossref`, `ingestion.cleaning`, `ingestion.corruption`, `evaluation.testset`, `evaluation.metrics`, `observability.quality`, `observability.reporting`, `retrieval.index` |
| Module sử dụng output | `generate_phase1_report`, `generate_corruption_report`, báo cáo nhóm |
| Điều kiện lỗi cần xử lý | Thiếu artifact baseline thì thoát và yêu cầu chạy `run_phase1.py`. Demo agent lỗi không được kéo theo baseline. Judge LLM lỗi thì metrics vẫn ghi, nhưng `judge_mode` phải nói đó là heuristic |

### Cách xác minh

```bash
python script/run_phase1.py
python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** cả hai lệnh exit 0. Console corruption in bảng 3 cột và 10 dòng impact. Baseline quality true, corrupted false, repaired true. Repaired log có `same_content=True` và `idempotent=True`.
- **Kết quả thực tế của artifact đang nộp:** hai lệnh đã chạy ra bộ số ngày 2026-09-26 (`phase1_report.md` ghi `2026-09-26 03:40:33 UTC`). Tôi kiểm tra thêm offline: 24 dòng repaired trùng 24 dòng clean trên title, summary, published, authors, categories và cả `age_days`. `question_impact.json` được sinh bằng đúng `build_question_impact` trên ba file answers và corruption log hiện có.
- **Artifact/log:** `data/results/baseline_metrics.json`, `corrupted_metrics.json`, `repaired_metrics.json`, `question_impact.json`, `data/reports/corruption_report.md`.

Lượt sửa này chưa chạy lại toàn bộ hai script. Bước index trong `src/retrieval/index.py` đang gọi `OpenAIEmbeddings()`, trong khi config ghi `all-MiniLM-L6-v2`. Chạy lại cần `OPENAI_API_KEY` và sẽ embed lại ba collection. Vì vậy `phase1_report.md` trên đĩa vẫn là bản của lần chạy trước: header chưa có `judge_mode` và `embedding_backend`. Hai field đó chỉ xuất hiện sau lần chạy `run_phase1.py` tiếp theo.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Repair có thể “trông đúng” nếu chỉ so tập `paper_id`. Một bản vá tay trên dataframe bẩn cũng trả lại đủ 24 id mà title hoặc summary vẫn sai.
- **Các phương án đã cân nhắc:** (1) sửa từng ô bị corruption; (2) rebuild từ raw và chỉ so `paper_id`; (3) rebuild từ raw, so các cột nội dung với baseline, và gọi repair lần hai cùng `run_date`.
- **Phương án đã chọn:** Phương án 3.
- **Lý do:** Vá tay không idempotent và dễ sót cột phái sinh như `text_for_embedding`. So mỗi id không phát hiện title còn bị cắt. Hai lần gọi cùng một `run_date` phải ra cùng dataframe thì mới đúng nghĩa idempotent trong rubric.
- **Bằng chứng:** `papers_clean.json` và `papers_clean_repaired.json` cùng 24 DOI và cùng nội dung. `question_impact.json` cho repaired hit = 1 và token F1 = 1.0 trên cả 10 câu.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** `baseline_metrics.json` có `judge_accuracy=1.0` và `mean_judge_score=5`, dễ bị đọc thành “LLM chấm tuyệt đối”.
- **Lệnh tái hiện:** mở `data/results/baseline_answers.json`, field `judge.reasoning`.
- **Nguyên nhân gốc:** `evaluation/metrics.py` bắt lỗi khi gọi LLM judge rồi chấm bằng token F1: F1 ≥ 0.95 thì điểm 5, ≥ 0.5 thì điểm 3, không thì điểm 1. Cả 10 câu baseline đều F1 = 1.0 nên heuristic cũng ra 5. Provider khai trong môi trường không xuất hiện trong reasoning.
- **Cách xử lý:** `_judge_mode` trong `phase1.py` ghi rõ heuristic fallback vào `source_summary`. Lần `run_phase1.py` sau sẽ in `judge_mode` ra `phase1_report.md`. Tôi không sửa số metrics.
- **Cách xác minh:** mọi câu trong `baseline_answers.json`, `corrupted_answers.json` và `repaired_answers.json` đều có reasoning heuristic, không có nhận xét của model.
- **Điều học được:** Điểm judge trong bài này là hàm của token F1, không phải một giám khảo độc lập. Hai số bằng nhau không có nghĩa hai phép đo cùng bắt một lỗi.

Phần còn mở, chưa xử lý trong file của tôi:

- **Phạm vi:** `src/retrieval/index.py` embed bằng `OpenAIEmbeddings()`. Ba collection trong `data/chroma/chroma.sqlite3` có dimension 1536. Manifest `papers_embeddings.json` vẫn ghi `sentence-transformers/all-MiniLM-L6-v2` vì index ghi `settings.embedding_model`, không ghi class đang chạy. `persist_path` trong manifest là đường dẫn tuyệt đối `D:\AITHUCCHIEN\...`.
- **Đã loại trừ:** metrics và answers không phải số viết tay. Chúng khớp nhau giữa JSON metrics, answers và `corruption_report.md`.
- **Bước tiếp theo:** đưa `index.py` về `MiniLMEmbeddings`, chạy lại hai script, rồi mới kết luận rubric embedding. Máy giám khảo không có `OPENAI_API_KEY` thì pipeline dừng ở bước embed.

## 7. Hiểu biết về luồng end-to-end

1. Crossref (hoặc snapshot `crossref_response.json`) được parse thành `PaperRecord`, lưu `crossref_records.json`. Cleaning khử trùng `paper_id`, tính `age_days`, ghép `text_for_embedding` năm dòng. Index embed cột đó và đưa vào Chroma kèm metadata. QA tìm đúng tiêu đề trong dấu nháy đơn trước, rồi mới tới vector search.
2. Mỗi câu test có `ground_truth_doc_ids`. Hit khi id đó nằm trong danh sách retrieve. Token F1 so câu trả lời với `ground_truth`. Câu trả lời không phải đoạn generate tự do: `qa.py` rút authors, ngày, categories hoặc câu đầu của summary từ metadata của tài liệu đứng đầu.
3. Quality check nhìn cấu trúc: số dòng, not-null, `paper_id` duy nhất, summary dài ít nhất 30 ký tự. Freshness nhìn thời gian: tỷ lệ `age_days > 180` không được quá 0.25. `success` của gate là cả hai cùng đạt. Dữ liệu đủ schema vẫn có thể làm RAG trả lời thông tin cũ.
4. Ba trạng thái dùng một `test_set.json`. Đổi câu hỏi thì không biết điểm giảm vì dữ liệu bẩn hay vì đề khó hơn.
5. Repair thành công khi nội dung repaired trùng clean, quality repaired `success=true`, freshness `is_fresh=true`, và 10 câu có hit cùng token F1 bằng baseline. Trên artifact hiện tại cả bốn điều đó đều đúng.

## 8. Phân tích kết quả

Số liệu lấy từ `data/results/*_metrics.json` và `data/quality/*_quality_report.json` của lần chạy 2026-09-26. Judge trong các file answers là heuristic.

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.000 | 0.700 | 1.000 | Đúng 3/10 câu mất tài liệu: `eval_001`, `eval_002`, `eval_003`, cả ba thuộc `drop_latest_records` |
| `mean_token_f1` | 1.000 | 0.640 | 1.000 | Ngoài 3 câu miss còn `eval_007` và `eval_008` có F1 = 0 dù hit vẫn true |
| `judge_accuracy` | 1.000 | 0.700 | 1.000 | Cũng 7/10, nhưng không phải cùng 7 câu với hit rate. Heuristic cho `eval_002` và `eval_003` là đúng vì F1 0.72 và 0.68 |
| `mean_judge_score` | 5.000 | 3.400 | 5.000 | Ba câu F1 = 0 được điểm 1. Hai câu F1 khoảng 0.7 được điểm 3. Năm câu còn lại điểm 5 |
| Quality checks | true | false | true | Corrupted fail `paper_id` unique và độ dài `summary`. Not-null vẫn pass vì summary rỗng là `""`, không phải null |
| Freshness status | true (1/24 = 0.042) | false (7/22 = 0.318) | true (1/24 = 0.042) | `stale_date` cộng bài cũ sẵn có, sau khi đã bỏ 5 bài mới |

### Kết luận từ số liệu

1. `drop_latest_records` bỏ năm bài mới, trong đó có đúng ba bài của câu summary. Quality gate không thấy việc mất bài: 22 dòng vẫn nằm trong khoảng 5–5000, và các id còn lại không vì thế mà thành null. Hit rate giảm 0.3. `eval_002` và `eval_003` vẫn nhận một bài “Advanced Perspectives” cùng chủ đề, nên F1 còn 0.720 và 0.684. Heuristic coi F1 ≥ 0.5 là đúng. Đó là silent failure kép: gate im, và judge còn chấm đúng trong khi retrieve sai tài liệu. `eval_003` trả về summary đã dính chuỗi `#### xq9 zz@@` của bài khác, bài đó bị `inject_noise`.
2. Repair đọc `crossref_records.json` và clean lại. Dataset repaired trùng dataset clean. Gate và freshness quay về true / 0.042. Cả 10 câu trong `question_impact.json` có hit và token F1 bằng 1.0.

**Corruption nào ảnh hưởng rõ nhất?** Với bộ test này là `drop_latest_records`, vì nó gây cả ba retrieval miss. `truncate_title` và `stale_date` nguy hiểm theo kiểu khác: tài liệu đúng vẫn nằm trong top-k nhưng câu trả lời sai.

- `eval_007` hỏi ngày của bài title bị cắt còn `Advance`. Lookup theo title đầy đủ thất bại, câu trả lời thành `2026-05-02` của một bài khác, trong khi ground truth là `2026-06-06`. Hit vẫn true vì DOI đúng còn ở vị trí thứ ba.
- `eval_008` retrieve đúng bài nhưng ngày đã lùi một năm: trả lời `2025-06-04` thay vì `2026-06-04`.

`blank_summary` (`eval_006`), `inject_noise` (`eval_004`, `eval_009`) và `stale_date` trên câu authors/categories (`eval_005`, `eval_010`) không đổi F1. QA lấy authors, ngày hoặc categories từ metadata, không lấy từ summary, nên summary bẩn không đụng những câu đó. `duplicate_rows` không đụng ground-truth doc nào của 10 câu, nhưng làm fail expectation unique. Gate và agent không bắt cùng một lớp lỗi.

**Kết quả khác kỳ vọng:** Tôi từng đọc hit rate 0.7 và judge accuracy 0.7 như cùng một sự sụt. Đối chiếu từng id thì giao nhau mỗi `eval_001`. Hai câu miss còn lại bị judge cho qua. Hai câu hit mà trả lời sai ngày thì judge bắt được. Không có kịch bản nào một mình giải thích cả bốn metric.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Pipeline:** artifact baseline là đầu vào của corruption flow. Test set tạo một lần. Sửa test set giữa chừng thì bảng ba cột không còn ý nghĩa.
2. **Observability:** unique, độ dài summary và freshness bắt được duplicate, summary rỗng và ngày bị lùi. Chúng không bắt được “mất 20% bài mới nhất”. Muốn thấy lỗi đó phải chấm retrieval trên một test set cố định.
3. **RAG:** hit rate không phải chất lượng câu trả lời. Agent có thể trả lời ngày sai từ đúng metadata đã bị sửa, hoặc trả lời gần đúng từ một bài anh em sau khi bài gốc biến mất, và không ném exception.

### Nếu có thêm thời gian

Đưa embedder trong `index.py` về `MiniLMEmbeddings(settings.embedding_model)`, xóa nhãn MiniLM giả trên vector OpenAI, chạy lại `run_phase1.py` rồi `run_corruption_flow.py`. Cách đo: collection dimension về 384, `phase1_report.md` có `embedding_backend=MiniLMEmbeddings` và `judge_mode`, `question_impact.json` được script ghi lại, repaired vẫn `same_content=true`.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Lê Văn Việt
**Ngày xác nhận:** 2026-09-26
