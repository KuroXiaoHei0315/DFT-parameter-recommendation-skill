#!/usr/bin/env python3
"""从 DFT 文献文本/PDF 中抽取计算参数。

用法:
    cat paper.txt | python scripts/parameter_extractor.py --doi 10.1103/...
    python scripts/parameter_extractor.py --file paper.pdf --doi 10.1103/...
    python scripts/parameter_extractor.py --dir ./papers/ --json
"""

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Optional

# 尝试加载 PDF 解析库
PDF_SUPPORT = False
try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    try:
        import fitz  # PyMuPDF
        PDF_SUPPORT = True
    except ImportError:
        pass


# --- 正则模式 ---
PATTERNS = {
    "cutoff_energy": {
        "pattern": r"(?i)(cutoff|plane.?wave|energy cut.?off|ecut|basis.?set.?cutoff)\s*(?:energy)?\s*(?:of|:|=|is|at)?\s*(\d+(?:\.\d+)?)\s*(eV|Ry|Hartree|Ha|Rydberg|keV|meV)?",
        "unit": "eV", "description": "截断能（平面波基组）",
    },
    "k_points_mesh": {
        "pattern": r"(?i)(\d+)\s*[×xX*]\s*(\d+)\s*[×xX*]\s*(\d+)\s*(?:k.?point|Monkhorst.?Pack|MP|mesh|grid|Brillouin|gamma)",
        "unit": "网格", "description": "k 点网格",
    },
    "k_points_scf": {
        "pattern": r"(?i)(?:SCF|self.?consistent)\s*(?:used|employed|with|at)?\s*(?:a\s*)?(\d+)\s*[×xX*]\s*(\d+)\s*[×xX*]\s*(\d+)\s*(?:k.?point|Monkhorst|MP|mesh|grid)",
        "unit": "网格", "description": "SCF k 点网格",
    },
    "pseudopotential": {
        "pattern": r"(?i)(ultrasoft|ultra.?soft|norm.?conserving|PAW|projector.?augmented.?wave|Vanderbilt|OTFG|ONCV|HGH)\s*(?:pseudo?potential)?",
        "unit": "类型", "description": "赝势类型",
    },
    "functional": {
        "pattern": r"(?i)(?<![a-z])(PBE|PBEsol|LDA|HSE06|HSE|B3LYP|PBE0|SCAN|revPBE|RPBE|BLYP|WC|AM05|PW91|M06-L|M06-2X)(?:\s*(?:functional|GGA|hybrid|exchange.?correlation))?",
        "unit": "泛函", "description": "交换关联泛函",
    },
    "dispersion": {
        "pattern": r"(?i)(DFT.?D3|Grimme|D3\(BJ\)|D3BJ|D3|TS|Tkatchenko.?Scheffler|MBD|many.?body.?dispersion|rVV10|dDsC|DFT.?D2|D2)",
        "unit": "类型", "description": "色散校正",
    },
    "scf_tolerance": {
        "pattern": r"(?i)(SCF|self.?consistent|electronic)\s*(?:convergence|tolerance|threshold|criteria)?\s*(?:of|:|=)?\s*((?:\d+(?:\.\d+)?)\s*[×xX*]?\s*10[\^⁻]?[⁰¹²³⁴⁵⁶⁷⁸⁹\-–]?(\d+)|1e[-–]?(\d+)|\d+\.?\d*[eE][-–]?\d+)\s*(?:eV|Ry|Ha|meV)?",
        "unit": "eV", "description": "SCF 收敛容差",
    },
    "force_tolerance": {
        "pattern": r"(?i)(force|ion|ionic|atomic)\s*(?:convergence|tolerance|threshold|criteria)?\s*(?:of|:|=)?\s*(?:below|less than|<)?\s*(\d+(?:\.\d+)?)\s*(?:eV/[\u00c5ÅA]|meV/[\u00c5ÅA])",
        "unit": "eV/\u00c5", "description": "力收敛容差",
    },
    "smearing": {
        "pattern": r"(?i)(Gaussian|Methfessel.?Paxton|Fermi.?Dirac|cold.?smearing|tetrahedron|MP|Marzari.?Vanderbilt)\s*(?:smearing|broadening)?\s*(?:of|:|=)?\s*(\d+(?:\.\d+)?)?\s*(?:eV|Ry)?",
        "unit": "eV/类型", "description": "smearing 方法/宽度",
    },
    "band_gap": {
        "pattern": r"(?i)(band.?gap|energy.?gap|fundamental.?gap|Eg|optical.?gap)\s*(?:of|:|=|is|about|around|approximately)?\s*(\d+(?:\.\d+)?)\s*(?:eV)?",
        "unit": "eV", "description": "带隙",
    },
    "lattice_constant": {
        "pattern": r"(?i)(lattice.?constant|(?:unit.?cell\s+)?parameter|a[0\s]?=|lattice\s+parameter)\s*(?:of|:|=)?\s*(\d+(?:\.\d+)?)\s*[\u00c5ÅA]",
        "unit": "\u00c5", "description": "晶格常数",
    },
    "spin_polarized": {
        "pattern": r"(?i)(spin.?polarized|spin.?polarization|LSDA|collinear|nonmagnetic|non.?magnetic|ferromagnetic|antiferromagnetic|FM|AFM)",
        "unit": "布尔", "description": "自旋极化",
    },
    "k_points_band_path": {
        "pattern": r"(?i)(\d+)\s*(?:k.?point|kpt|k.?points)\s*(?:per|in|along|for)\s*(?:segment|path|line|band)",
        "unit": "点/段", "description": "能带路径 k 点数",
    },
}


