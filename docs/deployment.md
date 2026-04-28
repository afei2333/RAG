# 本地运行说明

## 运行目标

项目面向本地自用，第一版优先实现功能，暂时不使用 Docker。推荐直接用 Python 虚拟环境启动 FastAPI 服务，并按需要连接本地 Ollama 或云端模型 API。

## 服务组成

- `api`: FastAPI HTTP 服务
- `sqlite`: 本地元数据数据库文件
- `qdrant`: 本地向量数据库服务，后续可替换为嵌入式向量库
- `ollama`: 可选，本地 LLM 和 embedding 服务

## 环境变量

建议复制 `.env.example` 为 `.env` 后修改。

```bash
APP_ENV=production
APP_HOST=0.0.0.0
APP_PORT=8000

DATABASE_URL=sqlite+aiosqlite:///./data/rag.db

QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=rag_chunks

STORAGE_DIR=./data/uploads

# 分别选择向量化和对话使用哪个后端：ollama 或 cloud。
EMBEDDING_BACKEND=ollama
LLM_BACKEND=ollama

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_LLM_MODEL=qwen2.5:7b

CLOUD_BASE_URL=https://api.openai.com/v1
CLOUD_API_KEY=replace_me
CLOUD_EMBEDDING_MODEL=text-embedding-3-small
CLOUD_LLM_MODEL=gpt-4.1-mini
```

## 模型模式

### 本地 Ollama

适合本地自用和隐私优先的场景。

建议配置：

```bash
EMBEDDING_BACKEND=ollama
LLM_BACKEND=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=qwen2.5:7b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
```

Ollama embedding 使用官方当前推荐的接口 `POST /api/embed`。如果上传时报 404，请确认 Ollama 版本较新，并确认服务地址是 `OLLAMA_BASE_URL` 配置的地址。

### 云端大模型 API

适合需要更强回答质量或更稳定推理能力的场景。云端 API 按 OpenAI-compatible 格式接入。

建议配置：

```bash
EMBEDDING_BACKEND=cloud
LLM_BACKEND=cloud
CLOUD_API_KEY=replace_me
CLOUD_EMBEDDING_BASE_URL=https://api.openai.com/v1
CLOUD_EMBEDDING_MODEL=text-embedding-3-small
CLOUD_LLM_BASE_URL=https://api.openai.com/v1
CLOUD_LLM_MODEL=gpt-4.1-mini
```

也可以直接复制云端模板：

```bash
cp .env.cloud.example .env
```

配置检查：

```bash
python scripts/check_config.py
```

Embedding 和 LLM 可以分别选择后端，不要求都用 Ollama 或都用云端：

- `EMBEDDING_BACKEND=ollama` 时，使用 `OLLAMA_EMBEDDING_MODEL`。
- `EMBEDDING_BACKEND=cloud` 时，使用 `CLOUD_EMBEDDING_BASE_URL`、`CLOUD_EMBEDDING_MODEL` 和 `CLOUD_EMBEDDING_API_KEY`。
- `LLM_BACKEND=ollama` 时，使用 `OLLAMA_LLM_MODEL`。
- `LLM_BACKEND=cloud` 时，使用 `CLOUD_LLM_BASE_URL`、`CLOUD_LLM_MODEL` 和 `CLOUD_LLM_API_KEY`。
- 如果两者使用同一个 key，可以只设置 `CLOUD_API_KEY`，不填单独的 key。
- 如果两者 key 也不同，就分别设置 `CLOUD_EMBEDDING_API_KEY` 和 `CLOUD_LLM_API_KEY`。
- 同一个知识库中，文档入库和提问必须使用同一个 embedding 模型。

从旧配置迁移时，建议删除这些旧变量，避免自己看配置时混淆：

```bash
MODEL_MODE
EMBEDDING_PROVIDER
EMBEDDING_BASE_URL
EMBEDDING_API_KEY
EMBEDDING_MODEL
LLM_PROVIDER
LLM_BASE_URL
LLM_API_KEY
LLM_MODEL
```

## 数据持久化

需要持久化：

- SQLite 数据库文件
- Qdrant 数据目录
- 上传文件目录

本地默认目录：

```text
./data/rag.db
./data/qdrant
./data/uploads
```

## 本地启动

后续编码完成后，预期启动方式：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

也可以使用脚本：

```bash
bash scripts/start_dev.sh
```

## 依赖安装

本仓库不会自动安装依赖。需要手动在目标运行环境执行：

```bash
pip install -r requirements.txt
```

依赖用途：

- `fastapi`: HTTP API 服务
- `uvicorn`: ASGI 启动器
- `httpx`: 调用 Ollama、云端 API 和 Qdrant REST API
- `python-multipart`: 支持文件上传
- `docling`: 高级 PDF layout、reading order、表格结构解析
- `pypdf`: 解析 PDF
- `python-docx`: 解析 DOCX

PDF 默认解析配置：

```bash
PDF_PARSER=docling
PDF_FALLBACK_PARSER=pypdf
```

## 运行检查

启动前检查：

- `/health` 返回 ok。
- 浏览器打开 `http://localhost:8000/` 可以使用本地前端页面。
- Ollama 模式下，`ollama serve` 正在运行。
- Ollama 模式下，所需模型已拉取。
- 云端模式下，API key 和 base URL 正确。
- 上传文档后任务能完成。
- 问答接口能返回 citations。
