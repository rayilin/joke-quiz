# -*- coding: utf-8 -*-
"""API 端點實測：health / quiz / submit（含對錯混合計分驗證）"""
import json
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
BANK_SIZE = len(json.loads((Path(__file__).resolve().parent / "data" / "questions.json").read_text(encoding="utf-8"))["questions"])


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as res:
        return json.loads(res.read().decode("utf-8"))


def post(path, payload):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read().decode("utf-8"))


h = get("/api/health")
print("== /api/health ==", h)
assert h["total_questions"] == BANK_SIZE
print(f"題庫總數 = {h['total_questions']}（與 questions.json 一致）✓｜分類數 = {h['categories']}")

quiz = get("/api/quiz?count=3")
print("== /api/quiz?count=3 == 取得", quiz["count"], "題")
assert quiz["count"] == 3
for q in quiz["questions"]:
    assert len(q["options"]) == 4
    assert "answer" not in q  # 不得洩漏答案
print("選項數=4 ✓｜回應不含答案欄位 ✓")

# 抓一題，故意：1 題答對、1 題答錯
answers_key = {a["id"]: a["answer"] for a in json.loads(
    open("data/answer_key.json", encoding="utf-8").read())["answers"]}
q0, q1 = quiz["questions"][0], quiz["questions"][1]
right = answers_key[q0["id"]]                       # 正解字母
wrong = next(l for l in "ABCD" if l != answers_key[q1["id"]])  # 故意答錯的字母
payload = {
    "answers": [
        {"id": q0["id"], "choice": right},          # 答對 → +1
        {"id": q1["id"], "choice": wrong},          # 答錯 → 0（不扣分）
    ]
}
sub = post("/api/submit", payload)
print("== /api/submit =", payload, "==>")
print("score =", sub["score"], "/ total =", sub["total"])
assert sub["score"] == 1 and sub["total"] == 2
assert sub["details"][0]["correct"] is True
assert sub["details"][1]["correct"] is False
assert len(sub["details"][1]["explanation"]) > 0
print("計分規則（對+1、錯0）✓｜解答與解析有回傳 ✓")

# 抽大題數（整個題庫）
big = get(f"/api/quiz?count={BANK_SIZE}")
assert big["count"] == BANK_SIZE
print(f"== /api/quiz?count={BANK_SIZE} == 整庫全抽 {big['count']} 題 ✓")
assert len({q['id'] for q in big['questions']}) == BANK_SIZE  # 全庫不重複

# 即時檢查單題：對與錯各測一次
c0 = q0["id"]
ans_right = post("/api/answer", {"id": c0, "choice": answers_key[c0]})
assert ans_right["correct"] is True and len(ans_right["explanation"]) > 0
wrong_letter = next(l for l in "ABCD" if l != answers_key[c0])
ans_wrong = post("/api/answer", {"id": c0, "choice": wrong_letter})
assert ans_wrong["correct"] is False and ans_wrong["answer"] == answers_key[c0]
print("== /api/answer == 答對→correct=true ✓｜答錯→correct=false＋正解 ✓")

print("\n全部 API 測試通過 ✅")
