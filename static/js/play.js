/* Player Handset */

let sessionId = null;
let teamId = null;
let teamName = null;
let browserId = getBrowserId();
let ws = null;
let timerInterval = null;
let lastState = null;
let selectedOptions = new Set();
let orderItems = [];
let dragSrcEl = null;

const LETTERS = ['A','B','C','D','E','F','G','H'];

// ── Browser ID ─────────────────────────────────────────────────────────────

function getBrowserId() {
  let id = localStorage.getItem('qm_browser_id');
  if (!id) {
    id = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2);
    localStorage.setItem('qm_browser_id', id);
  }
  return id;
}

// ── URL params pre-fill ────────────────────────────────────────────────────

const params = new URLSearchParams(location.search);
const urlSession = params.get('session');
if (urlSession) {
  document.getElementById('join-session-id').value = urlSession;
  // Focus team name
  setTimeout(() => document.getElementById('join-team-name').focus(), 100);
}

// Try saved team from this session
const savedTeam = localStorage.getItem('qm_team_' + urlSession);
if (savedTeam) {
  try {
    const t = JSON.parse(savedTeam);
    teamId = t.id;
    teamName = t.name;
    sessionId = urlSession;
    // Skip join and connect directly
    document.getElementById('join-team-name').value = t.name;
  } catch(e) {}
}

// ── Screen helpers ─────────────────────────────────────────────────────────

function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}

// ── Join ────────────────────────────────────────────────────────────────────

document.getElementById('btn-join').addEventListener('click', joinGame);
document.getElementById('join-team-name').addEventListener('keydown', e => {
  if (e.key === 'Enter') joinGame();
});

async function joinGame() {
  const sid = document.getElementById('join-session-id').value.trim();
  const name = document.getElementById('join-team-name').value.trim();
  const errEl = document.getElementById('join-error');

  if (!sid) { showError('Enter a session ID'); return; }
  if (!name) { showError('Enter a team name'); return; }

  errEl.classList.add('hidden');
  document.getElementById('btn-join').disabled = true;

  try {
    const res = await fetch(`/api/sessions/${sid}/join`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({team_name: name, browser_id: browserId}),
    });

    if (!res.ok) {
      const err = await res.json();
      showError(err.detail || 'Failed to join');
      document.getElementById('btn-join').disabled = false;
      return;
    }

    const data = await res.json();
    sessionId = sid;
    teamId = data.team_id;
    teamName = data.team_name;

    localStorage.setItem('qm_team_' + sid, JSON.stringify({id: teamId, name: teamName}));

    enterWaiting();
    connectWS();
  } catch(e) {
    showError('Network error — is the server running?');
    document.getElementById('btn-join').disabled = false;
  }
}

function showError(msg) {
  const el = document.getElementById('join-error');
  el.textContent = msg;
  el.classList.remove('hidden');
}

// ── If already have team, reconnect ───────────────────────────────────────

if (teamId && sessionId) {
  enterWaiting();
  connectWS();
}

// ── Waiting screen ─────────────────────────────────────────────────────────

