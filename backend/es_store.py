from typing import Dict, List
from urllib.error import URLError
from urllib.request import Request, urlopen

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError

from backend.config import EMBEDDING_DIM, ES_INDEX, ES_PING_TIMEOUT, ES_URL


class ESStore:
    def __init__(self) -> None:
        self.client = Elasticsearch(ES_URL, request_timeout=30, max_retries=0, retry_on_timeout=False)

    def ping(self) -> bool:
        try:
            req = Request(ES_URL, method="GET")
            with urlopen(req, timeout=ES_PING_TIMEOUT) as resp:
                return 200 <= resp.status < 500
        except (OSError, URLError):
            return False

    def create_index(self) -> None:
        if self.client.indices.exists(index=ES_INDEX):
            return

        mapping = {
            "mappings": {
                "properties": {

                    """在你的 properties 里：
                    text 类型 → 可以关键词搜索（搜内容）
                    keyword 类型 → 可以精确搜索（搜文件名、ID）
                    dense_vector 类型 → 不能关键词搜索，只能语义相似度检索
                    date/long 类型 → 可以范围搜索（大于、小于）  integer可精确可范围 """
                    
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
                }
            }
        }
        self.client.indices.create(index=ES_INDEX, body=mapping)#ES_INDEX索引名  相当于数据库表名
        """
        es.indices.create(...)    # 创建索引（表）
        es.indices.delete(...)    # 删除索引
        es.indices.exists(...)    # 判断索引是否存在
        es.indices.put_mapping(...) # 设置字段结构"""

    def index_chunk(self, chunk_id: str, doc: Dict) -> None:  #这里传入的chunk_id是什么
        self.client.index(index=ES_INDEX, id=chunk_id, document=doc)#往索引ES_INDEX里面添加数据  可以认为数据的唯一标识符是id

    def refresh(self) -> None:
        self.client.indices.refresh(index=ES_INDEX)

    def keyword_search(self, query: str, top_k: int) -> List[Dict]:#搜索跟query最相关的k个chunk
        if not self.client.indices.exists(index=ES_INDEX):
            return []
        body = {
            "size": top_k,
            "query": {
                "bool": {#有多个条件要使用bool  比如有must和filter
                    "must": [{"match": {"content": {"query": query, "operator": "or"}}}],#must必须满足的 "match"是全文匹配  query自动分词 去es的索引库的我们前面设计的"content"字段里去找
                                                                                            #"operator": "or" 意思满足分完词之后的一个就可以  and是必须分完词之后的所有此都能在一个content找到 才能被检索
                                                                                        #size query must filter match term是苦丁写法 content chunk_type是我们想去搜的字段名字
                    "filter": [{"term": {"chunk_type": "child"}}],#match是全文匹配  term是精确查询  必须有不分词的整句  才会被搜出来
                }
            },
        }
        res = self.client.search(index=ES_INDEX, body=body)
        """
        search出来的结构
        {
    "took": 1,            # 查询花了多久（毫秒）
    "timed_out": False,   # 是否超时
    "_shards": {...},     # 分片信息（不用管）
    
    "hits": {             # 👈 所有结果都在这里
        "total": {"value": 5},   # 总共有多少条匹配
        
        "hits": [         # 👈 真正的文档列表
            {
                "_index": "你的索引",   #我们的索引名字
                "_id": "123",           #chunk的唯一id  往索引里面加数据的时候指定的
                "_score": 1.8,         # 相关性分数
                "_source": {            # 👈 你存的数据！
                    "content": "RAG是检索增强生成",
                    "file_name": "test.pdf",
                    "chunk_type": "child"
                }
            },
            # 第二条、第三条...
        ]
    }
}"""
        return [
            {"chunk_id": hit["_id"], "score": float(hit["_score"]), "source": hit["_source"]}
            for hit in res["hits"]["hits"]
        ]

    def vector_search(self, query_vector: list[float], top_k: int) -> List[Dict]:
        if not self.client.indices.exists(index=ES_INDEX):
            return []
        body = {
            "knn": {#语义匹配
                "field": "embedding",#告诉es去我们设置的embedding字段找向量 算相似值  我们是只有孩子节点  算了相似值
                "query_vector": query_vector,
                "k": top_k,
                "num_candidates": max(top_k * 3, 50),
                "filter": [{"term": {"chunk_type": "child"}}],#这里放里面因为   knn内置了filter
            },
            "size": top_k,#搜一搜为什么 上面给了k  这里还要设置
        }
        res = self.client.search(index=ES_INDEX, body=body)
        return [
            {"chunk_id": hit["_id"], "score": float(hit["_score"]), "source": hit["_source"]}#搜搜 这两个 相关性分数的范围
            for hit in res["hits"]["hits"]
        ]

    def get_parent(self, doc_id: str, parent_id: str) -> Dict | None:
        try:
            res = self.client.get(index=ES_INDEX, id=f"{doc_id}_{parent_id}")
            return {"chunk_id": res["_id"], "source": res["_source"]}
        except NotFoundError:
            return None

    def get_neighbors(self, doc_id: str, chunk_index: int, window: int) -> List[Dict]:
        body = {
            "size": window * 2 + 1,#最多返回多少条
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"doc_id": doc_id}},
                        {"term": {"chunk_type": "child"}},
                        {"range": {"chunk_index": {"gte": max(0, chunk_index - window), "lte": chunk_index + window}}},
                    ]
                }
            },
            "sort": [{"chunk_index": {"order": "asc"}}],
        }
        res = self.client.search(index=ES_INDEX, body=body)
        return [{"chunk_id": hit["_id"], "source": hit["_source"]} for hit in res["hits"]["hits"]]

    def list_documents(self) -> List[Dict]:
        if not self.ping() or not self.client.indices.exists(index=ES_INDEX):
            return []
        body = {
            "size": 0,# 不返回原始数据，只返回聚合结果
            "query": {"term": {"chunk_type": "child"}}, # 过滤条件：只查 chunk_type = child 的数据
            "aggs": {# 开始聚合（统计）
                "docs": {# 聚合名字叫 docs（你可以随便改，不影响功能）
                    "terms": {"field": "doc_id", "size": 1000}, # 按字段分组 = SQL GROUP BY doc_id 最多返回 1000 个分组
                    "aggs": {# 嵌套聚合：分组之后，再做一次子聚合
                        "filename": { # 聚合名
                            "top_hits": {# 取每组的前N条数据
                                "size": 1,# 每组只返回 1 条
                                "_source": ["filename", "source_path", "file_hash"]}},# 只返回这3个字段，不返回全部数据
                    },
                }
            },
        }
        res = self.client.search(index=ES_INDEX, body=body)
        """返回结果
        "aggregations" : {
  "docs" : {
    "buckets" : [
      {
        "key" : "doc_123",  # doc_id
        "doc_count" : 10,   # 这个文件有10个chunk
        "filename" : {
          "hits" : {
            "hits" : [
              {
                "_source" : {
                  "filename" : "文件A.pdf",
                  "source_path" : "/tmp/xxx",
                  "file_hash" : "abcd1234"
                }
              }
            ]
          }
        }
      },
      ...
    ]
  }
}"""

        docs = []
        for bucket in res.get("aggregations", {}).get("docs", {}).get("buckets", []):
            hit = bucket["filename"]["hits"]["hits"][0]["_source"]
            docs.append(
                {
                    "doc_id": bucket["key"],
                    "filename": hit.get("filename", ""),
                    "source_path": hit.get("source_path", ""),
                    "file_hash": hit.get("file_hash", ""),
                    "chunks": bucket["doc_count"],
                }
            )
        return docs

    def find_document_by_hash(self, file_hash: str) -> Dict | None:
        if not file_hash or not self.ping() or not self.client.indices.exists(index=ES_INDEX):
            return None

        body = {
            "size": 1,
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"chunk_type": "child"}},
                        {"term": {"file_hash": file_hash}},
                    ]
                }
            },
        }
        res = self.client.search(index=ES_INDEX, body=body)
        hits = res["hits"]["hits"]
        if not hits:
            return None

        source = hits[0]["_source"]
        return {
            "doc_id": source["doc_id"],
            "filename": source.get("filename", ""),
            "file_hash": source.get("file_hash", ""),
        }

    def delete_document(self, doc_id: str) -> int:
        if not self.ping() or not self.client.indices.exists(index=ES_INDEX):
            return 0
        res = self.client.delete_by_query(index=ES_INDEX, body={"query": {"term": {"doc_id": doc_id}}}, refresh=True)
        return int(res.get("deleted", 0))
