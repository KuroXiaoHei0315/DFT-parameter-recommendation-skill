#!/usr/bin/env python3
"""B核·四重验证脚本：对抽取的参数执行提取准确性、来源一致性、物理合理性、组合一致性检查。

用法:
    python scripts/parameter_validator.py --params params.json
    python scripts/parameter_validator.py --params params.json --json
"""

import argparse
import json
import math
import os
import re
import sys
from typing import Dict, List, Tuple, Optional


def load_knowledge_base(kb_path: str) -> dict:
    with open(kb_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _find_element_from_param(param: dict, params: List[dict]) -> str:
    """从参数列表中尽量推断元素符号。"""
    val = param.get("value", "") or ""
    # 如果值本身就是元素符号
    elem_match = re.match(r"^([A-Z][a-z]?)\b", val)
    if elem_match:
        return elem_match.group(1).capitalize()
    # 在所有参数的上下文中查找元素
    for p in params:
        ctx = p.get("context_sentence", "") or ""
        hits = re.findall(r"\b(?:Ge|Si|C|O|N|Ti|Fe|Ni|Cu|Zn|Ga|As|Sr|Ba|Pb|La|Mn|Co|W|Mo|Nb|Sn|Bi|In|H|He|Li|Be|B|F|Ne|Na|Mg|Al|P|S|Cl|Ar|K|Ca|Sc|V|Cr|Se|Br|Kr|Rb|Y|Zr|Tc|Ru|Rh|Pd|Ag|Cd|Te|Xe|Cs|Hf|Ta|Re|Os|Ir|Pt|Au|Hg|Tl|Po|At|Rn|Fr|Ra|Ac|Th|Pa|U|Np|Pu)\b", ctx)
        if hits:
            return hits[0]
    return "default"


def _normalize_value(val_str: str) -> Tuple[Optional[float], str]:
    """抽取数值和原始字符串。返回 (数值, 原始串)。"""
    if not val_str:
        return None, val_str
    m = re.search(r"(\d+(?:\.\d+)?)", str(val_str))
    if m:
        return float(m.group(1)), val_str
    return None, val_str


def check_extraction_accuracy(param: dict) -> Tuple[str, str]:
    """第一重：提取准确性校验——用正则精确匹配数值+单位。"""
    context = param.get("context_sentence", "") or ""
    value = (param.get("value", "") or "").strip()
    unit = (param.get("unit", "") or "").strip()

    if not context:
        return "待人工判决", "无原文上下文，无法校验"

    # 用正则精确匹配：数值 + 单位
    escaped_val = re.escape(value)
    escaped_unit = re.escape(unit) if unit else ""
    if escaped_unit:
        pattern = rf"\b{escaped_val}\s*{escaped_unit}\b"
    else:
        pattern = rf"\b{escaped_val}\b"

    if re.search(pattern, context):
        return "通过", f"值 '{value} {unit}' 在原文中精确匹配"
    elif value.replace(".", "").isdigit():
        # 数值型参数，检查是否有太接近导致误报
        num_val = float(value) if "." in value else int(value)
        found_all = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)", context)]
        if found_all:
            close_matches = [f for f in found_all if abs(f - num_val) / max(num_val, 1) < 0.05]
            if close_matches:
                return "待人工判决", f"值 '{value}' 在上下文中找到相近数值 {close_matches}，需人工确认精确匹配"
        return "冲突", f"值 '{value}' 在上下文中未找到"
    else:
        # 非数值型（如泛函名、赝势类型）
        if value.lower() in context.lower():
            return "通过", f"值 '{value}' 在原文中存在"
        return "冲突", f"值 '{value}' 未在原文中找到"



def check_source_consistency(param: dict) -> Tuple[str, str]:
    """第二重：来源一致性校验。"""
    pname = param.get("parameter", "") or ""
    value = (param.get("value", "") or "").strip()
    unit = (param.get("unit", "") or "").strip()

    if "截断能" in pname and unit.lower() in ("ry", "rydberg", "ha", "hartree"):
        return "冲突", f"单位 '{unit}' 不是 eV，需确认是否已转换"
    return "通过", "参数名称与值逻辑一致"


