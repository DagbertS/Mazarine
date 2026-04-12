async function renderPlannerPage() {
  window._currentPage = 'planner';
  const content = document.getElementById('pageContent');
  content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  const today = new Date();
  const startOfWeek = new Date(today);
  startOfWeek.setDate(today.getDate() - today.getDay() + 1);
  if (!window._plannerWeekStart) window._plannerWeekStart = new Date(startOfWeek);
  const ws = window._plannerWeekStart;

  const days = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(ws);
    d.setDate(ws.getDate() + i);
    days.push(d);
  }
  const start = fmt(days[0]);
  const end = fmt(days[6]);
  const slots = ['breakfast', 'lunch', 'dinner', 'snack'];

  try {
    const data = await api.get(`/api/planner?start=${start}&end=${end}`);
    const entries = data.entries || [];
    const entryMap = {};
    entries.forEach(e => { const key = `${e.date}_${e.slot}`; if (!entryMap[key]) entryMap[key] = []; entryMap[key].push(e); });

    const dayHeaders = days.map(d => {
      const isToday = fmt(d) === fmt(today);
      return `<div class="planner-header ${isToday ? 'today' : ''}">${d.toLocaleDateString('en', {weekday:'short'})}<br>${d.getDate()}</div>`;
    }).join('');

    let rows = '';
    for (const slot of slots) {
      rows += `<div class="planner-slot-label">${slot}</div>`;
      for (const day of days) {
        const key = `${fmt(day)}_${slot}`;
        const items = entryMap[key] || [];
        rows += `<div class="planner-cell" data-date="${fmt(day)}" data-slot="${slot}"
                      ondrop="planDrop(event)" ondragover="event.preventDefault();this.classList.add('dragover')"
                      ondragleave="this.classList.remove('dragover')">
          ${items.map(e => e.recipe_id
            ? `<div class="planner-recipe" draggable="true" ondragstart="planDragStart(event,'${e.id}')"
                    onclick="app.goto('recipe/${e.recipe_id}')">${esc(e.recipe_title || 'Recipe')}</div>`
            : `<div class="planner-note">${esc(e.note || '')}</div>`
          ).join('')}
          <div class="planner-add" onclick="showPlanAdd('${fmt(day)}','${slot}')">+ Add</div>
        </div>`;
      }
    }

    const weekLabel = `${days[0].toLocaleDateString('en',{month:'short',day:'numeric'})} - ${days[6].toLocaleDateString('en',{month:'short',day:'numeric',year:'numeric'})}`;

    content.innerHTML = `
      <div class="content" style="max-width:100%;padding:2rem">
        <div class="page-header">
          <div>
            <h1>Meal Planner</h1>
            <p class="page-subtitle">${weekLabel}</p>
          </div>
          <div class="flex gap-1">
            <button class="btn btn-sm" onclick="planWeek(-1)">&#x2190; Prev</button>
            <button class="btn btn-sm" onclick="planToday()">Today</button>
            <button class="btn btn-sm" onclick="planWeek(1)">Next &#x2192;</button>
            <button class="btn btn-sm" onclick="duplicateWeek('${start}')">Duplicate Week</button>
          </div>
        </div>
        <div class="planner-grid">
          <div class="planner-header"></div>
          ${dayHeaders}
          ${rows}
        </div>
      </div>`;
  } catch(e) { content.innerHTML = `<p style="padding:2rem">Error: ${esc(e.message)}</p>`; }
}

function fmt(d) { return d.toISOString().split('T')[0]; }
function planWeek(delta) {
  window._plannerWeekStart.setDate(window._plannerWeekStart.getDate() + delta * 7);
  renderPlannerPage();
}
function planToday() { window._plannerWeekStart = null; renderPlannerPage(); }

let _dragEntryId = null;
function planDragStart(e, entryId) { _dragEntryId = entryId; e.dataTransfer.effectAllowed = 'move'; }
async function planDrop(e) {
  e.preventDefault();
  e.currentTarget.classList.remove('dragover');
  if (!_dragEntryId) return;
  const date = e.currentTarget.dataset.date;
  const slot = e.currentTarget.dataset.slot;
  try {
    await api.put(`/api/planner/${_dragEntryId}/move`, { new_date: date, new_slot: slot });
    toast('Moved', 'success');
    renderPlannerPage();
  } catch(err) { toast(err.message, 'error'); }
  _dragEntryId = null;
}

async function showPlanAdd(date, slot) {
  let recipes = [];
  try { const d = await api.get('/api/recipes?limit=100&sort=title&order=asc'); recipes = d.recipes; } catch(e) {}
  showModal('Add to Planner',
    `<div class="form-group">
       <label class="form-label">Recipe</label>
       <select class="form-select" id="planRecipeSelect">
         <option value="">-- No recipe (note only) --</option>
         ${recipes.map(r => `<option value="${r.id}">${esc(r.title)}</option>`).join('')}
       </select>
     </div>
     <div class="form-group">
       <label class="form-label">Note</label>
       <input class="form-input" id="planNote" placeholder="e.g. eating out, leftovers">
     </div>`,
    `<button class="btn" onclick="closeModal()">Cancel</button>
     <button class="btn btn-primary" onclick="addPlanEntry('${date}','${slot}')">Add</button>`);
}

async function addPlanEntry(date, slot) {
  const recipeId = document.getElementById('planRecipeSelect').value || null;
  const note = document.getElementById('planNote').value || null;
  try {
    await api.post('/api/planner', { date, slot, recipe_id: recipeId, note });
    closeModal();
    toast('Added to plan', 'success');
    renderPlannerPage();
  } catch(e) { toast(e.message, 'error'); }
}

async function duplicateWeek(sourceStart) {
  const ws = new Date(window._plannerWeekStart);
  ws.setDate(ws.getDate() + 7);
  const targetStart = fmt(ws);
  try {
    const res = await api.post(`/api/planner/duplicate-week?source_start=${sourceStart}&target_start=${targetStart}`);
    toast(`Duplicated ${res.entries_copied} entries`, 'success');
    window._plannerWeekStart.setDate(window._plannerWeekStart.getDate() + 7);
    renderPlannerPage();
  } catch(e) { toast(e.message, 'error'); }
}

window.renderPlannerPage = renderPlannerPage;
window.planWeek = planWeek;
window.planToday = planToday;
window.planDragStart = planDragStart;
window.planDrop = planDrop;
window.showPlanAdd = showPlanAdd;
window.addPlanEntry = addPlanEntry;
window.duplicateWeek = duplicateWeek;
