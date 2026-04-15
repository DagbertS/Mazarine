let _webResults = [];
let _selectedForPreview = new Set();
let _previewedRecipes = [];

async function renderWebSearchPage(query) {
  window._currentPage = 'web-search';
  const content = document.getElementById('pageContent');
  content.innerHTML = `
    <div class="content" style="max-width:1000px">
      <div class="flex-between mb-2">
        <a href="javascript:void(0)" onclick="app.goto('recipes')" class="text-sm text-muted">&larr; Back to recipes</a>
      </div>
      <h1 style="text-align:center;margin-bottom:0.5rem">Discover Recipes</h1>
      <p class="text-muted" style="text-align:center;margin-bottom:1.5rem">Search the web for new recipes to add to your collection</p>

      <div class="flex gap-1" style="max-width:500px;margin:0 auto 2rem">
        <input class="form-input" id="webSearchInput" type="text" placeholder="Search for any recipe..."
               value="${esc(query || '')}"
               onkeydown="if(event.key==='Enter'){doWebSearch()}">
        <button class="btn btn-primary" onclick="doWebSearch()">Search</button>
      </div>

      <div id="webSearchResults"></div>
    </div>`;

  if (query) doWebSearch();
}

async function doWebSearch() {
  const query = document.getElementById('webSearchInput').value.trim();
  if (!query) return;

  const resultsDiv = document.getElementById('webSearchResults');
  resultsDiv.innerHTML = `
    <div style="text-align:center;padding:3rem">
      <div class="spinner" style="margin:0 auto 1rem"></div>
      <p class="text-muted">Searching for "${esc(query)}" recipes...</p>
    </div>`;

  _selectedForPreview = new Set();

  try {
    const data = await api.post('/api/menu/web-search', { query });
    _webResults = data.results || [];
    renderWebResults(query);
  } catch(e) {
    resultsDiv.innerHTML = `
      <div class="empty-state">
        <div class="icon">&#x26A0;</div>
        <h3>Search Failed</h3>
        <p>${esc(e.message)}</p>
        <button class="btn mt-2" onclick="doWebSearch()">Try Again</button>
      </div>`;
  }
}

function renderWebResults(query) {
  const resultsDiv = document.getElementById('webSearchResults');
  if (!_webResults.length) {
    resultsDiv.innerHTML = `
      <div class="empty-state">
        <div class="icon">&#x1F50D;</div>
        <h3>No results found</h3>
        <p>Try a different search term</p>
      </div>`;
    return;
  }

  resultsDiv.innerHTML = `
    <div class="flex-between mb-2">
      <p class="text-sm text-muted">${_webResults.length} recipes found for "${esc(query)}"</p>
      <div class="flex gap-1" id="previewActions" style="display:none">
        <span class="text-sm text-muted" id="selectedCount">0 selected</span>
        <button class="btn btn-sm btn-primary" onclick="previewSelected()">Compare Selected</button>
      </div>
    </div>
    <p class="text-xs text-muted mb-2">Select up to 4 recipes to compare side by side, or add individual recipes directly.</p>

    <div class="web-results-grid">
      ${_webResults.map((r, i) => renderWebResultTile(r, i)).join('')}
    </div>`;
}