function enterWaiting() {
  showScreen('screen-waiting');
  document.getElementById('player-team-name').textContent = teamName || 'Your Team';
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

// ── State Handler ──────────────────────────────────────────────────────────────

function handleState(state) {
  lastState = state;

  switch(state.state) {
    case 'lobby':
      enterWaiting();
      document.getElementById('waiting-round-name').textContent = state.round_name || '';
      document.getElementById('waiting-team-count').textContent = state.total_teams;
      break;
    case 'question':
      renderQuestion(state);
      break;
    case 'answer_reveal':
      renderReveal(state);
      break;
    case 'leaderboard':
      renderLeaderboard(state);
      break;
    case 'ended':
      renderEnded(state);
      break;
  }
}

// ── Question ───────────────────────────────────────────────────────────────────

function renderQuestion(state) {
  const q = state.question;
  if (!q) return;

  // Reset state
  selectedOptions.clear();
  orderItems = [];

  // Check if already answered
  const alreadyAnswered = (state.answers || []).some(a => a.team_id === teamId);

  showScreen('screen-question');
  document.getElementById('play-round-label').textContent = state.round_name;
  document.getElementById('play-q-label').textContent = `Q${state.question_index + 1}`;
  document.getElementById('play-question-text').textContent = q.text;

  // Image
  const imgWrap = document.getElementById('play-question-image');
  if (q.image) {
    document.getElementById('play-question-img').src = q.image;
    imgWrap.classList.remove('hidden');
  } else {
    imgWrap.classList.add('hidden');
  }

  // Hide all input sections
  document.getElementById('play-options').classList.add('hidden');
  document.getElementById('play-select-many').classList.add('hidden');
  document.getElementById('play-order').classList.add('hidden');
  document.getElementById('play-numeric').classList.add('hidden');
  document.getElementById('play-first-letter').classList.add('hidden');
  document.getElementById('play-submitted').classList.add('hidden');

  if (alreadyAnswered) {
    document.getElementById('play-submitted').classList.remove('hidden');
  } else {
    renderQuestionInput(q);
  }

  // Timer
  startTimerDisplay(state.timer_ends_at, q.time || 30);
}

function renderQuestionInput(q) {
  if (q.type === 'multiple_choice' || q.type === 'picture') {
    const el = document.getElementById('play-options');
    el.innerHTML = (q.options || []).map((opt, i) => `
      <button class="play-option" data-index="${i}" onclick="selectOption(${i})">
        <div class="opt-letter">${LETTERS[i]}</div>
        <span>${escHtml(opt)}</span>
      </button>
    `).join('');
    el.classList.remove('hidden');

  } else if (q.type === 'select_many') {
    const el = document.getElementById('play-select-many-options');
    el.innerHTML = (q.options || []).map((opt, i) => `
      <button class="play-option" data-index="${i}" onclick="toggleOption(${i}, this)">
        <div class="opt-letter">${LETTERS[i]}</div>
        <span>${escHtml(opt)}</span>
      </button>
    `).join('');
    document.getElementById('play-select-many').classList.remove('hidden');

  } else if (q.type === 'order') {
    orderItems = (q.items || []).map((text, i) => ({text, originalIndex: i}));
    // Shuffle for player
    orderItems = shuffleArray([...orderItems]);
    renderOrderList();
    document.getElementById('play-order').classList.remove('hidden');

  } else if (q.type === 'numeric') {
    document.getElementById('play-numeric-input').value = '';
    document.getElementById('play-numeric').classList.remove('hidden');
    document.getElementById('play-numeric-input').focus();

  } else if (q.type === 'first_letter') {
    const letters = q.letters || "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split('');
    const gridEl = document.getElementById('letter-grid');
    gridEl.innerHTML = letters.map(l => `
      <button class="letter-btn" data-letter="${l}" onclick="selectLetter('${l}')">${l}</button>
    `).join('');
    document.getElementById('play-first-letter').classList.remove('hidden');
  }
}

function startTimerDisplay(timerEndsAt, duration) {
  clearInterval(timerInterval);
  const el = document.getElementById('play-timer');
  const valEl = document.getElementById('play-timer-value');

  function tick() {
    if (!timerEndsAt) return;
    const secs = Math.max(0, Math.round((new Date(timerEndsAt) - Date.now()) / 1000));
    valEl.textContent = secs;
    el.className = 'play-timer' + (secs <= 5 ? ' danger' : secs <= 10 ? ' warning' : '');
    if (secs <= 0) clearInterval(timerInterval);
  }
  tick();
  timerInterval = setInterval(tick, 500);
}

// ── Option selection ───────────────────────────────────────────────────────────

function selectOption(index) {
  submitAnswer([index]);
}

function toggleOption(index, btn) {
  if (selectedOptions.has(index)) {
    selectedOptions.delete(index);
    btn.classList.remove('selected');
  } else {
    selectedOptions.add(index);
    btn.classList.add('selected');
  }
}

document.getElementById('btn-submit-many').addEventListener('click', () => {
  if (selectedOptions.size === 0) return;
  submitAnswer([...selectedOptions]);
});

// ── Order drag-and-drop ────────────────────────────────────────────────────────

function renderOrderList() {
  const list = document.getElementById('play-order-list');
  list.innerHTML = orderItems.map((item, i) => `
    <div class="order-item" draggable="true" data-pos="${i}">
      <span class="drag-handle">&#8801;</span>
      <span class="order-item-text">${escHtml(item.text)}</span>
    </div>
  `).join('');

  list.querySelectorAll('.order-item').forEach(item => {
    item.addEventListener('dragstart', dragStart);
    item.addEventListener('dragover', dragOver);
    item.addEventListener('drop', dragDrop);
    item.addEventListener('dragend', dragEnd);
    // Touch support
    item.addEventListener('touchstart', touchStart, {passive:true});
    item.addEventListener('touchmove', touchMove, {passive:false});
    item.addEventListener('touchend', touchEnd);
  });
}

function dragStart(e) {
  dragSrcEl = this;
  this.classList.add('dragging');
  e.dataTransfer.effectAllowed = 'move';
}

function dragOver(e) {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  return false;
}

function dragDrop(e) {
  e.stopPropagation();
  if (dragSrcEl !== this) {
    const srcPos = parseInt(dragSrcEl.dataset.pos);
    const dstPos = parseInt(this.dataset.pos);
    const tmp = orderItems[srcPos];
    orderItems[srcPos] = orderItems[dstPos];
    orderItems[dstPos] = tmp;
    renderOrderList();
  }
  return false;
}

function dragEnd() {
  this.classList.remove('dragging');
}

// Touch drag
let touchDragEl = null, touchStartY = 0;
function touchStart(e) {
  touchDragEl = this;
  touchStartY = e.touches[0].clientY;
}
function touchMove(e) {
  e.preventDefault();
  if (!touchDragEl) return;
  const y = e.touches[0].clientY;
  const list = document.getElementById('play-order-list');
  const items = list.querySelectorAll('.order-item');
  items.forEach(item => {
    const rect = item.getBoundingClientRect();
    if (y >= rect.top && y <= rect.bottom && item !== touchDragEl) {
      const srcPos = parseInt(touchDragEl.dataset.pos);
      const dstPos = parseInt(item.dataset.pos);
      const tmp = orderItems[srcPos];
      orderItems[srcPos] = orderItems[dstPos];
      orderItems[dstPos] = tmp;
      renderOrderList();
    }
  });
}
function touchEnd() { touchDragEl = null; }

document.getElementById('btn-submit-order').addEventListener('click', () => {
  submitAnswer(orderItems.map(item => item.originalIndex));
});

// ── Numeric submit ─────────────────────────────────────────────────────────────

// ── First letter submit ───────────────────────────────────────────────────────

function selectLetter(letter) {
  submitAnswer([letter]);
}

document.getElementById('btn-submit-numeric').addEventListener('click', () => {
  const val = document.getElementById('play-numeric-input').value.trim();
  if (!val) return;
  submitAnswer([val]);
});

document.getElementById('play-numeric-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') document.getElementById('btn-submit-numeric').click();
});

