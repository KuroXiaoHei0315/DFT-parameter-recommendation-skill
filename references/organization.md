# 文献整理和引用管理

当用户收集很多文献、要做 Zotero/BibTeX、写综述或整理 PDF 时使用本文件。

## 推荐目录结构

```text
literature/
  00-search-log.md
  01-screening-table.md
  pdf/
  bib/
  notes/
```

## PDF 命名

推荐稳定命名：

```text
FirstAuthor_Year_ShortTitle_DOIorPMID.pdf
```

例子：

```text
Vaswani_2017_AttentionIsAllYouNeed_arXiv1706.03762.pdf
Smith_2024_LLMMedicalEducation_10.1234.example.pdf
```

不要保留 `science.pdf`、`main.pdf`、`download.pdf` 这种无法识别的文件名。

## 去重顺序

1. DOI。
2. PMID/PMCID。
3. arXiv 或预印本 ID。
4. 完整题名 + 第一作者 + 年份。
5. 模糊题名匹配，但必须人工确认。

## 建议记录字段

- 题名。
- 作者。
- 年份。
- 期刊/会议/来源。
- DOI、PMID、PMCID、arXiv ID。
- URL。
- 全文获取路径。
- 开放许可。
- PDF 文件名。
- 筛选决定。
- 标签和备注。

## 推荐工具

一般用户默认推荐 Zotero：浏览器抓取、PDF 元数据识别、标签、笔记、BibTeX 导出、重复项合并都比较顺手。

写 LaTeX、Markdown 或需要稳定引用键时，配合 Better BibTeX。

做系统综述时，可以考虑 Rayyan、Covidence、ASReview、EPPI-Reviewer，或者使用带纳入/排除理由的电子表格。
