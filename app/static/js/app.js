window.app = {
  user: null,

  async init() {
    try {
      const data = await api.get('/api/auth/me');
      this.user = data.user;
    } catch(e) {
      this.user = null;
    }
    this.route();
    window.addEventListener('popstate', () => this.route());
  },

  goto(page, params) {
    const path = params ? `${page}${params}` : page;
    history.pushState({}, '', `#${path}`);
    this.route();
  },

  route() {
    const hash = location.hash.slice(1) || 'home';
    const root = document.getElementById('app');

    // Clean up any leftover modal overlays or stale UI from previous routes
    closeModal();
    const staleOverlay = document.getElementById('modalOverlay');
    if (staleOverlay) staleOverlay.remove();

    if (!this.user && hash !== 'login' && !hash.startsWith('confirm/')) {
      root.innerHTML = renderLoginPage();
      return;
    }

    if (hash === 'login') {
      root.innerHTML = renderLoginPage();
      return;
    }

    if (hash.startsWith('confirm/')) {
      const token = hash.split('/')[1];
      api.get(`/api/auth/confirm/${token}`).then(() => {
        toast('Email confirmed! Please sign in.', 'success');
        this.goto('login');
      }).catch(e => toast(e.message, 'error'));
      return;
    }

    root.innerHTML = `
      ${renderHeader(this.user)}
      <div id="pageContent"></div>`;

    updateActiveNav(hash.split('/')[0].split('?')[0]);

    if (hash === 'home' || hash === '') {
      renderHomePage();
    } else if (hash.startsWith('recipes')) {
      const params = hash.includes('?') ? hash.substring(hash.indexOf('?')) : '';
      renderRecipesPage(params);
    } else if (hash.startsWith('recipe/new')) {
      renderRecipeEdit(null);
    } else if (hash.startsWith('recipe/edit/')) {
      const id = hash.split('/')[2];
      renderRecipeEdit(id);
    } else if (hash.startsWith('recipe/')) {
      const id = hash.split('/')[1];
      renderRecipeDetail(id);
    } else if (hash.startsWith('cooking/')) {
      const id = hash.split('/')[1];
      renderCookingMode(id);
    } else if (hash === 'menu' || hash.startsWith('menu')) {
      renderMenuBuilderPage();
    } else if (hash.startsWith('ingredient-search')) {
      const params = hash.includes('?') ? hash.substring(hash.indexOf('?')) : '';
      renderIngredientSearchPage(params);
    } else if (hash.startsWith('web-search')) {
      const params = hash.includes('?') ? hash.substring(hash.indexOf('?')) : '';
      const q = new URLSearchParams(params).get('q') || '';
      renderWebSearchPage(q);
    } else if (hash === 'planner') {
      renderPlannerPage();
    } else if (hash === 'shopping') {
      renderShoppingPage();
    } else if (hash === 'admin') {
      renderAdminPage();
    } else {
      document.getElementById('pageContent').innerHTML =
        '<div class="empty-state"><h3>Page not found</h3></div>';
    }
  },

  async logout() {
    try { await api.post('/api/auth/logout'); } catch(e) {}
    this.user = null;
    this.goto('login');
  }
};

function handleGlobalSearch(e, value) {
  if (e.key !== 'Enter' || !value.trim()) return;
  // If prefixed with "ing:" or "ingredient:", treat as ingredient search
  if (value.startsWith('ing:') || value.startsWith('ingredient:')) {
    const ingredients = value.replace(/^(ing:|ingredient:)\s*/, '');
    app.goto('ingredient-search', '?ingredients=' + encodeURIComponent(ingredients));
  } else {
    app.goto('recipes', '?q=' + encodeURIComponent(value));
  }
}

window.handleGlobalSearch = handleGlobalSearch;

document.addEventListener('DOMContentLoaded', () => app.init());
