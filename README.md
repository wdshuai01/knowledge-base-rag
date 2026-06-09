# 企业级知识库问答系统（LangChain + Elasticsearch Hybrid RAG）

本项目参考 RAGFlow 的 RAG 主链路，实现一个适合简历展示的企业知识库问答系统。LangChain 负责文档加载、文本切分、Prompt 和 LLM 编排；阿里云百炼负责 Embedding 和 Qwen 生成模型；Elasticsearch 统一存储 chunk 文本、元数据和 dense_vector 向量；后端自定义实现 BM25 + KNN 混合检索、分数归一化、父子 chunk 上下文扩展、引用来源和检索监控。

## 功能

- 上传 `.txt`、`.md`、`.pdf` 企业文档
- LangChain Loader 解析文档
- 父 chunk + 子 chunk 两级切分
- 百炼 `text-embedding-v4` 子 chunk 向量化
- Elasticsearch 存储父 chunk、子 chunk、元数据和 dense_vector
- ES BM25 关键词检索
- ES dense_vector KNN 向量检索
- Python 后端融合排序
- 命中子 chunk 后扩展父 chunk 和邻近 chunk
- LangChain PromptTemplate 拼接知识库上下文
- OpenAI 兼容接口调用百炼 `text-embedding-v4`
- LangChain ChatOpenAI 通过阿里云百炼 OpenAI 兼容接口调用 Qwen
- 前端展示答案、引用来源、文档列表、问答日志和 Recall@K 评测

## 目录

```text
RAG/
├── backend/
├── frontend/
├── data/
├── docker-compose.yml
├── requirements.txt
├── README.md
└── run.bat
```

## 启动步骤

1. 启动 Elasticsearch：

```powershell
docker compose up -d
curl http://localhost:9200
```

2. 创建虚拟环境并安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

3. 配置阿里云百炼 API Key：

```powershell
$env:DASHSCOPE_API_KEY="你的百炼 API Key"
```

4. 启动后端：

```powershell
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

或者双击/运行：

```powershell
.\run.bat
```

5. 打开浏览器：

```text
http://127.0.0.1:8000
```

## 配置

可通过环境变量覆盖默认配置：

```powershell
$env:ES_URL="http://localhost:9200"
$env:ES_INDEX="enterprise_rag_chunks"
$env:EMBEDDING_MODEL_NAME="text-embedding-v4"
$env:EMBEDDING_DIM="512"
$env:LLM_MODEL="qwen-turbo"
```

默认使用百炼 `text-embedding-v4` 并指定 512 维，和 Elasticsearch `dense_vector` 的 `dims=512` 保持一致。不要再下载 `BAAI/bge-small-zh-v1.5`。

## 评测集格式

编辑 `data/eval_questions.json`：

```json
[
  {
    "question": "报销流程是什么？",
    "doc_id": "上传后文档列表里的 doc_id"
  }
]
```

前端点击“运行评测”即可计算 `recall@1`、`recall@3`、`recall@5`。

## 面试讲法

入库阶段：使用 LangChain Loader 解析文档，再用 RecursiveCharacterTextSplitter 做父子 chunk 切分。父 chunk 保存完整上下文，子 chunk 更短、更适合检索。每个子 chunk 调用百炼 `text-embedding-v4` 生成 embedding 后，与文本和元数据一起写入 Elasticsearch。

检索阶段：用户问题先生成 embedding，然后在 ES 中分别做 BM25 关键词召回和 dense_vector KNN 语义召回。

排序阶段：后端合并两路结果，对 BM25 和 KNN 分数归一化，再按权重融合，得到最终 TopK。命中子 chunk 后，继续查父 chunk 和邻近 child chunk，补全上下文。

生成阶段：使用 LangChain PromptTemplate 拼接知识库上下文，通过百炼 OpenAI 兼容接口调用 Qwen 模型，并返回引用来源、检索分数和日志。

## 尚未实现

- 登录注册和多租户
- 外部 rerank 模型
- 流式输出
- Word / Excel / PPT / OCR 解析
- 异步任务队列
- 索引版本管理
