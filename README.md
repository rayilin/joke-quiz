# 2026 笑話問答場（joke-quiz）

從 NotebookLM「2026笑話大全：百則超好笑短笑話精選」整理出 40 題四選一問答，
另於 2026-10-24 自網路蒐集（冷笑話罐頭／A Day Magazine／腦筋急轉彎彙整等，
出處記錄在 `answer_key.json` 的 source 欄）改編新增 182 題，
合計 **222 題**。以 FastAPI + SQLite 當後端資料庫、純 HTML/JS 當前端。

題庫擴充的蒐集紀錄腳本：`data/expand_bank.py`（含所有新題原文與出處）。

**上線資訊**：GitHub repo <https://github.com/rayilin/joke-quiz>｜
Render 網址（部署後見下方「部署到 Render」段落）。

## 功能

- 選擇作答題數：10 / 20 / 30 題（隨機抽題、不重複）
- **語音唸題目**：出新題自動朗讀（zh-TW 繁中語音），可手動「🔊 唸題目」重播、可關閉自動朗讀；答完後朗讀「答對了！加一分／答錯了」判決
- **聽完題目才能作答**：朗讀中選項鎖定、顯示「🎧 請先聽完題目朗讀」提示；唸完自動解鎖，也可按「⏭ 跳過朗讀」立即作答（需要等嗎？沒有任何陷阱——失敗時必解鎖）
- **作答後立即揭曉對錯**：正解變綠、錯選變紅，同時顯示解析
- 即時累計分數：答對 +1 分、答錯不扣分（0 分）
- 答過的題目鎖定不可改答
- 最後交卷統一結算：總分＋逐題檢討（正解、解析、出處）

## 檔案結構

```
joke-quiz/
├── data/
│   ├── questions.json   # 題目檔：222 題＋四選項（不含答案）
│   └── answer_key.json  # 標準答案檔：答案字母、解析、出處
│   └── expand_bank.py   # 網路蒐集 182 題的合併腳本（蒐集紀錄）
├── backend/
│   ├── main.py          # FastAPI 應用（自動建 quiz.db 並灌題）
│   └── quiz.db          # SQLite 資料庫（第一次啟動自動產生，不入 git）
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── requirements.txt
└── validate.py          # 驗證題目檔與答案檔一致性
```

## 啟動方式（本機）

```powershell
cd joke-quiz
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --port 8000
```

打開瀏覽器前往 <http://localhost:8000> 即可遊玩。
API 文件（Swagger）在 <http://localhost:8000/docs>。

## 部署到 Render（免費層）

Repo 用 Blueprint 部署（`render.yaml` 已附）：
1. Render Dashboard → **New +** → **Blueprint** → 選 `rayilin/joke-quiz`
2. Render 會讀 `render.yaml`：build `pip install -r requirements.txt`、
   start `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`、健康檢查 `/api/health`
3. 送上線後與 <https://joke-quiz.onrender.com> 一樣的網址即可玩
   （免費層閒置 15 分鐘會休眠，冷啟動約需 30～60 秒）

線上版後端只有一顆 SQLite，一般是唯讀使用（計分即時計算，不寫入資料庫），
休眠喚醒後會自動從 JSON 重新灌題，無需人工維護。

## API

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/health` | 健康檢查＋題庫統計 |
| GET | `/api/quiz?count=N` | 隨機抽 N 題（1～題庫上限 250，不含答案） |
| POST | `/api/answer` | 即時檢查單題：`{"id":1,"choice":"B"}` → 對錯、正解、解析 |
| POST | `/api/submit` | 交卷計分：`{"answers":[{"id":1,"choice":"B"}, ...]}`，答對 +1、答錯 0 |
| GET | `/` | 前端頁面 |

## 資料分離原則

`questions.json` 只有題目與選項；正解（字母＋文字＋解析＋出處）獨立在
`answer_key.json`，只灌進後端資料庫。GET /api/quiz 永遠不回傳答案，
計分全程由後端進行，避免在瀏覽器上偷看解答。

修改題目後要重建資料庫：刪除 `backend/quiz.db` 再重啟後端即可。
