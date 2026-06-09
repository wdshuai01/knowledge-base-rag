import uuid
import hashlib
from pathlib import Path

from backend.chunker import split_parent_child
from backend.document_loader import load_document
from backend.embeddings import get_embedding_model
from backend.es_store import ESStore


class IngestService:
    def __init__(self, store: ESStore | None = None) -> None:
        self.store = store or ESStore()##这里后面再看  要仔细看

    def ingest(self, file_path: Path, original_filename: str | None = None) -> dict:
        # 入库前先确认 ES 可用，否则后面的建索引、写 chunk 都会失败。
        if not self.store.ping():
            raise RuntimeError("无法连接 Elasticsearch，请确认 http://localhost:9200 可访问")

        self.store.create_index()

        # 用文件内容 hash 做去重：同一个文件即使重复上传，也不会重复切分和写入 ES。
        file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()#跟前面的mk5 去重那里一样
        existing_doc = self.store.find_document_by_hash(file_hash)#如果有返回值 说明文件已经存过了
        if existing_doc:
            return {
                "doc_id": existing_doc["doc_id"],
                "filename": existing_doc["filename"],
                "parents": 0,
                "chunks": 0,
                "duplicated": True,
                "message": "文档内容已存在，不要重复入库",
            }

        display_filename = original_filename or file_path.name#有文件名的用原文件名字 没有的 使用我们给他起的

        # doc_id 是知识库里一份文档的唯一标识；同一文档下会有多个 parent/child chunk。
        doc_id = uuid.uuid4().hex

        # 读取文件文本，然后做父子 chunk 切分。
        # parent 保存较完整上下文，child 用于更精细的检索和向量匹配。
        text = load_document(str(file_path))#我们自己定义的读取文件函数  根据文件类型不同 做不同处理 返回出来是有所有文本的字符串  ###但是这里loader的大小有没有限制呢 我们控制没控制
        split_result = split_parent_child(text)#得到  {"parents": parents, "children": children}  字典  parents和childrean  是包含着各种信息的字典
        parents = split_result["parents"]#得到父块字典 除了内容每一项 还包含着每一项的各种信息
        children = split_result["children"]#得到孩子 字典

        if not children:
            raise ValueError("文档切分后没有可入库的 chunk")

        # parent chunk 不生成 embedding，主要用于命中 child 后扩展上下文。
        for parent in parents:
            chunk_id = f"{doc_id}_{parent['parent_id']}"##
            self.store.index_chunk(
                chunk_id,
                {
                    "doc_id": doc_id,#文件唯一标识符
                    "filename": display_filename,
                    "source_path": str(file_path),#文件绝对路径
                    "file_hash": file_hash,#类似mk5值
                    "chunk_type": "parent",
                    "parent_id": parent["parent_id"],#可以确定parent切分的块数
                    "parent_index": parent["parent_index"],#这个也可以确定
                    "chunk_index": -1,#占位用的  当没用就可   统一结构  不屑也没事
                    "content": parent["content"],#分块的内容
                },
            )

        # child chunk 生成向量后写入 ES，用于后续 KNN 向量检索。
        vectors = get_embedding_model().encode([child["content"] for child in children])#把每一段chunk的内容部分  编成向量
        for child, vector in zip(children, vectors):#打包成对list1 = [1, 2, 3] list2 = ['a', 'b', 'c'] result = zip(list1, list2)  变成(1, 'a'),  (2, 'b'),  (3, 'c')
            chunk_id = f"{doc_id}_child_{child['chunk_index']}"#可以确定是 doc_id文件的child的第chunk——index块
            self.store.index_chunk(
                chunk_id,#整块数据 在es的唯一标识符
                {
                    "doc_id": doc_id,
                    "filename": display_filename,
                    "source_path": str(file_path),
                    "file_hash": file_hash,
                    "chunk_type": "child",
                    "parent_id": child["parent_id"],
                    "parent_index": child["parent_index"],
                    "chunk_index": child["chunk_index"],#孩子在文件中的chunk数
                    "content": child["content"],
                    "embedding": vector.tolist(),#numpy 数组转普通数组
                },
            )

        # refresh 后，新写入的数据可以立刻被搜索到，适合本地教学演示。
        self.store.refresh()#es机制是 刚加入 你只能get到（使用id搜到确切的一条）在es设置的时间后自动refresh  这时候才能使用搜索 条件、全文、向量、聚合  看看为什么这么设计
        return {
            "doc_id": doc_id,
            "filename": display_filename,
            "parents": len(parents),
            "chunks": len(children),
            "duplicated": False,
        }
