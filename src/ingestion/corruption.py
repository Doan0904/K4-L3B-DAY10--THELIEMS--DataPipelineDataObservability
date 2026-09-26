from __future__ import annotations

from datetime import date, timedelta
import math
from typing import Any

import pandas as pd

from core.utils import write_json

DROP_LATEST_RATIO = 0.2
TRUNCATED_TITLE_LENGTH = 7
STALE_SHIFT_DAYS = 365
# No sentence-ending punctuation, so the noise merges into the summary's first sentence.
NOISE_PREFIX = "#### xq9 zz@@ %%lorem-noise%% ~~ ####"

# Row positions (after dropping the latest records, sorted newest first) hit by each
# scenario. The sets are disjoint so every scenario's effect stays attributable.
BLANK_SUMMARY_POSITIONS = (0, 5, 10)
NOISE_POSITIONS = (1, 6, 11)
TRUNCATE_TITLE_POSITIONS = (2, 7, 12)
STALE_DATE_POSITIONS = (3, 4, 8, 9, 13, 14)
DUPLICATE_POSITIONS = (15, 16, 17)


def _build_text_for_embedding(row: pd.Series) -> str:
    """Same 5-line layout as the clean dataset (see docs/PHAN_CONG.md, section 2.2)."""
    return (
        f"Title: {row['title']}\n"
        f"Authors: {row['authors_joined']}\n"
        f"Published: {row['published']}\n"
        f"Categories: {row['categories_joined']}\n"
        f"Summary: {row['summary']}"
    )


def _valid_positions(df: pd.DataFrame, positions: tuple[int, ...]) -> list[int]:
    return [position for position in positions if position < len(df)]


def _paper_ids(df: pd.DataFrame, labels) -> list[str]:
    return [str(paper_id) for paper_id in df.loc[labels, "paper_id"]]


def _log_entry(scenario: str, description: str, paper_ids: list[str], params: dict[str, Any]) -> dict[str, Any]:
    return {
        "scenario": scenario,
        "description": description,
        "affected_rows": len(paper_ids),
        "affected_paper_ids": paper_ids,
        "params": params,
    }


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Inject 6 deterministic data-quality incidents into a clean dataset.

    1. drop_latest_records  - lose the newest 20% of papers (stale index / missed load).
    2. blank_summary        - empty abstracts (completeness).
    3. inject_noise         - garbage prefixed to abstracts (validity / accuracy).
    4. truncate_title       - titles cut below 8 characters (validity, breaks exact lookup).
    5. stale_date           - publication dates pushed back 365 days (freshness).
    6. duplicate_rows       - repeated paper_ids (uniqueness).

    `summary_chars` and `text_for_embedding` are rebuilt afterwards so the corrupted
    content is what actually gets embedded. Every change is written to `output_log_path`.
    """
    input_rows = len(df)
    corrupted = (
        df.copy(deep=True)
        .sort_values(["published", "paper_id"], ascending=[False, True])
        .reset_index(drop=True)
    )
    log: list[dict[str, Any]] = []

    # 1. Drop latest records.
    drop_count = math.ceil(len(corrupted) * DROP_LATEST_RATIO)
    dropped_labels = corrupted.index[:drop_count]
    log.append(
        _log_entry(
            "drop_latest_records",
            f"Removed the newest {drop_count} papers by published date.",
            _paper_ids(corrupted, dropped_labels),
            {"ratio": DROP_LATEST_RATIO, "dropped_rows": drop_count},
        )
    )
    corrupted = corrupted.drop(index=dropped_labels).reset_index(drop=True)

    # 2. Blank summary.
    labels = _valid_positions(corrupted, BLANK_SUMMARY_POSITIONS)
    corrupted.loc[labels, "summary"] = ""
    log.append(
        _log_entry(
            "blank_summary",
            "Replaced the abstract with an empty string.",
            _paper_ids(corrupted, labels),
            {"positions": labels, "value": ""},
        )
    )

    # 3. Inject noise.
    labels = _valid_positions(corrupted, NOISE_POSITIONS)
    corrupted.loc[labels, "summary"] = [f"{NOISE_PREFIX} {summary}" for summary in corrupted.loc[labels, "summary"]]
    log.append(
        _log_entry(
            "inject_noise",
            "Prefixed garbage characters to the abstract.",
            _paper_ids(corrupted, labels),
            {"positions": labels, "noise_prefix": NOISE_PREFIX},
        )
    )

    # 4. Truncate title.
    labels = _valid_positions(corrupted, TRUNCATE_TITLE_POSITIONS)
    original_titles = list(corrupted.loc[labels, "title"])
    corrupted.loc[labels, "title"] = [title[:TRUNCATED_TITLE_LENGTH] for title in original_titles]
    entry = _log_entry(
        "truncate_title",
        f"Cut the title to {TRUNCATED_TITLE_LENGTH} characters.",
        _paper_ids(corrupted, labels),
        {"positions": labels, "max_length": TRUNCATED_TITLE_LENGTH},
    )
    entry["changes"] = [
        {"paper_id": paper_id, "before": before, "after": before[:TRUNCATED_TITLE_LENGTH]}
        for paper_id, before in zip(entry["affected_paper_ids"], original_titles)
    ]
    log.append(entry)

    # 5. Stale date.
    labels = _valid_positions(corrupted, STALE_DATE_POSITIONS)
    changes = []
    for label in labels:
        before = str(corrupted.at[label, "published"])
        after = (date.fromisoformat(before[:10]) - timedelta(days=STALE_SHIFT_DAYS)).isoformat()
        corrupted.at[label, "published"] = after
        if "age_days" in corrupted.columns:
            corrupted.at[label, "age_days"] = int(corrupted.at[label, "age_days"]) + STALE_SHIFT_DAYS
        changes.append({"paper_id": str(corrupted.at[label, "paper_id"]), "before": before, "after": after})
    entry = _log_entry(
        "stale_date",
        f"Moved the publication date back {STALE_SHIFT_DAYS} days.",
        [change["paper_id"] for change in changes],
        {"positions": labels, "shift_days": STALE_SHIFT_DAYS},
    )
    entry["changes"] = changes
    log.append(entry)

    # 6. Duplicate rows.
    labels = _valid_positions(corrupted, DUPLICATE_POSITIONS)
    duplicates = corrupted.loc[labels].copy()
    log.append(
        _log_entry(
            "duplicate_rows",
            "Appended exact copies of existing rows (same paper_id).",
            _paper_ids(corrupted, labels),
            {"positions": labels, "copies_per_row": 1},
        )
    )
    corrupted = pd.concat([corrupted, duplicates], ignore_index=True)

    # 7. Rebuild derived columns so embeddings reflect the corrupted content.
    corrupted["summary_chars"] = corrupted["summary"].str.len().astype(int)
    corrupted["text_for_embedding"] = corrupted.apply(_build_text_for_embedding, axis=1)

    # 8. Persist the corruption log.
    for entry in log:
        entry["input_rows"] = input_rows
        entry["output_rows"] = len(corrupted)
    write_json(output_log_path, log)
    return corrupted
