#!/usr/bin/env python3
"""Create student-friendly Chinese literature tables.

This script merges download status and verified journal metrics into every
paper-listing output. `期刊指标.csv`/`journal_metrics.csv` may exist as a
background source, but students should read the merged tables instead.
"""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path


METRIC_COLUMNS = ["影响因子", "JCR分区", "指标年份", "指标来源", "索引情况"]
OUTPUT_COLUMNS = [
    "序号",
    "题名",
    "年份",
    "期刊或来源",
    *METRIC_COLUMNS,
    "DOI",
    "文章地址",
    "全文状态",
    "文件或原因",
    "下一步建议",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def norm(value: object) -> str:
    return " ".join(str(value or "").casefold().strip().split())


def choose_candidate_rows(run_root: Path) -> list[dict[str, str]]:
    for name in ["candidate_table.csv", "候选文献总表.csv"]:
        rows = read_csv(run_root / name)
        if rows:
            return rows
    return []


def choose_log_rows(run_root: Path) -> list[dict[str, str]]:
    paths = [
        run_root / "总下载日志.csv",
        run_root / "combined_download_log.csv",
        run_root / "下载日志.csv",
        run_root / "download_log.csv",
        run_root / "download_logs" / "下载日志.csv",
        run_root / "download_logs" / "download_log.csv",
    ]
    for path in paths:
        rows = read_csv(path)
        if rows:
            return rows
    return []


def read_metrics(run_root: Path) -> dict[str, dict[str, str]]:
    metrics: dict[str, dict[str, str]] = {}
    for path in [run_root / "期刊指标.csv", run_root / "journal_metrics.csv"]:
        for row in read_csv(path):
            journal = row.get("期刊或来源") or row.get("journal") or row.get("source") or row.get("venue")
            if journal:
                metrics[norm(journal)] = row
    return metrics


def get_metric(row: dict[str, str], metric_row: dict[str, str], zh_key: str, en_key: str) -> str:
    return row.get(zh_key) or row.get(en_key) or metric_row.get(zh_key) or metric_row.get(en_key) or "待核验"


def status_text(status: str) -> str:
    return {
        "success_pdf": "已下载 PDF",
        "success_html": "已保存网页全文",
        "success_xml": "已保存 XML 全文",
        "inaccessible": "平台限制直连下载",
        "metadata_only": "只找到题录",
        "broken_link": "链接失效",
        "failed": "尝试失败",
        "excluded": "已排除",
    }.get(status, status or "待处理")


def next_step(status: str, reason: str) -> str:
    if status == "success_pdf":
        return "已拿到 PDF，优先阅读"
    if status in {"success_html", "success_xml"}:
        return "已保存全文页面，可人工继续追 PDF"
    if reason in {"http_403", "paywall_or_login_detected"} or status == "inaccessible":
        return "用学校图书馆/VPN；不行就馆际互借或联系作者"
    if reason == "html_stub_not_fulltext":
        return "只拿到跳转页/占位页；用 DOI 走学校库或人工打开出版社页"
    if status == "broken_link":
        return "用 DOI 重新打开出版社页面"
    return "人工复查 DOI、作者主页、机构仓储、Unpaywall"


def merge_candidate_and_log(candidate_rows: list[dict[str, str]], log_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    logs_by_id: dict[str, dict[str, str]] = {}
    logs_by_doi: dict[str, dict[str, str]] = {}
    for row in log_rows:
        row_id = row.get("id") or row.get("record_id") or ""
        doi = norm(row.get("doi") or row.get("DOI"))
        if row_id:
            logs_by_id[row_id] = row
        if doi:
            logs_by_doi[doi] = row
    if not candidate_rows:
        candidate_rows = log_rows
    merged = []
    for index, row in enumerate(candidate_rows, start=1):
        row_id = row.get("record_id") or row.get("id") or row.get("序号") or str(index)
        doi = norm(row.get("doi") or row.get("DOI"))
        log = logs_by_id.get(row_id) or logs_by_doi.get(doi) or {}
        item = dict(row)
        for key in ["status", "download_status", "file", "final_path", "reason", "failure_reason"]:
            if log.get(key):
                item[key] = log[key]
        if log.get("final_url") and not item.get("landing_page_url"):
            item["landing_page_url"] = log["final_url"]
        item["id"] = row_id
        merged.append(item)
    return merged


def convert_rows(rows: list[dict[str, str]], metrics: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    converted = []
    for index, row in enumerate(rows, start=1):
        journal = row.get("期刊或来源") or row.get("journal") or row.get("source") or ""
        metric_row = metrics.get(norm(journal), {})
        status = row.get("下载状态") or row.get("status") or row.get("download_status") or ""
        reason = row.get("reason") or row.get("failure_reason") or row.get("文件或原因") or ""
        file_value = row.get("文件或原因") or row.get("file") or row.get("final_path") or reason
        file_or_reason = Path(file_value).name if file_value and ("/" in file_value or "\\" in file_value) else file_value
        converted.append(
            {
                "序号": row.get("序号") or row.get("id") or row.get("record_id") or str(index),
                "题名": row.get("题名") or row.get("title") or row.get("paper") or "",
                "年份": row.get("年份") or row.get("year") or "",
                "期刊或来源": journal,
                "影响因子": get_metric(row, metric_row, "影响因子", "impact_factor"),
                "JCR分区": get_metric(row, metric_row, "JCR分区", "jcr_quartile"),
                "指标年份": get_metric(row, metric_row, "指标年份", "metric_year"),
                "指标来源": get_metric(row, metric_row, "指标来源", "metric_source"),
                "索引情况": get_metric(row, metric_row, "索引情况", "indexing"),
                "DOI": row.get("DOI") or row.get("doi") or "",
                "文章地址": row.get("文章地址") or row.get("article_url") or row.get("landing_page_url") or row.get("url") or "",
                "全文状态": status_text(status),
                "文件或原因": file_or_reason,
                "下一步建议": row.get("下一步建议") or next_step(status, reason),
            }
        )
    return converted


def ensure_fulltext_alias(run_root: Path) -> None:
    fulltext_dir = run_root / "已下载全文"
    fulltext_dir.mkdir(exist_ok=True)
    for suffix in ["*.pdf", "*.html", "*.xml"]:
        for path in run_root.glob(suffix):
            if path.name in {"下载报告.html", "下载报告.pdf"}:
                continue
            target = fulltext_dir / path.name
            if not target.exists():
                shutil.copyfile(path, target)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成学生可读的中文文献清单，并把期刊指标合并到每一行。")
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()

    run_root = Path(args.run_root).expanduser().resolve()
    rows = convert_rows(merge_candidate_and_log(choose_candidate_rows(run_root), choose_log_rows(run_root)), read_metrics(run_root))
    if not rows:
        raise SystemExit(f"没有找到可转换的文献表或下载日志：{run_root}")

    write_csv(run_root / "候选文献总表.csv", rows)
    write_csv(run_root / "高优先级文献.csv", rows)
    write_csv(run_root / "中优先级文献.csv", [])
    write_csv(run_root / "低优先级文献.csv", [row for row in rows if not row["全文状态"].startswith("已")])
    write_csv(run_root / "已下载文献清单.csv", [row for row in rows if row["全文状态"].startswith("已")])
    write_csv(run_root / "待处理文献清单.csv", [row for row in rows if not row["全文状态"].startswith("已")])
    ensure_fulltext_alias(run_root)
    print(f"已生成学生可读文献清单：{run_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
