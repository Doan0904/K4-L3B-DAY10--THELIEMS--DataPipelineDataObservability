from __future__ import annotations

from typing import Any

from core.config import Settings, load_settings, require_llm_credentials
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex

DEMO_QUESTION_LIMIT = 2


def _log(step: str, message: str) -> None:
    print(f"[phase1] {step:<10} {message}")


def _ensure_test_set(df, settings: Settings) -> list[dict[str, Any]]:
    """Build the evaluation set once; later runs (and the corruption flow) reuse the same file."""
    path = settings.paths.eval_testset
    if path.exists() and not settings.refresh_test_set:
        test_set = read_json(path)
        known_ids = set(df["paper_id"])
        if all(doc_id in known_ids for item in test_set for doc_id in item["ground_truth_doc_ids"]):
            return test_set
        _log("testset", "existing test set references unknown paper_ids -> rebuilding")
    return build_test_set(df, path)


def _run_agent_demo(settings: Settings, index: LocalEmbeddingIndex, test_set: list[dict[str, Any]]) -> None:
    """Optional: ask the tool-using agent a couple of benchmark questions. Never fails the pipeline."""
    try:
        require_llm_credentials(settings)
        from retrieval.agent import build_agent, run_agent_question

        agent = build_agent(settings, index)
        answers = [
            {"question": item["question"], "answer": run_agent_question(agent, item["question"])}
            for item in test_set[:DEMO_QUESTION_LIMIT]
        ]
        write_json(settings.paths.demo_answers, answers)
        _log("agent", f"demo answers -> {settings.paths.demo_answers.name}")
    except Exception as exc:  # the demo depends on an external LLM; the baseline must not
        _log("agent", f"demo skipped ({type(exc).__name__}: {str(exc)[:120]})")


def main() -> None:
    """Baseline pipeline: ingest -> clean -> index -> test set -> evaluate -> quality gate -> report."""
    settings = load_settings()
    paths = settings.paths
    run_date = now_utc()

    records = fetch_source_records(settings)
    _log("ingest", f"{len(records)} raw records -> {paths.raw_records_json.name}")

    df = build_clean_dataframe(records, run_date)
    write_csv(df, paths.clean_csv)
    write_json(paths.clean_json, df.to_dict(orient="records"))
    _log("clean", f"{len(df)} rows -> {paths.clean_csv.name}, {paths.clean_json.name}")

    index = LocalEmbeddingIndex.build(df, settings, paths.embeddings_json)
    _log("index", f"{len(index.documents)} docs -> Chroma collection '{index.collection_name}'")

    test_set = _ensure_test_set(df, settings)
    _log("testset", f"{len(test_set)} questions -> {paths.eval_testset.name}")

    bundle = evaluate_pipeline(settings, index, paths.eval_testset, paths.baseline_metrics, paths.baseline_answers)
    metrics = bundle.summary
    _log(
        "evaluate",
        f"hit_rate={metrics['retrieval_hit_rate']:.3f} token_f1={metrics['mean_token_f1']:.3f} "
        f"judge_acc={metrics['judge_accuracy']:.3f} -> {paths.baseline_metrics.name}",
    )

    quality = run_data_quality_checks(df, settings, "baseline")
    freshness = build_freshness_report(df, settings, paths.freshness_report)
    failed = [item["name"] for item in quality["expectations"] if not item["success"]]
    _log(
        "quality",
        f"success={quality['success']} is_fresh={freshness['is_fresh']} "
        f"stale={freshness['stale_rows']}/{freshness['total_rows']}" + (f" failed={failed}" if failed else ""),
    )

    source_summary = {
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "source_filter": settings.source_filter,
        "source_mode": (
            "live API requested (falls back to snapshot on failure)"
            if settings.refresh_source
            else "local snapshot (set REFRESH_SOURCE=1 for live API)"
        ),
        "raw_records": len(records),
        "clean_rows": len(df),
        "embedding_model": settings.embedding_model,
        "collection": index.collection_name,
        "top_k": settings.top_k,
        "llm_provider": settings.llm_provider,
        "run_at_utc": run_date.isoformat(timespec="seconds"),
    }
    generate_phase1_report(paths.baseline_report, source_summary, metrics, quality, freshness)
    _log("report", f"-> {paths.baseline_report.relative_to(paths.project_dir)}")

    _run_agent_demo(settings, index, test_set)
    _log("done", "baseline pipeline finished")
