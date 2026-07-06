#!/usr/bin/env python3
"""Generate a Chinese, human-readable literature download report.

The script reads common CSV logs produced by this skill and writes:
- 涓嬭浇鎶ュ憡.html
- README_鍏堢湅鎴?md
- 涓嬭浇鎶ュ憡.pdf when Edge/Chrome/Chromium is available

If `journal_metrics.csv` exists in the run folder, the report will show
impact factor/quartile/source fields. Metrics must be verified by the agent
or user before use; the script does not invent impact factors.
"""

from __future__ import annotations

import argparse
import csv
import html
import shutil
import subprocess
import sys
from pathlib import Path


STATUS_ZH = {
    "success_pdf": "宸蹭笅杞?PDF",
    "success_html": "宸蹭繚瀛樼綉椤靛叏鏂?,
    "success_xml": "宸蹭繚瀛?XML 鍏ㄦ枃",
    "metadata_only": "鍙壘鍒伴褰?,
    "inaccessible": "骞冲彴闄愬埗",
    "broken_link": "閾炬帴澶辨晥",
    "rate_limited": "琚檺娴?,
    "excluded": "宸叉帓闄?,
    "failed": "灏濊瘯澶辫触",
}


REASON_ZH = {
    "http_401": "闇€瑕佺櫥褰曟垨鏈烘瀯鏉冮檺",
    "http_402": "闇€瑕佷粯璐规垨璁㈤槄",
    "http_403": "骞冲彴鎷掔粷鐩磋繛涓嬭浇锛屽缓璁鏍″簱/VPN/棣嗛檯浜掑€?,
    "http_404": "閾炬帴涓嶅瓨鍦ㄦ垨宸插彉鏇?,
    "http_410": "閾炬帴宸插け鏁?,
    "paywall_or_login_detected": "妫€娴嬪埌鐧诲綍椤垫垨浠樿垂澧?,
    "no_candidate_url": "娌℃湁鎵惧埌鍙皾璇曠殑鍏ㄦ枃閾炬帴",
    "HTTPError": "缃戦〉璇锋眰澶辫触锛岄渶瑕佷汉宸ュ鏌ュ叆鍙?,
    "html_stub_not_fulltext": "鍙嬁鍒拌烦杞〉/鍗犱綅椤碉紝涓嶆槸鐪熸鍏ㄦ枃",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def choose_log(run_root: Path) -> tuple[Path | None, list[dict[str, str]]]:
    candidates = [
        run_root / "鎬讳笅杞芥棩蹇?csv",
        run_root / "combined_download_log.csv",
        run_root / "涓嬭浇鏃ュ織.csv",
        run_root / "download_log.csv",
        run_root / "download_logs" / "涓嬭浇鏃ュ織.csv",
        run_root / "download_logs" / "download_log.csv",
    ]
    for path in candidates:
        rows = read_csv(path)
        if rows:
            return path, rows
    return None, []


def choose_candidate_rows(run_root: Path) -> list[dict[str, str]]:
    for path in [run_root / "candidate_table.csv", run_root / "鍊欓€夋枃鐚€昏〃.csv"]:
        rows = read_csv(path)
        if rows:
            return rows
    return []


def normalize_key(value: object) -> str:
    return " ".join(str(value or "").casefold().strip().split())


def normalize_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    best: dict[str, dict[str, str]] = {}
    for index, row in enumerate(rows, start=1):
        row_id = row.get("id") or row.get("record_id") or str(index)
        row["id"] = row_id
        old = best.get(row_id)
        row_status = status(row)
        old_status = status(old) if old else ""
        if old is None or (not old_status.startswith("success") and row_status.startswith("success")):
            best[row_id] = row
    return [best[key] for key in sorted(best, key=lambda value: int(value) if value.isdigit() else 999999)]


def merge_candidate_and_log(candidate_rows: list[dict[str, str]], log_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    logs_by_id: dict[str, dict[str, str]] = {}
    logs_by_doi: dict[str, dict[str, str]] = {}
    for row in log_rows:
        row_id = row.get("id") or row.get("record_id") or ""
        doi = normalize_key(row.get("doi") or row.get("DOI"))
        if row_id:
            logs_by_id[row_id] = row
        if doi:
            logs_by_doi[doi] = row
    if not candidate_rows:
        return log_rows
    merged = []
    for index, row in enumerate(candidate_rows, start=1):
        row_id = row.get("record_id") or row.get("id") or row.get("搴忓彿") or str(index)
        doi = normalize_key(row.get("doi") or row.get("DOI"))
        log = logs_by_id.get(row_id) or logs_by_doi.get(doi) or {}
        item = dict(row)
        item["id"] = row_id
        for key in ["status", "download_status", "file", "final_path", "reason", "failure_reason"]:
            if log.get(key):
                item[key] = log[key]
        return_status = log.get("download_status") or log.get("status")
        if return_status:
            item["status"] = return_status
        if log.get("final_url") and not item.get("landing_page_url"):
            item["landing_page_url"] = log["final_url"]
        merged.append(item)
    return merged


def read_metrics(run_root: Path, explicit_path: str | None) -> dict[str, dict[str, str]]:
    paths = []
    if explicit_path:
        paths.append(Path(explicit_path))
    paths.append(run_root / "鏈熷垔鎸囨爣.csv")
    paths.append(run_root / "journal_metrics.csv")
    metrics: dict[str, dict[str, str]] = {}
    for path in paths:
        for row in read_csv(path.expanduser()):
            for key_name in ["journal", "source", "venue"]:
                key = normalize_key(row.get(key_name))
                if key:
                    metrics[key] = row
    return metrics


def apply_metrics(rows: list[dict[str, str]], metrics: dict[str, dict[str, str]]) -> None:
    for row in rows:
        metric_row = metrics.get(normalize_key(row.get("journal"))) or {}
        for field in ["impact_factor", "jcr_quartile", "metric_year", "metric_source", "indexing", "venue_note"]:
            if not row.get(field) and metric_row.get(field):
                row[field] = metric_row[field]


def status(row: dict[str, str] | None) -> str:
    if not row:
        return ""
    return row.get("status") or row.get("download_status") or "metadata_only"


def file_name(row: dict[str, str]) -> str:
    value = row.get("file") or row.get("final_path") or ""
    return Path(value).name if value else ""


def reason(row: dict[str, str]) -> str:
    raw = row.get("reason") or row.get("failure_reason") or ""
    return REASON_ZH.get(raw, raw)


def title(row: dict[str, str]) -> str:
    return row.get("title") or row.get("paper") or "鏈懡鍚嶆枃鐚?


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def metric_text(row: dict[str, str]) -> str:
    parts = []
    impact_factor = row.get("impact_factor") or row.get("if")
    if impact_factor:
        parts.append(f"IF {impact_factor}")
    if row.get("jcr_quartile"):
        parts.append(row["jcr_quartile"])
    if row.get("indexing"):
        parts.append(row["indexing"])
    if row.get("metric_year") or row.get("metric_source"):
        source = " / ".join(value for value in [row.get("metric_year"), row.get("metric_source")] if value)
        if source:
            parts.append(source)
    return "锛?.join(parts) if parts else "寰呮牳楠?


def action_text(row: dict[str, str]) -> str:
    row_status = status(row)
    if row_status == "success_pdf":
        return "鍙洿鎺ラ槄璇?PDF"
    if row_status in {"success_html", "success_xml"}:
        return "鍙厛闃呰鍏ㄦ枃椤甸潰锛屽啀浜哄伐杩?PDF"
    if row_status == "inaccessible":
        return "鐢ㄥ鏍″簱/VPN锛涗笉琛屽氨棣嗛檯浜掑€熸垨鑱旂郴浣滆€?
    if row_status == "metadata_only":
        return "缁х画鏌ヤ綔鑰呬富椤点€佹満鏋勪粨鍌ㄣ€乁npaywall"
    if row_status == "broken_link":
        return "鐢?DOI 閲嶆柊鎵撳紑鍑虹増绀鹃〉闈?
    return reason(row) or "浜哄伐澶嶆煡"


def status_class(row_status: str) -> str:
    if row_status == "success_pdf":
        return "ok"
    if row_status in {"success_html", "success_xml"}:
        return "warn"
    return "bad"


def browser_candidates() -> list[str]:
    names = ["msedge", "chrome", "chromium", "chromium-browser", "google-chrome"]
    found = [path for name in names if (path := shutil.which(name))]
    windows_paths = [
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    found.extend(path for path in windows_paths if Path(path).exists())
    return found


def print_pdf(html_path: Path, pdf_path: Path) -> str | None:
    for browser in browser_candidates():
        cmd = [
            browser,
            "--headless",
            "--disable-gpu",
            f"--print-to-pdf={pdf_path}",
            html_path.resolve().as_uri(),
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
            if pdf_path.exists() and pdf_path.stat().st_size > 1000:
                return browser
        except Exception:
            continue
    return None


def make_html(rows: list[dict[str, str]], title_text: str, source_log: Path | None) -> str:
    total = len(rows)
    pdf_count = sum(1 for row in rows if status(row) == "success_pdf")
    html_count = sum(1 for row in rows if status(row) in {"success_html", "success_xml"})
    failed_count = sum(1 for row in rows if not status(row).startswith("success"))
    metric_count = sum(1 for row in rows if metric_text(row) != "寰呮牳楠?)
    cards = [
        ("灏濊瘯鏂囩尞", total),
        ("宸蹭笅杞?PDF", pdf_count),
        ("缃戦〉/XML 鍏ㄦ枃", html_count),
        ("闇€鍚庣画澶勭悊", failed_count),
        ("宸叉爣娉ㄦ寚鏍?, metric_count),
    ]
    card_html = "\n".join(
        f"<div class='card'><div class='num'>{number}</div><div class='label'>{label}</div></div>"
        for label, number in cards
    )
    success_rows = [row for row in rows if status(row).startswith("success")]
    failed_rows = [row for row in rows if not status(row).startswith("success")]

    def table(section_rows: list[dict[str, str]], unresolved: bool) -> str:
        body = []
        for row in section_rows:
            row_status = status(row)
            status_text = STATUS_ZH.get(row_status, row_status)
            note = action_text(row) if unresolved else file_name(row)
            body.append(
                "<tr>"
                f"<td class='idx'>{esc(row.get('id'))}</td>"
                f"<td>{esc(row.get('year'))}</td>"
                f"<td><div class='paper-title'>{esc(title(row))}</div><div class='doi'>{esc(row.get('doi'))}</div></td>"
f"<td>{esc(row.get('journal'))}</td>"
f"<td>{esc(metric_text(row))}</td>"
                f"<td><span class='badge {status_class(row_status)}'>{esc(status_text)}</span></td>"
                f"<td>{esc(note)}</td>"
                "</tr>"
            )
        return "\n".join(body) or "<tr><td colspan='7'>鏃?/td></tr>"

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{esc(title_text)}</title>
<style>
body {{ font-family: "Microsoft YaHei", "Noto Sans CJK SC", Arial, sans-serif; margin: 34px; color: #172033; line-height: 1.55; background: #ffffff; }}
h1 {{ font-size: 30px; margin: 0 0 6px; letter-spacing: 0; }}
h2 {{ margin-top: 30px; border-bottom: 2px solid #e5e7eb; padding-bottom: 7px; font-size: 20px; }}
.sub {{ color: #667085; margin-bottom: 20px; }}
.cards {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin: 18px 0 22px; }}
.card {{ border: 1px solid #d7dee8; border-radius: 8px; padding: 13px; background: #f8fafc; }}
.num {{ font-size: 26px; font-weight: 800; color: #0f766e; }}
.label {{ color: #475467; font-size: 13px; }}
.note {{ background: #fff7ed; border: 1px solid #fdba74; padding: 12px 14px; border-radius: 8px; margin: 14px 0; }}
.tip {{ background: #ecfdf5; border: 1px solid #86efac; padding: 12px 14px; border-radius: 8px; margin: 14px 0; }}
table {{ width: 100%; border-collapse: collapse; font-size: 11.5px; table-layout: fixed; }}
th, td {{ border: 1px solid #d7dee8; padding: 7px; vertical-align: top; overflow-wrap: anywhere; }}
th {{ background: #eef2f7; text-align: left; color: #344054; }}
.idx {{ width: 32px; text-align: center; font-weight: 700; }}
.paper-title {{ font-weight: 700; color: #111827; }}
.doi {{ color: #667085; margin-top: 4px; font-size: 10.5px; }}
.badge {{ display: inline-block; border-radius: 999px; padding: 2px 7px; font-size: 11px; font-weight: 700; white-space: nowrap; }}
.ok {{ background: #dcfce7; color: #166534; }}
.warn {{ background: #fef3c7; color: #92400e; }}
.bad {{ background: #fee2e2; color: #991b1b; }}
code {{ background: #f3f4f6; padding: 2px 5px; border-radius: 4px; }}
@media print {{
  body {{ margin: 14mm; }}
  .cards {{ grid-template-columns: repeat(5, 1fr); }}
  table {{ font-size: 9.5px; }}
  h2 {{ break-after: avoid; }}
  tr {{ break-inside: avoid; }}
}}
</style>
</head>
<body>
<h1>{esc(title_text)}</h1>
<div class="sub">鏉ユ簮鏃ュ織锛歿esc(source_log) if source_log else "鏈壘鍒版棩蹇?}銆傛湰鎶ュ憡鍙粺璁″悎娉曠洿杩炰笅杞界粨鏋溿€?/div>
<div class="cards">{card_html}</div>
<div class="tip">闃呰椤哄簭锛氬厛鐪嬧€滃凡缁忔嬁鍒扮殑鍏ㄦ枃鈥濓紝鍐嶅鐞嗏€滈渶瑕佸悗缁鐞嗏€濄€傚奖鍝嶅洜瀛?鍒嗗尯浠呭湪宸叉牳楠屾潵婧愭椂鏄剧ず锛涙病鏈夋牳楠屾椂鏄剧ず鈥滃緟鏍搁獙鈥濄€?/div>
<div class="note">娌′笅鎴愰€氬父涓嶆槸绋嬪簭鍧忎簡锛岃€屾槸鍑虹増绀炬垨鏁版嵁搴撻檺鍒惰嚜鍔ㄧ洿杩炰笅杞姐€傞亣鍒?403銆佺櫥褰曢〉銆佽闃呴〉鏃讹紝搴斾娇鐢ㄥ鏍″浘涔﹂/VPN銆侀闄呬簰鍊熴€佹満鏋勪粨鍌ㄦ垨鑱旂郴浣滆€呫€?/div>

<h2>宸茬粡鎷垮埌鐨勫叏鏂?/h2>
<table>
<thead><tr><th style="width:32px">#</th><th style="width:42px">骞翠唤</th><th>棰樺悕 / DOI</th><th style="width:115px">鏈熷垔/鏉ユ簮</th><th style="width:105px">褰卞搷鍥犲瓙/鍒嗗尯</th><th style="width:70px">鐘舵€?/th><th>鏂囦欢/鍔ㄤ綔</th></tr></thead>
<tbody>{table(success_rows, False)}</tbody>
</table>

<h2>闇€瑕佸悗缁鐞嗙殑鏂囩尞</h2>
<table>
<thead><tr><th style="width:32px">#</th><th style="width:42px">骞翠唤</th><th>棰樺悕 / DOI</th><th style="width:115px">鏈熷垔/鏉ユ簮</th><th style="width:105px">褰卞搷鍥犲瓙/鍒嗗尯</th><th style="width:70px">鐘舵€?/th><th>寤鸿</th></tr></thead>
<tbody>{table(failed_rows, True)}</tbody>
</table>

<h2>缁欏鐢熺殑涓嬩竴姝?/h2>
<ol>
<li>鍏堣宸蹭笅杞?PDF 涓拰璇鹃鏈€璐磋繎鐨?5-8 绡囷紝杈硅杈瑰仛绗旇銆?/li>
<li>褰卞搷鍥犲瓙/鍒嗗尯鍙敤浜庡垵绛涳紝涓嶈浠ｆ浛璁烘枃璐ㄩ噺鍒ゆ柇锛涢噸鐐圭湅鏂规硶銆佹暟鎹€佺粨璁哄拰鍙鐜版€с€?/li>
<li>瀵规湭涓嬭浇鎴愬姛浣嗗緢閲嶈鐨勬枃鐚紝鐢?DOI 璧板鏍″浘涔﹂銆佹満鏋?VPN 鎴栭闄呬簰鍊熴€?/li>
<li>CSV 鏃ュ織鍙敤浜庤拷婧紝涓嶉渶瑕佹櫘閫氶槄璇绘椂鎵撳紑銆?/li>
<li>闇€瑕佹墦寮€鍘熸枃缃戦〉鏃讹紝鐪?<code>鏂囩珷鍦板潃鎬昏〃.csv</code>銆?/li>
</ol>
</body>
</html>
"""


def make_readme(run_root: Path, title_text: str, pdf_path: Path, html_path: Path, rows: list[dict[str, str]]) -> str:
    pdf_count = sum(1 for row in rows if status(row) == "success_pdf")
    html_count = sum(1 for row in rows if status(row) in {"success_html", "success_xml"})
    failed_count = sum(1 for row in rows if not status(row).startswith("success"))
    metric_count = sum(1 for row in rows if metric_text(row) != "寰呮牳楠?)
    return "\n".join(
        [
            f"# {title_text}",
            "",
            "鍏堢湅杩欎釜锛?,
            "",
            f"- PDF 鎶ュ憡锛歚{pdf_path}`" if pdf_path.exists() else f"- HTML 鎶ュ憡锛歚{html_path}`",
            f"- 鏂囩尞鐩綍锛歚{run_root}`",
            f"- 鎬讳笅杞芥棩蹇楋細`{run_root / '鎬讳笅杞芥棩蹇?csv'}`",
            f"- 宸蹭笅杞?PDF锛歚{pdf_count}`",
            f"- 宸蹭繚瀛樼綉椤?XML 鍏ㄦ枃锛歚{html_count}`",
            f"- 闇€瑕佸悗缁鐞嗭細`{failed_count}`",
            f"- 宸叉爣娉ㄥ奖鍝嶅洜瀛?鍒嗗尯锛歚{metric_count}`",
            "",
            "璇存槑锛氭病鏈夌洿鎺ヤ笅杞芥垚鍔熺殑鏂囩尞锛屽鏁版槸鍑虹増绀炬垨鏁版嵁搴撻檺鍒惰嚜鍔ㄧ洿杩炰笅杞姐€傚缓璁敤瀛︽牎鍥句功棣嗐€佹満鏋?VPN銆侀闄呬簰鍊熸垨鑱旂郴浣滆€呯户缁幏鍙栥€?,
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="鐢熸垚鏅€氫汉鑳界湅鎳傜殑涓枃鏂囩尞涓嬭浇鎶ュ憡銆?)
    parser.add_argument("--run-root", required=True, help="鏂囩尞涓嬭浇浠诲姟鐩綍銆?)
    parser.add_argument("--title", default="鏂囩尞涓嬭浇鎶ュ憡")
    parser.add_argument("--metrics-csv", help="鍙€夛細鍖呭惈 journal,impact_factor,jcr_quartile,metric_year,metric_source,indexing 鐨?CSV銆?)
    parser.add_argument("--pdf", action="store_true", help="灏濊瘯鐢?Edge/Chrome/Chromium 瀵煎嚭 PDF銆?)
    args = parser.parse_args()

    run_root = Path(args.run_root).expanduser().resolve()
    source_log, rows = choose_log(run_root)
    if not rows:
        print(f"娌℃湁鎵惧埌鍙敤涓嬭浇鏃ュ織锛歿run_root}", file=sys.stderr)
        return 2
    rows = normalize_rows(merge_candidate_and_log(choose_candidate_rows(run_root), rows))
    apply_metrics(rows, read_metrics(run_root, args.metrics_csv))

    html_path = run_root / "涓嬭浇鎶ュ憡.html"
    pdf_path = run_root / "涓嬭浇鎶ュ憡.pdf"
    readme_path = run_root / "README_鍏堢湅鎴?md"

    html_path.write_text(make_html(rows, args.title, source_log), encoding="utf-8")
    browser = print_pdf(html_path, pdf_path) if args.pdf else None
    readme_path.write_text(make_readme(run_root, args.title, pdf_path, html_path, rows), encoding="utf-8")

    if source_log and source_log.resolve() != (run_root / "鎬讳笅杞芥棩蹇?csv").resolve():
        shutil.copyfile(source_log, run_root / "鎬讳笅杞芥棩蹇?csv")

    print(f"HTML: {html_path}")
    if browser:
        print(f"PDF: {pdf_path}")
        print(f"PDF browser: {browser}")
    elif args.pdf:
        print("PDF: 鏈敓鎴愶紝鏈満娌℃湁鍙敤鐨?Edge/Chrome/Chromium 鏃犲ご鎵撳嵃鍛戒护")
    print(f"README: {readme_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