function renderWebResultTile(r, index) {
  const photo = r.photo_url || '';
  const selected = _selectedForPreview.has(index);
  return `
    <div class="web-result-tile ${selected ? 'selected' : ''}" id="webTile${index}">
      <div class="web-result-select" onclick="toggleWebSelect(${index})" title="Select to compare">
        <input type="checkbox" ${selected ? 'checked' : ''} tabindex="-1">
      </div>
      ${photo ? `<img class="web-result-img" src="${photo}" alt="${esc(r.title)}" loading="lazy">` :
        `<div class="web-result-img" style="display:flex;align-items:center;justify-content:center;background:var(--bg-hover);color:var(--border);font-size:2rem">&#x1F372;</div>`}
      <div class="web-result-body">
        <div class="web-result-cuisine">${esc(r.cuisine || '')}</div>
        <h3 class="web-result-title">${esc(r.title)}</h3>
        <p class="web-result-desc">${esc(r.description || '')}</p>
        <div class="web-result-meta">
          ${r.total_time_minutes ? `<span>${r.total_time_minutes}m</span>` : ''}
          ${r.difficulty ? `<span>${esc(r.difficulty)}</span>` : ''}
          ${r.servings ? `<span>${r.servings} servings</span>` : ''}
        </div>
        ${r.key_ingredients ? `<div class="web-result-tags">${r.key_ingredients.slice(0,4).map(k => `<span class="tag">${esc(k)}</span>`).join('')}</div>` : ''}
        <button class="btn btn-sm mt-1" onclick="addWebRecipeDirect(${index})">Add to Collection</button>
      </div>
    </div>`;
}

function toggleWebSelect(index) {
  if (_selectedForPreview.has(index)) {
    _selectedForPreview.delete(index);
  } else {
    if (_selectedForPreview.size >= 4) {
      toast('Maximum 4 recipes for comparison', 'error');
      return;
    }
    _selectedForPreview.add(index);
  }

  // Update tile visual
  const tile = document.getElementById(`webTile${index}`);
  if (tile) {
    tile.classList.toggle('selected', _selectedForPreview.has(index));
    const cb = tile.querySelector('input[type="checkbox"]');
    if (cb) cb.checked = _selectedForPreview.has(index);
  }

  // Update actions bar
  const actions = document.getElementById('previewActions');
  const count = document.getElementById('selectedCount');
  if (actions) actions.style.display = _selectedForPreview.size > 0 ? 'flex' : 'none';
  if (count) count.textContent = `${_selectedForPreview.size} selected`;
}

async function previewSelected() {
  if (_selectedForPreview.size === 0) return;

  const titles = Array.from(_selectedForPreview).map(i => _webResults[i].title);
  const content = document.getElementById('webSearchResults');
  content.innerHTML = `
    <div style="text-align:center;padding:3rem">
      <div class="spinner" style="margin:0 auto 1rem"></div>
      <p class="text-muted">Loading full recipes for comparison...</p>
    </div>`;

  try {
    const data = await api.post('/api/menu/web-search/preview', { titles });
    _previewedRecipes = data.recipes || [];
    renderPreviewComparison();
  } catch(e) {
    toast(e.message, 'error');
    renderWebResults('');
  }
}

function renderPreviewComparison() {
  const content = document.getElementById('webSearchResults');
  const count = _previewedRecipes.length;
  const colWidth = count <= 2 ? '1fr 1fr' : count === 3 ? '1fr 1fr 1fr' : '1fr 1fr 1fr 1fr';

  content.innerHTML = `
    <div class="flex-between mb-2">
      <button class="btn btn-sm" onclick="renderWebResults('')">&larr; Back to results</button>
      <button class="btn btn-sm btn-primary" onclick="addSelectedPreviewRecipes()">Add All to Collection</button>
    </div>

    <div class="preview-grid" style="display:grid;grid-template-columns:${colWidth};gap:1rem">
      ${_previewedRecipes.map((r, i) => `
        <div class="preview-card" style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-lg);overflow:hidden">
          ${r.photo_url ? `<img src="${r.photo_url}" style="width:100%;aspect-ratio:4/3;object-fit:cover" alt="">` : ''}
          <div style="padding:1rem">
            <label style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.75rem;cursor:pointer">
              <input type="checkbox" class="preview-check" data-index="${i}" checked>
              <span class="text-xs" style="text-transform:uppercase;letter-spacing:0.08em;color:var(--text-muted)">Add to collection</span>
            </label>
            <h3 style="font-family:var(--font-serif);font-size:1.1rem;margin-bottom:0.4rem">${esc(r.title)}</h3>
            ${r.description ? `<p class="text-sm text-muted" style="font-style:italic;margin-bottom:0.5rem">${esc(r.description)}</p>` : ''}
            <div class="text-xs text-muted mb-1">
              ${r.total_time_minutes ? `${r.total_time_minutes}m` : ''} ${r.servings ? `&middot; ${r.servings} servings` : ''}
            </div>
            <div class="recipe-section-title" style="margin-top:0.75rem">Ingredients</div>
            ${(r.ingredients || []).map(ing =>
              `<div style="font-size:0.8rem;padding:0.15rem 0;border-bottom:1px solid var(--border-light)">
                <strong>${esc(ing.qty)} ${esc(ing.unit)}</strong> ${esc(ing.name)}
              </div>`).join('')}
            <div class="recipe-section-title" style="margin-top:0.75rem">Directions</div>
            ${(r.directions || []).map(d =>
              `<div style="font-size:0.8rem;padding:0.2rem 0;display:flex;gap:0.5rem">
                <span style="color:var(--accent);font-weight:600">${d.step}</span>
                <span>${esc(d.text)}</span>
              </div>`).join('')}
            ${r.nutrition ? `
              <div class="text-xs text-muted mt-1">
                ${r.nutrition.calories || '?'} cal &middot; ${r.nutrition.protein || '?'}g protein
              </div>` : ''}
            <button class="btn btn-sm btn-accent mt-1" style="width:100%" onclick="addSinglePreviewRecipe(${i})">Add This Recipe</button>
          </div>
        </div>`).join('')}
    </div>`;
}

async function addWebRecipeDirect(index) {
  const r = _webResults[index];
  toast(`Getting full recipe for ${r.title}...`, 'info');

  try {
    // Get full recipe details first
    const data = await api.post('/api/menu/web-search/preview', { titles: [r.title] });
    if (!data.recipes || !data.recipes.length) {
      toast('Failed to get recipe details', 'error');
      return;
    }
    const recipe = data.recipes[0];
    recipe.photo_url = r.photo_url || recipe.photo_url;

    // Save with enrichment + duplicate check
    const res = await api.post('/api/menu/web-search/save', { recipes: [recipe] });
    const saved = res.recipes[0];
    if (saved.status === 'duplicate') {
      showDuplicateModal(saved.new_recipe, saved.match);
    } else {
      toast(`Added: ${saved.title}`, 'success');
      if (saved.id) app.goto(`recipe/${saved.id}`);
    }
  } catch(e) {
    toast(e.message, 'error');
  }
}

async function addSinglePreviewRecipe(index) {
  const recipe = _previewedRecipes[index];
  toast(`Saving ${recipe.title}...`, 'info');
  try {
    const res = await api.post('/api/menu/web-search/save', { recipes: [recipe] });
    const saved = res.recipes[0];
    if (saved.status === 'duplicate') {
      showDuplicateModal(saved.new_recipe, saved.match);
    } else {
      toast(`Added: ${saved.title}`, 'success');
    }
  } catch(e) { toast(e.message, 'error'); }
}

async function addSelectedPreviewRecipes() {
  const checks = document.querySelectorAll('.preview-check:checked');
  const indices = Array.from(checks).map(cb => parseInt(cb.dataset.index));
  if (!indices.length) { toast('No recipes selected', 'error'); return; }

  const recipes = indices.map(i => _previewedRecipes[i]);
  toast(`Saving ${recipes.length} recipes...`, 'info');

  try {
    const res = await api.post('/api/menu/web-search/save', { recipes });
    const saved = res.recipes.filter(r => r.status === 'saved');
    const dupes = res.recipes.filter(r => r.status === 'duplicate');
    toast(`Saved ${saved.length} recipe${saved.length !== 1 ? 's' : ''}${dupes.length ? `, ${dupes.length} duplicate(s) skipped` : ''}`, 'success');
  } catch(e) { toast(e.message, 'error'); }
}

window.renderWebSearchPage = renderWebSearchPage;
window.doWebSearch = doWebSearch;
window.toggleWebSelect = toggleWebSelect;
window.previewSelected = previewSelected;
window.addWebRecipeDirect = addWebRecipeDirect;
window.addSinglePreviewRecipe = addSinglePreviewRecipe;
window.addSelectedPreviewRecipes = addSelectedPreviewRecipes;
