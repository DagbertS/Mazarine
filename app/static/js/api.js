const API = '';

async function apiGet(path) {
  const res = await fetch(API + path, { credentials: 'include' });
  if (res.status === 401) { window.app.goto('login'); throw new Error('Not authenticated'); }
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || res.statusText); }
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(API + path, {
    method: 'POST', credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (res.status === 401) { window.app.goto('login'); throw new Error('Not authenticated'); }
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || res.statusText); }
  return res.json();
}

async function apiPut(path, body) {
  const res = await fetch(API + path, {
    method: 'PUT', credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (res.status === 401) { window.app.goto('login'); throw new Error('Not authenticated'); }
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || res.statusText); }
  return res.json();
}

async function apiDelete(path) {
  const res = await fetch(API + path, { method: 'DELETE', credentials: 'include' });
  if (res.status === 401) { window.app.goto('login'); throw new Error('Not authenticated'); }
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || res.statusText); }
  return res.json();
}

async function apiUpload(path, file) {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(API + path, { method: 'POST', credentials: 'include', body: form });
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || res.statusText); }
  return res.json();
}

window.api = { get: apiGet, post: apiPost, put: apiPut, del: apiDelete, upload: apiUpload };
