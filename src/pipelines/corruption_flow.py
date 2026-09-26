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


_CONTENT_FIELDS = ("paper_id", "title", "summary", "published", "authors_joined", "categories_joined")


def _content_rows(df: pd.DataFrame) -> list[tuple[str, ...]]:
    """Identity of the fields a reader sees. `age_days` is excluded because it follows the clock."""
    rows = []
    for record in df.to_dict(orient="records"):
        rows.append(tuple(str(record.get(field, "")) for field in _CONTENT_FIELDS))
    return sorted(rows)


def _frame_signature(df: pd.DataFrame) -> list[tuple]:
    rows = []
    for record in df.to_dict(orient="records"):
        items = []
        for key in sorted(record):
            value = record[key]
            if isinstance(value, list):
                value = tuple(value)
            items.append((key, value))
        rows.append(tuple(items))
    return sorted(rows)


def build_question_impact(
    test_set: list[dict[str, Any]],
    corruption_log: list[dict[str, Any]],
    baseline_answers: list[dict[str, Any]],
    corrupted_answers: list[dict[str, Any]],
    repaired_answers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Join each benchmark question to the corruption scenarios that touched its document."""
    scenarios_by_paper: dict[str, list[str]] = {}
    for entry in corruption_log:
        for paper_id in entry.get("affected_paper_ids", []):
            scenarios_by_paper.setdefault(str(paper_id), []).append(str(entry["scenario"]))

    def by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {str(row["id"]): row for row in rows}

    baseline = by_id(baseline_answers)
    corrupted = by_id(corrupted_answers)
    repaired = by_id(repaired_answers)
    impact: list[dict[str, Any]] = []
    for item in test_set:
        question_id = str(item["id"])
        doc_ids = [str(doc_id) for doc_id in item["ground_truth_doc_ids"]]
        scenarios: list[str] = []
        for doc_id in doc_ids:
            scenarios.extend(scenarios_by_paper.get(doc_id, []))
        base = baseline[question_id]
        dirty = corrupted[question_id]
        fixed = repaired[question_id]
        impact.append(
            {
                "id": question_id,
                "question_type": item["question_type"],
                "ground_truth_doc_ids": doc_ids,
                "scenarios": scenarios,
                "ground_truth": item["ground_truth"],
                "baseline_hit": bool(base["retrieval_hit"]),
                "corrupted_hit": bool(dirty["retrieval_hit"]),
                "repaired_hit": bool(fixed["retrieval_hit"]),
                "baseline_token_f1": base["token_f1"],
                "corrupted_token_f1": dirty["token_f1"],
                "repaired_token_f1": fixed["token_f1"],
                "corrupted_answer": dirty["answer"],
                "repaired_answer": fixed["answer"],
                "corrupted_judge_correct": bool(dirty["judge"]["correct"]),
            }
        )
    return impact


def _print_question_impact(impact: list[dict[str, Any]]) -> None:
    _log("impact", "question | type | scenario | hit | token_f1 | judge_correct")
    for row in impact:
        scenario = ",".join(row["scenarios"]) or "-"
        _log(
            "impact",
            f"{row['id']} {row['question_type']:<10} {scenario:<22} "
            f"hit {int(row['baseline_hit'])}->{int(row['corrupted_hit'])}->{int(row['repaired_hit'])} "
            f"f1 {row['baseline_token_f1']:.3f}->{row['corrupted_token_f1']:.3f}->{row['repaired_token_f1']:.3f} "
            f"judge_correct={row['corrupted_judge_correct']}",
        )


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
    repaired_again = _repair_from_raw_snapshot(settings, run_date)
    same_ids = sorted(repaired_df["paper_id"]) == sorted(clean_df["paper_id"])
    same_content = _content_rows(repaired_df) == _content_rows(clean_df)
    idempotent = _frame_signature(repaired_df) == _frame_signature(repaired_again)
    _log(
        "repair",
        f"{len(repaired_df)} rows rebuilt from {paths.raw_records_json.name}, "
        f"same_paper_ids={same_ids} same_content={same_content} idempotent={idempotent}",
    )

    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    _log("quality", f"repaired success={repaired_quality['success']} failed={_failed_checks(repaired_quality)}")

    repaired_metrics = _evaluate_state(
        settings, repaired_df, paths.repaired_embeddings_json, paths.repaired_metrics, paths.repaired_answers, "repaired"
    )

    # 5. Attribute each benchmark question to the scenario that touched its document.
    impact = build_question_impact(
        read_json(paths.eval_testset),
        read_json(paths.corruption_log),
        read_json(paths.baseline_answers),
        read_json(paths.corrupted_answers),
        read_json(paths.repaired_answers),
    )
    impact_path = paths.corruption_log.with_name("question_impact.json")
    write_json(impact_path, {"samples": len(impact), "questions": impact})
    _print_question_impact(impact)
    _log("impact", f"-> {impact_path.relative_to(paths.project_dir)}")

    # 6. Three-state comparison report (also printed to the console by the reporting module).
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
