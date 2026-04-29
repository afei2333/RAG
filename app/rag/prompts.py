SYSTEM_PROMPT = """你是一个严谨、克制的 RAG 问答助手。
回答必须遵守以下规则：
1. 只能依据提供的资料片段和必要的历史对话理解问题，不得使用外部知识补充事实结论。
2. 如果资料片段中没有足够依据回答问题，请明确说明“未在当前知识库中找到依据”或“当前资料不足以判断”，不要猜测。
3. 优先使用正文、摘要、方法、实验、结果和结论中的信息；不要把作者单位、脚注、页眉页脚、目录、参考文献当作正文结论。
4. 如果多个资料片段共同回答问题，请综合它们；不要只依赖单个片段导致回答片面。
5. 如果资料片段之间存在不一致，请指出差异，并说明哪些结论分别来自哪些片段。
6. 回答应简洁、直接、中文表达自然。
7. 涉及具体事实、数据、结论或来源时，应在句末标注引用编号，例如 [1]、[2]；不要引用未使用的片段。
8. 如果资料片段包含 Markdown 表格，回答涉及表格数据时应保留表格结构，或清晰列出关键行列；不要遗漏表头、单位和注释。
9. 如果用户要求总结、对比、提取要点或解释概念，请仍然保持基于资料片段，不要扩展到资料之外。"""



def build_messages(
    question: str,
    contexts: list[dict],
    conversation_history: list[dict] | None = None,
) -> list[dict[str, str]]:
    def format_context(index: int, item: dict) -> str:
        section = _section_label(item)
        content_type = _content_type_label(item)
        page = f" 第{item['page_number']}页" if item.get("page_number") else ""
        role = " 相邻上下文" if item.get("retrieval_role") == "neighbor" else ""
        return (
            f"[{index}] 来源: {item['source_name']}{page}{section}{content_type}{role}\n"
            f"{item['content']}"
        )

    context_text = "\n\n".join(
        format_context(index, item)
        for index, item in enumerate(contexts, start=1)
    )

    history_text = _format_history(conversation_history or [])

    user_prompt = f"""历史对话：
{history_text}

资料片段：
{context_text}

用户问题：
{question}

请结合必要的历史对话理解用户问题，但事实依据必须来自资料片段，并在合适位置提到引用编号。"""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def _section_label(item: dict) -> str:
    metadata = item.get("metadata") or {}
    if not metadata and item.get("metadata_json"):
        try:
            import json

            metadata = json.loads(item["metadata_json"])
        except Exception:
            metadata = {}
    section_title = metadata.get("section_title")
    if not section_title:
        return ""
    return f" 章节: {section_title}"


def _content_type_label(item: dict) -> str:
    metadata = item.get("metadata") or {}
    content_type = metadata.get("content_type")
    if content_type == "table":
        return " 类型: 表格"
    if content_type == "figure":
        return " 类型: 图片"
    return ""


def _format_history(history: list[dict]) -> str:
    if not history:
        return "无"
    lines = []
    for item in history[-6:]:
        lines.append(f"用户：{item.get('question', '')}")
        lines.append(f"助手：{item.get('answer', '')}")
    return "\n".join(lines)
