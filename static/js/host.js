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

async function loadQuizList(path = null) {
  try {
    const url = path ? `/api/quizzes?path=${encodeURIComponent(path)}` : '/api/quizzes';
    const res = await fetch(url);
    const data = await res.json();
    if (data.error) { showToast(data.error); return; }
    const sel = document.getElementById('quiz-select');
    // Build options: directories first (if any), then files
    let options = [];
    if (data.dirs && data.dirs.length) {
      // Parent directory link if applicable
      const cwd = data.cwd || '';
      try {
        const parent = cwd.split('/').slice(0, -1).join('/');
        if (parent) options.push(`<option value="DIR::${parent}">../</option>`);
      } catch(e) {}
      for (const d of data.dirs) {
        const name = d.split('/').slice(-1)[0] || d;
        options.push(`<option value="DIR::${d}">${name}/</option>`);
      }
    }
    if (data.files && data.files.length) {
      for (const f of data.files) {
        const label = (f + '').split('/').slice(-1)[0];
        options.push(`<option value="${f}">${label}</option>`);
      }
    }
    // Always include a Browse... option
    options.push(`<option value="__browse__">Browse...</option>`);

    sel.innerHTML = options.length ? options.join('') : '<option value="">No quiz files found</option>';
    // Select first real file if present
    const firstFile = (data.files && data.files.length) ? data.files[0] : null;
    if (firstFile) {
      sel.value = firstFile;
      updateQuizPreview(firstFile);
    } else {
      // If no files, select browse option
      sel.value = '__browse__';
      updateQuizPreview(sel.value);
    }
  } catch(e) {
    console.error(e);
    showToast('Failed to list quizzes');
  }
}

async function updateQuizPreview(file) {
  // We can't preview until loaded, so just show filename
  const preview = document.getElementById('quiz-preview');
  preview.innerHTML = `<strong>${file}</strong>`;
  preview.classList.remove('hidden');
}

document.getElementById('quiz-select').addEventListener('change', async e => {
  const v = e.target.value;
  if (!v) return;
  if (v === '__browse__') {
    openFileBrowser();
    return;
  }
  if (v.startsWith('DIR::')) {
    const dir = v.substring('DIR::'.length);
    await loadQuizList(dir);
    return;
  }
  updateQuizPreview(v);
});

