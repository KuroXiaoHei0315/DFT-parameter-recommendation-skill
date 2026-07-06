#!/usr/bin/env python3
"""解析 Materials Studio .xsd 文件，提取结构信息。

用法:
    python scripts/xsd_parser.py Ge.xsd
    python scripts/xsd_parser.py Ge.xsd --json

输出:
    - 化学式、空间群、晶系、晶格常数、原子种类与坐标
"""

import argparse
import json
import math
import re
import sys
from typing import Optional, List
from xml.etree import ElementTree as ET


def parse_xsd(filepath: str) -> dict:
    """解析 .xsd 文件，返回结构化信息字典。"""
    tree = ET.parse(filepath)
    root = tree.getroot()

    result = {
        "filename": filepath,
        "name": "",
        "space_group": {"name": "", "it_number": 0, "long_name": "", "schoenflies": ""},
        "crystal_system": "",
        "centering": "",
        "lattice": "",
        "lattice_vectors": {"a_vec": None, "b_vec": None, "c_vec": None},
        "conventional_lattice": {"a": 0, "b": 0, "c": 0, "alpha": 90, "beta": 90, "gamma": 90},
        "atoms": [],
        "num_atoms": 0,
    }

    # --- 提取名称 ---
    tree_root = root.find(".//AtomisticTreeRoot")
    if tree_root is not None:
        result["name"] = tree_root.get("Name", "")

    # --- 提取空间群和晶格 ---
    # 优先选有 ITNumber 的 SpaceGroup（即使 Hidden），其次选有晶格向量的
    space_groups = root.findall(".//SpaceGroup")
    sg_main = None
    sg_fallback = None
    for sg in space_groups:
        it = sg.get("ITNumber", "0")
        if it != "0":
            sg_main = sg
            break
        if sg_fallback is None:
            av = sg.get("AVector")
            bv = sg.get("BVector")
            cv = sg.get("CVector")
            if av and bv and cv:
                sg_fallback = sg
    sg_main = sg_main or sg_fallback or (space_groups[0] if space_groups else None)

    if sg_main is not None:
        result["space_group"]["name"] = sg_main.get("Name", "").strip()
        result["space_group"]["long_name"] = sg_main.get("LongName", "").strip()
        result["space_group"]["schoenflies"] = sg_main.get("SchoenfliesName", "").strip()
        try:
            result["space_group"]["it_number"] = int(sg_main.get("ITNumber", "0"))
        except ValueError:
            pass
        result["crystal_system"] = sg_main.get("System", "")
        result["centering"] = sg_main.get("Centering", "")
        result["lattice"] = sg_main.get("Lattice", "")
        result["lattice_vectors"]["a_vec"] = _parse_vector(sg_main.get("AVector", ""))
        result["lattice_vectors"]["b_vec"] = _parse_vector(sg_main.get("BVector", ""))
        result["lattice_vectors"]["c_vec"] = _parse_vector(sg_main.get("CVector", ""))

        # 如果是立方晶系且面心，直接从常规晶胞向量读 a
        va = result["lattice_vectors"]["a_vec"]
        vb = result["lattice_vectors"]["b_vec"]
        vc = result["lattice_vectors"]["c_vec"]
        if va and vb and vc:
            if result["crystal_system"] == "Cubic" and abs(va[1]) < 0.001:
                result["conventional_lattice"]["a"] = round(abs(va[0]), 4)
                result["conventional_lattice"]["b"] = round(abs(vb[1]), 4)
                result["conventional_lattice"]["c"] = round(abs(vc[2]), 4)
            else:
                _calc_conventional_lattice(result)

    # --- 提取原子（仅原始原子，跳过 ImageOf 镜像） ---
    seen_ids = set()
    for atom in root.findall(".//Atom3d"):
        aid = atom.get("ID", "")
        if aid in seen_ids or atom.get("ImageOf") is not None:
            seen_ids.add(aid)
            continue
        seen_ids.add(aid)
        components = atom.get("Components", "") or ""
        name = atom.get("Name", "") or ""
        element = components.split(",")[0].strip() if components else name.rstrip("0123456789")
        coords = _trace_mapping_coords(atom, root)
        result["atoms"].append({
            "id": aid, "name": name, "element": element, "coordinates": coords,
        })

    result["num_atoms"] = len(result["atoms"])
    return result


