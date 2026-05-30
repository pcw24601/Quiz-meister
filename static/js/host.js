/* Host control panel */

let sessionId = null;
let hostSecret = null;
let ws = null;
let lastState = null;
let pendingOverride = null;
let timerInterval = null;

const LETTERS = ['A','B','C','D','E','F','G','H'];

// ── Persistence ────────────────────────────────────────────────────────────

function saveSession() {
  if (sessionId && hostSecret) {
    localStorage.setItem('qm_session_id', sessionId);
    localStorage.setItem('qm_host_secret', hostSecret);
  }
}

function loadSession() {
  return {
    id: localStorage.getItem('qm_session_id'),
    secret: localStorage.getItem('qm_host_secret'),
  };
}

// ── Screen helpers ─────────────────────────────────────────────────────────

function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  const el = document.getElementById(id);
  if (el) el.classList.add('active');
}

function showPanel(id) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  const el = document.getElementById(id);
  if (el) el.classList.add('active');
}

function showToast(msg, duration = 3000) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  t.classList.remove('hidden');
  setTimeout(() => t.classList.remove('show'), duration);
}

// ── Setup ───────────────────────────────────────────────────────────────────

async function loadQuizList() {
  try {
    const res = await fetch('/api/quizzes');
    const data = await res.json();
    const sel = document.getElementById('quiz-select');
    sel.innerHTML = data.quizzes.length
      ? data.quizzes.map(f => `<option value="${f}">${f}</option>`).join('')
      : '<option value="">No quiz files found in /quizzes/</option>';
    if (data.quizzes.length) updateQuizPreview(data.quizzes[0]);
  } catch(e) {
    console.error(e);
  }
}

async function updateQuizPreview(file) {
  // We can't preview until loaded, so just show filename
  const preview = document.getElementById('quiz-preview');
  preview.innerHTML = `<strong>${file}</strong>`;
  preview.classList.remove('hidden');
}

document.getElementById('quiz-select').addEventListener('change', e => {
  if (e.target.value) updateQuizPreview(e.target.value);
});

document.getElementById('btn-create-session').addEventListener('click', async () => {
  const file = document.getElementById('quiz-select').value;
  if (!file) { showToast('Select a quiz file first'); return; }
  try {
    const res = await fetch('/api/sessions', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({quiz_file: file}),
    });
    if (!res.ok) {
      const err = await res.json();
      showToast(err.detail || 'Error creating session');
      return;
    }
    const data = await res.json();
    sessionId = data.session_id;
    hostSecret = data.host_secret;
    saveSession();
    enterHostScreen();
  } catch(e) {
    showToast('Failed to create session');
  }
});

document.getElementById('btn-resume-session').addEventListener('click', () => {
  const id = document.getElementById('resume-session-id').value.trim();
  const secret = document.getElementById('resume-secret').value.trim();
  if (!id || !secret) { showToast('Enter session ID and secret'); return; }
  sessionId = id;
  hostSecret = secret;
  saveSession();
  enterHostScreen();
});

// ── Enter Host Screen ────────────────────────────────────────────────────────

function enterHostScreen() {
  showScreen('screen-host');
  document.getElementById('sidebar-session-id').textContent = sessionId;

  const baseUrl = `${location.protocol}//${location.host}`;
  const joinUrl = `${baseUrl}/play?session=${sessionId}`;
  document.getElementById('join-url-display').textContent = joinUrl;

  // QR code
  document.getElementById('qr-code-container').innerHTML = '';
  new QRCode(document.getElementById('qr-code-container'), {
    text: joinUrl,
    width: 160,
    height: 160,
    colorDark: '#0f172a',
    colorLight: '#ffffff',
    correctLevel: QRCode.CorrectLevel.M,
  });

  document.getElementById('btn-show-display').addEventListener('click', () => {
    window.open(`/display?session=${sessionId}`, '_blank');
  });

  document.getElementById('btn-copy-join-link').addEventListener('click', () => {
    navigator.clipboard.writeText(joinUrl).then(() => showToast('Link copied!'));
  });

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
  // Keepalive
  setInterval(() => { if (ws.readyState === 1) ws.send('ping'); }, 30000);
}

// ── State Handler ──────────────────────────────────────────────────────────────

