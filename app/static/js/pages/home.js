async function renderHomePage() {
  window._currentPage = 'home';
  const content = document.getElementById('pageContent');
  content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
  try {
    const [recipes, cats, tags] = await Promise.all([
      api.get('/api/recipes?limit=12&sort=updated_at'),
      api.get('/api/categories'),
      api.get('/api/tags'),
    ]);
    const pinned = recipes.recipes.filter(r => r.is_pinned);
    const favourites = recipes.recipes.filter(r => r.is_favourite);
    const recent = recipes.recipes.slice(0, 8);

    content.innerHTML = `
      <div class="main-layout">
        ${renderSidebar(cats.categories, tags.tags)}
        <div class="content">
          <div class="page-header">
            <div>
              <h1>Good ${getGreeting()}</h1>
              <p class="page-subtitle">${recipes.total} recipes in your collection</p>
            </div>
            <div class="flex gap-1">
              <button class="btn" onclick="showImportModal()">Import URL</button>
              <button class="btn btn-primary" onclick="app.goto('recipe/new')">New Recipe</button>
            </div>
          </div>

          ${pinned.length ? `
            <div class="recipe-section">
              <h3 class="recipe-section-title">Pinned</h3>
              <div class="recipe-grid">${pinned.map(recipeCard).join('')}</div>
            </div>` : ''}

          ${favourites.length ? `
            <div class="recipe-section">
              <h3 class="recipe-section-title">Favourites</h3>
              <div class="recipe-grid">${favourites.map(recipeCard).join('')}</div>
            </div>` : ''}

          <div class="recipe-section">
            <h3 class="recipe-section-title">Recently Updated</h3>
            ${recent.length
              ? `<div class="recipe-grid">${recent.map(recipeCard).join('')}</div>`
              : `<div class="empty-state">
                  <div class="icon">&#x1F4D6;</div>
                  <h3>Your recipe collection is empty</h3>
                  <p>Import a recipe from a URL or create one from scratch</p>
                  <button class="btn btn-primary mt-2" onclick="app.goto('recipe/new')">Create Recipe</button>
                </div>`}
          </div>
        </div>
      </div>`;
  } catch(e) { content.innerHTML = `<p class="text-muted" style="padding:2rem">Error loading: ${esc(e.message)}</p>`; }
}

function renderSidebar(categories, tags) {
  const catItems = (categories || []).map(c => {
    let html = `<div class="sidebar-item" onclick="app.goto('recipes','?category_id=${c.id}')">
      ${esc(c.name)}
    </div>`;
    if (c.children && c.children.length) {
      html += c.children.map(sub =>
        `<div class="sidebar-item" style="padding-left:2rem" onclick="app.goto('recipes','?category_id=${sub.id}')">
          ${esc(sub.name)}</div>`
      ).join('');
    }
    return html;
  }).join('');

  const tagItems = (tags || []).slice(0, 15).map(t =>
    `<div class="sidebar-item" onclick="app.goto('recipes','?tag=${encodeURIComponent(t.name)}')">
      ${esc(t.name)} <span class="count">${t.recipe_count || 0}</span>
    </div>`
  ).join('');

  return `
    <aside class="sidebar">
      <div class="sidebar-section">
        <div class="sidebar-title">Quick Access</div>
        <div class="sidebar-item" onclick="app.goto('recipes')">All Recipes</div>
        <div class="sidebar-item" onclick="app.goto('recipes','?favourites=true')">Favourites</div>
        <div class="sidebar-item" onclick="app.goto('ingredient-search')">Search by Ingredient</div>
        <div class="sidebar-item" onclick="app.goto('menu')">Menu Builder</div>
      </div>
      ${catItems ? `<div class="sidebar-section">
        <div class="sidebar-title">Categories</div>
        ${catItems}
        <div class="sidebar-item text-muted" onclick="showCategoryModal()">+ Add Category</div>
      </div>` : `<div class="sidebar-section">
        <div class="sidebar-title">Categories</div>
        <div class="sidebar-item text-muted" onclick="showCategoryModal()">+ Add Category</div>
      </div>`}
      ${tagItems ? `<div class="sidebar-section">
        <div class="sidebar-title">Tags</div>
        ${tagItems}
      </div>` : ''}
    </aside>`;
}

function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return 'morning';
  if (h < 17) return 'afternoon';
  return 'evening';
}

function showImportModal() {
  showModal('Import Recipe from URL',
    `<div class="form-group">
       <label class="form-label">Recipe URL</label>
       <input class="form-input" id="importUrl" type="url" placeholder="https://..." required>
     </div>
     <p class="form-hint">Paste a link from any recipe website. We'll extract the recipe automatically.</p>`,
    `<button class="btn" onclick="closeModal()">Cancel</button>
     <button class="btn btn-primary" onclick="doImport()">Import</button>`);
}

async function doImport() {
  const url = document.getElementById('importUrl').value;
  if (!url) return;
  toast('Importing recipe...', 'info');
  closeModal();
  try {
    const data = await api.post('/api/import', { url, auto_save: true });

    // Check if duplicate was detected
    if (data.duplicate_action_required && data.duplicates && data.duplicates.length > 0) {
      // Show side-by-side comparison modal
      showDuplicateModal(data, data.duplicates[0]);
      return;
    }

    toast(`Imported: ${data.title}`, 'success');
    if (data.id) app.goto(`recipe/${data.id}`);
    else app.goto('recipes');
  } catch(e) { toast(`Import failed: ${e.message}`, 'error'); }
}

function showCategoryModal() {
  showModal('New Category',
    `<div class="form-group">
       <label class="form-label">Name</label>
       <input class="form-input" id="newCatName" required>
     </div>`,
    `<button class="btn" onclick="closeModal()">Cancel</button>
     <button class="btn btn-primary" onclick="createCategory()">Create</button>`);
}

async function createCategory() {
  const name = document.getElementById('newCatName').value;
  if (!name) return;
  try {
    await api.post('/api/categories', { name });
    closeModal();
    toast('Category created', 'success');
    renderHomePage();
  } catch(e) { toast(e.message, 'error'); }
}

window.renderHomePage = renderHomePage;
window.showImportModal = showImportModal;
window.doImport = doImport;
window.showCategoryModal = showCategoryModal;
window.createCategory = createCategory;