def _parse_vector(vec_str: str) -> Optional[List[float]]:
    """解析 'x,y,z' 格式的向量字符串。"""
    if not vec_str:
        return None
    parts = vec_str.split(",")
    if len(parts) != 3:
        return None
    try:
        return [float(p.strip()) for p in parts]
    except ValueError:
        return None


def _trace_mapping_coords(atom_elem, root) -> Optional[List[float]]:
    """从 Atom3d 的父 IdentityMapping 的 Element 属性中提取平移分量。"""
    mapping_id = atom_elem.get("Mapping")
    if not mapping_id:
        return None
    mapping = root.find(f".//*[@ID='{mapping_id}']")
    if mapping is None:
        return None
    identity = mapping.find("IdentityMapping")
    if identity is None:
        return None
    elem_str = identity.get("Element", "")
    parts = elem_str.split(",")
    if len(parts) == 12:
        try:
            return [float(parts[9]), float(parts[10]), float(parts[11])]
        except ValueError:
            pass
    return None


def _calc_conventional_lattice(result: dict) -> None:
    """从 primitive lattice vectors 推算常规晶胞参数。"""
    va, vb, vc = result["lattice_vectors"]["a_vec"], result["lattice_vectors"]["b_vec"], result["lattice_vectors"]["c_vec"]
    if not all([va, vb, vc]):
        return
    a = math.sqrt(sum(x * x for x in va))
    b = math.sqrt(sum(x * x for x in vb))
    c = math.sqrt(sum(x * x for x in vc))
    alpha = math.degrees(math.acos(sum(va[i] * vb[i] for i in range(3)) / (a * b) if a * b > 0 else 0))
    beta = math.degrees(math.acos(sum(vb[i] * vc[i] for i in range(3)) / (b * c) if b * c > 0 else 0))
    gamma = math.degrees(math.acos(sum(va[i] * vc[i] for i in range(3)) / (a * c) if a * c > 0 else 0))
    result["conventional_lattice"] = {
        "a": round(a, 4), "b": round(b, 4), "c": round(c, 4),
        "alpha": round(alpha, 2), "beta": round(beta, 2), "gamma": round(gamma, 2),
    }


def format_human(info: dict) -> str:
    lines = [f"材料名称: {info['name']}"]
    sg = info["space_group"]
    lines.append(f"空间群: {sg['name'] or '未识别'} (IT#{sg['it_number']})")
    if sg["long_name"]:
        lines.append(f"  全称: {sg['long_name']}")
    if sg["schoenflies"]:
        lines.append(f"  熊夫利记号: {sg['schoenflies']}")
    lines.append(f"晶系: {info['crystal_system']}")
    lines.append(f"晶格类型: {info['centering']} / {info['lattice']}")
    cl = info["conventional_lattice"]
    lines.append(f"晶格常数: a={cl['a']:.4f}, b={cl['b']:.4f}, c={cl['c']:.4f}, "
                 f"α={cl['alpha']:.1f}°, β={cl['beta']:.1f}°, γ={cl['gamma']:.1f}°")
    lines.append(f"原胞原子数: {info['num_atoms']}")
    for atom in info["atoms"]:
        cs = f"({', '.join(f'{c:.4f}' for c in atom['coordinates'])})" if atom["coordinates"] else "N/A"
        lines.append(f"  - {atom['element']} ({atom['name']}): {cs}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="解析 Materials Studio .xsd 结构文件")
    parser.add_argument("file", help=".xsd 文件路径")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()
    try:
        info = parse_xsd(args.file)
    except ET.ParseError as e:
        print(f"错误: XML 解析失败 - {e}", file=sys.stderr); return 1
    except FileNotFoundError:
        print(f"错误: 文件未找到 - {args.file}", file=sys.stderr); return 1
    if args.json:
        print(json.dumps(info, indent=2, ensure_ascii=False))
    else:
        print(format_human(info))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
