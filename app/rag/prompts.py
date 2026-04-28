SYSTEM_PROMPT = """你是一个严谨的 RAG 问答助手。
只能根据提供的资料片段回答问题。
如果资料中没有答案，请直接说明未在当前知识库中找到依据。
优先使用正文、摘要、方法、实验、结果和结论中的信息；不要把作者单位、脚注、页眉页脚、参考文献当作正文结论。
如果多个片段共同回答问题，请综合它们，避免只引用单个片段导致回答不完整。
回答要简洁，并尽量指出依据来自哪些资料。"""


def build_messages(
    question: str,
    contexts: list[dict],
    conversation_history: list[dict] | None = None,
) -> list[dict[str, str]]:
    def format_context(index: int, item: dict) -> str:
        section = _section_label(item)
        page = f" 第{item['page_number']}页" if item.get("page_number") else ""
        role = " 相邻上下文" if item.get("retrieval_role") == "neighbor" else ""
        return (
            f"[{index}] 来源: {item['source_name']}{page}{section}{role}\n"
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


def _format_history(history: list[dict]) -> str:
    if not history:
        return "无"
    lines = []
    for item in history[-6:]:
        lines.append(f"用户：{item.get('question', '')}")
        lines.append(f"助手：{item.get('answer', '')}")
    return "\n".join(lines)
