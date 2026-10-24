# -*- coding: utf-8 -*-
"""笑話問答後端服務：FastAPI + SQLite

題庫來源：data/questions.json（題目＋四選項）
標準答案：data/answer_key.json（答案字母、解析、出處）
第一次啟動時自動建立 backend/quiz.db 並灌入題庫。

API：
  GET  /api/health        健康檢查＋題庫統計
  GET  /api/quiz?count=N  抽 N 題（不含答案）
  POST /api/submit        交卷計分（答對 +1，答錯不扣分）
"""
from contextlib import asynccontextmanager
import json
import sqlite3
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent          # joke-quiz/backend
PROJECT_DIR = BASE_DIR.parent                        # joke-quiz/
DATA_DIR = PROJECT_DIR / "data"
FRONTEND_DIR = PROJECT_DIR / "frontend"
DB_PATH = BASE_DIR / "quiz.db"

LETTERS = "ABCD"


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """建表；若資料庫為空，則從 data/ 的兩個 JSON 灌入題庫。"""
    conn = db_connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS questions (
                id          INTEGER PRIMARY KEY,
                category    TEXT NOT NULL,
                question    TEXT NOT NULL,
                option_a    TEXT NOT NULL,
                option_b    TEXT NOT NULL,
                option_c    TEXT NOT NULL,
                option_d    TEXT NOT NULL,
                answer      TEXT NOT NULL CHECK (answer IN ('A','B','C','D')),
                answer_text TEXT NOT NULL,
                explanation TEXT NOT NULL,
                source      TEXT NOT NULL
            )
            """
        )
        count = conn.execute("SELECT COUNT(*) AS n FROM questions").fetchone()["n"]
        if count == 0:
            questions = json.loads(
                (DATA_DIR / "questions.json").read_text(encoding="utf-8")
            )["questions"]
            answers = {
                a["id"]: a
                for a in json.loads(
                    (DATA_DIR / "answer_key.json").read_text(encoding="utf-8")
                )["answers"]
            }
            for q in questions:
                key = answers[q["id"]]
                opts = q["options"]
                conn.execute(
                    """INSERT INTO questions
                       (id, category, question, option_a, option_b, option_c, option_d,
                        answer, answer_text, explanation, source)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        q["id"], q["category"], q["question"],
                        opts[0], opts[1], opts[2], opts[3],
                        key["answer"], key["answer_text"],
                        key["explanation"], key["source"],
                    ),
                )
            conn.commit()
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="笑話問答 API", version="1.0", lifespan=lifespan)


class Answer(BaseModel):
    id: int
    choice: str  # "A"～"D"；空字串代表此題沒作答


class AnswerCheck(BaseModel):
    id: int
    choice: str  # "A"～"D"


class SubmitPayload(BaseModel):
    answers: list[Answer]


@app.get("/api/health")
def health():
    conn = db_connect()
    try:
        total = conn.execute("SELECT COUNT(*) AS n FROM questions").fetchone()["n"]
    finally:
        conn.close()
    categories = 0
    if total:
        conn = db_connect()
        try:
            categories = conn.execute(
                "SELECT COUNT(DISTINCT category) AS n FROM questions"
            ).fetchone()["n"]
        finally:
            conn.close()
    return {"status": "ok", "total_questions": total, "categories": categories}


@app.get("/api/quiz")
def get_quiz(count: int = Query(10, ge=1, le=250, description="抽題數（1～題庫上限）")):
    """抽出 count 題（隨機、不重複），不回傳答案。"""
    conn = db_connect()
    try:
        total = conn.execute("SELECT COUNT(*) AS n FROM questions").fetchone()["n"]
        if total == 0:
            raise HTTPException(status_code=503, detail="題庫尚未載入，請重新啟動後端")
        n = min(count, total)
        rows = conn.execute(
            """SELECT id, category, question, option_a, option_b, option_c, option_d
               FROM questions ORDER BY RANDOM() LIMIT ?""",
            (n,),
        ).fetchall()
    finally:
        conn.close()
    return {
        "round_id": str(uuid.uuid4()),
        "count": n,
        "total_bank": total,
        "questions": [
            {
                "id": r["id"],
                "category": r["category"],
                "question": r["question"],
                "options": [r["option_a"], r["option_b"], r["option_c"], r["option_d"]],
            }
            for r in rows
        ],
    }


@app.post("/api/answer")
def check_answer(item: AnswerCheck):
    """即時檢查單題：回傳對錯、正解與解析（供前端立即回饋）。"""
    conn = db_connect()
    try:
        row = conn.execute(
            """SELECT id, answer, answer_text, explanation, source
               FROM questions WHERE id = ?""",
            (item.id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail=f"題號 {item.id} 不存在")
    choice = (item.choice or "").strip().upper()
    if choice not in LETTERS:
        raise HTTPException(status_code=422, detail="choice 必須是 A、B、C 或 D")
    return {
        "id": row["id"],
        "correct": choice == row["answer"],
        "answer": row["answer"],
        "answer_text": row["answer_text"],
        "explanation": row["explanation"],
        "source": row["source"],
    }


@app.post("/api/submit")
def submit(payload: SubmitPayload):
    """計分：答對 +1，答錯或沒答 0 分，不扣分。"""
    conn = db_connect()
    score = 0
    details = []
    try:
        for item in payload.answers:
            row = conn.execute(
                """SELECT id, question, option_a, option_b, option_c, option_d,
                          answer, answer_text, explanation, source
                   FROM questions WHERE id = ?""",
                (item.id,),
            ).fetchone()
            if row is None:
                continue  # 不存在的題號直接略過
            choice = (item.choice or "").strip().upper()
            options = [row["option_a"], row["option_b"], row["option_c"], row["option_d"]]
            chosen_text = None
            if choice in LETTERS:
                chosen_text = options[LETTERS.index(choice)]
            is_correct = choice == row["answer"]
            if is_correct:
                score += 1
            details.append(
                {
                    "id": row["id"],
                    "question": row["question"],
                    "chosen": choice if choice in LETTERS else None,
                    "chosen_text": chosen_text,
                    "correct": is_correct,
                    "answer": row["answer"],
                    "answer_text": row["answer_text"],
                    "explanation": row["explanation"],
                    "source": row["source"],
                }
            )
    finally:
        conn.close()
    return {
        "score": score,
        "total": len(details),
        "message": "答對 +1 分，答錯不扣分",
        "details": details,
    }


# 靜態前端（放到最後一個路由註冊，避免蓋掉 /api/*）
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
