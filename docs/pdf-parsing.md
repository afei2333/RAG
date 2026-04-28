# PDF 解析策略

## 结论

`pypdf` 适合作为兜底方案，不适合作为论文 PDF 的主解析器。论文常见的双栏排版、表格、公式、图片说明和复杂阅读顺序，会让基础文本抽取出现错序、断表、漏标题等问题。

MVP 默认使用 Docling 解析 PDF：

- 更关注页面 layout 和 reading order。
- 能将表格结构导出为 Markdown 形式，更适合后续 chunk 和 RAG 引用。
- 对论文里的双栏、标题层级、公式、图片说明等结构更友好。
- 可在本地运行，符合本项目本地自用目标。

`pypdf` 保留为 fallback：

- 安装更轻。
- 对简单文本 PDF 速度快。
- 当 Docling 未安装或解析失败时，可继续让系统尽量可用。

## 环境变量

```bash
PDF_PARSER=docling
PDF_FALLBACK_PARSER=pypdf
```

如果运行环境暂时不想安装 Docling，可以改成：

```bash
PDF_PARSER=pypdf
```

## 论文 PDF 优化点

### 清洗与去噪

入库前会先做论文友好的文本清洗：

- 删除跨页重复出现的页眉、页脚和页码。
- 删除常见的版权、预印本、DOI、短脚注和通讯作者邮箱行。
- 合并 PDF 抽取造成的断行和断词，保留标题、列表、表格的换行。
- 识别 `Abstract`、`Introduction`、`Method`、`Results`、`Conclusion` 等章节边界，避免把作者信息、注释、正文和参考文献切在同一个 chunk 中。
- 默认跳过 `References` / `Bibliography` 段落，减少参考文献条目污染正文检索。

已有文档如果是在旧逻辑下入库的，需要删除后重新上传，才能生成新的清洗结果和向量。

相关环境变量：

```bash
CHUNK_SIZE=1000
CHUNK_OVERLAP=150
MIN_CHUNK_CHARS=120
CONTEXT_WINDOW_CHUNKS=1
```

`MIN_CHUNK_CHARS` 用于过滤过短、信息密度低的片段；`CONTEXT_WINDOW_CHUNKS` 用于查询时补充命中片段前后的相邻上下文。

### 表格

Docling 会优先保留表格结构，导出 Markdown 后，切分器会尽量避免在表格行附近硬切。

### 双栏

Docling 的 layout 和 reading order 处理比纯文本抽取更适合双栏论文。这样可以减少左栏、右栏内容互相穿插的问题。

### 图片和图注

第一版会保留 Docling 导出的 Markdown 文本。图像本身暂不进入向量库，但图注、图片标题、附近说明文字会参与检索。

### 扫描版 PDF

Docling 支持 OCR 配置，但 OCR 会显著增加依赖和耗时。第一版先不默认开启 full-page OCR。遇到扫描版论文时，再单独打开 OCR 配置。

## 依赖说明

需要在运行环境手动安装：

```bash
pip install -r requirements.txt
```

其中：

- `docling`: 高级 PDF layout、reading order、表格结构解析。
- `pypdf`: 简单 PDF 文本抽取和 fallback。
