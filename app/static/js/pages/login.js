function renderLoginPage() {
  return `
    <div class="auth-page">
      <div class="auth-card">
        <div class="auth-logo">Mazarine</div>
        <div class="auth-subtitle">Your recipe collection, beautifully organised</div>
        <div id="authForm">${loginForm()}</div>
      </div>
    </div>`;
}

function loginForm() {
  return `
    <form onsubmit="doLogin(event)">
      <div class="form-group">
        <label class="form-label">Email or Username</label>
        <input class="form-input" type="text" id="loginEmail" required autocomplete="username">
      </div>
      <div class="form-group">
        <label class="form-label">Password</label>
        <input class="form-input" type="password" id="loginPassword" required autocomplete="current-password">
      </div>
      <button class="btn btn-primary" style="width:100%;margin-top:0.5rem" type="submit">Sign In</button>
    </form>
    <div class="auth-footer">
      Don't have an account? <a href="#" onclick="showRegister()">Create one</a>
    </div>`;
}

function registerForm() {
  return `
    <form onsubmit="doRegister(event)">
      <div class="form-group">
        <label class="form-label">Email</label>
        <input class="form-input" type="email" id="regEmail" required autocomplete="email">
      </div>
      <div class="form-group">
        <label class="form-label">Username</label>
        <input class="form-input" type="text" id="regUsername" required autocomplete="username">
      </div>
      <div class="form-group">
        <label class="form-label">Password</label>
        <input class="form-input" type="password" id="regPassword" required minlength="6" autocomplete="new-password">
      </div>
      <button class="btn btn-primary" style="width:100%;margin-top:0.5rem" type="submit">Create Account</button>
    </form>
    <div class="auth-footer">
      Already have an account? <a href="#" onclick="showLogin()">Sign in</a>
    </div>`;
}

function showRegister() { document.getElementById('authForm').innerHTML = registerForm(); }
function showLogin() { document.getElementById('authForm').innerHTML = loginForm(); }

async function doLogin(e) {
  e.preventDefault();
  try {
    const data = await api.post('/api/auth/login', {
      email_or_username: document.getElementById('loginEmail').value,
      password: document.getElementById('loginPassword').value,
    });
    window.app.user = data.user;
    toast('Welcome back!', 'success');
    app.goto('recipes');
  } catch(err) { toast(err.message, 'error'); }
}

async function doRegister(e) {
  e.preventDefault();
  try {
    const data = await api.post('/api/auth/register', {
      email: document.getElementById('regEmail').value,
      username: document.getElementById('regUsername').value,
      password: document.getElementById('regPassword').value,
    });
    if (data.confirmation_token) {
      await api.get(`/api/auth/confirm/${data.confirmation_token}`);
    }
    toast('Account created! Please sign in.', 'success');
    showLogin();
  } catch(err) { toast(err.message, 'error'); }
}

window.renderLoginPage = renderLoginPage;
window.doLogin = doLogin;
window.doRegister = doRegister;
window.showRegister = showRegister;
window.showLogin = showLogin;