document.getElementById('btn-create-session').addEventListener('click', async () => {
  const btn = document.getElementById('btn-create-session');
  if (btn.disabled) return;
  const file = document.getElementById('quiz-select').value;
  const bonusPoints = parseInt(document.getElementById('bonus-points').value) || 0;
  if (!file) { showToast('Select a quiz file first'); return; }
  btn.disabled = true;
  btn.textContent = 'Starting...';
  try {
    const res = await fetch('/api/sessions', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({quiz_file: file, bonus_points: bonusPoints}),
    });
    if (!res.ok) {
      const err = await res.json();
      showToast(err.detail || 'Error creating session');
      btn.disabled = false;
      btn.textContent = 'Start Session';
      return;
    }
    const data = await res.json();
    sessionId = data.session_id;
    hostSecret = data.host_secret;
    saveSession();
    enterHostScreen();
  } catch(e) {
    showToast('Failed to create session');
    btn.disabled = false;
    btn.textContent = 'Start Session';
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
  try {
    showScreen('screen-host');
    document.getElementById('sidebar-session-id').textContent = sessionId;

    // Fetch the correct player URL (uses LAN IP, not localhost)
    fetch('/api/config').then(r => r.json()).then(cfg => {
      const joinUrl = `${cfg.player_url}?session=${sessionId}`;
      document.getElementById('join-url-display').textContent = joinUrl;

      try {
        document.getElementById('qr-code-container').innerHTML = '';
        new QRCode(document.getElementById('qr-code-container'), {
          text: joinUrl,
          width: 160,
          height: 160,
          colorDark: '#0f172a',
          colorLight: '#ffffff',
          correctLevel: QRCode.CorrectLevel.M,
        });
      } catch(qrErr) {
        console.warn('QR code error:', qrErr);
      }

      const btnCopy = document.getElementById('btn-copy-join-link');
      btnCopy.onclick = () => navigator.clipboard.writeText(joinUrl).then(() => showToast('Link copied!'));
    }).catch(() => {
      // Fallback to location.host
      const joinUrl = `${location.protocol}//${location.host}/play?session=${sessionId}`;
      document.getElementById('join-url-display').textContent = joinUrl;
    });

    const btnDisplay = document.getElementById('btn-show-display');
    btnDisplay.onclick = () => window.open(`/display?session=${sessionId}`, '_blank');

    connectWS();
  } catch(e) {
    console.error('enterHostScreen error:', e);
    showToast('Error entering host screen: ' + e.message);
  }
}

// ── WebSocket ─────────────────────────────────────────────────────────────────

function connectWS() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws/${sessionId}`);
  ws.onmessage = e => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'state') handleState(msg);
  };
  ws.onclose = () => setTimeout(connectWS, 2000);
  // Keepalive
  setInterval(() => { if (ws.readyState === WebSocket.OPEN) ws.send('ping'); }, 30000);
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
  renderTeamList(state.teams, state.leaderboard);

  switch(state.state) {
    case 'lobby':       renderLobby(state); break;
    case 'round_intro': renderRoundIntro(state); break;
    case 'question':    renderQuestion(state); break;
    case 'answer_reveal': renderReveal(state); break;
    case 'leaderboard': renderLeaderboard(state); break;
    case 'ended':       renderEnded(state); break;
  }
}

function stateLabel(s) {
  return { lobby:'Lobby', round_intro:'Round Intro', question:'Question Active', answer_reveal:'Revealing Answer',
           leaderboard:'Leaderboard', ended:'Quiz Ended' }[s] || s;
}

function renderTeamList(teams, leaderboard) {
  const list = document.getElementById('team-list');
  if (!teams || teams.length === 0) {
    list.innerHTML = '';
    return;
  }

  // Create lookup for scores from leaderboard
  const scoreMap = new Map((leaderboard || []).map(entry => [entry.team_id, entry.total_score]));

  // Build items with score, sorted by score descending (with secondary tie-break on name)
  const sortedTeams = teams.map(t => ({
    id: t.id,
    name: t.name,
    score: scoreMap.has(t.id) ? scoreMap.get(t.id) : (t.score || 0)
  })).sort((a, b) => b.score - a.score || a.name.localeCompare(b.name));

  list.innerHTML = sortedTeams.map(t => `
    <div class="team-item">
      <span>${escHtml(t.name)}</span>
      <span class="team-score">${t.score} pts</span>
    </div>
  `).join('');
}

// ── Lobby ──────────────────────────────────────────────────────────────────────

function renderLobby(state) {
  showPanel('panel-lobby');
  document.getElementById('lobby-round-info').textContent =
    `${state.round_name} · ${state.total_questions} question${state.total_questions !== 1 ? 's' : ''}`;

  const btn = document.getElementById('btn-start-first-question');
  if (state.question_index === 0) {
    btn.textContent = state.round_index === 0 ? 'Start Quiz' : 'Start Round';
  } else {
    btn.textContent = 'Resume Question';
  }
}

document.getElementById('btn-start-first-question').addEventListener('click', () => {
  if (lastState && lastState.question_index > 0) {
    action('start_question');
  } else {
    action('start_round');
  }
});

// ── Round Intro ────────────────────────────────────────────────────────────────

function renderRoundIntro(state) {
  showPanel('panel-round-intro');
  document.getElementById('host-round-intro-badge').textContent = `Round ${state.round_index + 1} of ${state.total_rounds}`;
  document.getElementById('host-round-intro-title').textContent = state.round_name;
  
  const instEl = document.getElementById('host-round-intro-instructions');
  if (state.round_instructions) {
    instEl.textContent = state.round_instructions;
    instEl.classList.remove('hidden');
  } else {
    instEl.classList.add('hidden');
  }
  
  const imgWrap = document.getElementById('host-round-intro-image');
  const imgEl = document.getElementById('host-round-img');
  if (state.round_image) {
    imgEl.src = state.round_image;
    imgWrap.classList.remove('hidden');
  } else {
    imgWrap.classList.add('hidden');
  }
}

document.getElementById('btn-start-round-questions').addEventListener('click', () => action('start_question'));

// ── Question ───────────────────────────────────────────────────────────────────

function renderQuestion(state) {
  showPanel('panel-question');
  const q = state.question_with_answers;
  if (!q) return;

  document.getElementById('q-round-label').textContent = state.round_name;
  document.getElementById('q-num-label').textContent = `Q ${state.question_index + 1}/${state.total_questions}`;
  document.getElementById('q-type-label').textContent = qtypeLabel(q.type);
  document.getElementById('q-tiebreaker-label').classList.toggle('hidden', !q.tiebreaker);

  // Question text with optional note for first_letter questions
  const questionText = q.text + (q.note ? ` (${q.note})` : '');
  document.getElementById('host-question-text').textContent = questionText;

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

  const infoEl = document.getElementById('reveal-answer-info');
  if (infoEl) {
    if (q.answer_info) {
      infoEl.textContent = q.answer_info;
      infoEl.classList.remove('hidden');
    } else {
      infoEl.textContent = '';
      infoEl.classList.add('hidden');
    }
  }

  // Build answers table with ranking
  const teams = state.teams;
  const teamMap = Object.fromEntries(teams.map(t => [t.id, t]));
  const answers = state.answers || [];

  // Sort answers: correct first (by score desc), then by submission time
  const sortedAnswers = [...answers].sort((a, b) => {
    // Higher score first
    if (b.score !== a.score) return b.score - a.score;
    // Earlier submission first (if we had timestamp)
    return 0;
  });

  // Assign ranks
  let rank = 1;
  let lastScore = null;
  const rankedAnswers = sortedAnswers.map((a, i) => {
    if (lastScore !== a.score) {
      rank = i + 1;
      lastScore = a.score;
    }
    return { ...a, rank: a.score > 0 ? rank : '-' };
  });

  const tbody = document.getElementById('answers-tbody');
  tbody.innerHTML = rankedAnswers.map(a => {
    const team = teamMap[a.team_id] || {name:'Unknown'};
    const answerStr = formatAnswer(a.answer_data, q);
    const isCorrect = a.score > 0 && !a.score_overridden;
    const scoreClass = a.score_overridden ? 'score-overridden' : a.score > 0 ? 'score-correct' : 'score-zero';
    const rowClass = isCorrect ? 'correct-row' : '';
    const rankDisplay = a.rank === '-' ? '-' : (a.rank <= 3 ? ['1st','2nd','3rd'][a.rank-1] : `${a.rank}th`);
    const rankClass = a.rank === 1 ? 'rank-first' : a.rank === 2 ? 'rank-second' : a.rank === 3 ? 'rank-third' : '';
    return `
      <tr class="${rowClass}">
        <td class="rank-cell ${rankClass}">${rankDisplay}</td>
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
        <td class="rank-cell">-</td>
        <td>${escHtml(t.name)}</td>
        <td><em>No answer</em></td>
        <td class="score-zero">0</td>
        <td></td>
      </tr>
    `;
  });

  renderNextPreview(state);
}

function renderNextPreview(state) {
  const el = document.getElementById('host-next-preview');
  if (!el) return;

  if (state.next_is_end) {
    el.innerHTML = `<div class="next-preview-label">Coming up</div><div class="next-preview-body">Last question of the quiz</div>`;
    return;
  }

  if (state.next_is_new_round) {
    el.innerHTML = `
      <div class="next-preview-label">Coming up — Round ${state.next_round_index + 1}: ${escHtml(state.next_round_name)}</div>
      ${state.next_round_instructions ? `<div class="next-preview-body">${escHtml(state.next_round_instructions)}</div>` : ''}
    `;
    return;
  }

  const q = state.next_question;
  if (!q) return;
  el.innerHTML = `
    <div class="next-preview-label">Coming up — Round ${state.next_round_index + 1} · Q${state.next_question_index + 1}/${state.total_questions}</div>
    <div class="next-preview-body">
      <span class="next-preview-type">${qtypeLabel(q.type)}</span>
      <div class="next-preview-text">${escHtml(q.text)}</div>
      <div class="next-preview-answer">${correctAnswerHTML(q)}</div>
      ${q.image ? `<img class="next-preview-img" src="${escHtml(q.image)}" alt="">` : ''}
    </div>
  `;
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
document.getElementById('btn-back-to-reveal').addEventListener('click', () => action('back_to_reveal'));
document.getElementById('btn-next-question').addEventListener('click', () => action('start_question'));
document.getElementById('btn-restart-question').addEventListener('click', () => {
  if (confirm('Restart this question? All current answers will be deleted.')) {
    action('restart_question');
  }
});

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

// ── File Browser Modal ─────────────────────────────────────────────────────────

let fbCurrentPath = null;  // last directory browsed
let fbSelectedFile = null; // currently highlighted file path

async function openFileBrowser() {
  fbSelectedFile = null;
  document.getElementById('btn-fb-select').disabled = true;
  document.getElementById('modal-filebrowser').classList.remove('hidden');
  // Start from the last-browsed dir, or the default quizzes listing
  await fbNavigate(fbCurrentPath);
}

async function fbNavigate(path) {
  fbSelectedFile = null;
  document.getElementById('btn-fb-select').disabled = true;

  const listEl = document.getElementById('fb-list');
  listEl.innerHTML = '<div class="fb-empty">Loading…</div>';

  try {
    const url = path ? `/api/quizzes?path=${encodeURIComponent(path)}` : '/api/quizzes';
    const res = await fetch(url);
    const data = await res.json();
    if (data.error) { showToast(data.error); return; }

    fbCurrentPath = data.cwd;
    renderFbBreadcrumb(data.cwd);
    renderFbList(data);
  } catch (e) {
    listEl.innerHTML = '<div class="fb-empty">Error loading directory</div>';
  }
}

function renderFbBreadcrumb(cwd) {
  document.getElementById('fb-breadcrumb').textContent = cwd || '/';
}

function renderFbList(data) {
  const listEl = document.getElementById('fb-list');
  let html = '';

  // Parent directory entry
  if (data.cwd) {
    const parts = data.cwd.split('/');
    const parent = parts.slice(0, -1).join('/');
    if (parent) {
      html += `<div class="fb-item fb-parent fb-dir" data-dir="${escHtml(parent)}">
        <span class="fb-icon">&#11014;</span><span>../&ensp;(parent folder)</span>
      </div>`;
    }
  }

  // Subdirectories
  for (const d of (data.dirs || [])) {
    const name = d.split('/').pop() || d;
    html += `<div class="fb-item fb-dir" data-dir="${escHtml(d)}">
      <span class="fb-icon">&#128193;</span><span>${escHtml(name)}/</span>
    </div>`;
  }

  // Quiz files
  for (const f of (data.files || [])) {
    const name = f.split('/').pop() || f;
    html += `<div class="fb-item fb-file" data-file="${escHtml(f)}">
      <span class="fb-icon">&#128196;</span><span>${escHtml(name)}</span>
    </div>`;
  }

  if (!html) {
    html = '<div class="fb-empty">No quiz files or subdirectories here</div>';
  }

  listEl.innerHTML = html;

  // Attach click handlers
  listEl.querySelectorAll('.fb-dir').forEach(el => {
    el.addEventListener('click', () => fbNavigate(el.dataset.dir));
  });
  listEl.querySelectorAll('.fb-file').forEach(el => {
    el.addEventListener('click', () => fbSelectFile(el));
  });
}

function fbSelectFile(el) {
  document.querySelectorAll('#fb-list .fb-item.selected')
    .forEach(e => e.classList.remove('selected'));
  el.classList.add('selected');
  fbSelectedFile = el.dataset.file;
  document.getElementById('btn-fb-select').disabled = false;
}

function closeFbModal() {
  document.getElementById('modal-filebrowser').classList.add('hidden');
  fbSelectedFile = null;
}

document.getElementById('btn-fb-cancel').addEventListener('click', closeFbModal);

document.getElementById('btn-fb-select').addEventListener('click', () => {
  if (!fbSelectedFile) return;
  const sel = document.getElementById('quiz-select');
  // Add as an option if not already present
  let opt = [...sel.options].find(o => o.value === fbSelectedFile);
  if (!opt) {
    opt = new Option(fbSelectedFile.split('/').pop(), fbSelectedFile);
    // Insert before the Browse... option
    const browseOpt = [...sel.options].find(o => o.value === '__browse__');
    if (browseOpt) sel.insertBefore(opt, browseOpt);
    else sel.appendChild(opt);
  }
  sel.value = fbSelectedFile;
  updateQuizPreview(fbSelectedFile);
  closeFbModal();
});

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
