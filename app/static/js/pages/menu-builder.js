let _generatedMenu = null;

async function renderMenuBuilderPage() {
  window._currentPage = 'menu';
  const content = document.getElementById('pageContent');
  content.innerHTML = `
    <div class="content" style="max-width:900px">
      <div class="page-header">
        <div>
          <h1>Menu Builder</h1>
          <p class="page-subtitle">Let AI craft a complete menu for your occasion</p>
        </div>
      </div>

      <div id="menuForm">
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Number of Courses</label>
            <select class="form-select" id="menuCourses">
              <option value="2">2 courses</option>
              <option value="3" selected>3 courses</option>
              <option value="4">4 courses</option>
              <option value="5">5 courses</option>
              <option value="6">6 courses</option>
              <option value="7">7 courses (tasting menu)</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Guests</label>
            <input class="form-input" id="menuGuests" type="number" min="1" max="50" value="4">
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Cuisine / Inspiration</label>
            <input class="form-input" id="menuCuisine" placeholder="e.g. French, Japanese, Mediterranean, Fusion...">
          </div>
          <div class="form-group">
            <label class="form-label">Occasion</label>
            <input class="form-input" id="menuOccasion" placeholder="e.g. Date night, Birthday, Holiday dinner...">
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Max Total Duration (minutes)</label>
            <input class="form-input" id="menuDuration" type="number" placeholder="e.g. 120">
            <p class="form-hint">Total time for all courses combined</p>
          </div>
          <div class="form-group">
            <label class="form-label">Difficulty</label>
            <select class="form-select" id="menuDifficulty">
              <option value="">Any</option>
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="advanced">Advanced</option>
            </select>
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">Dietary Requirements</label>
          <div class="flex gap-1" style="flex-wrap:wrap" id="dietaryOptions">
            ${['Vegetarian','Vegan','Gluten-Free','Dairy-Free','Keto','Low-Carb','Nut-Free','Pescatarian','Halal','Kosher']
              .map(d => `<label style="font-size:0.85rem;cursor:pointer;padding:0.3rem 0.6rem;border:1px solid var(--border);border-radius:var(--radius);display:inline-flex;align-items:center;gap:0.3rem">
                <input type="checkbox" name="dietary" value="${d}"> ${d}
              </label>`).join(' ')}
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">Ingredients to Use (optional)</label>
          <input class="form-input" id="menuPantry" placeholder="e.g. salmon, asparagus, truffle...">
          <p class="form-hint">Comma-separated list of ingredients you'd like incorporated</p>
        </div>

        <div class="form-group">
          <label class="form-label">Ingredients to Avoid (optional)</label>
          <input class="form-input" id="menuAvoid" placeholder="e.g. shellfish, cilantro...">
          <p class="form-hint">Comma-separated list of ingredients to exclude</p>
        </div>

        <div class="form-group">
          <label class="form-label">Additional Notes</label>
          <textarea class="form-textarea" id="menuNotes" rows="2" placeholder="Any other preferences or context..."></textarea>
        </div>

        <button class="btn btn-primary" onclick="generateMenu()" id="generateBtn" style="width:100%;padding:0.8rem;font-size:0.9rem">
          Generate Menu
        </button>
      </div>

      <div id="menuResult" class="hidden mt-3"></div>
    </div>`;
}

async function generateMenu() {
  const btn = document.getElementById('generateBtn');
  btn.disabled = true;
  btn.textContent = 'Generating your menu...';

  const dietaryChecks = document.querySelectorAll('input[name="dietary"]:checked');
  const dietary = Array.from(dietaryChecks).map(c => c.value);
  const pantryVal = document.getElementById('menuPantry').value;
  const avoidVal = document.getElementById('menuAvoid').value;

  const body = {
    num_courses: parseInt(document.getElementById('menuCourses').value),
    guests: parseInt(document.getElementById('menuGuests').value) || 4,
    cuisine: document.getElementById('menuCuisine').value || null,
    occasion: document.getElementById('menuOccasion').value || null,
    max_duration_minutes: parseInt(document.getElementById('menuDuration').value) || null,
    difficulty: document.getElementById('menuDifficulty').value || null,
    dietary: dietary.length ? dietary : null,
    use_pantry: pantryVal ? pantryVal.split(',').map(s => s.trim()).filter(Boolean) : null,
    avoid_ingredients: avoidVal ? avoidVal.split(',').map(s => s.trim()).filter(Boolean) : null,
    notes: document.getElementById('menuNotes').value || null,
  };

  try {
    const menu = await api.post('/api/menu/generate', body);
    _generatedMenu = menu;
    renderMenuResult(menu);
    toast('Menu generated!', 'success');
  } catch(e) {
    toast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Generate Menu';
  }
}

