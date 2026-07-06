#!/usr/bin/env python3
"""Download directly accessible scholarly PDFs/HTML/XML from a candidate table."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path


PAYWALL_MARKERS = [
    "institutional login",
    "subscribe to access",
    "purchase access",
    "access through your institution",
    "sign in to access",
    "login required",
    "shibboleth",
    "ezproxy",
    "redirecting",
    "temporarily unavailable",
]


def clean(value: object) -> str:
    return str(value or "").strip()


def normalize_doi(value: str) -> str:
    value = clean(value)
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value, flags=re.I)
    value = re.sub(r"^doi:\s*", "", value, flags=re.I)
    return value.strip()


def stable_stem(row: dict[str, str]) -> str:
    title = clean(row.get("title")) or "untitled"
    year = clean(row.get("year")) or "unknown"
    first = clean(row.get("authors")).split(";")[0].split(",")[0].strip()
    raw = f"{first}_{year}_{title[:80]}" if first else f"{year}_{title[:80]}"
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("_")
    return stem[:120] or hashlib.sha1(title.encode("utf-8")).hexdigest()[:12]


def classify_payload(payload: bytes, content_type: str, final_url: str) -> str:
    head = payload[:200].lstrip()
    lowered = f"{content_type} {final_url}".lower()
    if head.startswith(b"%PDF") or "application/pdf" in lowered or final_url.lower().endswith(".pdf"):
        return "pdf"
    if "xml" in lowered or head.startswith(b"<?xml"):
        return "xml"
    if "html" in lowered or b"<html" in payload[:2000].lower() or b"<!doctype html" in payload[:2000].lower():
        return "html"
    return "binary"


def looks_paywalled(payload: bytes) -> bool:
    text = payload[:50000].decode("utf-8", errors="ignore").lower()
    return any(marker in text for marker in PAYWALL_MARKERS)


def candidate_urls(row: dict[str, str]) -> list[str]:
    urls: list[str] = []
    for key in ["pdf_url_candidate", "landing_page_url"]:
        value = clean(row.get(key))
        if value.startswith(("http://", "https://")):
            urls.append(value)
    raw_json = clean(row.get("candidate_urls_json"))
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, list):
                for item in parsed:
                    value = clean(item.get("url") if isinstance(item, dict) else item)
                    if value.startswith(("http://", "https://")):
                        urls.append(value)
        except json.JSONDecodeError:
            pass
    doi = normalize_doi(clean(row.get("doi")))
    if doi:
        urls.append(f"https://doi.org/{doi}")
    unique: list[str] = []
    seen: set[str] = set()
    for item in urls:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def fetch(url: str, timeout: int) -> tuple[bytes, str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "literature-downloader/1.0 (+lawful-access-check)",
            "Accept": "application/pdf,text/html,application/xml,text/xml,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read(), response.headers.get("Content-Type", ""), response.geturl()


def write_log(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
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
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def copy_alias(source: Path, alias: Path) -> None:
    if source.exists():
        shutil.copyfile(source, alias)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download lawful direct full-text files from candidate_table.csv.")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--max-attempts", type=int, default=3)
    args = parser.parse_args()

    run_root = Path(args.run_root).expanduser().resolve()
    candidate_path = run_root / "candidate_table.csv"
    output_dir = run_root / "downloaded_fulltexts"
    zh_output_dir = run_root / "已下载全文"
    log_path = run_root / "download_logs" / "download_log.csv"
    output_dir.mkdir(exist_ok=True)
    zh_output_dir.mkdir(exist_ok=True)
    log_path.parent.mkdir(exist_ok=True)

    existing: dict[str, dict[str, str]] = {}
    if log_path.exists() and not args.retry_failed:
        with log_path.open("r", newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                existing[clean(row.get("record_id"))] = dict(row)

    with candidate_path.open("r", newline="", encoding="utf-8-sig") as handle:
        candidates = list(csv.DictReader(handle))

    log_rows: list[dict[str, str]] = list(existing.values())
    processed = set(existing)
    for row in candidates:
        record_id = clean(row.get("record_id"))
        if not record_id or record_id in processed:
            continue
        if clean(row.get("exclusion_reason_if_any")):
            log_rows.append(
                {
                    "record_id": record_id,
                    "doi": clean(row.get("doi")),
                    "title": clean(row.get("title")),
                    "final_path": "",
                    "final_url": "",
                    "download_status": "excluded",
                    "failure_reason": clean(row.get("exclusion_reason_if_any")),
                    "access_route_used": "",
                    "content_format": "",
                    "attempt_count": "0",
                }
            )
            continue
        status = "metadata_only"
        reason = "no_candidate_url"
        final_path = ""
        final_url = ""
        content_format = ""
        attempts = 0
        for url in candidate_urls(row)[: args.max_attempts]:
            attempts += 1
            try:
                payload, content_type, resolved_url = fetch(url, args.timeout)
                kind = classify_payload(payload, content_type, resolved_url)
                if kind == "html" and looks_paywalled(payload):
                    status = "inaccessible"
                    reason = "paywall_or_login_detected"
                    final_url = resolved_url
                    content_format = "html"
                    continue
                if kind == "html" and len(payload) < 12000:
                    status = "inaccessible"
                    reason = "html_stub_not_fulltext"
                    final_url = resolved_url
                    content_format = "html"
                    continue
                extension = {"pdf": ".pdf", "html": ".html", "xml": ".xml"}.get(kind, ".bin")
                final = output_dir / f"{record_id}_{stable_stem(row)}{extension}"
                final.write_bytes(payload)
                zh_final = zh_output_dir / final.name
                shutil.copyfile(final, zh_final)
                status = f"success_{kind}"
                reason = ""
                final_path = str(zh_final)
                final_url = resolved_url
                content_format = kind
                break
            except urllib.error.HTTPError as exc:
                code = int(getattr(exc, "code", 0))
                status = "inaccessible" if code in {401, 402, 403} else ("broken_link" if code in {404, 410} else "metadata_only")
                if code == 429:
                    status = "rate_limited"
                reason = f"http_{code}"
                final_url = url
            except Exception as exc:  # noqa: BLE001
                status = "metadata_only"
                reason = type(exc).__name__
                final_url = url
            finally:
                time.sleep(args.delay)
        log_rows.append(
            {
                "record_id": record_id,
                "doi": clean(row.get("doi")),
                "title": clean(row.get("title")),
                "final_path": final_path,
                "final_url": final_url,
                "download_status": status,
                "failure_reason": reason,
                "access_route_used": "direct_url_or_doi",
                "content_format": content_format,
                "attempt_count": str(attempts),
            }
        )
        write_log(log_path, log_rows)
        copy_alias(log_path, run_root / "download_logs" / "下载日志.csv")

    write_log(log_path, log_rows)
    copy_alias(log_path, run_root / "download_logs" / "下载日志.csv")
    copy_alias(log_path, run_root / "下载日志.csv")
    print(f"Wrote {len(log_rows)} log rows to {log_path}")


if __name__ == "__main__":
    main()
