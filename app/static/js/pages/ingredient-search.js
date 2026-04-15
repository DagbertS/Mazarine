async function renderIngredientSearchPage(params) {
  window._currentPage = 'ingredient-search';
  const content = document.getElementById('pageContent');
  const sp = new URLSearchParams(params || '');
  const prefilledIngredients = sp.get('ingredients') || '';

  content.innerHTML = `
    <div class="content" style="max-width:900px">
      <div class="page-header">
        <div>
          <h1>Search by Ingredient</h1>
          <p class="page-subtitle">Find recipes that use specific ingredients</p>
        </div>
      </div>

      <div class="form-group">
        <label class="form-label">Ingredients</label>
        <div class="flex gap-1">
          <input class="form-input" id="ingredientInput" placeholder="Type an ingredient and press Enter or comma..."
                 value="${esc(prefilledIngredients)}"
                 onkeydown="handleIngredientKey(event)">
          <button class="btn btn-primary" onclick="doIngredientSearch()">Search</button>
        </div>
        <p class="form-hint">Separate multiple ingredients with commas</p>
      </div>

      <div class="form-group">
        <label style="font-size:0.85rem;cursor:pointer;display:inline-flex;align-items:center;gap:0.4rem">
          <input type="checkbox" id="matchAll"> Must contain ALL ingredients
        </label>
      </div>

      <div id="ingredientResults" class="mt-2"></div>
    </div>`;

  if (prefilledIngredients) {
    doIngredientSearch();
  }
}

function handleIngredientKey(e) {
  if (e.key === 'Enter') {
    e.preventDefault();
    doIngredientSearch();
  }
}

async function doIngredientSearch() {
  const input = document.getElementById('ingredientInput').value;
  if (!input.trim()) return;

  const ingredients = input.split(',').map(s => s.trim()).filter(Boolean);
  const matchAll = document.getElementById('matchAll').checked;
  const resultsDiv = document.getElementById('ingredientResults');
  resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const data = await api.post('/api/menu/search-by-ingredient', { ingredients, match_all: matchAll });
    const recipes = data.recipes || [];

    if (recipes.length === 0) {
      resultsDiv.innerHTML = `
        <div class="empty-state">
          <div class="icon">&#x1F50D;</div>
          <h3>No recipes found</h3>
          <p>No recipes contain ${matchAll ? 'all of' : 'any of'}: ${ingredients.map(i => `<strong>${esc(i)}</strong>`).join(', ')}</p>
        </div>`;
      return;
    }

    resultsDiv.innerHTML = `
      <p class="text-sm text-muted mb-2">${recipes.length} recipe${recipes.length !== 1 ? 's' : ''} found matching: ${data.searched_ingredients.map(i => `<strong>${esc(i)}</strong>`).join(', ')}</p>
      <div class="recipe-grid">
        ${recipes.map(r => {
          const matchedBadges = (r._matched_ingredients || []).map(m =>
            `<span class="tag" style="background:#E8F5E9;color:var(--success)">${esc(m)}</span>`).join('');
          const photo = r.photo_urls && r.photo_urls.length > 0 ? r.photo_urls[0] : null;
          const time = r.total_time_minutes || r.cook_time_minutes;
          const tags = (r.tags || []).slice(0, 3);

          return `
            <div class="recipe-card" onclick="app.goto('recipe/${r.id}')">
              ${photo
                ? `<img class="recipe-card-img" src="${photo}" alt="${esc(r.title)}" loading="lazy">`
                : `<div class="recipe-card-img placeholder">&#x1F372;</div>`}
              <div class="recipe-card-body">
                <div class="recipe-card-title">${esc(r.title)}</div>
                <div class="recipe-card-meta">
                  ${time ? `<span>${time} min</span>` : ''}
                  ${r.servings ? `<span>${r.servings} servings</span>` : ''}
                  <span class="text-sm" style="color:var(--success)">${r._match_count}/${data.searched_ingredients.length} matched</span>
                </div>
                <div class="recipe-card-tags mt-1">
                  ${matchedBadges}
                  ${tags.map(t => `<span class="tag">${esc(t.name)}</span>`).join('')}
                </div>
              </div>
            </div>`;
        }).join('')}
      </div>
      <div style="text-align:center;padding:2rem 0;margin-top:1.5rem;border-top:1px solid var(--border)">
        <p class="text-muted" style="margin-bottom:0.75rem">Didn't find what you're looking for?</p>
        <button class="btn" onclick="app.goto('web-search','?q=${encodeURIComponent(ingredients.join(' '))}')">Search the Web</button>
      </div>`;
  } catch(e) {
    resultsDiv.innerHTML = `<p style="color:var(--danger)">Error: ${esc(e.message)}</p>`;
  }
}

window.renderIngredientSearchPage = renderIngredientSearchPage;
window.doIngredientSearch = doIngredientSearch;
window.handleIngredientKey = handleIngredientKey;
