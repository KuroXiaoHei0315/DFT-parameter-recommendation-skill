#!/usr/bin/env python3
"""Generate lawful literature search routes and a tracking template."""

from __future__ import annotations

import argparse
import json
from urllib.parse import quote_plus


def url(label: str, target: str) -> dict[str, str]:
    return {"label": label, "url": target}


def split_groups(raw: str | None) -> list[list[str]]:
    if not raw:
        return []
    groups: list[list[str]] = []
    for group in raw.split(","):
        terms = [term.strip() for term in group.replace("/", "|").split("|") if term.strip()]
        if terms:
            groups.append(terms)
    return groups


def boolean_query(topic: str | None, keywords: str | None, years: str | None) -> str:
    groups = split_groups(keywords)
    if not groups and topic:
        groups = [[term] for term in topic.split() if term]
    parts = []
    for terms in groups:
        formatted = []
        for term in terms:
            if " " in term and not (term.startswith('"') and term.endswith('"')):
                formatted.append(f'"{term}"')
            else:
                formatted.append(term)
        parts.append("(" + " OR ".join(formatted) + ")")
    query = " AND ".join(parts) if parts else (topic or "")
    if years:
        query = f"{query} ({years})".strip()
    return query


def build_routes(args: argparse.Namespace) -> list[dict[str, str]]:
    routes: list[dict[str, str]] = []
    query = args.title or args.topic or args.doi or ""
    encoded_query = quote_plus(query)

    if args.doi:
        doi = args.doi.strip()
        encoded_doi = quote_plus(doi)
        routes.extend(
            [
                url("DOI resolver", f"https://doi.org/{doi}"),
                url("Unpaywall DOI lookup", f"https://unpaywall.org/{encoded_doi}"),
                url("Crossref metadata", f"https://search.crossref.org/?q={encoded_doi}"),
                url("Google Scholar exact DOI", f"https://scholar.google.com/scholar?q={encoded_doi}"),
            ]
        )

    if args.pmid:
        pmid = quote_plus(args.pmid.strip())
        routes.extend(
            [
                url("PubMed record", f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"),
                url("Europe PMC", f"https://europepmc.org/search?query=EXT_ID:{pmid}%20AND%20SRC:MED"),
            ]
        )

    if query:
        routes.extend(
            [
                url("Google Scholar", f"https://scholar.google.com/scholar?q={encoded_query}"),
                url("Semantic Scholar", f"https://www.semanticscholar.org/search?q={encoded_query}"),
                url("OpenAlex", f"https://openalex.org/works?page=1&filter=default.search:{encoded_query}"),
                url("Crossref", f"https://search.crossref.org/?q={encoded_query}"),
                url("CORE open access", f"https://core.ac.uk/search?q={encoded_query}"),
                url("BASE open access", f"https://www.base-search.net/Search/Results?lookfor={encoded_query}"),
                url("PubMed", f"https://pubmed.ncbi.nlm.nih.gov/?term={encoded_query}"),
                url("Europe PMC", f"https://europepmc.org/search?query={encoded_query}"),
                url("arXiv", f"https://arxiv.org/search/?query={encoded_query}&searchtype=all"),
            ]
        )

    return routes


def markdown(args: argparse.Namespace) -> str:
    query = boolean_query(args.topic, args.keywords, args.years)
    routes = build_routes(args)
    lines = [
        "# Literature Search Plan",
        "",
        f"- Topic: {args.topic or ''}",
        f"- Title: {args.title or ''}",
        f"- DOI: {args.doi or ''}",
        f"- PMID: {args.pmid or ''}",
        f"- Years: {args.years or ''}",
        "",
        "## Boolean Query Draft",
        "",
        f"```text\n{query}\n```",
        "",
        "## Lawful Lookup Routes",
        "",
    ]
    for route in routes:
        lines.append(f"- [{route['label']}]({route['url']})")
    lines.extend(
        [
            "",
            "## Tracking Table",
            "",
            "| Title | DOI/PMID | Source | Access status | Access route | Quality notes |",
            "|---|---|---|---|---|---|",
            "|  |  |  | metadata-only |  |  |",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate literature search links and tracking template.")
    parser.add_argument("--topic", help="Research topic or natural-language query.")
    parser.add_argument("--keywords", help="Comma-separated concept groups; use | or / for synonyms.")
    parser.add_argument("--title", help="Known paper title.")
    parser.add_argument("--doi", help="Known DOI.")
    parser.add_argument("--pmid", help="Known PubMed ID.")
    parser.add_argument("--years", help="Year range, e.g. 2021-2026.")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of Markdown.")
    args = parser.parse_args()

    if args.json:
        print(
            json.dumps(
                {
                    "boolean_query": boolean_query(args.topic, args.keywords, args.years),
                    "routes": build_routes(args),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(markdown(args))


if __name__ == "__main__":
    main()
