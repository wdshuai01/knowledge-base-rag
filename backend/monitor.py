import json
from datetime import datetime

from backend.config import LOG_DIR


LOG_FILE = LOG_DIR / "qa_logs.jsonl"


def write_log(record: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"created_at": datetime.now().isoformat(timespec="seconds"), **record}
    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")#json.dumps把字典转成字符串


def read_logs(limit: int = 20) -> list[dict]:
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text(encoding="utf-8").splitlines()#每一次的信息 都是按行存的  所以这里按行分
    items = [json.loads(line) for line in lines if line.strip()]#json.loads把json字符串 转成字典
    return list(reversed(items[-limit:]))#因为最新的日志在最下面一行 所以 我们用reversed（）讲列表逆序一下
                                            #items[-limit:]  -代表从倒数第limit开始数到：最后一个

