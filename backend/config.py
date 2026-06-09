import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent  #Path(__file__).resolve()得到当前文件的绝对路径 .parent的到上一级  所以这里最终是D:\xuexidedaimai\Rag与agent\Rag简历项目\RAG
DATA_DIR = BASE_DIR / "data"#pathlib中的Path类型 /是拼接符
UPLOAD_DIR = DATA_DIR / "uploads"#D:\xuexidedaimai\Rag与agent\Rag简历项目\RAG\data\uploads
LOG_DIR = DATA_DIR / "logs"
EVAL_FILE = DATA_DIR / "eval_questions.json"

ES_URL = os.getenv("ES_URL", "http://localhost:9200")
ES_INDEX = os.getenv("ES_INDEX", "enterprise_rag_chunks")#环境没这个字段  默认为enterprise_rag_chunks
ES_PING_TIMEOUT = float(os.getenv("ES_PING_TIMEOUT", "0.5"))

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-v4")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "512"))

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "80"))
PARENT_CHUNK_SIZE = int(os.getenv("PARENT_CHUNK_SIZE", "1500"))#先从环境里读这个字段 没有 使用1500
PARENT_CHUNK_OVERLAP = int(os.getenv("PARENT_CHUNK_OVERLAP", "200"))
NEIGHBOR_WINDOW = int(os.getenv("NEIGHBOR_WINDOW", "1"))

VECTOR_TOP_K = int(os.getenv("VECTOR_TOP_K", "20"))
TEXT_TOP_K = int(os.getenv("TEXT_TOP_K", "20"))#top-k
FINAL_TOP_K = int(os.getenv("FINAL_TOP_K", "5"))

VECTOR_WEIGHT = float(os.getenv("VECTOR_WEIGHT", "0.6"))
TEXT_WEIGHT = float(os.getenv("TEXT_WEIGHT", "0.4"))
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "6000"))

BAILIAN_BASE_URL = os.getenv("BAILIAN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
BAILIAN_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen-turbo")
