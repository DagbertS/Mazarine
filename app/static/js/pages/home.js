let _heroInterval = null;
let _heroIndex = 0;

async function renderHomePage() {
  window._currentPage = 'home';
  const content = document.getElementById('pageContent');
  content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
  try {
    const [recipes, cats, tags] = await Promise.all([
      api.get('/api/recipes?limit=50&sort=updated_at'),
      api.get('/api/categories'),
      api.get('/api/tags'),
    ]);
    const all = recipes.recipes;
    const recent = all.slice(0, 8);
    const withPhotos = all.filter(r => r.photo_urls && r.photo_urls.length);
    const heroRecipes = withPhotos.slice(0, 5);
    const favourites = all.filter(r => r.is_favourite).slice(0, 6);

    // Seasonal suggestions based on month
    const seasonal = getSeasonalRecipes(all);

    // Editorial picks — varied selection
    const editorial = getEditorialPicks(all);

    content.innerHTML = `
      <div class="content-full">
        <!-- Hero Carousel -->
        ${heroRecipes.length ? renderHeroCarousel(heroRecipes) : ''}

        <!-- Latest Recipes — horizontal scroll carousel -->
        <div class="landing-section">
          <div class="section-header">
            <span class="section-title">Latest Additions</span>
            <a href="javascript:void(0)" onclick="app.goto('recipes')" class="section-link">View All &rarr;</a>
          </div>
          <div class="h-carousel" id="latestCarousel">
            ${recent.map(r => renderCarouselItem(r)).join('')}
          </div>
        </div>

        <!-- Seasonal Banner -->
        ${seasonal.recipes.length ? renderSeasonalBanner(seasonal) : ''}

        <!-- Editorial Grid -->
        ${editorial.length >= 4 ? `
        <div class="landing-section">
          <div class="section-header">
            <span class="section-title">Explore</span>
            <a href="javascript:void(0)" onclick="app.goto('recipes')" class="section-link">Browse All &rarr;</a>
          </div>
          <div class="editorial-grid">
            ${editorial.slice(0, 2).map(r => renderEditorialCard(r, true)).join('')}
          </div>
          <div class="editorial-grid mt-2" style="grid-template-columns:repeat(4,1fr)">
            ${editorial.slice(2, 6).map(r => renderEditorialCard(r, false)).join('')}
          </div>
        </div>` : ''}

        ${favourites.length ? `
        <div class="landing-section">
          <div class="section-header">
            <span class="section-title">Your Favourites</span>
          </div>
          <div class="h-carousel">
            ${favourites.map(r => renderCarouselItem(r)).join('')}
          </div>
        </div>` : ''}

        <!-- Quick Actions -->
        <div class="landing-section" style="text-align:center;padding:3rem 2rem">
          <div style="max-width:500px;margin:0 auto">
            <h2 style="margin-bottom:0.5rem">What would you like to cook?</h2>
            <p class="text-muted" style="margin-bottom:1.5rem">Import a recipe from the web, build a menu with AI, or search by what's in your pantry</p>
            <div class="flex gap-1" style="justify-content:center;flex-wrap:wrap">
              <button class="btn" onclick="app.goto('recipe/new')">Import URL</button>
              <button class="btn" onclick="app.goto('menu')">Menu Builder</button>
              <button class="btn" onclick="app.goto('ingredient-search')">By Ingredient</button>
              <button class="btn btn-primary" onclick="app.goto('recipe/new')">New Recipe</button>
            </div>
          </div>
        </div>
      </div>`;

    // Start hero auto-rotation
    if (heroRecipes.length > 1) startHeroRotation(heroRecipes.length);

  } catch(e) { content.innerHTML = `<p class="text-muted" style="padding:2rem">Error: ${esc(e.message)}</p>`; }
}

/* ── Hero Carousel ── */
function renderHeroCarousel(recipes) {
  const first = recipes[0];
  const photo = first.photo_urls[0];
  const tags = (first.tags || []).slice(0, 2).map(t => t.name).join(' / ');
  return `
    <div class="hero-carousel">
      <div class="hero-slide" id="heroSlide" onclick="app.goto('recipe/${first.id}')">
        <img src="${photo}" alt="${esc(first.title)}" id="heroImg">
        <div class="hero-overlay">
          <div class="hero-tag" id="heroTag">${esc(tags)}</div>
          <div class="hero-title" id="heroTitle">${esc(first.title)}</div>
          <div class="hero-desc" id="heroDesc">${esc((first.description || '').substring(0, 120))}${first.description && first.description.length > 120 ? '...' : ''}</div>
        </div>
      </div>
      <div class="hero-dots" id="heroDots">
        ${recipes.map((r, i) => `<div class="hero-dot ${i === 0 ? 'active' : ''}" onclick="goHeroSlide(${i})"></div>`).join('')}
      </div>
    </div>`;
}

