function recipeCard(r) {
  const photo = r.photo_urls && r.photo_urls.length > 0 ? r.photo_urls[0] : null;
  const tags = (r.tags || []).slice(0, 3);
  const time = r.total_time_minutes || r.cook_time_minutes;
  const stars = renderStarsStatic(r.rating || 0);

  return `
    <div class="recipe-card" onclick="app.goto('recipe/${r.id}')">
      ${photo
        ? `<img class="recipe-card-img" src="${photo}" alt="${esc(r.title)}" loading="lazy">`
        : `<div class="recipe-card-img placeholder">&#x1F372;</div>`}
      <div class="recipe-card-body">
        <div class="flex-between">
          <div class="recipe-card-title">${esc(r.title)}</div>
          <button class="fav-btn ${r.is_favourite ? 'active' : ''}"
                  onclick="event.stopPropagation();toggleFav('${r.id}',${r.is_favourite})"
                  title="Favourite">&#x2665;</button>
        </div>
        <div class="recipe-card-meta">
          ${time ? `<span>${time} min</span>` : ''}
          ${r.servings ? `<span>${r.servings} servings</span>` : ''}
          ${stars}
        </div>
        ${tags.length ? `<div class="recipe-card-tags">${tags.map(t =>
          `<span class="tag ${t.type === 'dietary' ? 'dietary' : ''}">${esc(t.name)}</span>`
        ).join('')}</div>` : ''}
      </div>
    </div>`;
}

function renderStarsStatic(rating) {
  let html = '<div class="stars">';
  for (let i = 1; i <= 5; i++) {
    html += `<span class="star ${i <= rating ? 'filled' : ''}">&#x2605;</span>`;
  }
  html += '</div>';
  return html;
}

function renderStarsInput(rating, recipeId) {
  let html = '<div class="stars">';
  for (let i = 1; i <= 5; i++) {
    html += `<span class="star ${i <= rating ? 'filled' : ''}" onclick="setRating('${recipeId}',${i})">&#x2605;</span>`;
  }
  html += '</div>';
  return html;
}

async function toggleFav(id, current) {
  try {
    await api.put(`/api/recipes/${id}`, { is_favourite: !current });
    if (window._currentPage === 'recipes') loadRecipesPage();
    toast(current ? 'Removed from favourites' : 'Added to favourites', 'success');
  } catch(e) { toast(e.message, 'error'); }
}

async function setRating(id, rating) {
  try {
    await api.put(`/api/recipes/${id}`, { rating });
    toast('Rating updated', 'success');
    if (window._currentPage === 'recipe-detail') app.goto(`recipe/${id}`);
  } catch(e) { toast(e.message, 'error'); }
}

function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }

window.recipeCard = recipeCard;
window.renderStarsStatic = renderStarsStatic;
window.renderStarsInput = renderStarsInput;
window.toggleFav = toggleFav;
window.setRating = setRating;
window.esc = esc;
