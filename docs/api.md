# API 设计

## 通用约定

- Base URL: `/api/v1`
- 请求和响应默认使用 JSON。
- 文件上传使用 `multipart/form-data`。
- 错误响应统一包含 `code`、`message`、`detail`。

## 健康检查

### `GET /health`

响应：

```json
{
  "status": "ok"
}
```

## 上传文档

### `POST /api/v1/documents`

请求：

- `file`: 文档文件
- `metadata`: 可选 JSON 字符串

响应：

```json
{
  "document_id": "doc_123",
  "job_id": "job_123",
  "status": "completed"
}
```

MVP 阶段上传接口会同步执行文档解析、切分和向量化。后续引入异步任务队列后，`status` 可以返回 `queued` 或 `processing`。

## 文档列表

### `GET /api/v1/documents`

查询参数：

- `page`: 默认 1
- `page_size`: 默认 20
- `status`: 可选

响应：

```json
{
  "items": [
    {
      "id": "doc_123",
      "filename": "manual.pdf",
      "content_type": "application/pdf",
      "status": "completed",
      "created_at": "2026-04-28T00:00:00Z"
    }
  ],
  "total": 1
}
```

## 文档详情

### `GET /api/v1/documents/{document_id}`

响应：

```json
{
  "id": "doc_123",
  "filename": "manual.pdf",
  "status": "completed",
  "chunk_count": 42,
  "metadata": {}
}
```

## 删除文档

### `DELETE /api/v1/documents/{document_id}`

响应：

```json
{
  "deleted": true
}
```

## 查询处理任务

### `GET /api/v1/jobs/{job_id}`

响应：

```json
{
  "id": "job_123",
  "document_id": "doc_123",
  "status": "completed",
  "error": null
}
```

## RAG 问答

### `POST /api/v1/query`

请求：

```json
{
  "question": "这份文档的核心结论是什么？",
  "top_k": 5,
  "score_threshold": 0.2
}
```

响应：

```json
{
  "answer": "根据文档，核心结论是...",
  "citations": [
    {
      "document_id": "doc_123",
      "chunk_id": "chunk_456",
      "source_name": "manual.pdf",
      "page_number": 3,
      "score": 0.82,
      "text": "相关片段摘要"
    }
  ]
}
```
