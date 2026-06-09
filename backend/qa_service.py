import time

from backend.citation import build_references, fix_answer_citations
from backend.llm_client import LLMClient
from backend.monitor import write_log
from backend.prompt_builder import build_prompt
from backend.retriever import HybridRetriever


class QAService:
    def __init__(self, retriever: HybridRetriever | None = None) -> None:
        self.retriever = retriever or HybridRetriever()

    def ask(self, question: str) -> dict:
        start = time.perf_counter()#返回当前系统的高精度时间 单位是秒
        chunks = self.retriever.retrieve(question)#得到的是排序好的  扩展后的chunk 已经包含分数和 扩展内容
        retrieval_ms = (time.perf_counter() - start) * 1000#转换成毫秒单位 这是得到chuks的时间

        if not chunks:
            answer = "\u77e5\u8bc6\u5e93\u4e2d\u6ca1\u6709\u627e\u5230\u53ef\u7528\u6587\u6863\u6216\u76f8\u5173\u7247\u6bb5\uff0c\u8bf7\u5148\u4e0a\u4f20\u5e76\u6210\u529f\u5165\u5e93\u4f01\u4e1a\u6587\u6863\u3002"
            write_log(
                {
                    "question": question,
                    "answer": answer,
                    "retrieval_time_ms": retrieval_ms,
                    "generation_time_ms": 0.0,
                    "total_time_ms": (time.perf_counter() - start) * 1000,
                    "chunks": [],
                }
            )
            return {"answer": answer, "references": []}

        gen_start = time.perf_counter()
        prompt = build_prompt(question, chunks)#提示词生成完毕
        answer = LLMClient().generate(prompt)#返回模型的回复
        generation_ms = (time.perf_counter() - gen_start) * 1000
        total_ms = (time.perf_counter() - start) * 1000

        references = build_references(chunks)#拼接引用栏里要放的
        answer = fix_answer_citations(answer, references)#修正引用编号
        write_log(#写入日志
            {
                "question": question,
                "answer": answer,
                "retrieval_time_ms": retrieval_ms,
                "generation_time_ms": generation_ms,
                "total_time_ms": total_ms,
                "chunks": references,
            }
        )
        return {"answer": answer, "references": references}
