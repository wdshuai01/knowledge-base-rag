from typing import Dict, List

from backend.config import ES_INDEX, FINAL_TOP_K, NEIGHBOR_WINDOW, TEXT_TOP_K, TEXT_WEIGHT, VECTOR_TOP_K, VECTOR_WEIGHT
from backend.embeddings import get_embedding_model
from backend.es_store import ESStore


def _normalize(scores: Dict[str, float]) -> Dict[str, float]:
    if not scores:
        return {}
    max_score = max(scores.values())
    if max_score <= 0:#最大相关分数为负数  说明不相关  分数全置0   但是我们用的关键词和向量检索实际上返回都大于等于0  这里是为了保险
        return {key: 0.0 for key in scores}
    return {key: value / max_score for key, value in scores.items()}#最大最小标准化 ：除以最大值归一化  得到的结果分数都在0到1这个区间


class HybridRetriever:
    def __init__(self, store: ESStore | None = None) -> None:
        self.store = store or ESStore()

    def retrieve(self, question: str) -> List[Dict]:
        if not self.store.ping() or not self.store.client.indices.exists(index=ES_INDEX):#确定es索引 存在
            return []
        query_vector = get_embedding_model().encode_one(question)#找嵌入向量模型 把问题编成向量
        text_hits = self.store.keyword_search(question, TEXT_TOP_K)#检索出来k个带着id和相关性分数的chunk  全文检索
        vector_hits = self.store.vector_search(query_vector, VECTOR_TOP_K)#检索出来k个带着id和相关分数的chunk  向量相似性检索

        text_scores = {hit["chunk_id"]: hit["score"] for hit in text_hits}#最后得到是字典
        vector_scores = {hit["chunk_id"]: hit["score"] for hit in vector_hits}
        norm_text = _normalize(text_scores)
        norm_vector = _normalize(vector_scores)#两个标准化后 分数都为0-1这个区间  这里存的是id：归一化分数的字典

        merged: Dict[str, Dict] = {}
        for hit in text_hits + vector_hits:
            chunk_id = hit["chunk_id"]
            merged.setdefault(chunk_id, {"chunk_id": chunk_id, "source": hit["source"]})#字典中key已经存在就返回原有值 不修改  不存在 就新添 并返回刚添的这个值

#这个hit["source"]是你存es里的信息如下
        """mapping = {
            "mappings": {
                "properties": {
                    # 一份原始文档的唯一编号，删除文档、聚合同一文档的 chunk 都靠它。
                    "doc_id": {"type": "keyword"},
                    # 用户上传时的原始文件名，用于前端展示和引用来源展示。
                    "filename": {"type": "keyword"},
                    # 文件保存到本地磁盘后的路径，方便排查这个 chunk 来自哪个上传文件。
                    "source_path": {"type": "keyword"},
                    # 文件内容的 sha256 hash，用来判断重复上传，同内容文件不重复入库。
                    "file_hash": {"type": "keyword"},
                    # chunk 类型：parent 表示大块上下文，child 表示真正参与检索的小块。
                    "chunk_type": {"type": "keyword"},
                    # child chunk 所属的 parent chunk 编号，用来从小块扩展回大段上下文。
                    "parent_id": {"type": "keyword"},
                    # parent chunk 在原文里的顺序编号，方便按原文顺序组织上下文。
                    "parent_index": {"type": "integer"},
                    # child chunk 在原文里的顺序编号，方便取相邻 chunk 做上下文补充。
                    "chunk_index": {"type": "integer"},
                    # chunk 正文。text 类型会分词，主要用于 ES 的 BM25 关键词检索。
                    "content": {"type": "text", "analyzer": "standard"},
                    # chunk 向量。dense_vector 用于 KNN 语义检索，维度必须和百炼 embedding 输出一致。
                    "embedding": {
                        "type": "dense_vector",
                        "dims": EMBEDDING_DIM,
                        "index": True,
                        "similarity": "cosine",
                    },
                }"""


        ranked = []
        for chunk_id, item in merged.items():
            text_score = norm_text.get(chunk_id, 0.0)#key不存在返回0  存在 返回关键词匹配分数
            vector_score = norm_vector.get(chunk_id, 0.0)#返回 向量匹配分数
            score = TEXT_WEIGHT * text_score + VECTOR_WEIGHT * vector_score#全文匹配占0.4  向量占0.6
            expanded = self._expand_context(item["source"])#传入的是存入es的符合要求的chunk 组成的字典   得到的是传入的这个chunk的parent和neighbor组成的文本字符串
            ranked.append(
                {
                    **item,#把字典内容  拆成 和下面一样的格式加进来
                    "score": score,
                    "text_score": text_score,
                    "vector_score": vector_score,
                    "expanded_context": expanded,
                }
            )#给chunk  加上了score和扩展内容

        return sorted(ranked, key=lambda item: item["score"], reverse=True)[:FINAL_TOP_K]#sorted是python自带的全局函数   这里的item不是上面的 是ranked的每一个item 这里意思是按key里面的字段排序ranked顺序
                                                                                          #reverse=True 为倒序  即从大到小  返回的是排序好的扩展chunk
                                                                                            #排序好的截断  留FINAL_TOP_K=5个

    def _expand_context(self, source: Dict) -> str:
        doc_id = source["doc_id"]
        parent = self.store.get_parent(doc_id, source["parent_id"])
        neighbors = self.store.get_neighbors(doc_id, int(source["chunk_index"]), NEIGHBOR_WINDOW)#返回的是该位置的子chunk左边NEIGHBOR_WINDOW个 和右边NEIGHBOR_WINDOW个
        parts = []
        if parent:
            parts.append(parent["source"]["content"])
        parts.extend(item["source"]["content"] for item in neighbors)#extend是把另一个列表里面的数加到我们的列表里面  此时这里面有parent和neighbor的文本正文
        seen = set()
        unique_parts = []
        for part in parts:
            if part not in seen:#集合里面 不允许重复 seen集合是去重使用的
                seen.add(part)
                unique_parts.append(part)
        return "\n".join(unique_parts)#这里得到了 parent和neighbor的 去重正文 字符串