function renderMenuResult(menu) {
  const result = document.getElementById('menuResult');
  result.classList.remove('hidden');

  const courses = menu.courses || [];
  result.innerHTML = `
    <div style="border-top:1px solid var(--border);padding-top:2rem">
      <div class="flex-between mb-2">
        <div>
          <h2>${esc(menu.menu_title || 'Your Menu')}</h2>
          <p class="text-muted">${esc(menu.description || '')}</p>
          ${menu.total_estimated_time_minutes ? `<p class="text-sm text-muted mt-1">Estimated total time: ${menu.total_estimated_time_minutes} minutes</p>` : ''}
        </div>
        <div class="flex gap-1">
          <button class="btn btn-primary" onclick="saveMenu()">Save All Recipes</button>
          <button class="btn" onclick="generateMenu()">Regenerate</button>
        </div>
      </div>

      ${courses.map((c, i) => `
        <div class="menu-course" style="margin-bottom:2.5rem;padding:2rem;background:var(--bg-card);border:1px solid var(--border-light);border-radius:var(--radius-lg)">
          <div class="flex-between mb-1">
            <div>
              <span class="text-xs text-muted" style="text-transform:uppercase;letter-spacing:0.12em">${esc(c.course_name || `Course ${i+1}`)}</span>
              <h3 style="font-family:var(--font-serif);font-size:1.4rem;margin-top:0.25rem">${esc(c.recipe?.title || '')}</h3>
            </div>
            ${c.recipe?.total_time_minutes ? `<span class="tag">${c.recipe.total_time_minutes}m</span>` : ''}
          </div>
          ${c.recipe?.description ? `<p class="text-muted" style="font-style:italic;margin-bottom:1rem">${esc(c.recipe.description)}</p>` : ''}

          <div class="form-row" style="gap:2rem">
            <div style="flex:1">
              <div class="recipe-section-title">Ingredients</div>
              ${(c.recipe?.ingredients || []).map(ing =>
                `<div style="padding:0.3rem 0;border-bottom:1px solid var(--border-light);font-size:0.9rem">
                  <strong>${esc(ing.qty)} ${esc(ing.unit)}</strong> ${esc(ing.name)}${ing.note ? ` <em class="text-muted">${esc(ing.note)}</em>` : ''}
                </div>`
              ).join('')}
            </div>
            <div style="flex:1.5">
              <div class="recipe-section-title">Directions</div>
              ${(c.recipe?.directions || []).map(d =>
                `<div class="direction-step" style="padding:0.5rem 0">
                  <span class="step-number" style="font-size:1.1rem">${d.step}</span>
                  <span class="step-text" style="font-size:0.9rem">${esc(d.text)}</span>
                  ${d.timer_minutes ? `<span class="step-timer" onclick="startTimer('${esc(c.recipe?.title)} Step ${d.step}', ${d.timer_minutes})">&#x23F1; ${d.timer_minutes}m</span>` : ''}
                </div>`
              ).join('')}
            </div>
          </div>

          ${c.wine_pairing || c.plating_tip ? `
            <div class="flex gap-2 mt-2" style="padding-top:1rem;border-top:1px solid var(--border-light)">
              ${c.wine_pairing ? `<div class="text-sm"><strong>Wine pairing:</strong> ${esc(c.wine_pairing)}</div>` : ''}
              ${c.plating_tip ? `<div class="text-sm"><strong>Plating:</strong> ${esc(c.plating_tip)}</div>` : ''}
            </div>` : ''}

          ${c.recipe?.suggested_tags?.length ? `
            <div class="flex gap-1 mt-1">${c.recipe.suggested_tags.map(t => `<span class="tag">${esc(t)}</span>`).join('')}</div>` : ''}
        </div>
      `).join('')}

      ${menu.timeline ? `
        <div style="padding:1.5rem;background:var(--bg-hover);border-radius:var(--radius-lg);margin-bottom:1.5rem">
          <div class="recipe-section-title">Preparation Timeline</div>
          <p style="white-space:pre-line">${esc(menu.timeline)}</p>
        </div>` : ''}

      ${menu.shopping_summary?.length ? `
        <div style="padding:1.5rem;background:var(--bg-hover);border-radius:var(--radius-lg)">
          <div class="recipe-section-title">Shopping Summary</div>
          <div style="columns:2;gap:2rem">
            ${menu.shopping_summary.map(item => `<div style="padding:0.2rem 0;font-size:0.9rem">${esc(item)}</div>`).join('')}
          </div>
        </div>` : ''}
    </div>`;
}

async function saveMenu() {
  if (!_generatedMenu) return;
  try {
    const res = await api.post('/api/menu/save', {
      courses: _generatedMenu.courses,
      menu_title: _generatedMenu.menu_title,
    });
    toast(`Saved ${res.recipes.length} recipes to your collection!`, 'success');
  } catch(e) {
    toast(e.message, 'error');
  }
}

window.renderMenuBuilderPage = renderMenuBuilderPage;
window.generateMenu = generateMenu;
window.saveMenu = saveMenu;