function handleState(state) {
  lastState = state;

  // Sidebar
  document.getElementById('sidebar-quiz-title').textContent = state.quiz_title;
  document.getElementById('sidebar-round-name').textContent = state.round_name;
  document.getElementById('sidebar-team-count').textContent = `${state.total_teams} team${state.total_teams !== 1 ? 's' : ''}`;
  document.getElementById('team-count-badge').textContent = state.total_teams;
  document.getElementById('state-label').textContent = stateLabel(state.state);

  // Team list (sidebar)
  renderTeamList(state.teams, state.answers);

  switch(state.state) {
    case 'lobby':       renderLobby(state); break;
    case 'question':    renderQuestion(state); break;
    case 'answer_reveal': renderReveal(state); break;
    case 'leaderboard': renderLeaderboard(state); break;
    case 'ended':       renderEnded(state); break;
  }
}

function stateLabel(s) {
  return { lobby:'Lobby', question:'Question Active', answer_reveal:'Revealing Answer',
           leaderboard:'Leaderboard', ended:'Quiz Ended' }[s] || s;
}

function renderTeamList(teams, answers) {
  const list = document.getElementById('team-list');
  list.innerHTML = teams.map(t => `
    <div class="team-item">
      <span>${escHtml(t.name)}</span>
    </div>
  `).join('');
}

// ── Lobby ──────────────────────────────────────────────────────────────────────

function renderLobby(state) {
  showPanel('panel-lobby');
  document.getElementById('lobby-round-info').textContent =
    `${state.round_name} · ${state.total_questions} question${state.total_questions !== 1 ? 's' : ''}`;
}

document.getElementById('btn-start-first-question').addEventListener('click', () => action('start_question'));

// ── Question ───────────────────────────────────────────────────────────────────

function renderQuestion(state) {
  showPanel('panel-question');
  const q = state.question_with_answers;
  if (!q) return;

  document.getElementById('q-round-label').textContent = state.round_name;
  document.getElementById('q-num-label').textContent = `Q ${state.question_index + 1}/${state.total_questions}`;
  document.getElementById('q-type-label').textContent = qtypeLabel(q.type);
  document.getElementById('q-tiebreaker-label').classList.toggle('hidden', !q.tiebreaker);
  document.getElementById('host-question-text').textContent = q.text;

  // Image
  const imgWrap = document.getElementById('host-question-image');
  if (q.image) {
    document.getElementById('host-question-img').src = q.image;
    imgWrap.classList.remove('hidden');
  } else {
    imgWrap.classList.add('hidden');
  }

  // Options
  const optEl = document.getElementById('host-options');
  optEl.innerHTML = renderOptionsHTML(q);

  // Timer
  startTimerDisplay(state.timer_ends_at, q.time);

  // Progress
  updateAnswerProgress(state.answered_count, state.total_teams);
}

function qtypeLabel(type) {
  return { multiple_choice:'Multiple Choice', select_many:'Select Many',
           order:'Put in Order', numeric:'Numeric', picture:'Picture Round',
           first_letter:'First Letter' }[type] || type;
}

function renderOptionsHTML(q) {
  if (q.type === 'multiple_choice' || q.type === 'picture') {
    return (q.options || []).map((opt, i) => `
      <div class="option-row ${i === q.correct ? 'correct' : ''}">
        <div class="option-letter">${LETTERS[i]}</div>
        <div class="option-text">${escHtml(opt)}</div>
        ${i === q.correct ? '<span style="color:var(--success-600);font-weight:700">&#10003;</span>' : ''}
      </div>
    `).join('');
  }
  if (q.type === 'select_many') {
    const corrSet = new Set(q.correct || []);
    return (q.options || []).map((opt, i) => `
      <div class="option-row ${corrSet.has(i) ? 'correct' : ''}">
        <div class="option-letter">${LETTERS[i]}</div>
        <div class="option-text">${escHtml(opt)}</div>
        ${corrSet.has(i) ? '<span style="color:var(--success-600);font-weight:700">&#10003;</span>' : ''}
      </div>
    `).join('');
  }
  if (q.type === 'order') {
    return (q.items || []).map((item, i) => `
      <div class="option-row">
        <div class="option-letter">${i+1}</div>
        <div class="option-text">${escHtml(item)}</div>
      </div>
    `).join('');
  }
  if (q.type === 'numeric') {
    return `<div class="option-row correct">
      <div class="option-text">Correct answer: <strong>${q.answer}</strong></div>
    </div>`;
  }
  if (q.type === 'first_letter') {
    return `<div class="option-row correct">
      <div class="option-text">Correct first letter: <strong>${q.answer}</strong></div>
    </div>`;
  }
  return '';
}

