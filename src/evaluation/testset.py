from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json


def build_test_set(df: pd.DataFrame, output_path: str | Path) -> list[dict[str, Any]]:
    """Build a deterministic benchmark test set of 10 questions from cleaned DataFrame.

    Distribution required by contract:
    - 3 summary questions
    - 3 authors questions
    - 2 date questions
    - 2 categories questions
    All titles quoted in single quotes '...' for exact lookup.
    """
    if len(df) < 10:
        raise ValueError(f"Cleaned DataFrame has only {len(df)} rows; minimum 10 required.")

    # Select 10 distinct papers deterministically, spread across dataset
    if len(df) >= 20:
        sample_indices = [i * 2 for i in range(10)]
    else:
        sample_indices = list(range(10))

    selected_rows = df.iloc[sample_indices].to_dict(orient="records")

    # 3 summary, 3 authors, 2 date, 2 categories
    question_types = [
        "summary",
        "summary",
        "summary",
        "authors",
        "authors",
        "authors",
        "date",
        "date",
        "categories",
        "categories",
    ]

    items: list[dict[str, Any]] = []

    for i, (q_type, row) in enumerate(zip(question_types, selected_rows)):
        title = row["title"]
        paper_id = str(row["paper_id"])

        if q_type == "summary":
            question = f"What is the summary of the paper '{title}'?"
            ground_truth = first_sentence(str(row["summary"]))
        elif q_type == "authors":
            question = f"Who authored the paper '{title}'?"
            ground_truth = str(row["authors_joined"])
        elif q_type == "date":
            question = f"When was the paper '{title}' published?"
            ground_truth = str(row["published"])
        elif q_type == "categories":
            # Ensure categories_joined is non-empty
            cat_joined = str(row["categories_joined"]).strip()
            if not cat_joined:
                # Fallback to any row with non-empty categories
                cat_rows = df[df["categories_joined"].str.strip() != ""]
                if not cat_rows.empty:
                    fallback_row = cat_rows.iloc[0]
                    title = fallback_row["title"]
                    paper_id = str(fallback_row["paper_id"])
                    cat_joined = str(fallback_row["categories_joined"]).strip()
            question = f"What categories does the paper '{title}' belong to?"
            ground_truth = cat_joined
        else:
            raise ValueError(f"Unknown question type: {q_type}")

        items.append(
            {
                "id": f"eval_{i + 1:03d}",
                "question_type": q_type,
                "question": question,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [paper_id],
            }
        )

    out_p = Path(output_path)
    write_json(out_p, items)
    return items
