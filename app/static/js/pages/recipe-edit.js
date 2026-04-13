let _editIngredients = [];
let _editDirections = [];

async function renderRecipeEdit(recipeId) {
  window._currentPage = 'recipe-edit';
  const content = document.getElementById('pageContent');
  const isNew = !recipeId || recipeId === 'new';
  let recipe = { title: '', description: '', servings: 4, prep_time_minutes: null, cook_time_minutes: null,
                 ingredients: [], directions: [], notes: '', source_url: '', photo_urls: [], nutrition: {} };

  if (!isNew) {
    content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    try { recipe = await api.get(`/api/recipes/${recipeId}`); } catch(e) {
      content.innerHTML = `<p style="padding:2rem">Error: ${esc(e.message)}</p>`; return;
    }
  }

  _editIngredients = recipe.ingredients || [];
  _editDirections = recipe.directions || [];
  const cats = await api.get('/api/categories').catch(() => ({categories:[]}));
  const tags = await api.get('/api/tags').catch(() => ({tags:[]}));
  const recipeCatIds = (recipe.categories || []).map(c => c.id);
  const recipeTagNames = (recipe.tags || []).map(t => t.name);

  content.innerHTML = `
    <div class="content">
      <div class="recipe-detail">
        <div class="flex-between mb-2">
          <a href="#" onclick="${isNew ? "app.goto('recipes')" : `app.goto('recipe/${recipeId}')`}" class="text-sm text-muted">&larr; Back</a>
          <h2>${isNew ? 'New Recipe' : 'Edit Recipe'}</h2>
        </div>

        <form onsubmit="saveRecipe(event, '${recipeId || ''}')">
          <div class="form-row">
            <div class="form-group" style="flex:2">
              <label class="form-label">Title</label>
              <input class="form-input" id="editTitle" value="${esc(recipe.title)}" required>
            </div>
            <div class="form-group">
              <label class="form-label">Servings</label>
              <input class="form-input" id="editServings" type="number" min="1" value="${recipe.servings || ''}">
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Description</label>
            <textarea class="form-textarea" id="editDescription" rows="2">${esc(recipe.description || '')}</textarea>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Prep Time (min)</label>
              <input class="form-input" id="editPrep" type="number" value="${recipe.prep_time_minutes || ''}">
            </div>
            <div class="form-group">
              <label class="form-label">Cook Time (min)</label>
              <input class="form-input" id="editCook" type="number" value="${recipe.cook_time_minutes || ''}">
            </div>
            <div class="form-group">
              <label class="form-label">Total Time (min)</label>
              <input class="form-input" id="editTotal" type="number" value="${recipe.total_time_minutes || ''}">
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Source URL</label>
            <input class="form-input" id="editSource" type="url" value="${esc(recipe.source_url || '')}">
          </div>

          <div class="form-group">
            <label class="form-label">Ingredients</label>
            <div id="ingredientEditor">${renderIngredientEditor()}</div>
            <button type="button" class="btn btn-sm mt-1" onclick="addIngredient()">+ Add Ingredient</button>
          </div>

          <div class="form-group">
            <label class="form-label">Directions</label>
            <div id="directionEditor">${renderDirectionEditor()}</div>
            <button type="button" class="btn btn-sm mt-1" onclick="addDirection()">+ Add Step</button>
          </div>

          <div class="form-group">
            <label class="form-label">Categories</label>
            <div class="flex gap-1" style="flex-wrap:wrap">
              ${flattenCats(cats.categories).map(c => `
                <label style="font-size:0.85rem;cursor:pointer">
                  <input type="checkbox" name="cats" value="${c.id}" ${recipeCatIds.includes(c.id)?'checked':''}> ${esc(c.name)}
                </label>`).join(' ')}
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Tags (comma-separated)</label>
            <input class="form-input" id="editTags" value="${recipeTagNames.join(', ')}">
          </div>

          <div class="form-group">
            <label class="form-label">Notes</label>
            <textarea class="form-textarea" id="editNotes" rows="3">${esc(recipe.notes || '')}</textarea>
          </div>

          ${!isNew ? `<div class="form-group">
            <label class="form-label">Photo</label>
            <input type="file" id="editPhoto" accept="image/*" onchange="uploadPhoto('${recipeId}')">
          </div>` : ''}

          <div class="modal-actions" style="border:none;padding-top:0">
            <button type="button" class="btn" onclick="${isNew ? "app.goto('recipes')" : `app.goto('recipe/${recipeId}')`}">Cancel</button>
            <button type="submit" class="btn btn-primary">Save Recipe</button>
          </div>
        </form>
      </div>
    </div>`;
}

