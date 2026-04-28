# 数据流程

## 文档入库流程

```mermaid
sequenceDiagram
  participant U as User
  participant A as API
  participant S as Storage
  participant D as SQLite
  participant P as Pipeline
  participant E as Embedding
  participant V as VectorDB

  U->>A: Upload document
  A->>S: Save file
  A->>D: Create document and job
  A->>P: Run ingestion
  P->>S: Read file
  P->>P: Parse and clean text
  P->>P: Split into chunks
  P->>D: Save chunks
  P->>E: Embed chunks
  P->>V: Upsert vectors
  P->>D: Mark job completed
  A-->>U: Return document_id and job status
```

## 问答流程

```mermaid
sequenceDiagram
  participant U as User
  participant A as API
  participant E as Embedding
  participant V as VectorDB
  participant D as SQLite
  participant L as LLM

  U->>A: Ask question
  A->>E: Embed question
  A->>V: Search similar chunks
  A->>D: Load chunk metadata
  A->>A: Build context prompt
  A->>L: Generate answer
  A->>D: Save query log
  A-->>U: Return answer and citations
```

## Chunk 设计

建议默认值：

- `chunk_size`: 800 到 1200 中文字符，或对应 token 长度
- `chunk_overlap`: 100 到 200 中文字符
- `top_k`: 5
- `score_threshold`: 按向量库实际分数标定

每个 chunk 至少保存：

- `id`
- `document_id`
- `content`
- `chunk_index`
- `page_number`
- `source_name`
- `metadata`

## 引用策略

回答返回 citations：

```json
[
  {
    "document_id": "doc_123",
    "chunk_id": "chunk_456",
    "source_name": "example.pdf",
    "page_number": 3,
    "score": 0.82,
    "text": "引用片段摘要"
  }
]
```

前端或调用方可以据此展示来源。
