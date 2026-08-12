/* Big Screen Display */

let sessionId = null;
let ws = null;
let timerInterval = null;
let lastTimerDuration = 30;
let qrRendered = false;
let leaderboardRevealTimer = null;

const LETTERS = ['A','B','C','D','E','F','G','H'];
const COLORS = ['#3b82f6','#ef4444','#22c55e','#f97316','#8b5cf6','#06b6d4','#ec4899','#eab308'];

// ── URL params ─────────────────────────────────────────────────────────────

const params = new URLSearchParams(location.search);
const urlSession = params.get('session');
if (urlSession) {
  sessionId = urlSession;
  enterDisplay();
}

// ── Screen helpers ─────────────────────────────────────────────────────────

function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}

function showState(id) {
  document.querySelectorAll('.display-state').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}

// ── Connect ───────────────────────────────────────────────────────────────────

document.getElementById('btn-connect-display').addEventListener('click', () => {
  const id = document.getElementById('display-session-id').value.trim();
  if (!id) return;
  sessionId = id;
  enterDisplay();
});

function enterDisplay() {
  showScreen('screen-display');
  connectWS();
}

// ── WebSocket ─────────────────────────────────────────────────────────────────

function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws/${sessionId}`);
  ws.onmessage = e => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'state') handleState(msg);
  };
  ws.onclose = () => setTimeout(connectWS, 2000);
  setInterval(() => { if (ws.readyState === 1) ws.send('ping'); }, 30000);
}

// ── HUD ────────────────────────────────────────────────────────────────────────

function updateHUD(state) {
  document.getElementById('hud-title').textContent = state.quiz_title;
  document.getElementById('hud-round').textContent = state.round_name;
  document.getElementById('hud-teams').textContent = `${state.total_teams} teams`;
}

// ── State Handler ──────────────────────────────────────────────────────────────

function handleState(state) {
  updateHUD(state);

  switch(state.state) {
    case 'lobby':         renderLobby(state); break;
    case 'round_intro':   renderRoundIntro(state); break;
    case 'question':      renderQuestion(state); break;
    case 'answer_reveal': renderReveal(state); break;
    case 'leaderboard':   renderLeaderboard(state); break;
    case 'ended':         renderEnded(state); break;
  }
}

// ── Lobby ──────────────────────────────────────────────────────────────────────

function renderLobby(state) {
  showState('display-lobby');
  document.getElementById('display-quiz-title-lobby').textContent = state.quiz_title;

  // QR code (only render once)
  if (!qrRendered) {
    fetch('/api/config').then(r => r.json()).then(cfg => {
      const joinUrl = `${cfg.player_url}?session=${sessionId}`;
      document.getElementById('display-join-url').textContent = joinUrl.replace(/^https?:\/\//, '');
      new QRCode(document.getElementById('display-qr'), {
        text: joinUrl,
        width: 200,
        height: 200,
        colorDark: '#0f172a',
        colorLight: '#ffffff',
        correctLevel: QRCode.CorrectLevel.M,
      });
    }).catch(() => {
      const joinUrl = `${location.protocol}//${location.host}/play?session=${sessionId}`;
      document.getElementById('display-join-url').textContent = joinUrl.replace(/^https?:\/\//, '');
      new QRCode(document.getElementById('display-qr'), {
        text: joinUrl, width: 200, height: 200,
        colorDark: '#0f172a', colorLight: '#ffffff',
        correctLevel: QRCode.CorrectLevel.M,
      });
    });
    qrRendered = true;
  }

  // Team grid
  const grid = document.getElementById('display-team-grid');
  const existing = new Set(Array.from(grid.children).map(c => c.dataset.teamId));
  (state.teams || []).forEach(t => {
    if (!existing.has(t.id)) {
      const chip = document.createElement('div');
      chip.className = 'team-chip';
      chip.dataset.teamId = t.id;
      chip.textContent = t.name;
      grid.appendChild(chip);
    }
  });
}

// ── Round Intro ────────────────────────────────────────────────────────────────

function renderRoundIntro(state) {
  showState('display-round-intro');
  document.getElementById('display-quiz-title-intro').textContent = state.quiz_title;
  document.getElementById('display-round-number').textContent = `Round ${state.round_index + 1} of ${state.total_rounds}`;
  document.getElementById('display-round-title').textContent = state.round_name;
  
  const instEl = document.getElementById('display-round-instructions');
  if (state.round_instructions) {
    instEl.textContent = state.round_instructions;
    instEl.classList.remove('hidden');
  } else {
    instEl.classList.add('hidden');
  }
  
  const imgWrap = document.getElementById('display-round-intro-image');
  const imgEl = document.getElementById('display-round-img');
  if (state.round_image) {
    imgEl.src = state.round_image;
    imgWrap.classList.remove('hidden');
  } else {
    imgWrap.classList.add('hidden');
  }
}

