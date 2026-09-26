from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def _log(step: str, message: str) -> None:
    print(f"[corruption] {step:<10} {message}")


def _require_baseline(settings: Settings) -> None:
    paths = settings.paths
    required = [paths.raw_records_json, paths.clean_json, paths.eval_testset, paths.baseline_metrics]
    missing = [str(path.relative_to(paths.project_dir)) for path in required if not path.exists()]
    if missing:
        raise SystemExit(f"Missing baseline artifacts {missing}. Run `python script/run_phase1.py` first.")


def _save_dataset(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    write_csv(df, csv_path)
    write_json(json_path, df.to_dict(orient="records"))


def _evaluate_state(
    settings: Settings,
    df: pd.DataFrame,
    embeddings_path: Path,
    metrics_path: Path,
    answers_path: Path,
    label: str,
) -> dict[str, Any]:
    """Index `df` into its own Chroma collection and score it on the shared baseline test set."""
    index = LocalEmbeddingIndex.build(df, settings, embeddings_path)
    summary = evaluate_pipeline(settings, index, settings.paths.eval_testset, metrics_path, answers_path).summary
    _log(
        label,
        f"collection='{index.collection_name}' hit_rate={summary['retrieval_hit_rate']:.3f} "
        f"token_f1={summary['mean_token_f1']:.3f} judge_acc={summary['judge_accuracy']:.3f}",
    )
    return summary


def _failed_checks(quality: dict[str, Any]) -> list[str]:
    failed = [
        f"{item['name']}({item['column']})" if item.get("column") else item["name"]
        for item in quality["expectations"]
        if not item["success"]
    ]
    if not quality["freshness"]["is_fresh"]:
        failed.append(f"freshness(stale_ratio={quality['freshness']['stale_ratio']:.3f})")
    return failed


def _repair_from_raw_snapshot(settings: Settings, run_date: datetime) -> pd.DataFrame:
    """Rebuild the clean dataset from the preserved raw records (lineage anchor).

    No API call and no patching of the corrupted frame: the corrupted data is discarded
    and the trusted raw snapshot goes through the same cleaning code again, so running
    the repair any number of times yields the same dataset (idempotent).
    """
    return build_clean_dataframe(load_raw_records(settings.paths.raw_records_json), run_date)


def main() -> None:
    """Corruption flow: corrupt -> quality gate -> evaluate -> auto-repair -> re-evaluate -> compare."""
    settings = load_settings()
    paths = settings.paths
    _require_baseline(settings)
    run_date = now_utc()

    baseline_metrics = read_json(paths.baseline_metrics)
    clean_df = pd.DataFrame(read_json(paths.clean_json))
    _log("baseline", f"{len(clean_df)} clean rows, test set {paths.eval_testset.name} (reused, not rebuilt)")

    # 1. Corrupt the clean dataset.
    corrupted_df = corrupt_clean_dataframe(clean_df, paths.corruption_log)
    _save_dataset(corrupted_df, paths.corrupted_clean_csv, paths.corrupted_clean_json)
    scenarios = [entry["scenario"] for entry in read_json(paths.corruption_log)]
    _log("corrupt", f"{len(clean_df)} -> {len(corrupted_df)} rows, scenarios={scenarios}")

    # 2. Quality gate on the corrupted data.
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    failed = _failed_checks(corrupted_quality)
    _log("quality", f"corrupted success={corrupted_quality['success']} failed={failed}")

    # 3. Index + evaluate anyway to measure the silent-failure impact on the agent.
    corrupted_metrics = _evaluate_state(
        settings, corrupted_df, paths.corrupted_embeddings_json, paths.corrupted_metrics, paths.corrupted_answers, "corrupted"
    )

    # 4. Repair, triggered by the quality gate.
    if corrupted_quality["success"]:
        _log("repair", "quality gate passed -> repair still run so the three states can be compared")
    else:
        _log("repair", f"quality gate FAILED on {len(failed)} check(s) -> auto-repair from raw snapshot")
    repaired_df = _repair_from_raw_snapshot(settings, run_date)
    _save_dataset(repaired_df, paths.repaired_clean_csv, paths.repaired_clean_json)
    same_ids = sorted(repaired_df["paper_id"]) == sorted(clean_df["paper_id"])
    _log("repair", f"{len(repaired_df)} rows rebuilt from {paths.raw_records_json.name}, same paper_ids as baseline={same_ids}")

    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    _log("quality", f"repaired success={repaired_quality['success']} failed={_failed_checks(repaired_quality)}")

    repaired_metrics = _evaluate_state(
        settings, repaired_df, paths.repaired_embeddings_json, paths.repaired_metrics, paths.repaired_answers, "repaired"
    )

    # 5. Three-state comparison report (also printed to the console by the reporting module).
    generate_corruption_report(
        paths.comparison_report,
        baseline_metrics,
        corrupted_metrics,
        repaired_metrics,
        corrupted_quality,
        repaired_quality,
        corrupted_quality["freshness"],
        repaired_quality["freshness"],
    )
    _log("report", f"-> {paths.comparison_report.relative_to(paths.project_dir)}")