def extract_pdf_text(filepath: str) -> str:
    """从 PDF 文件中提取文本。"""
    if not PDF_SUPPORT:
        print("警告: 未安装 PDF 解析库，请安装 pdfplumber 或 PyMuPDF", file=sys.stderr)
        print("  pip install pdfplumber", file=sys.stderr)
        return ""

    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
    except ImportError:
        try:
            import fitz
            doc = fitz.open(filepath)
            for page in doc:
                text += page.get_text() + "\n"
            doc.close()
        except ImportError:
            pass
    return text


def extract_from_text(text: str, doi: str = "", source: str = "user") -> List[Dict]:
    """从文本中抽取所有匹配的 DFT 参数。"""
    results = []
    seen = set()

    for param_name, cfg in PATTERNS.items():
        for match in re.finditer(cfg["pattern"], text):
            line_start = max(0, match.start() - 60)
            line_end = min(len(text), match.end() + 100)
            context = text[line_start:line_end].replace("\n", " ").strip()

            key = f"{param_name}:{match.start()}"
            if key in seen:
                continue
            seen.add(key)

            entry = {
                "parameter": cfg["description"],
                "unit": cfg["unit"],
                "matched_text": match.group(0).strip(),
                "value": _extract_value(match, cfg),
                "context_sentence": context,
                "doi": doi,
                "source": source,
            }
            results.append(entry)

    return results


def _extract_value(match, cfg: Dict) -> str:
    """从正则匹配中提取有用的数值。"""
    groups = match.groups()
    for g in groups:
        if g and re.match(r"^[\d.]+$", g):
            return g
    for g in groups:
        if g and not re.match(r"^(eV|Ry|Ha|Hartree|meV|keV)$", g, re.IGNORECASE):
            return g.strip()
    return match.group(0).strip()


def extract_from_file(filepath: str, doi: str = "") -> List[Dict]:
    """从文件读取文本并抽取参数。支持 .txt 和 .pdf。"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        text = extract_pdf_text(filepath)
        if not text:
            print(f"  无法提取 PDF 文本: {filepath}", file=sys.stderr)
            return []
    else:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    return extract_from_text(text, doi=doi or os.path.basename(filepath), source="auto_retrieved")


def main():
    parser = argparse.ArgumentParser(description="从 DFT 文献文本/PDF 中抽取计算参数")
    parser.add_argument("--file", help="单篇文献文件路径（支持 .txt .pdf）")
    parser.add_argument("--dir", help="文献目录（批量处理）")
    parser.add_argument("--doi", default="", help="文献 DOI（可选）")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--stdin", action="store_true", help="从标准输入读取")

    args = parser.parse_args()
    all_results = []

    if args.stdin or not (args.file or args.dir):
        if not sys.stdin.isatty():
            text = sys.stdin.read()
            all_results = extract_from_text(text, doi=args.doi)
        else:
            parser.print_help()
            return 1
    elif args.file:
        all_results = extract_from_file(args.file, doi=args.doi)
        print(f"文件: {args.file}")
        print(f"找到 {len(all_results)} 个参数\n")
    elif args.dir:
        total = 0
        for fname in os.listdir(args.dir):
            fpath = os.path.join(args.dir, fname)
            if not os.path.isfile(fpath):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext not in (".txt", ".pdf", ".txt.pdf"):
                continue
            results = extract_from_file(fpath, doi=fname)
            all_results.extend(results)
            total += 1
        print(f"扫描 {total} 个文件，共找到 {len(all_results)} 个参数\n")

    if args.json:
        print(json.dumps(all_results, indent=2, ensure_ascii=False))
    elif all_results:
        by_param: Dict[str, list] = {}
        for r in all_results:
            by_param.setdefault(r["parameter"], []).append(r)
        for pname, entries in by_param.items():
            print(f"\u2500\u2500 {pname} \u2500\u2500")
            for e in entries:
                print(f"  值: {e['value']} {e['unit']}")
                print(f"  原文: {e['context_sentence'][:120]}...")
                print(f"  DOI: {e['doi']}\n")
    else:
        print("未找到匹配的参数。")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
