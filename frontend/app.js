/* 2026 笑話問答場 —— 前端邏輯
   流程：首頁選題數 → 抽題作答，每題作答後「立即揭曉對錯＋解析」並即時計分
   （答對 +1、答錯 0 分不扣）→ 最後交卷，統一結算總分＋逐題檢討 */
"use strict";

const LETTERS = ["A", "B", "C", "D"];

const state = {
  round: [],        // 本輪題目 [{id, category, question, options[]}]
  picked: {},       // id -> "A"~"D"（作答當下就鎖定）
  revealed: {},     // id -> {correct, answer, answer_text, explanation, source}
  liveScore: 0,     // 即時累計分數
  index: 0,
  submitted: false,
  lockWaiting: false, // 「聽完題目才可作答」的鎖定狀態
  ttsReadIds: new Set(), // 已自動朗讀過的題號（每題只自動唸一次）
};

const $ = (sel) => document.querySelector(sel);
const screens = { home: $("#home"), quiz: $("#quiz"), result: $("#result") };

/* ---------- 語音朗讀（Web Speech API，zh-TW） ---------- */
const tts = {
  auto: localStorage.getItem("jokeQuiz.ttsAuto") !== "0",
  ready: "speechSynthesis" in window,
};

/* 「聽完題目才能作答」狀態：true ＝ 朗讀進行中，選項鎖住 */
function setAnswerLock(locked) {
  state.lockWaiting = locked;
  if (locked) {
    $("#answer-hint").classList.remove("hidden");
    $("#skip-tts").classList.remove("hidden");
  } else {
    $("#answer-hint").classList.add("hidden");
    $("#skip-tts").classList.add("hidden");
  }
  renderQuestion(); // 依鎖定狀態更新選項
}

function unlockOptions() {
  if (state.lockWaiting) setAnswerLock(false);
}

function pickTtsVoice() {
  const voices = speechSynthesis.getVoices() || [];
  return (
    voices.find((v) => /zh[-_]?tw|hant/i.test(v.lang)) ||       // 繁中優先
    voices.find((v) => /^zh/i.test(v.lang)) ||                   // 任何中文
    voices.find((v) => /^en/i.test(v.lang)) || null              // 兜底
  );
}

function speak(text, { onend } = {}) {
  if (!tts.ready || !text) {
    if (onend) onend();
    return;
  }
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "zh-TW";
  u.rate = 1.05;
  const voice = pickTtsVoice();
  if (voice) u.voice = voice;
  if (onend) {
    u.onend = onend;
    u.onerror = onend; // 朗讀失敗也要解鎖，不能把玩家卡死
  }
  speechSynthesis.speak(u);
}

function stopSpeak() {
  if (tts.ready && (speechSynthesis.speaking || speechSynthesis.pending)) {
    speechSynthesis.cancel();
  }
}

/* 出新題時（每題只一次）：鎖定作答 → 朗讀題目 → 唸完解鎖 */
function ttsAutoReadQuestion(q) {
  if (!tts.auto || state.ttsReadIds.has(q.id)) return;
  state.ttsReadIds.add(q.id);
  setAnswerLock(true);
  speak(q.question, { onend: unlockOptions });
}

function ttsSpeakVerdict(correct, score) {
  speak(correct ? `答對了！加一分，目前${score}分` : `答錯了，零分，目前的${score}分`);
}

function show(name) {
  Object.values(screens).forEach((el) => el.classList.remove("active"));
  screens[name].classList.add("active");
  window.scrollTo({ top: 0 });
}

/* ---------- 首頁 ---------- */
async function loadBankInfo() {
  try {
    const res = await fetch("/api/health");
    if (!res.ok) throw new Error("health " + res.status);
    const data = await res.json();
    $("#bank-count").textContent = data.total_questions;
  } catch {
    $("#home-error").textContent =
      "連不上後端（請確認 uvicorn 已啟動：python -m uvicorn backend.main:app --port 8000）";
  }
}

