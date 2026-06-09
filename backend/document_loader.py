from pathlib import Path

from langchain_community.document_loaders import PyMuPDFLoader, TextLoader


def load_document(path: str) -> str:
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix in {".txt", ".md"}:
        loader = TextLoader(str(file_path), encoding="utf-8", autodetect_encoding=True)
    elif suffix == ".pdf":
        loader = PyMuPDFLoader(str(file_path))
    else:
        raise ValueError(f"不支持的文件类型: {suffix}，仅支持 .txt、.md、.pdf")
    #pdf读出来 每页是一个document loader是一个列表  而txt读出来 整个文本就是一个document
    docs = loader.load()
    text = "\n".join(doc.page_content for doc in docs)#page_content读出document的内容   "\n".join是让后面的列表按"\n"连接起来成字符串
    if not text.strip():
        raise ValueError("文档解析后没有可用文本")
    return text

