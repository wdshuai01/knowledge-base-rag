import json

from backend.config import EVAL_FILE
from backend.retriever import HybridRetriever


class EvalService:
    def __init__(self, retriever: HybridRetriever | None = None) -> None:
        self.retriever = retriever or HybridRetriever()

    def recall_at_k(self) -> dict:
        if not EVAL_FILE.exists():
            return {"total": 0, "metrics": {}, "message": "未找到 data/eval_questions.json"}

        questions = json.loads(EVAL_FILE.read_text(encoding="utf-8-sig"))#返回的是存着json的列表
        if not questions:
            return {"total": 0, "metrics": {}, "message": "评测集为空"}

        hits = {"recall@1": 0, "recall@3": 0, "recall@5": 0}
        for item in questions:
            expected_doc_id = item.get("doc_id")#正确的id
            result_doc_ids = [hit["source"]["doc_id"] for hit in self.retriever.retrieve(item["question"])]#retrieve返回的是排序好的扩展chunk
            if expected_doc_id in result_doc_ids[:1]:
                hits["recall@1"] += 1
            if expected_doc_id in result_doc_ids[:3]:
                hits["recall@3"] += 1
            if expected_doc_id in result_doc_ids[:5]:
                hits["recall@5"] += 1

        total = len(questions)
        return {"total": total, "metrics": {key: value / total for key, value in hits.items()}}