def check_physical_reasonability(param: dict, kb: dict, all_params: List[dict]) -> Tuple[str, str]:
    """第三重：物理合理性校验——使用知识库按元素+赝势类型检查。"""
    pname = param.get("parameter", "") or ""
    val_str = (param.get("value", "") or "").strip()
    unit = (param.get("unit", "") or "").strip()
    num_val, _ = _normalize_value(val_str)

    if num_val is None:
        return "待人工判决", f"无法解析数值 '{val_str}'"

    # 确定元素
    element = _find_element_from_param(param, all_params)

    # 确定赝势类型（从所有参数中检索）
    pp_type = "default"
    for p in all_params:
        pv = (p.get("value", "") or "").lower()
        if "ultrasoft" in pv or "vanderbilt" in pv:
            pp_type = "us"
        elif "norm" in pv or "nc" in pv or "oncv" in pv or "hgh" in pv:
            pp_type = "nc"
        elif "paw" in pv or "projector" in pv:
            pp_type = "paw"

    # 截断能检查：按元素+赝势类型查知识库
    if "截断能" in pname:
        cutoff_map = kb.get("cutoff_energy", {}).get("by_element", {}).get(element) or kb.get("cutoff_energy", {}).get("by_element", {}).get("default", {})
        pp_range = cutoff_map.get(pp_type, cutoff_map.get("default", cutoff_map.get("us", [200, 600])))
        lo, hi = pp_range[0], pp_range[1]

        if num_val < lo:
            return "冲突", f"{element} {pp_type.upper()} 截断能 {num_val} eV 偏低（典型范围 {lo}-{hi} eV），可能未收敛"
        elif num_val > hi:
            note = cutoff_map.get("note", "")
            detail = f"，{note}" if note else ""
            return "冲突", f"{element} {pp_type.upper()} 截断能 {num_val} eV 偏高（典型范围 {lo}-{hi} eV{detail}），计算成本可能过大"
        else:
            return "通过", f"{element} {pp_type.upper()} 截断能 {num_val} eV 在典型范围 {lo}-{hi} eV 内"

    # k 点检查
    if "k 点" in pname:
        if num_val > 24:
            return "冲突", f"k 点网格维度 {num_val} 异常偏大，建议确认"
        elif num_val < 1:
            return "冲突", f"k 点网格维度 {num_val} 过小，仅 Gamma 点"
        else:
            return "通过", f"k 点网格维度 {num_val} 在合理范围内"

    # 带隙检查
    if "带隙" in pname or "band gap" in pname.lower():
        if num_val < -1:
            return "冲突", f"带隙为负值 {num_val} {unit}，物理上不合理"
        elif 0 <= num_val < 0.1:
            return "通过", f"带隙 {num_val} eV 接近零，预测为半金属（常见于 PBE 对窄带隙半导体）"
        elif num_val > 20:
            return "冲突", f"带隙 {num_val} eV 异常偏高"
        else:
            # 查知识库中该材料的已知带隙问题
            bg_issues = kb.get("band_gap_known_issues", {}).get("entries", [])
            for entry in bg_issues:
                if element == entry.get("material", ""):
                    exp = entry.get("experimental", 0)
                    if abs(num_val - exp) < 0.3:
                        return "通过", f"带隙 {num_val} eV 接近实验值 {exp} eV"
            return "通过", f"带隙 {num_val} eV 在合理范围内"

    # 自旋极化检查
    if "自旋" in pname:
        # 检查是否为已知磁性元素
        magnetic_elements = set(kb.get("magnetic_elements", []))
        if element in magnetic_elements and "non" in val_str.lower():
            return "冲突", f"{element} 通常是磁性元素，自旋极化设为 '否' 可能不合理"
        elif element not in magnetic_elements and ("spin" in val_str.lower() or "ferro" in val_str.lower()):
            return "待人工判决", f"{element} 通常非磁性，自旋极化开启需文献支持"
        return "通过", "自旋极化设置合理"

    # 晶格常数检查
    if "晶格常数" in pname:
        if num_val < 1.0 or num_val > 50:
            return "冲突", f"晶格常数 {num_val} {unit} 异常（典型范围 1-50 \u00c5）"
        return "通过", f"晶格常数 {num_val} {unit} 在合理范围内"

    return "待人工判决", f"无法根据知识库判定参数 '{pname}' 的合理性"