// ── Submit Answer ──────────────────────────────────────────────────────────────

async function submitAnswer(answerData) {
  if (!teamId || !sessionId) return;

  // Show submitted immediately
  document.getElementById('play-options').classList.add('hidden');
  document.getElementById('play-select-many').classList.add('hidden');
  document.getElementById('play-order').classList.add('hidden');
  document.getElementById('play-numeric').classList.add('hidden');
  document.getElementById('play-first-letter').classList.add('hidden');
  document.getElementById('play-submitted').classList.remove('hidden');

  try {
    await fetch(`/api/sessions/${sessionId}/answer`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({team_id: teamId, answer_data: answerData}),
    });
  } catch(e) {
    console.error('Failed to submit answer', e);
  }
}

// ── Reveal ─────────────────────────────────────────────────────────────────────

function renderReveal(state) {
  clearInterval(timerInterval);
  showScreen('screen-reveal');

  const q = state.question_with_answers;
  if (!q) return;

  document.getElementById('reveal-question').textContent = q.text;

  // Show correct answer
  const answerEl = document.getElementById('reveal-answer-display');
  if (q.type === 'multiple_choice' || q.type === 'picture') {
    answerEl.textContent = `${LETTERS[q.correct]}. ${(q.options || [])[q.correct] || ''}`;
  } else if (q.type === 'select_many') {
    answerEl.textContent = (q.correct || []).map(i => `${LETTERS[i]}. ${(q.options || [])[i] || ''}`).join(', ');
  } else if (q.type === 'order') {
    answerEl.textContent = (q.items || []).join(' → ');
  } else if (q.type === 'numeric') {
    answerEl.textContent = `Answer: ${q.answer}`;
  } else if (q.type === 'first_letter') {
    answerEl.textContent = `First letter: ${q.answer}`;
  }

  // Show my answer
  const myAnswer = (state.answers || []).find(a => a.team_id === teamId);
  const yourEl = document.getElementById('reveal-your-answer');
  const scoreEl = document.getElementById('reveal-score-change');

  if (myAnswer) {
    yourEl.textContent = `Your answer: ${formatMyAnswer(myAnswer.answer_data, q)}`;
    if (myAnswer.score > 0) {
      scoreEl.textContent = `+${myAnswer.score} point${myAnswer.score !== 1 ? 's' : ''}`;
      scoreEl.style.color = 'var(--success-600)';
      scoreEl.classList.remove('hidden');
    } else {
      scoreEl.classList.add('hidden');
    }
  } else {
    yourEl.textContent = 'You did not answer';
    scoreEl.classList.add('hidden');
  }
}

