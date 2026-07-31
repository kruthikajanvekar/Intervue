/* ============================================================
   Intervue frontend — vanilla JS, no build step.
   Talks to the FastAPI backend over the routes defined in
   app/api/interview.py and app/api/feedback.py.
   ============================================================ */

const state = {
  apiBase: 'http://localhost:8000/api/v1',
  interviewId: null,
  sessionToken: null,
  candidateName: '',
  role: '',
  maxQuestions: 8,
  questionsAsked: 1,
  difficulty: 'easy',
  isRecording: false,
  mediaRecorder: null,
  audioChunks: [],
  timerInterval: null,
  startTime: null,
};

const els = {};

function cacheEls() {
  const ids = [
    'topbar-meta', 'meta-candidate', 'meta-role', 'meta-timer',
    'conn-status', 'conn-dot', 'conn-label',
    'view-setup', 'view-interview', 'view-report',
    'setup-form', 'f-name', 'f-role', 'f-level', 'f-focus', 'f-apibase', 'btn-start',
    'progress-track', 'rung-marker',
    'question-text', 'subtopic-chip', 'speaker-tag', 'waveform',
    'transcript', 'eval-strip',
    'bar-correctness', 'bar-depth', 'bar-communication', 'bar-confidence',
    'mode-voice', 'mode-text', 'answer-voice', 'answer-text',
    'btn-record', 'record-label', 'record-hint',
    'f-answer-text', 'btn-send-text',
    'report-name', 'score-fill', 'score-number', 'rec-badge', 'report-summary',
    'list-strengths', 'list-weaknesses', 'report-comm', 'topic-chips',
    'breakdown-body', 'btn-download-pdf', 'btn-restart',
    'error-banner', 'error-text', 'error-dismiss',
  ];
  ids.forEach((id) => { els[id] = document.getElementById(id); });
}

/* ---------------- API helpers ---------------- */

async function apiFetch(path, options = {}) {
  const url = `${state.apiBase}${path}`;
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (state.sessionToken) headers.Authorization = `Bearer ${state.sessionToken}`;

  let resp;
  try {
    resp = await fetch(url, { ...options, headers });
  } catch (err) {
    throw new Error(`Could not reach backend at ${state.apiBase}. Is it running?`);
  }
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail || detail;
    } catch (_) { /* ignore parse failure */ }
    throw new Error(detail);
  }
  return resp.json();
}

async function checkBackend() {
  try {
    await fetch(`${state.apiBase}/health`).then((r) => { if (!r.ok) throw new Error(); });
    setConnStatus(true);
  } catch (_) {
    setConnStatus(false);
  }
}

function setConnStatus(ok) {
  els['conn-dot'].classList.toggle('ok', ok);
  els['conn-dot'].classList.toggle('err', !ok);
  els['conn-label'].textContent = ok ? 'backend connected' : 'backend unreachable';
}

/* ---------------- Error toast ---------------- */

function showError(message) {
  els['error-text'].textContent = message;
  els['error-banner'].hidden = false;
}
function hideError() {
  els['error-banner'].hidden = true;
}

/* ---------------- View switching ---------------- */

function showView(name) {
  ['view-setup', 'view-interview', 'view-report'].forEach((v) => {
    els[v].classList.toggle('active', v === name);
  });
}

/* ---------------- Timer ---------------- */

function startTimer() {
  state.startTime = Date.now();
  state.timerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - state.startTime) / 1000);
    const mm = String(Math.floor(elapsed / 60)).padStart(2, '0');
    const ss = String(elapsed % 60).padStart(2, '0');
    els['meta-timer'].textContent = `${mm}:${ss}`;
  }, 1000);
}
function stopTimer() {
  clearInterval(state.timerInterval);
}

/* ---------------- Progress + difficulty UI ---------------- */

function renderProgress() {
  els['progress-track'].innerHTML = '';
  for (let i = 1; i <= state.maxQuestions; i++) {
    const dot = document.createElement('span');
    dot.className = 'progress-dot';
    if (i < state.questionsAsked) dot.classList.add('done');
    if (i === state.questionsAsked) dot.classList.add('current');
    els['progress-track'].appendChild(dot);
  }
}

function renderDifficulty() {
  const levels = ['easy', 'medium', 'hard'];
  const idx = Math.max(0, levels.indexOf(state.difficulty));
  document.querySelectorAll('.rung').forEach((el) => {
    el.classList.toggle('active', el.dataset.level === state.difficulty);
  });
  els['rung-marker'].style.transform = `translateX(${idx * 100}%)`;
}

/* ---------------- Transcript ---------------- */

function appendTranscriptTurn(role, text) {
  const wrap = document.createElement('div');
  wrap.className = `transcript-turn ${role}`;
  const label = document.createElement('span');
  label.className = 'turn-speaker';
  label.textContent = role === 'interviewer' ? 'Interviewer' : 'You';
  const body = document.createElement('p');
  body.style.margin = '0';
  body.textContent = text;
  wrap.appendChild(label);
  wrap.appendChild(body);
  els['transcript'].appendChild(wrap);
  els['transcript'].scrollTop = els['transcript'].scrollHeight;
}

