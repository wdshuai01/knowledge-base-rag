from typing import Dict, List

from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.config import CHUNK_OVERLAP, CHUNK_SIZE, PARENT_CHUNK_OVERLAP, PARENT_CHUNK_SIZE

#这里做 normalize_text() 是为了在切 chunk、检索、喂给大模型之前，把文档文本变得更干净、更稳定
def normalize_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]#text.splitlines()按换行符取   line.strip()把每一行前后空格、换行、制表符去掉  这里去掉是为什么
    return "\n".join(line for line in lines if line)#if line 行为空就不保留  然后重新组装  相当于把每一行前后的空格和制表符  和空白行给去掉了  统一格式了


def split_parent_child(text: str) -> Dict[str, List[Dict]]:
    text = normalize_text(text)#规整的字符串
    if not text:
        return {"parents": [], "children": []}

    parent_splitter = RecursiveCharacterTextSplitter(#langchain里面的文本分割器
        chunk_size=PARENT_CHUNK_SIZE,#默认单位是「字符数」（中文、英文、标点、空格都算 1 个字符）。
        chunk_overlap=PARENT_CHUNK_OVERLAP,
        separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
    )
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
    )

    parents = []
    children = []
    for parent_index, parent_text in enumerate(parent_splitter.split_text(text)):#python中的enumerate可以让我们拿到内容的序号   #注意for index, chunk in enumerate(chunks):print(f"第 {index} 块：{chunk}")
        parent_id = f"parent_{parent_index}"#parent_index是后面的内容是文件的第几个chunk parent_index从0开始


        #parent_id 是父 chunk 的唯一标识，用来“找回这个父块”。 比如 child chunk 命中了：
        #{
#  "doc_id": "abc",
#  "parent_id": "parent_3",
 # "content": "二线城市住宿标准为每晚不超过 400 元"
#}
        #系统就可以根据doc_id + parent_id找 找到唯一的parent块

        #因为 parent_id 更像“名字/编号”，适合拼 ES 文档 ID：
        #而 parent_index 是数字，适合排序和范围计算：  不考虑这个 我感觉用一个index就足够了


        parents.append({"parent_id": parent_id, "parent_index": parent_index, "content": parent_text})
        for child_text in child_splitter.split_text(parent_text):##对一个父块 再切分
            children.append(
                {
                    "parent_id": parent_id,
                    "parent_index": parent_index,
                    "chunk_index": len(children),
                    "content": child_text,
                }
            )
    return {"parents": parents, "children": children}