// ── Question ───────────────────────────────────────────────────────────────────

function renderQuestion(state) {
  showState('display-question');
  const q = state.question;
  if (!q) return;

  document.getElementById('display-round-name').textContent = state.round_name;
  document.getElementById('display-q-num').textContent = `Q${state.question_index + 1}`;

  // Question text with optional note for first_letter questions
  const questionText = q.text + (q.note ? ` (${q.note})` : '');
  document.getElementById('display-question-text').textContent = questionText;

  // Image
  const imgWrap = document.getElementById('display-question-image');
  if (q.image) {
    document.getElementById('display-question-img').src = q.image;
    imgWrap.classList.remove('hidden');
  } else {
    imgWrap.classList.add('hidden');
  }

  // Options (multiple choice / picture / select_many)
  const optEl = document.getElementById('display-options');
  if (['multiple_choice','picture','select_many'].includes(q.type)) {
    optEl.innerHTML = (q.options || []).map((opt, i) => `
      <div class="display-option" data-index="${i}" style="border-left: 4px solid ${COLORS[i % COLORS.length]}">
        <div class="display-option-letter" style="background:${COLORS[i % COLORS.length]}">${LETTERS[i]}</div>
        <span>${escHtml(opt)}</span>
      </div>
    `).join('');
    optEl.style.display = 'grid';
  } else if (q.type === 'order') {
    optEl.innerHTML = (q.items || []).map((item, i) => `
      <div class="display-option">
        <div class="display-option-letter">${i+1}</div>
        <span>${escHtml(item)}</span>
      </div>
    `).join('');
    optEl.style.display = 'grid';
    optEl.style.gridTemplateColumns = '1fr';
  } else if (q.type === 'numeric') {
    optEl.innerHTML = `<div class="display-option" style="grid-column:1/-1;justify-content:center;font-size:1.5rem">
      Enter a number
    </div>`;
    optEl.style.display = 'grid';
    optEl.style.gridTemplateColumns = '1fr';
  } else if (q.type === 'first_letter') {
    const letters = q.letters || "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split('');
    optEl.innerHTML = `<div class="display-letter-grid" style="grid-column:1/-1;display:flex;flex-wrap:wrap;gap:12px;justify-content:center;padding:16px">
      ${letters.map(l => `<div class="display-letter-box">${l}</div>`).join('')}
    </div>`;
    optEl.style.display = 'grid';
    optEl.style.gridTemplateColumns = '1fr';
  } else {
    optEl.style.display = 'none';
  }

  // Timer
  lastTimerDuration = q.time || 30;
  startTimerDisplay(state.timer_ends_at, q.time || 30);

  // Answer progress bar
  updateAnswerBar(state.answered_count, state.total_teams);
}

function startTimerDisplay(timerEndsAt, duration) {
  clearInterval(timerInterval);
  const numEl = document.getElementById('display-timer');
  const fillEl = document.getElementById('timer-ring-fill');
  const circumference = 175.9;

  function tick() {
    if (!timerEndsAt) return;
    const secs = Math.max(0, (new Date(timerEndsAt) - Date.now()) / 1000);
    numEl.textContent = Math.ceil(secs);

    const pct = secs / duration;
    const offset = circumference * (1 - pct);
    fillEl.style.strokeDashoffset = offset;
    fillEl.style.stroke = secs <= 5 ? '#ef4444' : secs <= 10 ? '#eab308' : '#60a5fa';

    if (secs <= 0) clearInterval(timerInterval);
  }
  tick();
  timerInterval = setInterval(tick, 250);
}

function updateAnswerBar(answered, total) {
  const pct = total > 0 ? (answered / total) * 100 : 0;
  document.getElementById('display-answer-bar').style.width = pct + '%';
  const label = document.getElementById('display-answer-count');
  label.textContent = total > 0 ? `${answered} / ${total} answered` : '';
}

// ── Reveal ─────────────────────────────────────────────────────────────────────

