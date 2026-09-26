# Báo cáo Phase 1 (Baseline)

## 1. Thông tin nguồn dữ liệu
- **source_api**: https://api.crossref.org/works
- **source_query**: agentic retrieval augmented generation large language model
- **source_filter**: from-pub-date:2026-03-30,has-abstract:true
- **raw_records_count**: 24
- **clean_records_count**: 24
- **run_time**: 2026-09-26 03:40:33 UTC

## 2. Kết quả Evaluation Metrics
| Metric | Giá trị |
|---|---|
| samples | 10.000 |
| retrieval_hit_rate | 1.000 |
| mean_token_f1 | 1.000 |
| judge_accuracy | 1.000 |
| mean_judge_score | 5.000 |

## 3. Data Quality Gate & Freshness
- **Tổng quan Quality Gate**: ✅ PASS
- **Tổng quan Freshness**: ✅ YES

### Chi tiết Expectations (Great Expectations 1.x)
| Tên Rule (Expectation) | Cột áp dụng | Kết quả | Giá trị quan sát |
|---|---|---|---|
| expect_table_row_count_to_be_between | - | ✅ Pass | 24 |
| expect_column_values_to_not_be_null | paper_id | ✅ Pass | - |
| expect_column_values_to_not_be_null | title | ✅ Pass | - |
| expect_column_values_to_not_be_null | text_for_embedding | ✅ Pass | - |
| expect_column_values_to_be_unique | paper_id | ✅ Pass | - |
| expect_column_value_lengths_to_be_between | summary | ✅ Pass | - |

### Chi tiết Freshness (Độ tươi mới)
| Tiêu chí | Giá trị |
|---|---|
| latest_published | 2026-07-22 |
| oldest_published | 2026-03-28 |
| stale_rows | 1 |
| total_rows | 24 |
| stale_ratio | 0.042 |
| threshold_days | 180 |
| max_stale_ratio | 0.250 |
| is_fresh | True |
