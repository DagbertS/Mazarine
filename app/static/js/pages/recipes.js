async function renderRecipesPage(params) {
  window._currentPage = 'recipes';
  const content = document.getElementById('pageContent');
  content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
  const sp = new URLSearchParams(params || '');
  const q = sp.get('q') || '';
  const catId = sp.get('category_id') || '';
  const tag = sp.get('tag') || '';
  const favs = sp.get('favourites') === 'true';
  const sort = sp.get('sort') || 'updated_at';

  let query = `/api/recipes?limit=50&sort=${sort}`;
  if (q) query += `&q=${encodeURIComponent(q)}`;
  if (catId) query += `&category_id=${catId}`;
  if (tag) query += `&tag=${encodeURIComponent(tag)}`;
  if (favs) query += `&favourites=true`;

  try {
    const [data, cats, tags] = await Promise.all([
      api.get(query),
      api.get('/api/categories'),
      api.get('/api/tags'),
    ]);
    let title = 'All Recipes';
    if (q) title = `Search: "${q}"`;
    else if (favs) title = 'Favourites';
    else if (tag) title = `Tag: ${tag}`;

    content.innerHTML = `
      <div class="main-layout">
        ${renderSidebar(cats.categories, tags.tags)}
        <div class="content">
          <div class="page-header">
            <div>
              <h1>${esc(title)}</h1>
              <p class="page-subtitle">${data.total} recipe${data.total !== 1 ? 's' : ''}</p>
            </div>
            <div class="flex gap-1">
              <select class="form-select" style="width:auto;padding:0.4rem 0.8rem;font-size:0.8rem" onchange="app.goto('recipes','?sort='+this.value+'${q?'&q='+encodeURIComponent(q):''}')">
                <option value="updated_at" ${sort==='updated_at'?'selected':''}>Recently Updated</option>
                <option value="created_at" ${sort==='created_at'?'selected':''}>Newest</option>
                <option value="title" ${sort==='title'?'selected':''}>A-Z</option>
                <option value="rating" ${sort==='rating'?'selected':''}>Rating</option>
              </select>
              <button class="btn btn-primary" onclick="app.goto('recipe/new')">Add Recipe</button>
            </div>
          </div>
          ${data.recipes.length
            ? `<div class="recipe-grid">${data.recipes.map(recipeCard).join('')}</div>`
            : `<div class="empty-state">
                <div class="icon">&#x1F50D;</div>
                <h3>No recipes found</h3>
                <p>${q ? 'Try different search terms' : 'Start by importing or creating a recipe'}</p>
              </div>`}
        </div>
      </div>`;
  } catch(e) { content.innerHTML = `<p style="padding:2rem">Error: ${esc(e.message)}</p>`; }
}

window.renderRecipesPage = renderRecipesPage;
