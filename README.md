# DFT-parameter-recommendation

> **一体化 DFT 参数文献校对引擎** — 从文献中抽取 DFT 计算参数，四重核验后输出参数推荐与文献对照表。

![Version](https://img.shields.io/badge/version-v1.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.8%2B-orange)

---

## 📋 概述

`DFT-parameter-recommendation` 是一个面向计算材料学研究者的自动化工具。它的核心理念是**结果导向**：用户只需描述想计算什么性质，引擎会自动完成以下全部流程：

1. **结构解析** — 解析 Materials Studio `.xsd` 文件，提取空间群、晶格常数、原子信息
2. **目标澄清** — 通过结构化对话明确用户的计算目标
3. **文献检索与采集** — 通过 OpenAlex / Crossref 等 API 自动检索相关文献
4. **参数抽取** — 从文献中提取 DFT 计算参数，绑定 DOI 和原文引证
5. **四重验证** — B 核审稿人引擎执行提取准确性、来源一致性、物理合理性、组合一致性验证
6. **输出推荐** — 生成参数推荐与文献对照表

## ✨ 特性

- 🔍 **双通道文献获取**：用户上传文献 + API 自动检索
- 🧠 **双核对抗引擎**：A 核教授挖掘参数 + B 核审稿人四重验证
- 🔄 **两种运行模式**：逐步确认模式（stepwise）适合首次使用；全自动模式（auto）适合批量运行
- 📦 **内置知识库**：含 DFT 参数合理性规则（截断能范围、k 点密度、泛函组合兼容性等）
- 📄 **XML .xsd 原生支持**：解析 Materials Studio 格式的结构文件
- 🛡️ **防幻觉设计**：所有参数必须绑定原文 DOI 和引证句

## ✨ 适用与不适用
-**适用场景**：周期性体系 DFT 计算参数推荐、CASTEP/VASP 参数文献校对、计算材料学文献元分析、MS 参数模板迭代。
-**不适用场景**：分子/团簇体系（Gaussian/ORCA 类）、量化计算参数、实验-only 文献检索、参数填写与作业提交、非 DFT 的第一性原理方法。


## 🚀 快速开始

### 安装

```bash
git clone https://github.com/your-username/DFT-parameter-recommendation.git
cd DFT-parameter-recommendation
pip install -r requirements.txt
```

### 基本用法

**全自动模式：**
```bash
python scripts/main.py auto --xsd path/to/structure.xsd --target "band structure"
```

**逐步确认模式（推荐首次使用）：**
```bash
python scripts/main.py stepwise --xsd path/to/structure.xsd
```

**指定目标性质：**
```bash
python scripts/main.py auto --xsd MnO.xsd --target "lattice constant optimization" --spin yes --dispersion D3
```

### 在 Codex CLI 中使用

将本仓库放入 Codex skills 目录：

```powershell
# Windows
git clone https://github.com/your-username/DFT-parameter-recommendation.git $env:USERPROFILE\.codex\skills\DFT-parameter-recommendation
```

然后在 Codex 对话中通过 `$dft-parameter` 触发。

## 📂 项目结构

```
DFT-parameter-recommendation/
├── SKILL.md                    # Codex Skill 定义（主入口）
├── README.md                   # 项目说明
├── LICENSE                     # MIT 许可证
├── .gitignore
├── requirements.txt            # Python 依赖
├── CONTRIBUTING.md             # 贡献指南
├── scripts/
│   ├── main.py                 # 主流程编排（入口）
│   ├── xsd_parser.py           # .xsd 结构文件解析
│   ├── parameter_extractor.py  # 文献参数自动抽取
│   ├── parameter_validator.py  # B 核四重验证自动化
│   ├── litplan.py              # 文献检索计划生成
│   ├── prepare_harvest_run.py  # 批量采集准备
│   ├── download_accessible_fulltexts.py  # 开放获取全文下载
│   ├── rank_candidates.py      # 候选文献优先级排序
│   ├── organize_final_outputs.py  # 输出文件整理
│   ├── make_student_outputs.py    # 学生友好输出生成
│   └── generate_readable_report.py  # 可读报告生成
├── references/
│   ├── dft_knowledge_base.json # DFT 参数知识库
│   ├── search-strategy.md      # 检索策略方法论
│   ├── source-quality.md       # 来源质量标准
│   ├── full-text-access.md     # 合法全文获取指南
│   ├── organization.md         # 结果整理规范
│   ├── output-reporting.md     # 输出报告格式
│   ├── prompt_template.md      # 提示词模板
│   ├── config_template.json    # 配置文件模板
│   ├── batch-harvest.md        # 批量采集工作流
│   └── journal_metrics_template.csv  # 期刊指标模板
├── examples/
│   ├── Si.xsd                  # 示例：硅晶体结构
│   └── example_output.md       # 示例输出
└── .github/
    └── workflows/
        └── ci.yml              # GitHub Actions CI
```

## 🔧 配置

在项目根目录创建 `config.local.json` 可覆盖默认配置：

```json
{
  "api": {
    "user_agent": "MyProject/1.0 (mailto:my@email.com)",
    "timeout": 15
  },
  "paths": {
    "output_dir": "./output"
  }
}
```

## 📖 引用文献

本工具使用的核心基准文献：

| 用途 | 文献 | DOI |
|:-----|:-----|:---:|
| PBE 泛函 | Perdew et al., PRL (1996) | `10.1103/physrevlett.77.3865` |
| DFT+U 方法 | Dudarev et al., PRB (1998) | `10.1103/physrevb.57.1505` |
| DFT-D3 校正 | Grimme et al., JCP (2010) | `10.1063/1.3382344` |
| GMTKN30 基准 | Goerigk & Grimme, PCCP (2011) | `10.1039/C0CP02984J` |

## 📄 许可证

本项目基于 **MIT License** 开源。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！详见 [CONTRIBUTING.md](CONTRIBUTING.md)。
