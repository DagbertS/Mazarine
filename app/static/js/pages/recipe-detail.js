async function renderRecipeDetail(recipeId) {
  window._currentPage = 'recipe-detail';
  const content = document.getElementById('pageContent');
  content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
  try {
    const r = await api.get(`/api/recipes/${recipeId}`);
    const photo = r.photo_urls && r.photo_urls.length ? r.photo_urls[0] : null;
    const ingredients = r.ingredients || [];
    const directions = r.directions || [];
    const nutrition = r.nutrition || {};
    const cats = (r.categories || []).map(c => `<span class="tag">${esc(c.name)}</span>`).join(' ');
    const tags = (r.tags || []).map(t => `<span class="tag ${t.type==='dietary'?'dietary':''}">${esc(t.name)}</span>`).join(' ');
    const linked = (r.linked_recipes || []).map(l =>
      `<a href="#" onclick="app.goto('recipe/${l.id}')" style="color:var(--accent)">${esc(l.title)}</a>`).join(', ');

    content.innerHTML = `
      <div class="content">
        <div class="recipe-detail">
          <div class="flex-between mb-2">
            <a href="#" onclick="app.goto('recipes')" class="text-sm text-muted">&larr; Back to recipes</a>
            <div class="flex gap-1">
              <button class="btn btn-sm" onclick="app.goto('cooking/${recipeId}')">Cook Mode</button>
              <button class="btn btn-sm" onclick="addToShoppingList('${recipeId}')">Add to List</button>
              <button class="btn btn-sm" onclick="enrichRecipe('${recipeId}')">AI Enrich</button>
              <button class="btn btn-sm" onclick="app.goto('recipe/edit/${recipeId}')">Edit</button>
              <button class="btn btn-sm btn-danger" onclick="deleteRecipe('${recipeId}')">Delete</button>
            </div>
          </div>

          ${photo ? `<img class="recipe-hero" src="${photo}" alt="${esc(r.title)}">` : ''}

          <div class="flex-between">
            <h1 class="recipe-title">${esc(r.title)}</h1>
            <div class="flex gap-1" style="align-items:center">
              <button class="fav-btn ${r.is_favourite?'active':''}" onclick="toggleFav('${r.id}',${r.is_favourite})">&#x2665;</button>
              ${renderStarsInput(r.rating || 0, r.id)}
            </div>
          </div>
          ${r.description ? `<p class="recipe-description">${esc(r.description)}</p>` : ''}
          ${cats || tags ? `<div class="flex gap-1 mb-2">${cats} ${tags}</div>` : ''}
          ${r.source_url ? `<p class="text-sm text-muted">Source: <a href="${esc(r.source_url)}" target="_blank">${esc(r.source_name || r.source_url)}</a></p>` : ''}

          <div class="recipe-meta-bar">
            ${r.prep_time_minutes ? `<div class="recipe-meta-item"><span class="label">Prep</span><span class="value">${r.prep_time_minutes}m</span></div>` : ''}
            ${r.cook_time_minutes ? `<div class="recipe-meta-item"><span class="label">Cook</span><span class="value">${r.cook_time_minutes}m</span></div>` : ''}
            ${r.total_time_minutes ? `<div class="recipe-meta-item"><span class="label">Total</span><span class="value">${r.total_time_minutes}m</span></div>` : ''}
            ${r.servings ? `<div class="recipe-meta-item">
              <span class="label">Servings</span>
              <div class="scaler">
                <button onclick="scaleView('${recipeId}', -1)">-</button>
                <span class="value" id="servingCount">${r.servings}</span>
                <button onclick="scaleView('${recipeId}', 1)">+</button>
              </div>
            </div>` : ''}
          </div>

          <div class="recipe-section">
            <div class="recipe-section-title">Ingredients</div>
            <div id="ingredientsList">
              ${ingredients.map(i => `
                <label class="ingredient-check">
                  <input type="checkbox" onchange="this.parentElement.classList.toggle('checked')">
                  <span class="qty-unit">${esc(i.qty)}${i.unit ? ' '+esc(i.unit) : ''}</span>
                  <span>${esc(i.name)}${i.note ? ' <em class="text-muted">'+esc(i.note)+'</em>' : ''}</span>
                </label>`).join('')}
            </div>
            <div class="flex gap-1 mt-1">
              <button class="btn btn-sm" onclick="convertUnits('${recipeId}','metric')">Metric</button>
              <button class="btn btn-sm" onclick="convertUnits('${recipeId}','imperial')">Imperial</button>
            </div>
          </div>

          <div class="recipe-section">
            <div class="recipe-section-title">Directions</div>
            ${directions.map(d => `
              <div class="direction-step">
                <span class="step-number">${d.step}</span>
                <span class="step-text">${esc(d.text)}</span>
                ${d.timer_minutes ? `<span class="step-timer" onclick="startTimer('Step ${d.step}', ${d.timer_minutes})">&#x23F1; ${d.timer_minutes}m</span>` : ''}
              </div>`).join('')}
          </div>

          ${Object.keys(nutrition).length ? `
            <div class="recipe-section">
              <div class="recipe-section-title">Nutrition (per serving)</div>
              <div class="nutrition-grid">
                ${Object.entries(nutrition).map(([k,v]) => `
                  <div class="nutrition-item">
                    <div class="nutrition-value">${v}</div>
                    <div class="nutrition-label">${esc(k)}</div>
                  </div>`).join('')}
              </div>
            </div>` : ''}

          ${r.notes ? `<div class="recipe-section">
            <div class="recipe-section-title">Notes</div>
            <p>${esc(r.notes)}</p>
          </div>` : ''}

          ${linked ? `<div class="recipe-section">
            <div class="recipe-section-title">Linked Recipes</div>
            <p>${linked}</p>
          </div>` : ''}
        </div>
      </div>`;
    window._currentRecipe = r;
  } catch(e) { content.innerHTML = `<p style="padding:2rem">Error: ${esc(e.message)}</p>`; }
}