/* ---------- 開考 ---------- */
async function startRound(count) {
  $("#home-error").classList.add("hidden");
  try {
    const res = await fetch(`/api/quiz?count=${count}`);
    if (!res.ok) throw new Error("quiz " + res.status);
    const data = await res.json();
    state.round = data.questions;
    state.picked = {};
    state.revealed = {};
    state.liveScore = 0;
    state.index = 0;
    state.submitted = false;
    state.lockWaiting = false;
    state.ttsReadIds = new Set();
    show("quiz");
    renderQuestion();
  } catch (err) {
    $("#home-error").textContent =
      "取題失敗：" + err.message + "（後端沒開起來嗎？）";
    $("#home-error").classList.remove("hidden");
  }
}

/* ---------- 作答 ---------- */
function renderQuestion() {
  const q = state.round[state.index];
  const total = state.round.length;
  const rev = state.revealed[q.id];

  $("#progress-text").textContent = `第 ${state.index + 1} / ${total} 題`;
  $("#live-score").textContent =
    `已答 ${Object.keys(state.revealed).length}｜目前 ${state.liveScore} 分`;
  $("#progress-fill").style.width = `${((state.index + 1) / total) * 100}%`;

  $("#q-category").textContent = q.category;
  $("#q-id").textContent = `題號 ${q.id}`;
  $("#q-text").textContent = q.question;

  const box = $("#options");
  box.classList.toggle("locked", Boolean(rev));
  box.innerHTML = "";
  q.options.forEach((text, i) => {
    const letter = LETTERS[i];
    const btn = document.createElement("button");
    let cls = "option-btn";
    if (!rev && state.picked[q.id] === letter) cls += " selected";
    if (rev && letter === rev.answer) cls += " as-correct";
    if (rev && state.picked[q.id] === letter && !rev.correct) cls += " as-wrong";
    btn.className = cls;
    btn.disabled = Boolean(state.lockWaiting) && !rev; // 聽題中鎖住選項
    btn.innerHTML = `<span class="letter">${letter}</span><span>${text}</span>`;
    btn.addEventListener("click", () => pick(q.id, letter));
    box.appendChild(btn);
  });

  renderFeedback(rev);

  const isLast = state.index === total - 1;
  $("#next-btn").classList.toggle("hidden", isLast);
  $("#submit-btn").classList.toggle("hidden", !isLast);
  $("#next-btn").disabled = !rev;
  if (isLast) $("#submit-btn").disabled = !rev;

  if (!rev) ttsAutoReadQuestion(q); // 新題目自動朗讀
}

function renderFeedback(rev) {
  const fb = $("#feedback");
  if (!rev) {
    fb.classList.add("hidden");
    return;
  }
  fb.classList.remove("hidden");
  fb.className = "feedback " + (rev.correct ? "good" : "bad");
  const yourLetter = state.picked[rev.id];
  fb.innerHTML = `
    <div class="fb-head">${rev.correct ? "✓ 答對了！+1 分" : "✗ 答錯了，0 分不扣"}</div>
    <div class="fb-answer">正解：${rev.answer}）${rev.answer_text}</div>
    ${rev.correct ? "" : `<div class="fb-yours">你的答案：${yourLetter}）——</div>`}
    <div class="fb-explain">💡 ${rev.explanation}</div>
  `;
}

async function pick(qid, letter) {
  if (state.revealed[qid] || state.lockWaiting) return; // 已揭曉或還在聽題時不能作答
  try {
    const res = await fetch("/api/answer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: qid, choice: letter }),
    });
    if (!res.ok) throw new Error("answer " + res.status);
    const data = await res.json();
    state.picked[qid] = letter;
    state.revealed[qid] = data;
    if (data.correct) state.liveScore += 1;
    renderQuestion();
    ttsSpeakVerdict(data.correct, state.liveScore); // 朗讀對錯判決
  } catch (err) {
    alert("檢查答案失敗：" + err.message);
  }
}

