#!/usr/bin/env python3
"""Create a reproducible literature harvest run scaffold."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from urllib.parse import quote_plus


CANDIDATE_FIELDS = [
    "record_id",
    "title",
    "authors",
    "year",
    "journal",
    "doi",
    "pmid",
    "pmcid",
    "source_database",
    "abstract_if_available",
    "article_type_guess",
    "keyword_include_hits",
    "keyword_secondary_hits",
    "keyword_exclude_hits",
    "keyword_relevance_score",
    "priority",
    "open_access_status_if_detectable",
    "pdf_url_candidate",
    "landing_page_url",
    "article_url",
    "candidate_urls_json",
    "download_status",
    "exclusion_reason_if_any",
    "quality_notes",
    "impact_factor",
    "jcr_quartile",
    "metric_year",
    "metric_source",
    "indexing",
    "venue_note",
]


def split_groups(raw: str | None) -> list[list[str]]:
    if not raw:
        return []
    groups: list[list[str]] = []
    for group in raw.split(","):
        terms = [term.strip() for term in group.replace("/", "|").split("|") if term.strip()]
        if terms:
            groups.append(terms)
    return groups


def boolean_query(topic: str, keywords: str | None, years: str | None) -> str:
    groups = split_groups(keywords)
    if not groups:
        groups = [[term] for term in topic.split() if term]
    parts = []
    for terms in groups:
        formatted = [f'"{term}"' if " " in term and not term.startswith('"') else term for term in terms]
        parts.append("(" + " OR ".join(formatted) + ")")
    query = " AND ".join(parts)
    if years:
        query = f"{query} ({years})"
    return query


def terms(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.replace("|", ",").split(",") if item.strip()]


def write_csv_header(path: Path, fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()


def copy_alias(source: Path, alias: Path) -> None:
    if source.exists():
        shutil.copyfile(source, alias)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a local literature harvest run scaffold.")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--keywords", help="Concept groups separated by commas; synonyms separated by | or /.")
    parser.add_argument("--years", default="")
    parser.add_argument("--include-terms", default="")
    parser.add_argument("--secondary-terms", default="")
    parser.add_argument("--exclude-terms", default="editorial,commentary,news,conference abstract,patent")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--max-results", type=int, default=100)
    args = parser.parse_args()

    run_root = Path(args.output_root).expanduser().resolve() / args.run_name
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "downloaded_fulltexts").mkdir(exist_ok=True)
    (run_root / "已下载全文").mkdir(exist_ok=True)
    (run_root / "download_logs").mkdir(exist_ok=True)

    query = boolean_query(args.topic, args.keywords, args.years)
    include_terms = terms(args.include_terms) or [term for group in split_groups(args.keywords) for term in group]
    config = {
        "tool_name": "literature_downloader",
        "email": "",
        "topic": args.topic,
        "years": args.years,
        "sources": {
            "pubmed": True,
            "pmc": True,
            "europepmc": True,
            "crossref": True,
            "openalex": True,
            "semantic_scholar": True,
            "google_scholar_manual": True,
        },
        "max_results_per_query": {
            "pubmed": args.max_results,
            "pmc": args.max_results,
            "europepmc": args.max_results,
            "crossref": args.max_results,
            "openalex": args.max_results,
        },
        "delay_seconds": {"api": 0.5, "download": 0.5},
        "download": {"enabled": True, "timeout_seconds": 30, "max_attempts_per_record": 3},
        "prefer_research_articles": True,
        "exclude_reviews_by_default": False,
        "include_terms": include_terms,
        "secondary_terms": terms(args.secondary_terms),
        "exclude_terms": terms(args.exclude_terms),
        "queries": [{"name": "topic_query_1", "query": query}],
    }
    (run_root / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    copy_alias(run_root / "config.json", run_root / "配置文件.json")

    encoded = quote_plus(args.topic)
    plan = [
        "# Literature Harvest Search Plan",
        "",
        f"- Topic: {args.topic}",
        f"- Years: {args.years}",
        "",
        "## Boolean Query",
        "",
        f"```text\n{query}\n```",
        "",
        "## Manual Search Entrypoints",
        "",
        f"- Google Scholar: https://scholar.google.com/scholar?q={encoded}",
        f"- Semantic Scholar: https://www.semanticscholar.org/search?q={encoded}",
        f"- OpenAlex: https://openalex.org/works?page=1&filter=default.search:{encoded}",
        f"- Crossref: https://search.crossref.org/?q={encoded}",
        f"- PubMed: https://pubmed.ncbi.nlm.nih.gov/?term={encoded}",
        f"- Europe PMC: https://europepmc.org/search?query={encoded}",
        "",
        "## Next Steps",
        "",
        "1. Add verified records to `candidate_table.csv`.",
        "2. Run `rank_candidates.py`.",
        "3. Run `download_accessible_fulltexts.py` only for lawful direct URLs.",
    ]
    (run_root / "search_plan.md").write_text("\n".join(plan) + "\n", encoding="utf-8")
    copy_alias(run_root / "search_plan.md", run_root / "检索计划.md")

    write_csv_header(run_root / "candidate_table.csv", CANDIDATE_FIELDS)
    copy_alias(run_root / "candidate_table.csv", run_root / "候选文献总表.csv")
    for name, alias in [
        ("high_priority.csv", "高优先级文献.csv"),
        ("medium_priority.csv", "中优先级文献.csv"),
        ("low_priority.csv", "低优先级文献.csv"),
    ]:
        write_csv_header(run_root / name, CANDIDATE_FIELDS)
        copy_alias(run_root / name, run_root / alias)
    write_csv_header(
        run_root / "download_logs" / "download_log.csv",
        [
            "record_id",
            "doi",
            "title",
            "final_path",
            "final_url",
            "download_status",
            "failure_reason",
            "access_route_used",
            "content_format",
            "attempt_count",
        ],
    )
    copy_alias(run_root / "download_logs" / "download_log.csv", run_root / "download_logs" / "下载日志.csv")
    write_csv_header(run_root / "dedup_manifest.csv", ["keep", "record_id", "doi", "title", "path", "duplicate_reason"])
    copy_alias(run_root / "dedup_manifest.csv", run_root / "去重清单.csv")
    write_csv_header(
        run_root / "journal_metrics.csv",
        ["journal", "impact_factor", "jcr_quartile", "metric_year", "metric_source", "indexing", "venue_note"],
    )
    copy_alias(run_root / "journal_metrics.csv", run_root / "期刊指标.csv")
    (run_root / "harvest_summary.md").write_text(
        "# Literature Harvest Summary\n\n"
        "- Candidate rows: `0`\n"
        "- High-priority rows: `0`\n"
        "- Medium-priority rows: `0`\n"
        "- True PDFs: `0`\n"
        "- HTML/XML full texts: `0`\n"
        "- Metadata-only or unresolved: `0`\n",
        encoding="utf-8",
    )
    copy_alias(run_root / "harvest_summary.md", run_root / "下载汇总.md")
    print(run_root)


if __name__ == "__main__":
    main()
