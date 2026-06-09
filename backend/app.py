import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import BASE_DIR, ES_INDEX, ES_URL, UPLOAD_DIR
from backend.document_service import DocumentService
from backend.eval_service import EvalService
from backend.ingest_service import IngestService
from backend.monitor import read_logs
from backend.qa_service import QAService
from backend.schemas import AskRequest, DeleteDocumentRequest


app = FastAPI(title="Enterprise RAG QA", version="1.0.0")

# 允许前端页面直接调用后端接口，方便本地联调。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = BASE_DIR / "frontend"
if FRONTEND_DIR.exists():
    # 把 frontend 目录挂到 /static，浏览器可以访问 app.js、style.css。
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/app.js")
def app_js():
    return FileResponse(FRONTEND_DIR / "app.js", media_type="application/javascript")


@app.get("/style.css")
def style_css():
    return FileResponse(FRONTEND_DIR / "style.css", media_type="text/css")


@app.get("/api/health")
def health():
    from backend.es_store import ESStore

    # 健康检查：确认后端能连上 Elasticsearch。
    es_ok = ESStore().ping()
    return {"status": "ok" if es_ok else "degraded", "elasticsearch": es_ok, "es_url": ES_URL, "index": ES_INDEX}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):#UploadFile是fastapi带的类型 有文件name 文件内容和后缀  = File(...)意思这是必穿字段 不然报错 告诉后端从html表单的文件那里取
    # file: UploadFile = File(...) 表示从 multipart/form-data 表单里接收一个上传文件。
    # suffix 只取文件扩展名并转成小写，用来限制当前项目支持的文档类型。
    suffix = Path(file.filename or "").suffix.lower()#Path是文件类型 Path()可能是相对路径也可能是绝对路径 没传文件file.filename 是 None 设置""保证不报错 Path("")返回一个空文件类型
                                                    #suffix取后缀 lower()小写
    if suffix not in {".txt", ".md", ".pdf"}:
        raise HTTPException(status_code=400, detail="仅支持 .txt、.md、.pdf 文件")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)#mkdir创建路径文件夹 parents=True 路径的父路径中有不存在的文件夹 也给创建了 exist_ok=True路径所在文件夹已经存在不报错
    # Path(...).name 只保留文件名，避免用户传入 ../a.txt 这类路径穿越内容。
    # 如果直接按原始文件名保存，同名文件会覆盖前一个上传文件。
    # 这里用 UUID 拼到保存文件名前面，避免同名文件覆盖；原始文件名仍然传给入库逻辑展示。
    original_name = Path(file.filename or "upload").name#这里对name又转化成PATH防止用户 以文件路径命名 出现错误  如果没有名字 以upload命名
    target = UPLOAD_DIR / f"{uuid.uuid4().hex}_{original_name}"#如果传入了多个没名字的文件或者名字相同的文件那就 覆盖了 所以 没传名字的文件明前 加uuid 防止被覆盖
    target.write_bytes(await file.read())#file.read()读出来就是二进制 write_bytes把二进制内容存进文件 他只接收二进制

    try:
        # 真正的解析、切分、向量化、写入 ES 都交给 IngestService。
        data = IngestService().ingest(target, original_name)
        return {"message": data.get("message") or "文档入库成功", "data": data}#data只有已经入过库之后 才有message这个key
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/ask")
def ask(payload: AskRequest):
    try:
        # 问答入口：先检索知识库，再调用大模型生成答案。
        return QAService().ask(payload.question)#返回{"answer": answer, "references": references}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/documents")#查已经存入的文件
def list_documents():
    try:
        # 文档列表来自 ES 里的 chunk 元数据聚合。
        return {"data": DocumentService().list_documents()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/api/documents")#前端传doc_id
def delete_document(payload: DeleteDocumentRequest):
    try:
        # 按 doc_id 删除该文档对应的所有 parent/child chunk。
        deleted = DocumentService().delete_document(payload.doc_id)
        return {"message": "删除成功", "deleted": deleted}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/documents/deduplicate")
def deduplicate_documents():
    try:
        # 对历史已入库的重复文档做清理。
        return DocumentService().deduplicate_documents()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

#日志监控
@app.get("/api/monitor/logs")
def monitor_logs(limit: int = 20):
    # 返回最近的问答日志，前端用它展示耗时和历史问题。
    return {"data": read_logs(limit)}


@app.get("/api/eval/recall")
def eval_recall():#  我们做的粗粒度检测 只要命中文档 就算正确
    try:
        # 基于 data/eval_questions.json 做 Recall@K 检索评测。
        return EvalService().recall_at_k()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True)