const _timers = [];

function startTimer(label, minutes) {
  const id = Date.now();
  const timer = { id, label, total: minutes * 60, remaining: minutes * 60, running: true, interval: null };
  timer.interval = setInterval(() => {
    if (!timer.running) return;
    timer.remaining--;
    renderTimerBar();
    if (timer.remaining <= 0) {
      clearInterval(timer.interval);
      timer.running = false;
      timerDone(timer);
    }
  }, 1000);
  _timers.push(timer);
  renderTimerBar();
  toast(`Timer started: ${label} (${minutes}m)`, 'info');
}

function timerDone(timer) {
  renderTimerBar();
  toast(`Timer done: ${timer.label}`, 'success');
  if ('Notification' in window && Notification.permission === 'granted') {
    new Notification('Mazarine Timer', { body: `${timer.label} is done!` });
  }
  try { const audio = new Audio('data:audio/wav;base64,UklGRl9vT19teleXRlZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQ=='); audio.play().catch(()=>{}); } catch(e){}
}

function pauseTimer(id) {
  const t = _timers.find(t => t.id === id);
  if (t) { t.running = !t.running; renderTimerBar(); }
}

function removeTimer(id) {
  const idx = _timers.findIndex(t => t.id === id);
  if (idx >= 0) { clearInterval(_timers[idx].interval); _timers.splice(idx, 1); renderTimerBar(); }
}

function formatTime(secs) {
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function renderTimerBar() {
  let bar = document.getElementById('timerBar');
  if (_timers.length === 0) {
    if (bar) bar.remove();
    return;
  }
  if (!bar) {
    bar = document.createElement('div');
    bar.id = 'timerBar';
    bar.className = 'timer-bar';
    document.body.appendChild(bar);
  }
  bar.innerHTML = _timers.map(t => `
    <div class="timer-pill ${t.running ? 'running' : ''} ${t.remaining <= 0 ? 'done' : ''}">
      <span>${esc(t.label)}</span>
      <span class="time">${formatTime(Math.max(0, t.remaining))}</span>
      ${t.remaining > 0 ? `<button class="btn-icon" onclick="pauseTimer(${t.id})" style="color:inherit">${t.running ? '&#x23F8;' : '&#x25B6;'}</button>` : ''}
      <button class="btn-icon" onclick="removeTimer(${t.id})" style="color:inherit">&#x2715;</button>
    </div>
  `).join('');
}

if ('Notification' in window && Notification.permission === 'default') {
  Notification.requestPermission();
}

window.startTimer = startTimer;
window.pauseTimer = pauseTimer;
window.removeTimer = removeTimer;
