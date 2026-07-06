# 合法全文获取流程

当用户需要 PDF 或全文时，按这个顺序走。

## 优先顺序

1. 先解析标识符：
   - DOI、PMID、PMCID、arXiv ID、题名、作者、期刊、年份。
   - DOI/PMID/PMCID 优先于模糊题名。
2. 查官方入口：
   - DOI 跳转页。
   - 出版社文章页面。
   - 期刊官网归档。
   - Supplementary files、appendix、supporting information。
3. 查开放获取：
   - PubMed Central。
   - Europe PMC。
   - Unpaywall。
   - DOAJ。
   - arXiv、bioRxiv、medRxiv、SSRN、RePEc、OSF、Zenodo、Figshare。
   - 学校/机构仓储。
   - 作者主页、课题组主页。
4. 查机构路径：
   - 学校图书馆 discovery。
   - 图书馆代理/VPN。
   - 馆际互借。
   - 文献传递。
5. 联系作者：
   - 给通讯作者发简短邮件，请求其在允许范围内分享个人副本或 accepted manuscript。
6. 找替代版本：
   - 预印本。
   - accepted manuscript。
   - 相关综述、数据集、协议、被引文献。

## 明确不要做

- 不绕过付费墙、DRM、登录系统或访问控制。
- 不共享学校账号或机构账号。
- 不推荐盗版库、泄露 PDF 或影子图书馆。
- 不声称某个副本合法，除非来源是出版社、作者、机构仓储、基金仓储、预印本平台或明确许可页面。

## 全文状态标签

- `downloaded-official`：出版社或期刊官方 PDF。
- `downloaded-oa`：开放获取 PDF，例如 PMC、预印本、机构仓储、作者页面。
- `metadata-only`：只有元数据，暂时没有全文。
- `library-needed`：大概率需要学校图书馆/机构订阅。
- `author-request`：建议联系作者。
- `unavailable`：已经查过常规合法渠道，暂时找不到。

## 邮件模板

```text
Subject: Request for a copy of your article

Dear Professor/Dr. [Name],

I am reading literature on [topic] and found your article:
[Full citation or DOI]

I do not currently have access through my library. If you are able to share a personal copy or accepted manuscript, I would be very grateful.

Best regards,
[Name]
```
