# 开发计划

## 阶段 1：工程骨架

- 创建 Python 项目结构。
- 添加 FastAPI 应用入口。
- 添加配置读取。
- 添加统一日志。
- 添加健康检查接口。
- 添加 `.env.example`。

验收标准：

- `GET /health` 返回 `{"status": "ok"}`。
- 本地环境可以通过环境变量启动服务。

## 阶段 2：数据库与模型

- 使用标准库 sqlite3 实现本地数据库访问。
- 定义 Document、Chunk、IngestionJob、QueryLog。
- 添加基础 CRUD。

验收标准：

- 可以创建和查询文档记录。
- 首次启动会自动创建所需表。

## 阶段 3：文档上传与存储

- 实现文件上传接口。
- 保存原始文件。
- 创建 document 和 ingestion job。
- 返回 document_id 和 job_id。

验收标准：

- 上传文件后能在存储目录看到文件。
- 数据库中有对应记录。

## 阶段 4：文档解析与切分

- 实现 PDF、TXT、Markdown 基础解析。
- PDF 默认使用 Docling 进行 layout-aware 解析，pypdf 作为 fallback。
- 实现 chunk splitter，并尽量按 Markdown 章节和表格边界切分。
- 保存 chunk 内容和元数据。

验收标准：

- 文档能被拆分为多个 chunk。
- chunk 能关联原始 document。

## 阶段 5：向量化和索引

- 实现 embedding provider，支持 Ollama 和 OpenAI-compatible API。
- 实现 Qdrant vector store。
- 将 chunk 向量写入 Qdrant。

验收标准：

- 文档处理完成后 Qdrant collection 中有向量。
- 可以用 query vector 搜索到相关 chunk。

## 阶段 6：问答接口

- 实现 query embedding。
- 实现 retriever。
- 实现 prompt builder。
- 实现 LLM provider，支持 Ollama 和 OpenAI-compatible API。
- 返回 answer 和 citations。

验收标准：

- `POST /api/v1/query` 能返回回答。
- 返回结果包含来源引用。

## 阶段 7：本地运行完善

- 添加启动脚本。
- 补充本地运行文档。
- 补充 Ollama 模式和云端 API 模式切换说明。

验收标准：

- 本地能直接启动完整服务。
- Ollama 模式和云端 API 模式至少一种可以完整跑通。
- API、数据库、向量库都能正常工作。