/* ---------------- Waveform state ---------------- */

function setWaveform(mode) {
  // mode: 'idle' | 'speaking' | 'listening'
  els['waveform'].classList.remove('speaking', 'listening');
  if (mode !== 'idle') els['waveform'].classList.add(mode);
}

/* ---------------- Audio playback ---------------- */

function playBase64Audio(base64) {
  return new Promise((resolve) => {
    if (!base64) { resolve(); return; }
    const audio = new Audio(`data:audio/mpeg;base64,${base64}`);
    setWaveform('speaking');
    audio.onended = () => { setWaveform('idle'); resolve(); };
    audio.onerror = () => { setWaveform('idle'); resolve(); };
    audio.play().catch(() => { setWaveform('idle'); resolve(); });
  });
}

/* ---------------- Evaluation bars ---------------- */

function renderEvaluation(evaluation) {
  if (!evaluation) { els['eval-strip'].hidden = true; return; }
  els['eval-strip'].hidden = false;
  const fields = ['correctness', 'depth', 'communication', 'confidence'];
  fields.forEach((f) => {
    const pct = Math.max(0, Math.min(10, evaluation[f] || 0)) * 10;
    els[`bar-${f}`].style.width = `${pct}%`;
    els[`bar-${f}`].style.background = pct >= 70 ? 'var(--good)' : pct >= 40 ? 'var(--amber)' : 'var(--bad)';
  });
}

/* ---------------- Setup submit ---------------- */

function handleSetupSubmit(e) {
  e.preventDefault();
  hideError();

  state.apiBase = els['f-apibase'].value.trim().replace(/\/$/, '');
  state.candidateName = els['f-name'].value.trim();
  state.role = els['f-role'].value.trim();
  const level = els['f-level'].value;
  const focusAreas = els['f-focus'].value
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

  els['btn-start'].disabled = true;
  els['btn-start'].querySelector('span').textContent = 'Starting…';

  apiFetch('/interviews/start', {
    method: 'POST',
    body: JSON.stringify({
      candidate_name: state.candidateName,
      role: state.role,
      experience_level: level,
      focus_areas: focusAreas,
    }),
  })
    .then((data) => {
      state.interviewId = data.interview_id;
      state.sessionToken = data.session_token;
      state.difficulty = data.difficulty;
      state.questionsAsked = 1;

      els['meta-candidate'].textContent = state.candidateName;
      els['meta-role'].textContent = state.role;
      els['topbar-meta'].hidden = false;

      showView('view-interview');
      renderProgress();
      renderDifficulty();
      startTimer();

      els['question-text'].textContent = data.question_text;
      if (data.subtopic) {
        els['subtopic-chip'].hidden = false;
        els['subtopic-chip'].textContent = data.subtopic;
      }
      appendTranscriptTurn('interviewer', data.question_text);

      return playBase64Audio(data.question_audio_base64);
    })
    .catch((err) => {
      showError(err.message);
    })
    .finally(() => {
      els['btn-start'].disabled = false;
      els['btn-start'].querySelector('span').textContent = 'Begin interview';
    });
}

/* ---------------- Answer mode toggle ---------------- */

function setAnswerMode(mode) {
  els['mode-voice'].classList.toggle('active', mode === 'voice');
  els['mode-text'].classList.toggle('active', mode === 'text');
  els['answer-voice'].hidden = mode !== 'voice';
  els['answer-text'].hidden = mode !== 'text';
}

/* ---------------- Voice recording ---------------- */

async function toggleRecording() {
  if (state.isRecording) {
    state.mediaRecorder.stop();
    return;
  }

  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    showError('Microphone access was denied or is unavailable. Try typing your answer instead.');
    return;
  }

  const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '';
  state.mediaRecorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
  state.audioChunks = [];

  state.mediaRecorder.ondataavailable = (e) => {
    if (e.data.size > 0) state.audioChunks.push(e.data);
  };

  state.mediaRecorder.onstop = () => {
    stream.getTracks().forEach((t) => t.stop());
    setWaveform('idle');
    state.isRecording = false;
    els['btn-record'].setAttribute('aria-pressed', 'false');
    els['record-label'].textContent = 'Start recording';
    els['record-hint'].textContent = 'Transcribing and evaluating your answer…';

    const blob = new Blob(state.audioChunks, { type: mimeType || 'audio/webm' });
    const reader = new FileReader();
    reader.onloadend = () => {
      const base64 = reader.result.split(',')[1];
      submitAnswer({ answer_audio_base64: base64, audio_format: 'webm' });
    };
    reader.readAsDataURL(blob);
  };

  state.mediaRecorder.start();
  state.isRecording = true;
  setWaveform('listening');
  els['btn-record'].setAttribute('aria-pressed', 'true');
  els['record-label'].textContent = 'Stop && send';
  els['record-hint'].textContent = 'Recording… click to stop and send.';
}

/* ---------------- Text answer ---------------- */

function submitTextAnswer() {
  const text = els['f-answer-text'].value.trim();
  if (!text) return;
  els['f-answer-text'].value = '';
  submitAnswer({ answer_text: text });
}

