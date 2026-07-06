#!/usr/bin/env python3
"""Rank a literature candidate table into high, medium, and low priority CSVs."""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path


def contains(text: str, term: str) -> bool:
    return term.lower() in text.lower()


def split_terms(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.replace("|", ";").replace(",", ";").split(";") if item.strip()]


def guess_article_type(title: str, article_type: str) -> str:
    text = f"{title} {article_type}".lower()
    if any(token in text for token in ["systematic review", "meta-analysis", "review"]):
        return "review"
    if any(token in text for token in ["editorial", "commentary", "news", "conference abstract", "patent"]):
        return "exclude_non_article"
    if any(token in text for token in ["journal article", "research article", "article"]):
        return "research_article"
    return article_type or "research_article_like"


def score_row(row: dict[str, str], include_terms: list[str], secondary_terms: list[str], exclude_terms: list[str]) -> dict[str, str]:
    evidence = " ".join(
        [
            row.get("title", ""),
            row.get("abstract_if_available", ""),
            row.get("journal", ""),
            row.get("quality_notes", ""),
        ]
    )
    include_hits = [term for term in include_terms if contains(evidence, term)]
    secondary_hits = [term for term in secondary_terms if contains(evidence, term)]
    exclude_hits = [term for term in exclude_terms if contains(evidence, term)]
    article_type = guess_article_type(row.get("title", ""), row.get("article_type_guess", ""))
    score = 0
    if include_hits:
        score += 2 + min(len(include_hits), 3)
    if secondary_hits:
        score += min(len(secondary_hits), 2)
    if "open" in row.get("open_access_status_if_detectable", "").lower() or row.get("pdf_url_candidate", ""):
        score += 1
    if article_type == "review":
        score -= 1
    if article_type == "exclude_non_article":
        score -= 3
    if exclude_hits and not include_hits:
        score -= 2
    exclusion = row.get("exclusion_reason_if_any", "")
    if not row.get("title", ""):
        exclusion = "missing_title"
    elif article_type == "exclude_non_article":
        exclusion = "non_article_type"
    elif exclude_hits and not include_hits:
        exclusion = "excluded_by_title_abstract_terms"
    elif score < 1:
        exclusion = "low_relevance"
    priority = "high" if score >= 4 else ("medium" if score >= 2 else "low")
    row["article_type_guess"] = article_type
    row["keyword_include_hits"] = "; ".join(include_hits)
    row["keyword_secondary_hits"] = "; ".join(secondary_hits)
    row["keyword_exclude_hits"] = "; ".join(exclude_hits)
    row["keyword_relevance_score"] = str(score)
    row["priority"] = priority
    row["exclusion_reason_if_any"] = exclusion
    if not row.get("download_status"):
        row["download_status"] = "excluded" if exclusion else "pending"
    return row


def read_config_terms(run_root: Path) -> tuple[list[str], list[str], list[str]]:
    import json

    config = json.loads((run_root / "config.json").read_text(encoding="utf-8"))
    return (
        [str(item) for item in config.get("include_terms", [])],
        [str(item) for item in config.get("secondary_terms", [])],
        [str(item) for item in config.get("exclude_terms", [])],
    )


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def copy_alias(source: Path, alias: Path) -> None:
    if source.exists():
        shutil.copyfile(source, alias)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank literature candidates by topic relevance.")
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()

    run_root = Path(args.run_root).expanduser().resolve()
    candidate_path = run_root / "candidate_table.csv"
    include_terms, secondary_terms, exclude_terms = read_config_terms(run_root)

    with candidate_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [score_row(dict(row), include_terms, secondary_terms, exclude_terms) for row in reader]

    rows.sort(key=lambda row: int(row.get("keyword_relevance_score") or 0), reverse=True)
    write_rows(candidate_path, fieldnames, rows)
    copy_alias(candidate_path, run_root / "候选文献总表.csv")
    high_path = run_root / "high_priority.csv"
    medium_path = run_root / "medium_priority.csv"
    low_path = run_root / "low_priority.csv"
    write_rows(high_path, fieldnames, [row for row in rows if row.get("priority") == "high" and not row.get("exclusion_reason_if_any")])
    write_rows(medium_path, fieldnames, [row for row in rows if row.get("priority") == "medium" and not row.get("exclusion_reason_if_any")])
    write_rows(low_path, fieldnames, [row for row in rows if row.get("priority") == "low" or row.get("exclusion_reason_if_any")])
    copy_alias(high_path, run_root / "高优先级文献.csv")
    copy_alias(medium_path, run_root / "中优先级文献.csv")
    copy_alias(low_path, run_root / "低优先级文献.csv")
    print(f"Ranked {len(rows)} candidates in {run_root}")


if __name__ == "__main__":
    main()
