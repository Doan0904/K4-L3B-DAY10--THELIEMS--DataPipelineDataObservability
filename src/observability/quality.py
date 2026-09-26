from __future__ import annotations

from typing import Any

import pandas as pd
import great_expectations as gx
import great_expectations.expectations as gxe

from core.config import Settings
from core.utils import write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Chạy Data Quality Gate bằng Great Expectations 1.x."""
    # Khởi tạo GX 1.x context
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    # Định nghĩa các rules
    expectations = [
        gxe.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000),
        gxe.ExpectColumnValuesToNotBeNull(column="paper_id"),
        gxe.ExpectColumnValuesToNotBeNull(column="title"),
        gxe.ExpectColumnValuesToNotBeNull(column="text_for_embedding"),
        gxe.ExpectColumnValuesToBeUnique(column="paper_id"),
        gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30),
    ]

    expectations_results = []
    all_success = True

    for exp in expectations:
        result = batch.validate(exp)
        
        exp_success = bool(result.success)
        all_success = all_success and exp_success
        
        # Lấy tên cột nếu có
        kwargs = result.expectation_config.kwargs
        column = kwargs.get("column")
        
        # Trích xuất giá trị quan sát được (observed value)
        observed = None
        if "observed_value" in result.result:
            observed = result.result["observed_value"]
            
        expectations_results.append({
            "name": result.expectation_config.type,
            "column": column,
            "success": exp_success,
            "observed": observed
        })

    # Tính toán freshness
    freshness_report_path = settings.paths.quality_dir / f"{report_name}_freshness_report.json"
    freshness_result = build_freshness_report(df, settings, freshness_report_path)

    # Đánh giá tổng quan (Tất cả rule pass VÀ freshness pass)
    overall_success = all_success and freshness_result["is_fresh"]

    # Đóng gói payload trả về
    final_report = {
        "report_name": report_name,
        "success": overall_success,
        "row_count": len(df),
        "expectations": expectations_results,
        "freshness": freshness_result
    }

    # Ghi báo cáo chất lượng ra file
    quality_report_path = settings.paths.quality_dir / f"{report_name}_quality_report.json"
    write_json(quality_report_path, final_report)

    return final_report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Đánh giá và tổng hợp báo cáo độ tươi mới của dữ liệu."""
    total_rows = len(df)
    
    if total_rows == 0:
        stale_rows = 0
        stale_ratio = 0.0
        latest_published = ""
        oldest_published = ""
    else:
        stale_rows = int((df["age_days"] > settings.freshness_threshold_days).sum())
        stale_ratio = stale_rows / total_rows
        latest_published = str(df["published"].max())
        oldest_published = str(df["published"].min())
        
    is_fresh = stale_ratio <= 0.25
    
    payload = {
        "latest_published": latest_published,
        "oldest_published": oldest_published,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": stale_ratio,
        "threshold_days": settings.freshness_threshold_days,
        "max_stale_ratio": 0.25,
        "is_fresh": is_fresh
    }
    
    write_json(report_path, payload)
    
    return payload
