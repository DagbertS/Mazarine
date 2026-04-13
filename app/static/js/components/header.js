function renderHeader(user) {
  const isAdmin = user && user.role === 'admin';
  return `
    <header class="header">
      <button class="header-hamburger" onclick="toggleMobileMenu()" aria-label="Menu">
        <span></span><span></span><span></span>
      </button>
      <a class="header-logo" href="javascript:void(0)" onclick="app.goto('home')">
        <img src="/static/img/logo.svg" alt="Mazarine" class="logo-img">
      </a>
      <div class="header-right">
        <div class="search-bar">
          <svg class="search-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="7"/><line x1="16.5" y1="16.5" x2="21" y2="21"/></svg>
          <input type="text" placeholder="Search..." id="globalSearch"
                 onkeydown="handleGlobalSearch(event, this.value)">
        </div>
        <span class="header-user">${user ? user.display_name || user.username : ''}</span>
        ${user ? '<button class="btn btn-sm header-logout" onclick="app.logout()">Logout</button>' : ''}
      </div>
    </header>
    <nav class="nav-bar" id="navBar">
      <a href="javascript:void(0)" onclick="app.goto('recipes');closeMobileMenu()" data-page="recipes">Recipes</a>
      <a href="javascript:void(0)" onclick="app.goto('menu');closeMobileMenu()" data-page="menu">Menu Builder</a>
      <a href="javascript:void(0)" onclick="app.goto('planner');closeMobileMenu()" data-page="planner">Planner</a>
      <a href="javascript:void(0)" onclick="app.goto('shopping');closeMobileMenu()" data-page="shopping">Shopping</a>
      <a href="javascript:void(0)" onclick="app.goto('ingredient-search');closeMobileMenu()" data-page="ingredient-search">By Ingredient</a>
      ${isAdmin ? `<a href="javascript:void(0)" onclick="app.goto('admin');closeMobileMenu()" data-page="admin">Admin</a>` : ''}
    </nav>`;
}

function updateActiveNav(page) {
  document.querySelectorAll('.nav-bar a').forEach(a => {
    a.classList.toggle('active', a.dataset.page === page);
  });
}

function toggleMobileMenu() {
  const nav = document.getElementById('navBar');
  const burger = document.querySelector('.header-hamburger');
  if (nav) nav.classList.toggle('open');
  if (burger) burger.classList.toggle('open');
}

function closeMobileMenu() {
  const nav = document.getElementById('navBar');
  const burger = document.querySelector('.header-hamburger');
  if (nav) nav.classList.remove('open');
  if (burger) burger.classList.remove('open');
}

window.renderHeader = renderHeader;
window.updateActiveNav = updateActiveNav;
window.toggleMobileMenu = toggleMobileMenu;
window.closeMobileMenu = closeMobileMenu;