function updateAnswerProgress(answered, total) {
  const pct = total > 0 ? Math.round((answered / total) * 100) : 0;
  document.getElementById('answer-progress-bar').style.width = pct + '%';
  document.getElementById('answer-progress-label').textContent = `${answered} / ${total} answered`;
}

function startTimerDisplay(timerEndsAt, duration) {
  clearInterval(timerInterval);
  const el = document.getElementById('host-timer');
  const valEl = document.getElementById('host-timer-value');

  function tick() {
    if (!timerEndsAt) { valEl.textContent = '—'; return; }
    const secs = Math.max(0, Math.round((new Date(timerEndsAt) - Date.now()) / 1000));
    valEl.textContent = secs;
    el.className = 'timer-display' + (secs <= 5 ? ' danger' : secs <= 10 ? ' warning' : '');
    if (secs <= 0) clearInterval(timerInterval);
  }
  tick();
  timerInterval = setInterval(tick, 500);
}

document.getElementById('btn-reveal-now').addEventListener('click', () => action('reveal_answer'));

// ── Answer Reveal ──────────────────────────────────────────────────────────────

function renderReveal(state) {
  showPanel('panel-reveal');
  const q = state.question_with_answers;
  if (!q) return;

  document.getElementById('reveal-question-text').textContent = q.text;
  document.getElementById('reveal-correct-answer').innerHTML = correctAnswerHTML(q);

  // Build answers table
  const teams = state.teams;
  const teamMap = Object.fromEntries(teams.map(t => [t.id, t]));
  const answers = state.answers || [];

  const tbody = document.getElementById('answers-tbody');
  tbody.innerHTML = answers.map(a => {
    const team = teamMap[a.team_id] || {name:'Unknown'};
    const answerStr = formatAnswer(a.answer_data, q);
    const scoreClass = a.score_overridden ? 'score-overridden' : a.score > 0 ? 'score-correct' : 'score-zero';
    return `
      <tr>
        <td>${escHtml(team.name)}</td>
        <td>${escHtml(answerStr)}</td>
        <td class="${scoreClass}">${a.score}</td>
        <td>
          <button class="override-btn" onclick="openOverride('${a.id}','${escHtml(team.name)}',${a.score})">
            Edit
          </button>
        </td>
      </tr>
    `;
  }).join('');

  // Teams that didn't answer
  const answeredIds = new Set(answers.map(a => a.team_id));
  teams.filter(t => !answeredIds.has(t.id)).forEach(t => {
    tbody.innerHTML += `
      <tr style="opacity:0.5">
        <td>${escHtml(t.name)}</td>
        <td><em>No answer</em></td>
        <td class="score-zero">0</td>
        <td></td>
      </tr>
    `;
  });
}

function correctAnswerHTML(q) {
  if (q.type === 'multiple_choice' || q.type === 'picture') {
    return `Correct: <strong>${LETTERS[q.correct]}. ${escHtml((q.options || [])[q.correct] || '')}</strong>`;
  }
  if (q.type === 'select_many') {
    const opts = (q.correct || []).map(i => `${LETTERS[i]}. ${escHtml((q.options || [])[i] || '')}`);
    return `Correct: <strong>${opts.join(', ')}</strong>`;
  }
  if (q.type === 'order') {
    return `Correct order: <strong>${(q.items || []).join(' → ')}</strong>`;
  }
  if (q.type === 'numeric') {
    return `Correct answer: <strong>${q.answer}</strong>`;
  }
  if (q.type === 'first_letter') {
    return `Correct first letter: <strong>${q.answer}</strong>`;
  }
  return '';
}