let _scaledServings = null;
async function scaleView(recipeId, delta) {
  const el = document.getElementById('servingCount');
  let current = parseInt(el.textContent);
  current = Math.max(1, current + delta);
  el.textContent = current;
  try {
    const data = await api.get(`/api/recipes/${recipeId}/cook?servings=${current}`);
    const list = document.getElementById('ingredientsList');
    list.innerHTML = data.ingredients.map(i => `
      <label class="ingredient-check">
        <input type="checkbox" onchange="this.parentElement.classList.toggle('checked')">
        <span class="qty-unit">${esc(i.qty)}${i.unit ? ' '+esc(i.unit) : ''}</span>
        <span>${esc(i.name)}${i.note ? ' <em class="text-muted">'+esc(i.note)+'</em>' : ''}</span>
      </label>`).join('');
  } catch(e) { toast(e.message, 'error'); }
}

async function convertUnits(recipeId, system) {
  const el = document.getElementById('servingCount');
  const servings = el ? parseInt(el.textContent) : null;
  try {
    const data = await api.get(`/api/recipes/${recipeId}/cook?units=${system}${servings ? '&servings='+servings : ''}`);
    const list = document.getElementById('ingredientsList');
    list.innerHTML = data.ingredients.map(i => `
      <label class="ingredient-check">
        <input type="checkbox" onchange="this.parentElement.classList.toggle('checked')">
        <span class="qty-unit">${esc(i.qty)}${i.unit ? ' '+esc(i.unit) : ''}</span>
        <span>${esc(i.name)}${i.note ? ' <em class="text-muted">'+esc(i.note)+'</em>' : ''}</span>
      </label>`).join('');
    toast(`Converted to ${system}`, 'success');
  } catch(e) { toast(e.message, 'error'); }
}

async function deleteRecipe(id) {
  if (!confirm('Delete this recipe?')) return;
  try {
    await api.del(`/api/recipes/${id}`);
    toast('Recipe deleted', 'success');
    app.goto('recipes');
  } catch(e) { toast(e.message, 'error'); }
}

async function enrichRecipe(id) {
  toast('Enriching with AI...', 'info');
  try {
    const data = await api.post(`/api/recipes/${id}/enrich`);
    if (data.status === 'enriched') {
      toast(`Enriched: ${data.fields_updated.join(', ')}`, 'success');
      app.goto(`recipe/${id}`);
    } else {
      toast(data.message || 'Nothing to enrich', 'info');
    }
  } catch(e) { toast(e.message, 'error'); }
}

async function addToShoppingList(recipeId) {
  try {
    const lists = await api.get('/api/shopping/lists');
    if (lists.lists.length === 0) {
      const created = await api.post('/api/shopping/lists', { name: 'Shopping List' });
      await api.post(`/api/shopping/lists/${created.id}/add-recipe/${recipeId}`);
      toast('Ingredients added to new shopping list', 'success');
    } else {
      const listId = lists.lists[0].id;
      await api.post(`/api/shopping/lists/${listId}/add-recipe/${recipeId}`);
      toast('Ingredients added to shopping list', 'success');
    }
  } catch(e) { toast(e.message, 'error'); }
}

window.renderRecipeDetail = renderRecipeDetail;
window.scaleView = scaleView;
window.convertUnits = convertUnits;
window.deleteRecipe = deleteRecipe;
window.enrichRecipe = enrichRecipe;
window.addToShoppingList = addToShoppingList;