function startHeroRotation(count) {
  if (_heroInterval) clearInterval(_heroInterval);
  _heroIndex = 0;
  _heroInterval = setInterval(() => {
    _heroIndex = (_heroIndex + 1) % count;
    goHeroSlide(_heroIndex);
  }, 5000);
}

function goHeroSlide(index) {
  _heroIndex = index;
  // We need the recipe data — fetch from the carousel items
  const slides = document.querySelectorAll('#heroDots .hero-dot');
  slides.forEach((d, i) => d.classList.toggle('active', i === index));

  // Get recipe data from the page state
  api.get('/api/recipes?limit=5&sort=updated_at').then(data => {
    const withPhotos = data.recipes.filter(r => r.photo_urls && r.photo_urls.length);
    const r = withPhotos[index];
    if (!r) return;
    const img = document.getElementById('heroImg');
    const title = document.getElementById('heroTitle');
    const desc = document.getElementById('heroDesc');
    const tag = document.getElementById('heroTag');
    const slide = document.getElementById('heroSlide');
    if (img) { img.style.opacity = 0; setTimeout(() => { img.src = r.photo_urls[0]; img.style.opacity = 1; }, 200); img.style.transition = 'opacity 0.4s'; }
    if (title) title.textContent = r.title;
    if (desc) desc.textContent = (r.description || '').substring(0, 120);
    if (tag) tag.textContent = (r.tags || []).slice(0, 2).map(t => t.name).join(' / ');
    if (slide) slide.onclick = () => app.goto(`recipe/${r.id}`);
  }).catch(() => {});
}

