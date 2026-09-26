from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
import time
from typing import Any

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json

CROSSREF_WORKS_URL = "https://api.crossref.org/works"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_RETRIES = 4
REQUEST_TIMEOUT_SECONDS = 30

_TAG_PATTERN = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _strip_markup(text: str) -> str:
    """Remove JATS/HTML tags (e.g. `<jats:p>`) and collapse whitespace."""
    return normalize_whitespace(_TAG_PATTERN.sub(" ", text or ""))


def _first_text(value: Any) -> str:
    if isinstance(value, list):
        value = value[0] if value else ""
    return normalize_whitespace(str(value or ""))


def _parse_authors(raw_authors: list[dict[str, Any]] | None) -> list[str]:
    authors: list[str] = []
    for author in raw_authors or []:
        name = normalize_whitespace(f"{author.get('given', '')} {author.get('family', '')}")
        name = name or normalize_whitespace(str(author.get("name", "")))
        if name:
            authors.append(name)
    return authors


def _parse_date_parts(value: dict[str, Any] | None) -> str:
    """Convert Crossref `{"date-parts": [[YYYY, MM, DD]]}` to `YYYY-MM-DD` (missing month/day -> 1)."""
    parts = ((value or {}).get("date-parts") or [[]])[0] or []
    if not parts or parts[0] is None:
        return ""
    year, month, day = (list(parts) + [1, 1])[:3]
    return f"{int(year):04d}-{int(month or 1):02d}-{int(day or 1):02d}"


def _parse_published(item: dict[str, Any]) -> str:
    for key in ("published", "published-online", "published-print", "issued", "created"):
        published = _parse_date_parts(item.get(key))
        if published:
            return published
    return ""


def _parse_updated(item: dict[str, Any], published: str) -> str:
    for key in ("created", "deposited", "indexed"):
        date_time = str((item.get(key) or {}).get("date-time", ""))
        if len(date_time) >= 10:
            return date_time[:10]
    return published


def _parse_item(item: dict[str, Any]) -> PaperRecord | None:
    doi = normalize_whitespace(str(item.get("DOI", "")))
    title = _first_text(item.get("title"))
    summary = _strip_markup(str(item.get("abstract", "")))
    published = _parse_published(item)
    if not doi or not title or not summary or not published:
        return None

    categories = [normalize_whitespace(str(subject)) for subject in item.get("subject") or []]
    categories = [category for category in categories if category]
    abs_url = normalize_whitespace(str(item.get("URL", ""))) or f"https://doi.org/{doi}"
    links = item.get("link") or []
    pdf_url = normalize_whitespace(str(links[0].get("URL", ""))) if links else ""

    return PaperRecord(
        paper_id=doi,
        title=title,
        summary=summary,
        authors=_parse_authors(item.get("author")),
        categories=categories,
        primary_category=categories[0] if categories else "",
        published=published,
        updated=_parse_updated(item, published),
        abs_url=abs_url,
        pdf_url=pdf_url or abs_url,
        comment=f"Crossref record {doi}",
    )


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse a Crossref `/works` payload into `PaperRecord`s.

    Items missing a DOI, title, abstract or publication date are skipped, and
    duplicate DOIs keep only their first occurrence.
    """
    records: list[PaperRecord] = []
    seen_ids: set[str] = set()
    for item in (payload.get("message") or {}).get("items") or []:
        record = _parse_item(item)
        if record is None or record.paper_id.lower() in seen_ids:
            continue
        seen_ids.add(record.paper_id.lower())
        records.append(record)
    return records


def _request_crossref(settings: Settings) -> dict[str, Any]:
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    headers = {"User-Agent": "K4-DAY10-DataObservabilityLab/0.1 (educational use)"}
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(
                CROSSREF_WORKS_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS
            )
            if response.status_code in RETRYABLE_STATUS_CODES:
                raise requests.HTTPError(f"Crossref returned HTTP {response.status_code}", response=response)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status is not None and status not in RETRYABLE_STATUS_CODES:
                break
            if attempt < MAX_RETRIES - 1:
                time.sleep(2**attempt)
    raise RuntimeError(f"Crossref request failed after retries: {last_error}")


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Load source records and persist both raw artifacts for lineage.

    By default the committed snapshot (`data/raw/crossref_response.json`) is the
    source of truth so runs are reproducible. With `REFRESH_SOURCE=1` the live
    Crossref API is called (with retry/backoff on 429/5xx); if that fails, the
    pipeline falls back to the snapshot instead of aborting.
    """
    snapshot_path = settings.paths.raw_api_response
    payload: dict[str, Any] | None = None

    if settings.refresh_source or not snapshot_path.exists():
        try:
            payload = _request_crossref(settings)
            write_json(snapshot_path, payload)
            print(f"[ingestion] Fetched live data from {settings.source_api}.")
        except RuntimeError as exc:
            if not snapshot_path.exists():
                raise
            print(f"[ingestion] {exc} -> falling back to local snapshot {snapshot_path.name}.")

    if payload is None:
        payload = read_json(snapshot_path)
        print(f"[ingestion] Using local snapshot {snapshot_path.name}.")

    records = parse_crossref_payload(payload)
    if not records:
        raise ValueError("Crossref payload produced no valid records.")
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Read the raw records snapshot and map each row back to `PaperRecord`."""
    return [PaperRecord(**row) for row in read_json(path)]
