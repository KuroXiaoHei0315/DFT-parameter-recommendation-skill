# Prompt Template — DFT-Parameter V1.0

用于其他 AI agent 调用本 skill 时的推荐提示词模板：

\```text
请使用 DFT-Parameter V1.0 技能执行以下任务：

材料/结构文件: <path/to/structure.xsd>
计算目标: <能带结构/弹性常数/光学性质/...>
泛函: <PBE/HSE06/LDA/...>
自旋极化: <是/否>
色散校正: <是(D3)/否>
特殊要求: <氧空位/应变/...>

请按以下工作流执行：
1. 解析 .xsd 文件提取结构信息
2. 检索相关 DFT 文献并获取全文
3. 从文献中抽取计算参数（截断能、k 点、赝势等）
4. 执行四重验证（提取准确性、来源一致性、物理合理性、组合一致性）
5. 输出参数推荐与文献对照表
\```

使用 scripts/ 中的工具：
- python scripts/xsd_parser.py <file.xsd> — 解析结构文件
- python scripts/litplan.py --topic "..." --keywords "..." — 生成检索计划
- python scripts/parameter_extractor.py --stdin --doi "..." — 从文本抽取参数
- python scripts/parameter_validator.py --params params.json --kb references/dft_knowledge_base.json — 四重验证
- python scripts/main.py auto --xsd <file.xsd> --target "..." — 主流程编排