function formatAnswer(answerData, q) {
  if (!answerData || !answerData.length) return 'No answer';
  if (q.type === 'multiple_choice' || q.type === 'picture') {
    const i = parseInt(answerData[0]);
    return `${LETTERS[i]}. ${(q.options || [])[i] || '?'}`;
  }
  if (q.type === 'select_many') {
    return answerData.map(i => `${LETTERS[parseInt(i)]}`).join(', ');
  }
  if (q.type === 'order') {
    return answerData.map(i => q.items?.[parseInt(i)] || i).join(' → ');
  }
  if (q.type === 'numeric') {
    return answerData[0];
  }
  if (q.type === 'first_letter') {
    return `Letter: ${answerData[0]}`;
  }
  return answerData.join(', ');
}

document.getElementById('btn-show-leaderboard').addEventListener('click', () => action('show_leaderboard'));
document.getElementById('btn-next-question').addEventListener('click', () => action('start_question'));

// ── Score Override Modal ───────────────────────────────────────────────────────

function openOverride(answerId, teamName, currentScore) {
  pendingOverride = answerId;
  document.getElementById('modal-override-info').textContent = `Team: ${teamName} — Current score: ${currentScore}`;
  document.getElementById('modal-score-input').value = currentScore;
  document.getElementById('modal-override').classList.remove('hidden');
}

document.getElementById('btn-modal-cancel').addEventListener('click', () => {
  document.getElementById('modal-override').classList.add('hidden');
  pendingOverride = null;
});

document.getElementById('btn-modal-confirm').addEventListener('click', async () => {
  if (!pendingOverride) return;
  const score = parseInt(document.getElementById('modal-score-input').value) || 0;
  await action('override_score', {answer_id: pendingOverride, score});
  document.getElementById('modal-override').classList.add('hidden');
  pendingOverride = null;
  showToast('Score updated');
});

// ── Leaderboard ─────────────────────────────────────────────────────────────

function renderLeaderboard(state) {
  showPanel('panel-leaderboard');
  renderLBList('host-leaderboard', state.leaderboard);
}

document.getElementById('btn-next-round').addEventListener('click', () => {
  if (!lastState) return;
  const ri = lastState.round_index;
  const total = lastState.total_rounds;
  if (ri + 1 >= total) {
    action('next_round'); // will end
  } else {
    action('next_round');
  }
});

// ── Ended ──────────────────────────────────────────────────────────────────────

function renderEnded(state) {
  showPanel('panel-ended');
  renderLBList('final-leaderboard', state.leaderboard);
}

document.getElementById('btn-new-quiz').addEventListener('click', () => {
  localStorage.removeItem('qm_session_id');
  localStorage.removeItem('qm_host_secret');
  location.reload();
});

// ── Leaderboard helper ─────────────────────────────────────────────────────────

function renderLBList(containerId, leaderboard) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = (leaderboard || []).map((entry, i) => `
    <div class="lb-entry">
      <div class="lb-rank">${i + 1}</div>
      <div class="lb-name">${escHtml(entry.name)}</div>
      <div class="lb-score">${entry.total_score}</div>
    </div>
  `).join('');
}

// ── Action helper ──────────────────────────────────────────────────────────────

async function action(actionName, payload = {}) {
  try {
    const res = await fetch(`/api/sessions/${sessionId}/action`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({host_secret: hostSecret, action: actionName, payload}),
    });
    if (!res.ok) {
      const err = await res.json();
      showToast(err.detail || 'Action failed');
    }
  } catch(e) {
    showToast('Network error');
  }
}

// ── Utils ──────────────────────────────────────────────────────────────────────

function escHtml(str) {
  return String(str ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Init ───────────────────────────────────────────────────────────────────────

(function init() {
  loadQuizList();

  // Check for session in URL params
  const params = new URLSearchParams(location.search);
  const urlSession = params.get('session');
  const urlSecret = params.get('secret');

  if (urlSession && urlSecret) {
    sessionId = urlSession;
    hostSecret = urlSecret;
    saveSession();
    enterHostScreen();
    return;
  }

  // Try resuming from localStorage
  const saved = loadSession();
  if (saved.id && saved.secret) {
    document.getElementById('resume-session-id').value = saved.id;
    document.getElementById('resume-secret').value = saved.secret;
  }
})();