function renderIngredientEditor() {
  return _editIngredients.map((ing, i) => `
    <div class="ingredient-row">
      <input class="qty" placeholder="Qty" value="${esc(ing.qty || '')}" onchange="updateIng(${i},'qty',this.value)">
      <input class="unit" placeholder="Unit" value="${esc(ing.unit || '')}" onchange="updateIng(${i},'unit',this.value)">
      <input class="name" placeholder="Ingredient" value="${esc(ing.name || '')}" onchange="updateIng(${i},'name',this.value)">
      <input class="note" placeholder="Note" value="${esc(ing.note || '')}" onchange="updateIng(${i},'note',this.value)">
      <button type="button" class="btn-icon" onclick="removeIng(${i})">&#x2715;</button>
    </div>`).join('');
}

function renderDirectionEditor() {
  return _editDirections.map((d, i) => `
    <div class="ingredient-row">
      <span class="text-muted" style="min-width:30px">${i+1}.</span>
      <textarea class="name" rows="2" style="min-height:50px" onchange="updateDir(${i},'text',this.value)">${esc(d.text || '')}</textarea>
      <input style="width:80px" placeholder="Timer" type="number" value="${d.timer_minutes || ''}" onchange="updateDir(${i},'timer_minutes',parseInt(this.value)||null)">
      <button type="button" class="btn-icon" onclick="removeDir(${i})">&#x2715;</button>
    </div>`).join('');
}

function addIngredient() { _editIngredients.push({qty:'',unit:'',name:'',note:'',group:''}); document.getElementById('ingredientEditor').innerHTML = renderIngredientEditor(); }
function removeIng(i) { _editIngredients.splice(i,1); document.getElementById('ingredientEditor').innerHTML = renderIngredientEditor(); }
function updateIng(i,k,v) { _editIngredients[i][k] = v; }
function addDirection() { _editDirections.push({step:_editDirections.length+1,text:'',timer_minutes:null}); document.getElementById('directionEditor').innerHTML = renderDirectionEditor(); }
function removeDir(i) { _editDirections.splice(i,1); _editDirections.forEach((d,j)=>d.step=j+1); document.getElementById('directionEditor').innerHTML = renderDirectionEditor(); }
function updateDir(i,k,v) { _editDirections[i][k] = v; }

function flattenCats(cats, depth=0) {
  let result = [];
  for (const c of (cats || [])) {
    result.push(c);
    if (c.children) result = result.concat(flattenCats(c.children, depth+1));
  }
  return result;
}

async function saveRecipe(e, recipeId) {
  e.preventDefault();
  const isNew = !recipeId || recipeId === 'new';
  const catCheckboxes = document.querySelectorAll('input[name="cats"]:checked');
  const catIds = Array.from(catCheckboxes).map(cb => cb.value);
  const tagStr = document.getElementById('editTags').value;
  const tagNames = tagStr ? tagStr.split(',').map(t => t.trim()).filter(Boolean) : [];

  _editDirections.forEach((d,i) => d.step = i+1);

  const body = {
    title: document.getElementById('editTitle').value,
    description: document.getElementById('editDescription').value,
    servings: parseInt(document.getElementById('editServings').value) || null,
    prep_time_minutes: parseInt(document.getElementById('editPrep').value) || null,
    cook_time_minutes: parseInt(document.getElementById('editCook').value) || null,
    total_time_minutes: parseInt(document.getElementById('editTotal').value) || null,
    source_url: document.getElementById('editSource').value || null,
    ingredients: _editIngredients,
    directions: _editDirections,
    notes: document.getElementById('editNotes').value,
    category_ids: catIds,
    tag_names: tagNames,
  };

  try {
    if (isNew) {
      // Check for duplicates before creating
      const dupCheck = await api.post('/api/check-duplicate', { title: body.title, ingredients: body.ingredients });
      if (dupCheck.has_duplicates) {
        // Show comparison modal — pass a callback to do the actual save
        showDuplicateModalForCreate(body, dupCheck.duplicates[0], async () => {
          try {
            const res = await api.post('/api/recipes', body);
            toast('Recipe created!', 'success');
            app.goto(`recipe/${res.id}`);
          } catch(err2) { toast(err2.message, 'error'); }
        });
        return;
      }
      const res = await api.post('/api/recipes', body);
      toast('Recipe created!', 'success');
      app.goto(`recipe/${res.id}`);
    } else {
      await api.put(`/api/recipes/${recipeId}`, body);
      toast('Recipe saved!', 'success');
      app.goto(`recipe/${recipeId}`);
    }
  } catch(err) { toast(err.message, 'error'); }
}

async function uploadPhoto(recipeId) {
  const file = document.getElementById('editPhoto').files[0];
  if (!file) return;
  try {
    const res = await api.upload(`/api/recipes/${recipeId}/photo`, file);
    toast('Photo uploaded!', 'success');
  } catch(e) { toast(e.message, 'error'); }
}

window.renderRecipeEdit = renderRecipeEdit;
window.addIngredient = addIngredient;
window.removeIng = removeIng;
window.updateIng = updateIng;
window.addDirection = addDirection;
window.removeDir = removeDir;
window.updateDir = updateDir;
window.saveRecipe = saveRecipe;
window.uploadPhoto = uploadPhoto;
