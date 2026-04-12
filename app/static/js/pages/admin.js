async function renderAdminPage() {
  window._currentPage = 'admin';
  const content = document.getElementById('pageContent');
  content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
  try {
    const [stats, users, activity] = await Promise.all([
      api.get('/api/admin/stats'),
      api.get('/api/admin/users'),
      api.get('/api/admin/activity?limit=30'),
    ]);

    content.innerHTML = `
      <div class="content" style="max-width:1100px">
        <div class="page-header">
          <div>
            <h1>Administration</h1>
            <p class="page-subtitle">User management and platform overview</p>
          </div>
        </div>

        <div class="admin-stats">
          <div class="stat-card">
            <div class="label">Total Users</div>
            <div class="value">${stats.total_users}</div>
          </div>
          <div class="stat-card">
            <div class="label">Active Users</div>
            <div class="value">${stats.active_users}</div>
          </div>
          <div class="stat-card">
            <div class="label">Total Recipes</div>
            <div class="value">${stats.total_recipes}</div>
          </div>
          <div class="stat-card">
            <div class="label">Total Logins</div>
            <div class="value">${stats.total_logins}</div>
          </div>
        </div>

        <h2 class="mb-2">Users</h2>
        <table class="admin-table">
          <thead>
            <tr>
              <th>Username</th>
              <th>Email</th>
              <th>Role</th>
              <th>Status</th>
              <th>Logins</th>
              <th>Last Login</th>
              <th>Recipes</th>
              <th>Last Search</th>
              <th>Uploads</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${users.users.map(u => `
              <tr>
                <td><strong>${esc(u.username)}</strong></td>
                <td>${esc(u.email)}</td>
                <td><span class="tag">${u.role}</span></td>
                <td><span class="status-badge status-${u.status}">${u.status}</span></td>
                <td>${u.login_count || 0}</td>
                <td>${u.last_login ? new Date(u.last_login).toLocaleDateString() : '-'}</td>
                <td>${u.recipe_count || '-'}</td>
                <td>${u.last_search ? esc(u.last_search) : '-'}</td>
                <td>${u.upload_count || 0}</td>
                <td>
                  <div class="flex gap-1">
                    ${u.status === 'blocked'
                      ? `<button class="btn btn-sm" onclick="adminAction('unblock','${u.id}')">Unblock</button>`
                      : `<button class="btn btn-sm btn-danger" onclick="adminAction('block','${u.id}')">Block</button>`}
                    <button class="btn btn-sm" onclick="adminAction('reset-password','${u.id}')">Reset PW</button>
                    <button class="btn btn-sm" onclick="adminToggle('${u.id}','upload',${u.can_upload})">${u.can_upload ? 'Disable' : 'Enable'} Upload</button>
                    <button class="btn btn-sm" onclick="adminToggle('${u.id}','download',${u.can_download})">${u.can_download ? 'Disable' : 'Enable'} Download</button>
                  </div>
                </td>
              </tr>`).join('')}
          </tbody>
        </table>

        <h2 class="mt-3 mb-2">Recent Activity</h2>
        <table class="admin-table">
          <thead><tr><th>Time</th><th>User</th><th>Action</th><th>Details</th></tr></thead>
          <tbody>
            ${activity.activities.map(a => `
              <tr>
                <td class="text-sm">${new Date(a.timestamp).toLocaleString()}</td>
                <td>${esc(a.username || a.user_id || '-')}</td>
                <td><span class="tag">${esc(a.action)}</span></td>
                <td class="text-sm text-muted">${esc(typeof a.details === 'string' ? a.details : JSON.stringify(a.details || {})).substring(0,80)}</td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  } catch(e) { content.innerHTML = `<p style="padding:2rem">Error: ${esc(e.message)}</p>`; }
}

async function adminAction(action, userId) {
  try {
    if (action === 'reset-password') {
      const res = await api.post(`/api/admin/users/${userId}/reset-password`);
      alert(`New password: ${res.new_password}`);
    } else if (action === 'block') {
      if (!confirm('Block this user?')) return;
      await api.post(`/api/admin/users/${userId}/block`);
      toast('User blocked', 'success');
    } else if (action === 'unblock') {
      await api.post(`/api/admin/users/${userId}/unblock`);
      toast('User unblocked', 'success');
    }
    renderAdminPage();
  } catch(e) { toast(e.message, 'error'); }
}

async function adminToggle(userId, field, current) {
  try {
    const body = {};
    body[`can_${field}`] = !current;
    await api.put(`/api/admin/users/${userId}`, body);
    toast(`${field} ${current ? 'disabled' : 'enabled'}`, 'success');
    renderAdminPage();
  } catch(e) { toast(e.message, 'error'); }
}

window.renderAdminPage = renderAdminPage;
window.adminAction = adminAction;
window.adminToggle = adminToggle;