$("#next-btn").addEventListener("click", () => {
  if (state.index < state.round.length - 1) { state.index += 1; renderQuestion(); }
});
$("#submit-btn").addEventListener("click", submitRound);
$("#quit-btn").addEventListener("click", () => { stopSpeak(); show("home"); });

/* 語音朗讀控制 */
$("#tts-btn").addEventListener("click", () => {
  const q = state.round[state.index];
  if (!q || state.revealed[q.id]) return;
  setAnswerLock(true);          // 手動重播音：同樣要聽完才能作答
  speak(q.question, { onend: unlockOptions });
});
$("#skip-tts").addEventListener("click", () => {
  stopSpeak();
  unlockOptions();
});
$("#tts-auto").checked = tts.auto;
$("#tts-auto").addEventListener("change", (e) => {
  tts.auto = e.target.checked;
  localStorage.setItem("jokeQuiz.ttsAuto", tts.auto ? "1" : "0");
  if (!tts.auto) {
    stopSpeak();
    unlockOptions();            // 關掉自動朗讀＝不需要等
  }
});

/* ---------- 交卷（統一結算） ---------- */
async function submitRound() {
  if (state.submitted) return;
  state.submitted = true;
  stopSpeak();
  const answers = state.round.map((q) => ({
    id: q.id,
    choice: state.picked[q.id] || "",
  }));
  try {
    const res = await fetch("/api/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers }),
    });
    if (!res.ok) throw new Error("submit " + res.status);
    const data = await res.json();
    renderResult(data);
  } catch (err) {
    alert("計分失敗：" + err.message);
    state.submitted = false;
  }
}

/* ---------- 結算 ---------- */
function renderResult(data) {
  const total = data.total;
  const score = data.score;
  const ratio = total ? score / total : 0;

  let emoji = "🫠", title = "笑話還需要修練", msg = "答錯不扣分，下次一定！";
  if (ratio >= 0.9)      { emoji = "🏆"; title = "笑話十段高手！"; msg = "全場最懂笑點的人就是你。"; }
  else if (ratio >= 0.7) { emoji = "😂"; title = "很有哏魂！"; msg = "大部分笑點都接得住，值得慶祝。"; }
  else if (ratio >= 0.4) { emoji = "🤔"; title = "一半一半，再接再厲"; msg = "有些冷笑話真的太冷，不怪你。"; }
  else                   { emoji = "🫠"; title = "笑點還需要修練"; msg = "答錯不扣分，把檢討看完就會變強！"; }

  $("#result-emoji").textContent = emoji;
  $("#result-title").textContent = title;
  $("#result-score").textContent = score;
  $("#result-total").textContent = total;
  $("#result-message").textContent = msg;

  const list = $("#review-list");
  list.innerHTML = "";
  data.details.forEach((d) => {
    const div = document.createElement("div");
    div.className = "review-item " + (d.correct ? "correct" : "wrong");
    div.innerHTML = `
      <div class="rv-head">
        <span class="rv-tag">${d.correct ? "✓ 答對" : "✗ 答錯"}</span>
        <span class="rv-source">題號 ${d.id}｜${d.source}</span>
      </div>
      <div class="rv-question">${d.question}</div>
      <div class="rv-line your-answer">你的答案：${d.chosen ? `${d.chosen}）${d.chosen_text}` : "沒作答"}</div>
      ${d.correct ? "" : `<div class="rv-line right-answer">正解：${d.answer}）${d.answer_text}</div>`}
      <div class="rv-explain">💡 ${d.explanation}</div>
    `;
    list.appendChild(div);
  });
  stopSpeak();
  show("result");
}

$("#restart-btn").addEventListener("click", () => {
  startRound(state.round.length);
});
$("#home-btn").addEventListener("click", () => {
  show("home");
  loadBankInfo();
});

/* ---------- 首頁按鈕 ---------- */
document.querySelectorAll(".round-btn").forEach((btn) => {
  btn.addEventListener("click", () => startRound(Number(btn.dataset.count)));
});

loadBankInfo();
