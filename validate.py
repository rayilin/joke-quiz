# -*- coding: utf-8 -*-
"""驗證 questions.json 與 answer_key.json 的一致性"""
import json
import collections
from pathlib import Path

root = Path(__file__).resolve().parent
q = json.loads((root / "data" / "questions.json").read_text(encoding="utf-8"))
a = json.loads((root / "data" / "answer_key.json").read_text(encoding="utf-8"))
qs, ans = q["questions"], a["answers"]

qids = [x["id"] for x in qs]
aids = [x["id"] for x in ans]
assert qids == list(range(1, len(qs) + 1)), "questions ids 不連續"
assert aids == list(range(1, len(ans) + 1)), "answer ids 不連續"
assert len(qs) == len(ans), f"題數 {len(qs)} 與答案數 {len(ans)} 不相同"

dist = collections.Counter(x["answer"] for x in ans)
errors = []
for x in ans:
    qq = qs[x["id"] - 1]
    opts = qq["options"]
    if len(opts) != 4:
        errors.append(f"Q{x['id']}: 選項數 != 4")
    idx = "ABCD".find(x["answer"])
    if idx < 0:
        errors.append(f"Q{x['id']}: answer 非法")
    elif opts[idx] != x["answer_text"]:
        errors.append(f"Q{x['id']}: answer_text 與 options[{x['answer']}] 不一致 → key={opts[idx]!r} / text={x['answer_text']!r}")

print("答案字母分布:", dict(sorted(dist.items())))
print("題數:", len(qids), "／答案數:", len(aids))
print("檢查結果:", "全部一致，無錯誤" if not errors else errors)