function formatMyAnswer(answerData, q) {
  if (!answerData || !answerData.length) return 'No answer';
  if (q.type === 'multiple_choice' || q.type === 'picture') {
    const i = parseInt(answerData[0]);
    return `${LETTERS[i]}. ${(q.options || [])[i] || '?'}`;
  }
  if (q.type === 'select_many') {
    return answerData.map(i => LETTERS[parseInt(i)]).join(', ');
  }
  if (q.type === 'order') {
    return answerData.map(i => q.items?.[parseInt(i)] || i).join(' → ');
  }
  if (q.type === 'first_letter') {
    return `You chose: ${answerData[0]}`;
  }
  return String(answerData[0]);
}

// ── Leaderboard ────────────────────────────────────────────────────────────────

function renderLeaderboard(state) {
  showScreen('screen-leaderboard');
  const lb = state.leaderboard || [];
  const listEl = document.getElementById('play-leaderboard');
  const myRank = lb.findIndex(e => e.team_id === teamId) + 1;

  listEl.innerHTML = lb.map((entry, i) => `
    <div class="play-lb-entry ${entry.team_id === teamId ? 'you' : ''}">
      <div class="play-lb-rank">${i+1}</div>
      <div class="play-lb-name">${escHtml(entry.name)}${entry.team_id === teamId ? ' (you)' : ''}</div>
      <div class="play-lb-score">${entry.total_score}</div>
    </div>
  `).join('');

  const rankEl = document.getElementById('your-rank-display');
  if (myRank > 0) {
    rankEl.textContent = `You are ${ordinal(myRank)} of ${lb.length}`;
  }
}

// ── Ended ──────────────────────────────────────────────────────────────────────

function renderEnded(state) {
  showScreen('screen-ended');
  const lb = state.leaderboard || [];
  const listEl = document.getElementById('play-final-lb');
  listEl.innerHTML = lb.map((entry, i) => `
    <div class="play-lb-entry ${entry.team_id === teamId ? 'you' : ''}">
      <div class="play-lb-rank">${i+1}</div>
      <div class="play-lb-name">${escHtml(entry.name)}${entry.team_id === teamId ? ' (you)' : ''}</div>
      <div class="play-lb-score">${entry.total_score}</div>
    </div>
  `).join('');
}

// ── Utils ──────────────────────────────────────────────────────────────────────

function escHtml(str) {
  return String(str ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function ordinal(n) {
  const s = ['th','st','nd','rd'];
  const v = n % 100;
  return n + (s[(v-20)%10] || s[v] || s[0]);
}

function shuffleArray(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}
