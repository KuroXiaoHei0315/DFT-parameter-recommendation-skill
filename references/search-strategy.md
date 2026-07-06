# 中文检索策略

当用户给出一个研究主题时，用本文件把主题变成可复现的检索式。

## 先确认的信息

- 研究主题或具体问题。
- 学科领域和目标数据库。
- 年份范围。
- 文献类型：综述、系统综述、Meta 分析、实验研究、队列研究、方法论文、数据集、标准、指南、学位论文。
- 语言：中文、英文或中英都要。
- 目标：只要文献清单、必须下载全文、要高影响因子、要 Zotero/BibTeX、要写综述。
- 质量条件：影响因子、JCR 分区、SJR 分区、SCI/SSCI/EI、Scopus、PubMed、CCF、核心期刊等。

## 关键词拆分

把主题拆成 2-5 个概念块。每个概念块都补：

- 精确短语：`"large language model"`。
- 同义词：`LLM OR ChatGPT OR GPT-4`。
- 缩写和拼写变体：`behavior OR behaviour`。
- 上位词/下位词：`environmental science OR climate change OR sustainability`。
- 控制词：PubMed 的 MeSH、Embase 的 Emtree、IEEE taxonomy、ACM CCS、ERIC 主题词等。

例子：

```text
("large language model*" OR LLM OR ChatGPT OR GPT)
AND
("environmental science" OR climate OR sustainability OR ecology OR pollution OR "water management")
AND
(application OR assessment OR prediction OR "decision support")
```

## 查得太少怎么办

- 去掉一个限制概念块。
- 把精确短语换成同义词。
- 查关键文献的参考文献。
- 查关键文献的被引文献。
- 查预印本、机构仓储、作者主页。
- 用作者名、数据集名、软件名、项目名、基金号继续追。

## 查得太多怎么办

- 限定题名/摘要字段。
- 加入研究对象、方法、场景、指标。
- 加年份、文章类型、学科分类、同行评议过滤。
- 先看前 50-100 条，确认噪声词后再加排除词。

## 数据库写法

PubMed 示例：

```text
("large language model*"[tiab] OR LLM[tiab] OR ChatGPT[tiab])
AND
("environmental science"[tiab] OR climate[tiab] OR pollution[tiab])
```

Google Scholar：

- 用短检索式。
- 已知文献用完整题名加引号。
- 用 `author:` 和 `source:` 限定作者或来源。
- 用 Cited by 和 Related articles 扩展。

中文数据库：

- 同时用中文词和英文词。
- 尝试官方译名、常用译名、缩写、机构名。
- CNKI、万方、维普的下载状态要单独记录，不要和 DOI 元数据混在一起。

## 检索日志模板

```markdown
| 日期 | 数据库 | 检索式 | 过滤条件 | 命中数 | 保留数 | 备注 |
|---|---|---|---|---:|---:|---|
| YYYY-MM-DD | PubMed | ... | 2021-2026, review | 128 | 12 | 增加 MeSH/同义词 |
```
