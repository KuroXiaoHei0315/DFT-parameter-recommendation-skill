# 批量文献采集流程

当用户要很多篇文献、可复现检索、批量下载、下载日志、去重 PDF/HTML/XML 文献包时，使用本文件。

本流程参考 `zhongzhx/literature-harvest` 的思路：用配置文件驱动关键词检索，保留完整候选表，不因为下载失败就丢掉记录，只尝试合法全文路径，PDF 不可用时保留 HTML/XML，最后做去重和汇总。

## 任务目录结构

每次批量任务生成一个目录：

```text
<run-root>/
  config.json
  配置文件.json
  search_plan.md
  检索计划.md
  candidate_table.csv
  候选文献总表.csv
  high_priority.csv
  高优先级文献.csv
  medium_priority.csv
  中优先级文献.csv
  low_priority.csv
  低优先级文献.csv
  journal_metrics.csv
  期刊指标.csv  # 后台核验来源，不作为主要交付物
  downloaded_fulltexts/
  已下载全文/
  download_logs/
    download_log.csv
    下载日志.csv
  dedup_manifest.csv
  去重清单.csv
  harvest_summary.md
  下载汇总.md
  下载报告.html
  下载报告.pdf
  README_先看我.md
  00_先看我_文件说明.txt
  文章地址总表.csv
  内部数据_一般不用打开/
```

中文文件名是给用户看的主入口；英文文件名保留给脚本兼容和跨平台工具使用。交付时优先告诉用户中文文件。

注意：所有列出文献的中文 CSV 都必须把期刊指标合并到每一行，包括影响因子、分区、指标年份、指标来源、索引情况。不要让用户单独打开 `期刊指标.csv` 去对照。

## 配置文件要写什么

- `topic`：中文主题。
- `years`：年份范围。
- `queries`：检索式列表。
- `include_terms`：强相关关键词。
- `secondary_terms`：辅助相关关键词。
- `exclude_terms`：噪声词或排除词。
- `sources`：计划使用的数据源，例如 PubMed、PMC、Europe PMC、Crossref、OpenAlex、Google Scholar、Semantic Scholar、出版社页面、机构仓储。
- `download`：超时、尝试次数、延迟。

## 候选表字段

尽量使用这些列：

```text
record_id,title,authors,year,journal,doi,pmid,pmcid,source_database,abstract_if_available,article_type_guess,keyword_include_hits,keyword_secondary_hits,keyword_exclude_hits,keyword_relevance_score,priority,open_access_status_if_detectable,pdf_url_candidate,landing_page_url,candidate_urls_json,download_status,exclusion_reason_if_any,quality_notes,impact_factor,jcr_quartile,metric_year,metric_source,indexing,venue_note
```

下载失败也不要删行。保留元数据，并标记状态。

## 优先级规则

高优先级：

- 强相关关键词命中，并且辅助词也命中。
- 有开放获取或直接 PDF 信号。
- 是研究论文、综述、指南、benchmark、方法论文，且符合用户目标。
- 年份符合要求。
- 期刊/会议质量高，或引用/学科声誉强。

中优先级：

- 相关但缺少摘要或全文。
- 方法相关但场景稍偏。
- 访问路径不确定。

低优先级/排除：

- editorial、commentary、news、conference abstract、patent，除非用户明确要。
- 只有关键词碰巧命中，内容不相关。
- 超出年份范围。
- 明显误检。

## 下载状态标签

- `success_pdf`：保存了真正 PDF。
- `success_html`：保存了 HTML 全文。
- `success_xml`：保存了 XML 全文。
- `metadata_only`：只有元数据，没有可访问全文。
- `inaccessible`：需要订阅、登录、403/401、付费墙或被阻止。
- `broken_link`：404/410 或无效链接。
- `rate_limited`：被限流，稍后重试。
- `excluded`：筛选时排除，不下载。

## HTML/XML 二次检查

如果保存的是 HTML/XML，继续查里面有没有合法 PDF 链接：

- 出版社 Download PDF。
- PMC PDF。
- 机构仓储附件。
- DOI 或文章 canonical 链接。

汇报时必须区分 true PDF、HTML 全文、XML 全文，不要混在一起。

## 去重规则

下载后再去重：

1. DOI。
2. PMID/PMCID。
3. 标准化题名。
4. 文件哈希。

优先保留真正 PDF，其次 HTML/XML；优先保留官方出版社或机构仓储版本；同一篇保留更完整的文件。

## 最终汇报

最终汇报要分两层：先给普通人看的报告，再给技术日志。

普通人看的报告必须说明：

- 候选总数。
- 高/中/低优先级数量。
- 真正 PDF 数量。
- HTML/XML 全文数量。
- 只有元数据的数量。
- 不可访问数量。
- 去重后保留数量。
- 剩余文献下一步合法路线：学校库、馆际互借、联系作者、机构仓储继续搜索、找替代文献。

技术日志保留 CSV：

- `候选文献总表.csv` / `candidate_table.csv`：全部候选。
- `下载日志.csv` / `download_log.csv`：每次下载尝试。
- `总下载日志.csv` / `combined_download_log.csv`：合并后的最终状态。
- `去重清单.csv` / `dedup_manifest.csv`：去重依据。

## 影响因子和分区

不要让脚本凭空猜影响因子。影响因子、JCR 分区、SJR、CiteScore 都会随年份变化，必须写来源和年份。

可在候选表中直接填这些列，也可以填 `journal_metrics.csv`：

```text
journal,impact_factor,jcr_quartile,metric_year,metric_source,indexing,venue_note
Environmental Science & Technology,11.3,Q1,2024,JCR,SCIE; Scopus,环境领域高影响期刊
```

报告生成时会自动显示“影响因子/分区”。没有核验的期刊显示“待核验”，不要用空白或虚构数字。

下载或核验结束后，运行：

```bash
python scripts/make_student_outputs.py --run-root <run-root>
```

它会生成学生实际要看的中文表：

- `候选文献总表.csv`
- `高优先级文献.csv`
- `已下载文献清单.csv`
- `待处理文献清单.csv`

最后运行：

```bash
python scripts/organize_final_outputs.py --run-root <run-root>
```

它会生成 `文章地址总表.csv`，并把英文兼容文件和原始日志移动到 `内部数据_一般不用打开/`，让根目录保持清楚。

这些表都会直接包含题名、年份、期刊或来源、影响因子、JCR 分区、指标年份、指标来源、索引情况、DOI、全文状态和下一步建议。

## 生成可读报告

下载结束后运行：

```bash
python scripts/generate_readable_report.py --run-root <run-root> --title "文献下载报告" --pdf
```

这个脚本会生成：

- `下载报告.html`：浏览器可读报告。
- `下载报告.pdf`：如果本机有 Edge、Chrome 或 Chromium，会自动用无头浏览器打印成 PDF。
- `README_先看我.md`：极简中文说明。

如果 PDF 生成失败，不要阻塞任务；把 HTML 报告交给用户，并说明原因通常是本机没有可用浏览器命令。
