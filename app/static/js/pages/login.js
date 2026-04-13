let _pendingEmail = '';
let _authView = 'login'; // 'login', 'register', 'verify'

function renderLoginPage() {
  // Preserve the current auth view state across re-renders
  let formHtml;
  if (_authView === 'register') {
    formHtml = registerForm();
  } else if (_authView === 'verify') {
    formHtml = verificationForm(_pendingEmail);
  } else {
    formHtml = loginForm();
  }

  return `
    <div class="auth-page">
      <div class="auth-card">
        <div class="auth-logo">Mazarine</div>
        <div class="auth-subtitle">A Personal Cookbook</div>
        <div id="authForm">${formHtml}</div>
      </div>
    </div>`;
}

/* ── Login Form ── */
function loginForm() {
  return `
    <form onsubmit="doLogin(event)">
      <div class="form-group">
        <label class="form-label">Email</label>
        <input class="form-input" type="email" id="loginEmail" required autocomplete="email" placeholder="you@example.com">
      </div>
      <div class="form-group">
        <label class="form-label">Password</label>
        <input class="form-input" type="password" id="loginPassword" required autocomplete="current-password">
      </div>
      <div id="loginError" style="color:var(--danger);font-size:0.85rem;margin-bottom:0.75rem;display:none"></div>
      <button class="btn btn-primary" style="width:100%;margin-top:0.5rem" type="submit">Sign In</button>
    </form>
    <div class="auth-footer">
      Don't have an account? <a href="javascript:void(0)" onclick="showRegister()">Create one</a>
    </div>`;
}

/* ── Register Form ── */
function registerForm() {
  return `
    <form onsubmit="doRegister(event)">
      <div class="form-group">
        <label class="form-label">Email Address</label>
        <input class="form-input" type="email" id="regEmail" required autocomplete="email" placeholder="you@example.com">
        <p class="form-hint">This will also be your username</p>
      </div>
      <div class="form-group">
        <label class="form-label">Choose a Password</label>
        <input class="form-input" type="password" id="regPassword" required minlength="6" autocomplete="new-password">
        <p class="form-hint">At least 6 characters</p>
      </div>
      <div id="regError" style="color:var(--danger);font-size:0.85rem;margin-bottom:0.75rem;display:none"></div>
      <button class="btn btn-primary" style="width:100%;margin-top:0.5rem" type="submit">Create Account</button>
    </form>
    <div class="auth-footer">
      Already have an account? <a href="javascript:void(0)" onclick="showLogin()">Sign in</a>
    </div>`;
}

/* ── Verification Code Form ── */
function verificationForm(email) {
  return `
    <div style="text-align:center;margin-bottom:1.5rem">
      <div style="font-size:2rem;margin-bottom:0.5rem">&#x2709;</div>
      <p>We sent a 6-digit confirmation code to</p>
      <p style="font-weight:600;margin-bottom:0.25rem">${esc(email || '...')}</p>
      <p class="text-sm text-muted">Check your inbox and enter the code below</p>
    </div>
    <form onsubmit="doVerify(event)">
      <div class="form-group">
        <label class="form-label">Confirmation Code</label>
        <input class="form-input" type="text" id="verifyCode" required maxlength="6" pattern="[0-9]{6}"
               placeholder="000000" autocomplete="one-time-code" inputmode="numeric"
               style="text-align:center;font-size:1.5rem;letter-spacing:0.5em;font-family:var(--font-mono)">
      </div>
      <div id="verifyError" style="color:var(--danger);font-size:0.85rem;margin-bottom:0.75rem;display:none"></div>
      <button class="btn btn-primary" style="width:100%;margin-top:0.5rem" type="submit">Verify & Activate</button>
    </form>
    <div class="auth-footer">
      Didn't receive it? <a href="javascript:void(0)" onclick="resendCode()">Resend code</a>
      <br><br>
      <a href="javascript:void(0)" onclick="showLogin()" style="color:var(--text-muted)">Back to sign in</a>
    </div>`;
}

function showRegister() {
  _authView = 'register';
  document.getElementById('authForm').innerHTML = registerForm();
}

function showLogin() {
  _authView = 'login';
  _pendingEmail = '';
  document.getElementById('authForm').innerHTML = loginForm();
}

function showVerify(email) {
  _authView = 'verify';
  _pendingEmail = email;
  document.getElementById('authForm').innerHTML = verificationForm(email);
}

/* ── Login Action ── */
async function doLogin(e) {
  e.preventDefault();
  const errEl = document.getElementById('loginError');
  errEl.style.display = 'none';
  try {
    const data = await api.post('/api/auth/login', {
      email_or_username: document.getElementById('loginEmail').value,
      password: document.getElementById('loginPassword').value,
    });
    window.app.user = data.user;
    _authView = 'login'; // reset for next time
    toast('Welcome back!', 'success');
    app.goto('home');
  } catch(err) {
    if (err.message && err.message.includes('not yet verified')) {
      _pendingEmail = document.getElementById('loginEmail').value;
      showVerify(_pendingEmail);
      toast('Please verify your account first', 'info');
    } else {
      errEl.textContent = err.message || 'Invalid credentials';
      errEl.style.display = 'block';
    }
  }
}

/* ── Register Action ── */
async function doRegister(e) {
  e.preventDefault();
  const errEl = document.getElementById('regError');
  errEl.style.display = 'none';
  const email = document.getElementById('regEmail').value.trim();
  const password = document.getElementById('regPassword').value;
  try {
    const data = await api.post('/api/auth/register', { email, password });
    toast('Confirmation code sent to your email!', 'success');
    showVerify(email);
    // In dev mode, show the code for testing
    if (data._dev_code) {
      setTimeout(() => toast(`Dev code: ${data._dev_code}`, 'info'), 500);
    }
  } catch(err) {
    errEl.textContent = err.message || 'Registration failed';
    errEl.style.display = 'block';
  }
}

/* ── Verify Action ── */
async function doVerify(e) {
  e.preventDefault();
  const errEl = document.getElementById('verifyError');
  errEl.style.display = 'none';
  const code = document.getElementById('verifyCode').value.trim();
  try {
    await api.post('/api/auth/confirm', { code });
    toast('Account verified! Please sign in.', 'success');
    _authView = 'login';
    showLogin();
    // Pre-fill email
    setTimeout(() => {
      const emailInput = document.getElementById('loginEmail');
      if (emailInput && _pendingEmail) emailInput.value = _pendingEmail;
    }, 100);
  } catch(err) {
    errEl.textContent = err.message || 'Invalid code. Please try again.';
    errEl.style.display = 'block';
  }
}

/* ── Resend Code ── */
async function resendCode() {
  if (!_pendingEmail) { toast('No email to resend to', 'error'); return; }
  try {
    const data = await api.post('/api/auth/resend-code', { email: _pendingEmail });
    toast('New code sent!', 'success');
    if (data._dev_code) {
      setTimeout(() => toast(`Dev code: ${data._dev_code}`, 'info'), 500);
    }
  } catch(err) {
    toast(err.message || 'Failed to resend', 'error');
  }
}

window.renderLoginPage = renderLoginPage;
window.doLogin = doLogin;
window.doRegister = doRegister;
window.doVerify = doVerify;
window.showRegister = showRegister;
window.showLogin = showLogin;
window.showVerify = showVerify;
window.resendCode = resendCode;
