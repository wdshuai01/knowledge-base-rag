@echo off
setlocal
if not exist .venv (
  echo Virtual environment not found. Run: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  exit /b 1
)
call .venv\Scripts\activate
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000

