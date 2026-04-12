function renderHeader(user) {
  const isAdmin = user && user.role === 'admin';
  return `
    <header class="header">
      <a class="header-logo" href="javascript:void(0)" onclick="app.goto('home')">Mazarine</a>
      <nav class="header-nav">
        <a href="javascript:void(0)" onclick="app.goto('recipes')" data-page="recipes">Recipes</a>
        <a href="javascript:void(0)" onclick="app.goto('menu')" data-page="menu">Menu Builder</a>
        <a href="javascript:void(0)" onclick="app.goto('planner')" data-page="planner">Planner</a>
        <a href="javascript:void(0)" onclick="app.goto('shopping')" data-page="shopping">Shopping</a>
        ${isAdmin ? `<a href="javascript:void(0)" onclick="app.goto('admin')" data-page="admin">Admin</a>` : ''}
      </nav>
      <div class="header-actions">
        <div class="search-bar">
          <span class="search-icon">&#x1F50D;</span>
          <input type="text" placeholder="Search recipes or ingredients..." id="globalSearch"
                 onkeydown="handleGlobalSearch(event, this.value)">
        </div>
        <span class="header-user">${user ? user.display_name || user.username : ''}</span>
        ${user ? '<button class="btn btn-sm" onclick="app.logout()">Logout</button>' : ''}
      </div>
    </header>`;
}

function updateActiveNav(page) {
  document.querySelectorAll('.header-nav a').forEach(a => {
    a.classList.toggle('active', a.dataset.page === page);
  });
}

window.renderHeader = renderHeader;
window.updateActiveNav = updateActiveNav;