function renderReveal(state) {
  clearInterval(timerInterval);
  showState('display-reveal');

  const q = state.question_with_answers;
  if (!q) return;

  document.getElementById('display-reveal-question').textContent = q.text;

  // Show correct answer
  const answerEl = document.getElementById('display-reveal-answer');
  const optionsEl = document.getElementById('display-reveal-options');
  const infoEl = document.getElementById('display-reveal-info');

  if (q.type === 'multiple_choice' || q.type === 'picture') {
    answerEl.textContent = `${LETTERS[q.correct]}. ${(q.options || [])[q.correct] || ''}`;
    optionsEl.innerHTML = '';
  } else if (q.type === 'first_letter') {
    const letters = q.letters || "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split('');
    const correctLetter = q.answer;
    optionsEl.innerHTML = `<div class="reveal-letter-grid">
      ${letters.map(l => `<div class="reveal-letter-box ${l === correctLetter ? 'correct' : ''}">${l}</div>`).join('')}
    </div>`;
    answerEl.textContent = '';
  } else if (q.type === 'select_many') {
    answerEl.textContent = '';
    optionsEl.innerHTML = (q.options || []).map((opt, i) => {
      const isCorrect = (q.correct || []).includes(i);
      return `
        <div class="display-option ${isCorrect ? 'correct' : 'wrong'}">
          <div class="display-option-letter">${LETTERS[i]}</div>
          <span>${escHtml(opt)}</span>
          ${isCorrect ? '<span style="margin-left:auto">&#10003;</span>' : ''}
        </div>
      `;
    }).join('');
  } else if (q.type === 'order') {
    answerEl.textContent = (q.items || []).join(' → ');
    optionsEl.innerHTML = '';
  } else if (q.type === 'numeric') {
    answerEl.textContent = String(q.answer);
    optionsEl.innerHTML = '';
  } else {
    answerEl.textContent = '';
    optionsEl.innerHTML = '';
  }

  // Show answer_info if present
  if (q.answer_info) {
    infoEl.textContent = q.answer_info;
    infoEl.classList.remove('hidden');
  } else {
    infoEl.textContent = '';
    infoEl.classList.add('hidden');
  }
}

// ── Leaderboard ────────────────────────────────────────────────────────────────

function renderLeaderboard(state) {
  showState('display-leaderboard');
  if (leaderboardRevealTimer) clearTimeout(leaderboardRevealTimer);

  const lb = state.leaderboard || [];
  const listEl = document.getElementById('display-lb-list');
  listEl.innerHTML = lb.map((entry, i) => `
    <div class="display-lb-entry" data-rank="${lb.length - i}">
      <div class="lb-rank-big">${i+1}</div>
      <div class="lb-name-big">${escHtml(entry.name)}</div>
      <div class="lb-score-big">${entry.total_score}</div>
    </div>
  `).join('');

  // Dramatic reveal: bottom to top
  const entries = Array.from(listEl.querySelectorAll('.display-lb-entry')).reverse();
  entries.forEach((el, i) => {
    leaderboardRevealTimer = setTimeout(() => el.classList.add('visible'), i * 350 + 300);
  });
}

// ── Ended ──────────────────────────────────────────────────────────────────────

function renderEnded(state) {
  showState('display-ended');

  const lb = state.leaderboard || [];
  const listEl = document.getElementById('display-final-lb');
  listEl.innerHTML = lb.map((entry, i) => `
    <div class="display-lb-entry" data-rank="${lb.length - i}">
      <div class="lb-rank-big">${i+1}</div>
      <div class="lb-name-big">${escHtml(entry.name)}</div>
      <div class="lb-score-big">${entry.total_score}</div>
    </div>
  `).join('');

  // Reveal
  const entries = Array.from(listEl.querySelectorAll('.display-lb-entry')).reverse();
  entries.forEach((el, i) => {
    setTimeout(() => el.classList.add('visible'), i * 400 + 500);
  });

  launchFireworks();
}

function launchFireworks() {
  const bg = document.getElementById('fireworks-bg');
  const colors = ['#fbbf24','#60a5fa','#34d399','#f87171','#a78bfa','#fb923c'];
  let count = 0;

  function burst() {
    if (count++ > 40) return;
    const x = Math.random() * 100;
    const y = Math.random() * 60;
    for (let i = 0; i < 12; i++) {
      const spark = document.createElement('div');
      spark.className = 'spark';
      spark.style.cssText = `
        left:${x}%; top:${y}%;
        background:${colors[Math.floor(Math.random()*colors.length)]};
        --tx:${(Math.random()-0.5)*200}px;
        --ty:${(Math.random()-0.5)*200}px;
        animation-delay:${Math.random()*0.3}s;
      `;
      bg.appendChild(spark);
      setTimeout(() => spark.remove(), 1500);
    }
    setTimeout(burst, 400);
  }
  burst();
}

// ── Utils ──────────────────────────────────────────────────────────────────────

function escHtml(str) {
  return String(str ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
