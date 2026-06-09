from langchain_core.prompts import PromptTemplate

from backend.config import MAX_CONTEXT_CHARS


PROMPT = PromptTemplate.from_template(
    """你是企业知识库问答助手。请只根据给定资料回答问题。
如果资料中没有答案，请明确说明“知识库中没有找到足够依据”。
回答要准确、简洁，并在关键结论后标注引用 ID，例如 [1]。
引用 ID 必须来自对应资料块开头的编号。不要猜测编号，不要把一个资料块的结论标成另一个资料块的编号。

资料：
{context}

问题：{question}

答案："""
)


def build_prompt(question: str, chunks: list[dict]) -> str:
    parts = []
    total = 0
    for idx, chunk in enumerate(chunks, start=1):#给每个dict编号 从1开始
        source = chunk["source"]
        text = chunk.get("expanded_context") or source["content"]#没有扩展的内容 就用子chunk自己的内容   这个expanded_context有父chunk所以已经包括子chunk的内容了
        block = f"资料ID [{idx}]\n文件：{source['filename']}，chunk：{source['chunk_index']}\n{text}"
        if total + len(block) > MAX_CONTEXT_CHARS:#？？？？  这里为什么固定  这里可以修改成动态的
            break
        parts.append(block)
        total += len(block)#总字符数
    context = "\n\n".join(parts) if parts else "无可用资料。"#  总资料 拼成字符串了
    return PROMPT.format(context=context, question=question)
