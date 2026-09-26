from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from typing import Any

import pandas as pd

from core.utils import normalize_whitespace
from ingestion.crossref import PaperRecord


def build_text_for_embedding(row: dict[str, Any] | pd.Series) -> str:
    """Build standardized 5-line text block used for embedding.

    Format:
    Title: ...
    Authors: ...
    Published: ...
    Categories: ...
    Summary: ...
    """
    title = row.get("title", "") if isinstance(row, dict) else row["title"]
    authors_joined = row.get("authors_joined", "") if isinstance(row, dict) else row["authors_joined"]
    published = row.get("published", "") if isinstance(row, dict) else row["published"]
    categories_joined = row.get("categories_joined", "") if isinstance(row, dict) else row["categories_joined"]
    summary = row.get("summary", "") if isinstance(row, dict) else row["summary"]
    return (
        f"Title: {title}\n"
        f"Authors: {authors_joined}\n"
        f"Published: {published}\n"
        f"Categories: {categories_joined}\n"
        f"Summary: {summary}"
    )


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records and return a standardized DataFrame ready for indexing.

    Steps according to contract:
    1. Convert records to DataFrame.
    2. Normalize whitespace in title, summary, and clean authors/categories lists.
    3. Standardize published and updated dates to 'YYYY-MM-DD' strings.
    4. Compute age_days based on run_date (UTC).
    5. Construct helper columns: authors_joined, categories_joined, summary_chars, text_for_embedding.
    6. Drop rows with empty title/summary and deduplicate on paper_id (keep='first').
    7. Sort by published descending, then paper_id ascending; reset index.
    """
    if not records:
        cols = [
            "paper_id", "title", "summary", "authors", "categories",
            "primary_category", "published", "updated", "abs_url", "pdf_url", "comment",
            "authors_joined", "categories_joined", "summary_chars", "age_days", "text_for_embedding",
        ]
        return pd.DataFrame(columns=cols)

    # 1. Convert to DataFrame
    raw_dicts = [asdict(r) if hasattr(r, "__dataclass_fields__") else dict(r) for r in records]
    df = pd.DataFrame(raw_dicts)

    # 2. Normalize whitespace for title and summary
    df["title"] = df["title"].fillna("").astype(str).map(normalize_whitespace)
    df["summary"] = df["summary"].fillna("").astype(str).map(normalize_whitespace)

    def clean_str_list(items: Any) -> list[str]:
        if not isinstance(items, (list, tuple)):
            return []
        return [str(item).strip() for item in items if item and str(item).strip()]

    df["authors"] = df["authors"].map(clean_str_list)
    df["categories"] = df["categories"].map(clean_str_list)

    # 3. Standardize published and updated to 'YYYY-MM-DD' string
    df["published"] = pd.to_datetime(df["published"], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
    df["updated"] = pd.to_datetime(df["updated"], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")

    # 4. Compute age_days
    run_d = run_date.date() if isinstance(run_date, datetime) else run_date

    def calc_age_days(pub_val: str) -> int:
        if not pub_val:
            return 0
        try:
            pub_d = date.fromisoformat(str(pub_val)[:10])
            return (run_d - pub_d).days
        except Exception:
            return 0

    df["age_days"] = df["published"].map(calc_age_days).astype(int)

    # 5. Helper columns
    df["authors_joined"] = df["authors"].map(lambda a: ", ".join(a) if isinstance(a, list) else "")
    df["categories_joined"] = df["categories"].map(lambda c: ", ".join(c) if isinstance(c, list) else "")
    df["summary_chars"] = df["summary"].map(lambda s: len(s) if isinstance(s, str) else 0).astype(int)
    df["text_for_embedding"] = df.apply(build_text_for_embedding, axis=1)

    # 6. Filter empty title or summary & deduplicate on paper_id
    df = df[(df["title"].str.strip() != "") & (df["summary"].str.strip() != "")]
    df = df.drop_duplicates(subset=["paper_id"], keep="first")

    # 7. Sort by published descending, then paper_id ascending
    df = df.sort_values(by=["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)

    return df
