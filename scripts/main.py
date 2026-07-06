#!/usr/bin/env python3
"""DFT-parameter-recommendation V1.0.0 主流程编排脚本。

用法:
    # 自动模式
    python scripts/main.py auto --xsd Ge.xsd --target "band structure" --functional PBE

    # 逐步模式（每步确认）
    python scripts/main.py stepwise --xsd Ge.xsd
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)


def _run_script(script: str, args: list, capture: bool = True) -> subprocess.CompletedProcess:
    cmd = [sys.executable, os.path.join(SCRIPT_DIR, script)] + args
    return subprocess.run(cmd, capture_output=capture, text=True)


def phase0_parse_xsd(xsd_path: str, output_dir: str) -> str:
    """Phase 0: 一次性解析 .xsd 并保存结果。"""
    out_path = os.path.join(output_dir, "structure_info.json")
    r = _run_script("xsd_parser.py", [xsd_path, "--json"], capture=True)
    if r.returncode != 0:
        print(f"  [Phase 0] xsds 解析失败: {r.stderr}")
        return ""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(r.stdout)
    info = json.loads(r.stdout)
    print(f"  [Phase 0] 材料: {info['name']} | 空间群: {info['space_group']['name']} | a={info['conventional_lattice']['a']}")
    print(f"  [Phase 0] 结果已保存: {out_path}")
    return out_path


def phase1_search(output_dir: str, topic: str, keywords: str):
    plan_path = os.path.join(output_dir, "search_plan.md")
    r = _run_script("litplan.py", ["--topic", topic, "--keywords", keywords, "--years", "2000-2026"])
    print(f"  [Phase 1] 检索计划已生成")
    return r.returncode == 0


def phase2_extract(text: str, doi: str, output_dir: str) -> str:
    out_path = os.path.join(output_dir, "extracted_params.json")
    r = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "parameter_extractor.py"),
                         "--stdin", "--doi", doi, "--json"],
                        input=text, capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(r.stdout)
        params = json.loads(r.stdout)
        print(f"  [Phase 2] 提取到 {len(params)} 个参数，已保存: {out_path}")
        return out_path
    print("  [Phase 2] 未提取到参数")
    return ""


def phase3_validate(params_path: str, kb_path: str, output_dir: str) -> str:
    out_path = os.path.join(output_dir, "validation_report.json")
    r = _run_script("parameter_validator.py", ["--params", params_path, "--kb", kb_path, "--json"], capture=True)
    if r.returncode != 0:
        print(f"  [Phase 3] 验证失败")
        return ""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(r.stdout)
    report = json.loads(r.stdout)
    s = report.get("summary", {})
    print(f"  [Phase 3] \u2705通过:{s.get('通过',0)} \u26a0冲突:{s.get('冲突',0)} \u274c未报道:{s.get('未报道',0)} \U0001f914待判决:{s.get('待人工判决',0)}")
    print(f"  [Phase 3] 报告已保存: {out_path}")
    return out_path


def phase4_show(output_dir: str):
    print("  [Phase 4] 工作目录内容:")
    for fname in sorted(os.listdir(output_dir)):
        fpath = os.path.join(output_dir, fname)
        if os.path.isfile(fpath):
            print(f"    - {fname} ({os.path.getsize(fpath)} bytes)")


def auto_mode(args):
    output_dir = tempfile.mkdtemp(prefix="dft_param_")
    print(f"  [全自动模式] 工作目录: {output_dir}\n")

    if args.from_phase in ("phase0", "") and args.xsd:
        phase0_parse_xsd(args.xsd, output_dir)

    if args.from_phase in ("phase0", "phase1", ""):
        topic = f"{os.path.basename(args.xsd or '')} {args.target} {args.functional}"
        keywords = f"{args.target}|property,{args.functional}|functional,DFT|first-principles"
        phase1_search(output_dir, topic, keywords)

    phase4_show(output_dir)
    print("\n  全自动流程完成。")
    return 0


def stepwise_mode(args):
    output_dir = tempfile.mkdtemp(prefix="dft_param_step_")
    print(f"\n  [逐步模式] 工作目录: {output_dir}")
    print("  在每个 Phase 完成后，输入 y 继续，输入 n 终止。\n")

    if args.xsd:
        input("  [Phase 0] 按 Enter 解析 .xsd 文件...")
        struct_path = phase0_parse_xsd(args.xsd, output_dir)
        if not struct_path:
            return 1
        if input("  继续 Phase 1? (y/n): ").strip().lower() != "y":
            print("  用户终止"); return 0

    input("  [Phase 1] 按 Enter 生成检索计划...")
    topic = f"{os.path.basename(args.xsd or '')} band structure PBE"
    keywords = "band structure,DFT|PBE,electronic properties"
    phase1_search(output_dir, topic, keywords)
    if input("  继续 Phase 2? (y/n): ").strip().lower() != "y":
        print("  用户终止"); return 0

    input("  [Phase 2] 按 Enter 演示参数抽取（需提供文献文本）...")
    sample_text = "We used a cutoff energy of 350 eV with a 6x6x6 k-point mesh and PBE functional."
    phase2_extract(sample_text, "demo", output_dir)
    if input("  继续 Phase 3? (y/n): ").strip().lower() != "y":
        print("  用户终止"); return 0

    input("  [Phase 3] 按 Enter 执行四重验证...")
    params_file = os.path.join(output_dir, "extracted_params.json")
    kb_file = os.path.join(SKILL_DIR, "references", "dft_knowledge_base.json")
    if os.path.exists(params_file):
        phase3_validate(params_file, kb_file, output_dir)

    print(f"\n  逐步流程完成。输出目录: {output_dir}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="DFT-parameter-recommendation V1.0.0 主流程编排")
    sub = parser.add_subparsers(dest="mode")

    auto_p = sub.add_parser("auto", help="全自动模式")
    auto_p.add_argument("--xsd", help=".xsd 结构文件路径")
    auto_p.add_argument("--target", default="band structure")
    auto_p.add_argument("--functional", default="PBE")
    auto_p.add_argument("--from", dest="from_phase", default="", help="起始阶段")

    step_p = sub.add_parser("stepwise", help="逐步确认模式")
    step_p.add_argument("--xsd", help=".xsd 结构文件路径")

    args = parser.parse_args()
    if args.mode == "auto":
        return auto_mode(args)
    elif args.mode == "stepwise":
        return stepwise_mode(args)
    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    raise SystemExit(main())