def check_combination_consistency(params: List[dict], kb: dict) -> List[Tuple[str, str, str]]:
    """第四重：参数标准组合一致性校验。"""
    results = []
    func_combo = kb.get("functional_combinations", {}).get("compatible", {})

    funcs = [p for p in params if "泛函" in (p.get("parameter", "") or "")]
    disps = [p for p in params if "色散" in (p.get("parameter", "") or "")]
    spins = [p for p in params if "自旋" in (p.get("parameter", "") or "")]
    ppts = [p for p in params if "赝势" in (p.get("parameter", "") or "")]
    cutoffs = [p for p in params if "截断" in (p.get("parameter", "") or "")]
    element = _find_element_from_param({"value": ""}, params)

    for f in funcs:
        fname = ((f.get("value", "") or "").upper().strip().split()[0])
        for d in disps:
            dname = (d.get("value", "") or "").upper().strip()
            if fname in func_combo:
                compat = str(func_combo[fname].get(dname, "未知"))
                if "不推荐" in compat:
                    results.append(("冲突", f"{fname} + {dname}", compat))
                elif "标准" in compat or "常用" in compat:
                    results.append(("通过", f"{fname} + {dname}", compat))
                else:
                    results.append(("待人工判决", f"{fname} + {dname}", compat))

    # 赝势类型与截断能匹配
    pp_types_info = kb.get("pseudopotential_types", {})
    for p in ppts:
        pv = (p.get("value", "") or "").lower()
        for c in cutoffs:
            num_val, _ = _normalize_value(c.get("value", ""))
            if num_val is None:
                continue
            pp_key = None
            if "ultrasoft" in pv or "vanderbilt" in pv:
                pp_key = "ultrasoft"
            elif "norm" in pv or "oncv" in pv:
                pp_key = "norm_conserving"
            elif "paw" in pv:
                pp_key = "PAW"
            if pp_key and pp_key in pp_types_info:
                lo, hi = pp_types_info[pp_key]["cutoff_range"]
                if num_val < lo:
                    results.append(("冲突", f"{pp_key} + {num_val}eV", f"该赝势典型截断能范围 {lo}-{hi} eV"))
                elif num_val > hi:
                    results.append(("冲突", f"{pp_key} + {num_val}eV", f"该赝势典型截断能范围 {lo}-{hi} eV"))

    return results


def validate_all(params: List[dict], kb_path: str) -> dict:
    kb = load_knowledge_base(kb_path)
    report = {
        "summary": {"通过": 0, "冲突": 0, "未报道": 0, "待人工判决": 0},
        "checks": [], "combination_checks": [],
    }

    for param in params:
        pname = param.get("parameter", "未知")
        val_str = (param.get("value", "") or "").strip()
        if val_str.startswith("文献未报道"):
            report["summary"]["未报道"] += 1
            continue

        acc_s, acc_n = check_extraction_accuracy(param)
        con_s, con_n = check_source_consistency(param)
        phy_s, phy_n = check_physical_reasonability(param, kb, params)

        statuses = [acc_s, con_s, phy_s]
        if all(s == "通过" for s in statuses):
            final = "通过"
        elif "冲突" in statuses:
            final = "冲突"
        else:
            final = "待人工判决"

        report["summary"][final] = report["summary"].get(final, 0) + 1
        report["checks"].append({
            "parameter": pname,
            "value": f"{val_str} {param.get('unit', '')}".strip(),
            "extraction_check": {"status": acc_s, "note": acc_n},
            "consistency_check": {"status": con_s, "note": con_n},
            "physical_check": {"status": phy_s, "note": phy_n},
            "overall": final,
            "doi": param.get("doi", ""),
        })

    combo_results = check_combination_consistency(params, kb)
    for status, name, note in combo_results:
        report["summary"][status] = report["summary"].get(status, 0) + 1
        report["combination_checks"].append({"combination": name, "status": status, "note": note})

    return report


def format_report(report: dict) -> str:
    s = report["summary"]
    lines = [
        f"审计摘要: 通过 {s.get('通过', 0)} | 冲突 {s.get('冲突', 0)} | 未报道 {s.get('未报道', 0)} | 待判决 {s.get('待人工判决', 0)}",
    ]
    icons = {"通过": "\u2705", "冲突": "\u26a0\ufe0f", "待人工判决": "\U0001f914", "未报道": "\u274c"}
    for check in report["checks"]:
        ov = check["overall"]
        icon = icons.get(ov, "\u2753")
        lines.append(f"{icon} {check['parameter']}: {check['value']}")
        lines.append(f"   提取: {check['extraction_check']['status']} \u2014 {check['extraction_check']['note']}")
        lines.append(f"   来源: {check['consistency_check']['status']} \u2014 {check['consistency_check']['note']}")
        lines.append(f"   物理: {check['physical_check']['status']} \u2014 {check['physical_check']['note']}")
        lines.append(f"   DOI: {check['doi']}\n")
    if report["combination_checks"]:
        lines.append("\u2500\u2500 第四重 \u00b7 组合一致性校验 \u2500\u2500")
        for cc in report["combination_checks"]:
            icon = icons.get(cc["status"], "\U0001f914")
            lines.append(f"{icon} {cc['combination']}: {cc['note']}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="DFT 参数四重验证（B核）")
    parser.add_argument("--params", required=True, help="参数 JSON 文件路径")
    parser.add_argument("--kb", default=os.path.join(os.path.dirname(__file__), "..", "references", "dft_knowledge_base.json"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    with open(args.params, "r", encoding="utf-8") as f:
        params = json.load(f)
    if not os.path.exists(args.kb):
        args.kb = os.path.join(os.path.dirname(__file__), "..", "references", "dft_knowledge_base.json")
    report = validate_all(params, args.kb)
    print(json.dumps(report, indent=2, ensure_ascii=False) if args.json else format_report(report))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