/* ---------------- Submit answer (shared) ---------------- */

function setAnswerControlsDisabled(disabled) {
  els['btn-record'].disabled = disabled;
  els['btn-send-text'].disabled = disabled;
  els['f-answer-text'].disabled = disabled;
}

function submitAnswer(payload) {
  hideError();
  setAnswerControlsDisabled(true);

  apiFetch(`/interviews/${state.interviewId}/answer`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
    .then((data) => {
      if (data.transcribed_text) {
        appendTranscriptTurn('candidate', data.transcribed_text);
      }
      renderEvaluation(data.evaluation);

      state.difficulty = data.difficulty;
      state.questionsAsked = data.questions_asked;
      state.maxQuestions = data.max_questions;
      renderDifficulty();
      renderProgress();

      if (data.is_final) {
        appendTranscriptTurn('interviewer', data.next_question_text);
        return playBase64Audio(data.next_question_audio_base64).then(() => {
          stopTimer();
          loadReport();
        });
      }

      els['question-text'].textContent = data.next_question_text;
      if (data.subtopic) {
        els['subtopic-chip'].hidden = false;
        els['subtopic-chip'].textContent = data.subtopic;
      }
      appendTranscriptTurn('interviewer', data.next_question_text);
      return playBase64Audio(data.next_question_audio_base64);
    })
    .catch((err) => {
      showError(err.message);
    })
    .finally(() => {
      setAnswerControlsDisabled(false);
      els['record-hint'].textContent = 'Click to record, click again to send your answer.';
    });
}

/* ---------------- Report ---------------- */

function loadReport() {
  showView('view-report');
  els['report-name'].textContent = `Feedback for ${state.candidateName}`;

  apiFetch(`/feedback/${state.interviewId}/generate`, { method: 'POST' })
    .then(renderReport)
    .catch((err) => showError(err.message));
}

function renderReport(report) {
  const score = report.overall_score;
  els['score-number'].textContent = score;
  const circumference = 377;
  const offset = circumference - (circumference * score) / 100;
  requestAnimationFrame(() => {
    els['score-fill'].style.strokeDashoffset = offset;
  });
  els['score-fill'].style.stroke = score >= 70 ? 'var(--good)' : score >= 45 ? 'var(--amber)' : 'var(--bad)';

  const recLabel = (report.recommendation || '').replace(/_/g, ' ');
  els['rec-badge'].textContent = recLabel;
  els['rec-badge'].classList.toggle('warn', ['no_hire', 'lean_no_hire'].includes(report.recommendation));

  els['report-summary'].textContent = report.summary;

  els['list-strengths'].innerHTML = '';
  (report.strengths || []).forEach((s) => {
    const li = document.createElement('li');
    li.textContent = s;
    els['list-strengths'].appendChild(li);
  });

  els['list-weaknesses'].innerHTML = '';
  (report.weaknesses || []).forEach((w) => {
    const li = document.createElement('li');
    li.textContent = w;
    els['list-weaknesses'].appendChild(li);
  });

  els['report-comm'].textContent = report.communication_notes;

  els['topic-chips'].innerHTML = '';
  (report.recommended_topics || []).forEach((t) => {
    const chip = document.createElement('span');
    chip.className = 'topic-chip';
    chip.textContent = t;
    els['topic-chips'].appendChild(chip);
  });

  els['breakdown-body'].innerHTML = '';
  (report.per_question_breakdown || []).forEach((row) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${escapeHtml(row.subtopic)}</td><td class="score-cell">${row.score}/10</td><td>${escapeHtml(row.note)}</td>`;
    els['breakdown-body'].appendChild(tr);
  });

  els['btn-download-pdf'].hidden = !report.pdf_available;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function downloadPdf() {
  window.open(`${state.apiBase}/feedback/${state.interviewId}/pdf`, '_blank');
}

function restart() {
  stopTimer();
  Object.assign(state, {
    interviewId: null, sessionToken: null, questionsAsked: 1,
    difficulty: 'easy', isRecording: false,
  });
  els['transcript'].innerHTML = '';
  els['eval-strip'].hidden = true;
  els['topbar-meta'].hidden = true;
  els['meta-timer'].textContent = '00:00';
  showView('view-setup');
}

/* ---------------- Wire up ---------------- */

function init() {
  cacheEls();
  checkBackend();
  setInterval(checkBackend, 15000);

  els['setup-form'].addEventListener('submit', handleSetupSubmit);
  els['mode-voice'].addEventListener('click', () => setAnswerMode('voice'));
  els['mode-text'].addEventListener('click', () => setAnswerMode('text'));
  els['btn-record'].addEventListener('click', toggleRecording);
  els['btn-send-text'].addEventListener('click', submitTextAnswer);
  els['f-answer-text'].addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submitTextAnswer();
  });
  els['btn-download-pdf'].addEventListener('click', downloadPdf);
  els['btn-restart'].addEventListener('click', restart);
  els['error-dismiss'].addEventListener('click', hideError);
}

document.addEventListener('DOMContentLoaded', init);
