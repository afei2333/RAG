# AI RAG

一个本地自用的 RAG 问答项目。当前阶段先完成文档和工程约定，之后按功能优先逐步编码。

## 项目目标

- 支持上传或导入文档，完成清洗、切分、向量化和索引。
- 支持基于自然语言问题检索相关片段，并调用大模型生成带引用的回答。
- 优先实现可用功能，暂时不引入 Docker 和复杂部署链路。
- 支持本地 Ollama 和云端大模型 API 两种模型模式。
- 支持替换 embedding 模型、LLM provider 和向量数据库。
- 保持接口清晰，便于后续接入 Web UI、企业微信、飞书、钉钉或其他客户端。

## 默认技术路线

- 后端：Python 3.11+，FastAPI
- 任务处理：MVP 阶段先同步处理，后续再引入异步队列
- 元数据数据库：SQLite 起步，后续可切换 PostgreSQL
- 向量数据库：本地 Qdrant 起步，后续可切换 Chroma 或 PGVector
- 文件存储：本地目录
- 文档解析：PDF 默认 Docling，pypdf 兜底；DOCX 使用 python-docx
- 模型模式：本地 Ollama 或云端 OpenAI-compatible API
- Embedding：Ollama embedding 或云端 embedding API
- LLM：Ollama chat model 或云端 chat API

## 文档入口

- [需求说明](docs/requirements.md)
- [系统架构](docs/architecture.md)
- [数据流程](docs/data-flow.md)
- [API 设计](docs/api.md)
- [PDF 解析策略](docs/pdf-parsing.md)
- [本地运行说明](docs/deployment.md)
- [开发计划](docs/development-plan.md)

## 预期目录结构

```text
ai_RAG/
  app/
    api/
    core/
    db/
    ingest/
    rag/
  docs/
  tests/
  scripts/
  .env.example
  README.md
```

## 当前阶段

1. 完成项目文档和接口约定。
2. 搭建后端工程骨架。
3. 实现文档入库、切分和向量化。
4. 实现检索问答接口。
5. 增加本地运行脚本和基础使用说明。