/* ── Carousel Item ── */
function renderCarouselItem(r) {
  const photo = r.photo_urls && r.photo_urls.length ? r.photo_urls[0] : '';
  const time = r.total_time_minutes || r.cook_time_minutes;
  const date = r.updated_at ? new Date(r.updated_at).toLocaleDateString('en', { month: 'short', day: 'numeric' }) : '';
  return `
    <div class="h-carousel-item" onclick="app.goto('recipe/${r.id}')">
      ${photo ? `<img class="h-carousel-img" src="${photo}" alt="${esc(r.title)}" loading="lazy">` :
        `<div class="h-carousel-img" style="display:flex;align-items:center;justify-content:center;font-size:2rem;color:var(--border)">&#x1F372;</div>`}
      <div class="h-carousel-date">${date}</div>
      <div class="h-carousel-title">${esc(r.title)}</div>
      <div class="h-carousel-meta">${time ? time + ' min' : ''}${r.servings ? ' &middot; ' + r.servings + ' servings' : ''}</div>
    </div>`;
}

/* ── Editorial Card ── */
function renderEditorialCard(r, large) {
  const photo = r.photo_urls && r.photo_urls.length ? r.photo_urls[0] : '';
  const tag = (r.tags || []).find(t => ['Italian','French','Japanese','Indian','Thai','Mexican','Korean','Mediterranean','Middle Eastern','Asian','American','Vietnamese'].includes(t.name));
  return `
    <div class="editorial-card ${large ? 'large' : ''}" onclick="app.goto('recipe/${r.id}')">
      ${photo ? `<img class="editorial-card-img" src="${photo}" alt="${esc(r.title)}" loading="lazy">` :
        `<div class="editorial-card-img" style="background:var(--bg-hover)"></div>`}
      <div class="editorial-card-tag">${tag ? esc(tag.name) : (r.source_name || 'Recipe')}</div>
      <div class="editorial-card-title">${esc(r.title)}</div>
      ${large && r.description ? `<div class="editorial-card-desc">${esc(r.description.substring(0, 100))}...</div>` : ''}
    </div>`;
}

/* ── Seasonal Banner ── */
function renderSeasonalBanner(seasonal) {
  return `
    <div class="landing-section">
      <div class="seasonal-banner">
        <div class="seasonal-text">
          <div class="seasonal-label">${seasonal.label}</div>
          <div class="seasonal-title">${seasonal.title}</div>
          <div class="seasonal-desc">${seasonal.desc}</div>
        </div>
        <div class="seasonal-grid">
          ${seasonal.recipes.slice(0, 3).map(r => `
            <div class="seasonal-card" onclick="app.goto('recipe/${r.id}')">
              ${r.photo_urls && r.photo_urls.length ? `<img src="${r.photo_urls[0]}" alt="${esc(r.title)}" loading="lazy">` : ''}
              <div class="seasonal-card-title">${esc(r.title)}</div>
            </div>`).join('')}
        </div>
      </div>
    </div>`;
}

function getSeasonalRecipes(all) {
  const month = new Date().getMonth();
  let label, title, desc, keywords;
  if (month >= 2 && month <= 4) {
    label = 'Spring Collection'; title = 'Fresh & Light'; desc = 'Seasonal recipes celebrating spring produce, fresh herbs, and vibrant flavours.';
    keywords = ['salad', 'fresh', 'light', 'spring', 'herb', 'green', 'asparagus', 'pea'];
  } else if (month >= 5 && month <= 7) {
    label = 'Summer Kitchen'; title = 'Sun-Kissed Flavours'; desc = 'Cool salads, refreshing drinks, and dishes made for warm evenings.';
    keywords = ['summer', 'salad', 'fresh', 'cold', 'smoothie', 'grill', 'light', 'gazpacho', 'tomato'];
  } else if (month >= 8 && month <= 10) {
    label = 'Autumn Harvest'; title = 'Warm & Comforting'; desc = 'Hearty soups, roasted vegetables, and the rich flavours of fall.';
    keywords = ['soup', 'stew', 'roast', 'comfort', 'pumpkin', 'squash', 'mushroom', 'warm', 'autumn'];
  } else {
    label = 'Winter Warmers'; title = 'Cosy & Nourishing'; desc = 'Soul-warming recipes for cold nights and festive gatherings.';
    keywords = ['soup', 'stew', 'comfort', 'warm', 'winter', 'bread', 'roast', 'curry'];
  }
  const matches = all.filter(r => {
    const text = (r.title + ' ' + (r.description || '') + ' ' + (r.tags || []).map(t => t.name).join(' ')).toLowerCase();
    return keywords.some(k => text.includes(k));
  });
  return { label, title, desc, recipes: matches.slice(0, 3) };
}

function getEditorialPicks(all) {
  // Pick varied recipes: try to get different cuisines
  const seen = new Set();
  const picks = [];
  const cuisines = ['Italian','French','Japanese','Indian','Thai','Mexican','Korean','Mediterranean','Middle Eastern'];
  for (const cuisine of cuisines) {
    const match = all.find(r => !seen.has(r.id) && (r.tags || []).some(t => t.name === cuisine));
    if (match) { picks.push(match); seen.add(match.id); }
    if (picks.length >= 6) break;
  }
  // Fill remainder
  for (const r of all) {
    if (!seen.has(r.id) && r.photo_urls && r.photo_urls.length) { picks.push(r); seen.add(r.id); }
    if (picks.length >= 6) break;
  }
  return picks;
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

// Also used by recipes.js sidebar
function renderSidebar(categories, tags) {
  const catItems = (categories || []).map(c => {
    let html = `<div class="sidebar-item" onclick="app.goto('recipes','?category_id=${c.id}')">
      ${esc(c.name)}</div>`;
    if (c.children && c.children.length) {
      html += c.children.map(sub =>
        `<div class="sidebar-item" style="padding-left:2rem" onclick="app.goto('recipes','?category_id=${sub.id}')">
          ${esc(sub.name)}</div>`).join('');
    }
    return html;
  }).join('');
  const tagItems = (tags || []).slice(0, 15).map(t =>
    `<div class="sidebar-item" onclick="app.goto('recipes','?tag=${encodeURIComponent(t.name)}')">
      ${esc(t.name)} <span class="count">${t.recipe_count || 0}</span></div>`).join('');
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
      ${tagItems ? `<div class="sidebar-section"><div class="sidebar-title">Tags</div>${tagItems}</div>` : ''}
    </aside>`;
}

window.renderHomePage = renderHomePage;
window.renderSidebar = renderSidebar;
window.showCategoryModal = showCategoryModal;
window.createCategory = createCategory;
window.goHeroSlide = goHeroSlide;
