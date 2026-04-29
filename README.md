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

## 本地启动

启动 Qdrant：

```bash
mkdir -p data/qdrant
docker run -d \
  --name ai-rag-qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v "$(pwd)/data/qdrant:/qdrant/storage" \
  qdrant/qdrant:latest
```

安装依赖并检查配置：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/check_config.py
```

启动后端服务：

```bash
bash scripts/start_dev.sh
```

或直接运行：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8008 --reload
```

启动后访问 `http://localhost:8008/`。如需使用其他端口，可以设置 `APP_PORT`：

```bash
APP_PORT=8000 bash scripts/start_dev.sh
```

## 论文图片处理

PDF 入库时会额外提取论文中的图片，并把图片作为可引用的视觉证据返回给前端。

图片本体保存到本地上传目录：

```text
data/uploads/{document_id}/figures/
```

元数据和切分后的 chunk 保存到 SQLite：

```text
data/rag.db
```

Qdrant 中只保存向量和 payload，不保存图片文件本体。对于论文图片，只索引能匹配到 caption 的图片，并生成 `figure` 类型的 chunk。embedding 内容由图片页码、图片序号、caption，以及正文中引用该 figure 的句子组成，不使用整页正文作为图片上下文。payload 会包含：

```json
{
  "document_id": "doc_xxx",
  "chunk_id": "chunk_xxx",
  "source_name": "paper.pdf",
  "page_number": 5,
  "content_type": "figure"
}
```

查询命中图片相关 chunk 时，接口返回的 citation 会包含 `image_url` 和 `caption`。前端会在“引用来源”中展示图片预览，点击图片可以打开大图。

整体存储关系：

```text
PDF 原文件
  -> data/uploads/

提取出的论文图片
  -> data/uploads/{document_id}/figures/

文本 chunk、figure chunk 元数据
  -> data/rag.db

文本 chunk、figure chunk 向量
  -> Qdrant collection: rag_chunks
```

## 项目和对话范围

左侧栏以“项目”为主要入口。项目是一组已索引文档组成的知识库范围，适合把同一主题、同一论文组或同一业务资料放在一起提问。

基本流程：

1. 上传文档并完成索引。
2. 点击“新建项目”，多选已索引完成的文档。
3. 创建项目后，点击项目进入该项目的对话历史。
4. 在项目内提问时，检索范围只包含该项目下的文档。
5. 点击左侧返回按钮可以回到项目列表。

对话历史会归属到当前项目下。重新打开项目时，左侧栏展示该项目的历史对话；未选择项目时，默认检索全部已索引文档。

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
