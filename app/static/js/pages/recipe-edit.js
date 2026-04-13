let _editIngredients = [];
let _editDirections = [];
let _editPhotos = [];

async function renderRecipeEdit(recipeId) {
  window._currentPage = 'recipe-edit';
  const content = document.getElementById('pageContent');
  const isNew = !recipeId || recipeId === 'new';

  if (isNew) {
    renderAddRecipePage();
    return;
  }

  // Edit existing recipe
  content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
  let recipe;
  try { recipe = await api.get(`/api/recipes/${recipeId}`); } catch(e) {
    content.innerHTML = `<p style="padding:2rem">Error: ${esc(e.message)}</p>`; return;
  }

  _editIngredients = recipe.ingredients || [];
  _editDirections = recipe.directions || [];
  _editPhotos = recipe.photo_urls || [];
  renderRecipeForm(content, recipe, recipeId);
}

/* ═══════════════════════════════════════════════
   UNIFIED ADD RECIPE — 3 methods
   ═══════════════════════════════════════════════ */
function renderAddRecipePage() {
  const content = document.getElementById('pageContent');
  content.innerHTML = `
    <div class="content" style="max-width:700px">
      <div class="flex-between mb-2">
        <a href="javascript:void(0)" onclick="app.goto('recipes')" class="text-sm text-muted">&larr; Back</a>
      </div>
      <h1 style="text-align:center;margin-bottom:0.5rem">Add a Recipe</h1>
      <p class="text-muted" style="text-align:center;margin-bottom:2rem">Choose how you'd like to add your recipe</p>

      <div class="add-method-grid">
        <!-- Photo / Camera -->
        <div class="add-method-card" onclick="showPhotoMethod()">
          <div class="add-method-icon"><svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.2" width="48" height="48"><rect x="4" y="10" width="40" height="30" rx="3"/><circle cx="24" cy="26" r="8"/><circle cx="24" cy="26" r="4"/><path d="M16 10L18 5h12l2 5"/></svg></div>
          <h3>Scan or Photo</h3>
          <p>Take a photo of a recipe or dish, or upload from your library. AI will extract all the details.</p>
          <div class="add-method-actions">
            <label class="btn btn-primary btn-sm add-camera-btn">
              Camera
              <input type="file" accept="image/*" capture="environment" onchange="handlePhotoCapture(this)" style="display:none">
            </label>
            <label class="btn btn-sm">
              Photo Library
              <input type="file" accept="image/*" onchange="handlePhotoCapture(this)" style="display:none">
            </label>
          </div>
        </div>

        <!-- Import URL -->
        <div class="add-method-card">
          <div class="add-method-icon"><svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.2" width="48" height="48"><circle cx="24" cy="24" r="18"/><path d="M8 24h32M24 6c-5 5-8 11-8 18s3 13 8 18c5-5 8-11 8-18s-3-13-8-18"/></svg></div>
          <h3>Import from URL</h3>
          <p>Paste a link from any recipe website. We'll extract everything automatically.</p>
          <div style="margin-top:1rem" onclick="event.stopPropagation()">
            <input class="form-input" id="addImportUrl" type="url" placeholder="https://..." style="margin-bottom:0.5rem"
                   onkeydown="if(event.key==='Enter'){event.preventDefault();handleUrlImport()}">
            <button class="btn btn-primary btn-sm" onclick="handleUrlImport()" style="width:100%">Import Recipe</button>
          </div>
        </div>

        <!-- Manual -->
        <div class="add-method-card" onclick="startManualRecipe()">
          <div class="add-method-icon"><svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.2" width="48" height="48"><path d="M8 40l3-12L35 4l5 5-24 24z"/><path d="M28 11l5 5"/><line x1="11" y1="37" x2="17" y2="31"/></svg></div>
          <h3>Write from Scratch</h3>
          <p>Create a recipe manually by filling in the title, ingredients, directions, and photos.</p>
          <button class="btn btn-sm mt-1">Start Writing</button>
        </div>
      </div>
    </div>`;
}

/* ── Photo / Camera method ── */
async function handlePhotoCapture(input) {
  const file = input.files[0];
  if (!file) return;
  input.value = '';

  const content = document.getElementById('pageContent');
  // Show the image being analyzed
  const imgUrl = URL.createObjectURL(file);
  content.innerHTML = `
    <div class="content" style="max-width:600px;text-align:center">
      <h2 style="margin-bottom:1rem">Analysing your image...</h2>
      <img src="${imgUrl}" style="max-width:100%;max-height:300px;border-radius:var(--radius-lg);margin-bottom:1.5rem;object-fit:contain">
      <div class="loading"><div class="spinner"></div></div>
      <p class="text-muted">Claude is reading your recipe. This takes a few seconds.</p>
    </div>`;

  try {
    const res = await api.upload('/api/analyze-image', file);
    if (res.error) {
      toast(res.error, 'error');
      renderAddRecipePage();
      return;
    }
    toast(`Recipe detected: ${res.title}`, 'success');

    // Pre-fill the form with OCR results
    _editIngredients = res.ingredients || [];
    _editDirections = res.directions || [];
    _editPhotos = res.photo_urls || [];

    const recipe = {
      title: res.title || '',
      description: res.description || '',
      servings: res.servings || null,
      prep_time_minutes: res.prep_time_minutes || null,
      cook_time_minutes: res.cook_time_minutes || null,
      total_time_minutes: res.total_time_minutes || null,
      source_url: '',
      notes: res.confidence ? `OCR confidence: ${res.confidence}` : '',
      nutrition: res.nutrition || {},
      photo_urls: _editPhotos,
      tags: (res.suggested_tags || []).map(t => ({name: t})),
      categories: [],
    };
    renderRecipeForm(content, recipe, '', res.suggested_tags);
  } catch(e) {
    toast(`Analysis failed: ${e.message}`, 'error');
    renderAddRecipePage();
  }
}

function showPhotoMethod() {
  // On mobile, the card click doesn't need to do anything extra
  // since the buttons inside handle the file inputs
}

/* ── URL import method ── */
async function handleUrlImport() {
  const url = document.getElementById('addImportUrl').value;
  if (!url) { toast('Enter a URL', 'error'); return; }

  const content = document.getElementById('pageContent');
  content.innerHTML = `
    <div class="content" style="max-width:600px;text-align:center">
      <h2 style="margin-bottom:1rem">Importing recipe...</h2>
      <div class="loading"><div class="spinner"></div></div>
      <p class="text-muted">${esc(url)}</p>
    </div>`;

  try {
    const data = await api.post('/api/import', { url, auto_save: true });

    if (data.duplicate_action_required && data.duplicates && data.duplicates.length > 0) {
      showDuplicateModal(data, data.duplicates[0]);
      renderAddRecipePage();
      return;
    }
    if (data.saved && data.id) {
      toast(`Imported: ${data.title}`, 'success');
      app.goto(`recipe/${data.id}`);
    } else {
      // Not auto-saved — show in the form
      _editIngredients = data.ingredients || [];
      _editDirections = data.directions || [];
      _editPhotos = data.photo_urls || [];
      const recipe = {
        title: data.title || '', description: data.description || '',
        servings: data.servings, prep_time_minutes: data.prep_time_minutes,
        cook_time_minutes: data.cook_time_minutes, total_time_minutes: data.total_time_minutes,
        source_url: data.source_url || url, notes: '', nutrition: data.nutrition || {},
        photo_urls: _editPhotos, tags: [], categories: [],
      };
      renderRecipeForm(content, recipe, '');
    }
  } catch(e) {
    toast(`Import failed: ${e.message}`, 'error');
    renderAddRecipePage();
  }
}

/* ── Manual method ── */
function startManualRecipe() {
  _editIngredients = [];
  _editDirections = [];
  _editPhotos = [];
  const recipe = {
    title: '', description: '', servings: 4,
    prep_time_minutes: null, cook_time_minutes: null, total_time_minutes: null,
    source_url: '', notes: '', nutrition: {},
    photo_urls: [], tags: [], categories: [],
  };
  renderRecipeForm(document.getElementById('pageContent'), recipe, '');
}

/* ═══════════════════════════════════════════════
   RECIPE FORM — shared by all methods + edit
   ═══════════════════════════════════════════════ */
async function renderRecipeForm(content, recipe, recipeId, suggestedTags) {
  const isNew = !recipeId;
  const cats = await api.get('/api/categories').catch(() => ({categories:[]}));
  const tags = await api.get('/api/tags').catch(() => ({tags:[]}));
  const recipeCatIds = (recipe.categories || []).map(c => c.id || c);
  const recipeTagNames = suggestedTags || (recipe.tags || []).map(t => t.name || t);

  content.innerHTML = `
    <div class="content" style="max-width:800px">
      <div class="recipe-detail">
        <div class="flex-between mb-2">
          <a href="javascript:void(0)" onclick="${isNew ? "app.goto('recipe/new')" : `app.goto('recipe/${recipeId}')`}" class="text-sm text-muted">&larr; ${isNew ? 'Back to methods' : 'Back'}</a>
          <h2>${isNew ? 'New Recipe' : 'Edit Recipe'}</h2>
        </div>

        <!-- Photo section -->
        <div class="form-group">
          <label class="form-label">Photos</label>
          <div id="photoGallery" class="photo-gallery">
            ${_editPhotos.map((url, i) => `
              <div class="photo-thumb">
                <img src="${esc(url)}" alt="">
                <button type="button" class="photo-remove" onclick="removePhoto(${i})">&times;</button>
              </div>`).join('')}
            <label class="photo-add">
              <span>+</span>
              <input type="file" accept="image/*" onchange="addPhotoToForm(this)" style="display:none" multiple>
            </label>
            <label class="photo-add add-camera-only">
              <span>&#x1F4F7;</span>
              <input type="file" accept="image/*" capture="environment" onchange="addPhotoToForm(this)" style="display:none">
            </label>
          </div>
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

          <input type="hidden" id="editSourceUrl" value="${esc(recipe.source_url || '')}">

          <div class="modal-actions" style="border:none;padding-top:0">
            <button type="button" class="btn" onclick="${isNew ? "app.goto('recipes')" : `app.goto('recipe/${recipeId}')`}">Cancel</button>
            <button type="submit" class="btn btn-primary">Save Recipe</button>
          </div>
        </form>
      </div>
    </div>`;
}

/* ── Photo management in form ── */
async function addPhotoToForm(input) {
  const files = input.files;
  if (!files || !files.length) return;
  for (const file of files) {
    // Upload immediately and get URL back
    toast('Uploading photo...', 'info');
    try {
      // Create a temporary upload endpoint call
      const form = new FormData();
      form.append('file', file);
      const res = await fetch('/api/analyze-image', {
        method: 'POST', credentials: 'include', body: form
      });
      // We don't need OCR here, just the photo URL. Use a simpler upload.
      // Actually, let's use a direct photo save approach:
      const imgUrl = URL.createObjectURL(file);
      // Store the file for upload after recipe save
      if (!window._pendingPhotoFiles) window._pendingPhotoFiles = [];
      window._pendingPhotoFiles.push(file);
      _editPhotos.push(imgUrl);
      refreshPhotoGallery();
      toast('Photo added', 'success');
    } catch(e) {
      toast(e.message, 'error');
    }
  }
  input.value = '';
}

function removePhoto(index) {
  _editPhotos.splice(index, 1);
  if (window._pendingPhotoFiles && window._pendingPhotoFiles[index]) {
    window._pendingPhotoFiles.splice(index, 1);
  }
  refreshPhotoGallery();
}

function refreshPhotoGallery() {
  const gallery = document.getElementById('photoGallery');
  if (!gallery) return;
  gallery.innerHTML = `
    ${_editPhotos.map((url, i) => `
      <div class="photo-thumb">
        <img src="${esc(url)}" alt="">
        <button type="button" class="photo-remove" onclick="removePhoto(${i})">&times;</button>
      </div>`).join('')}
    <label class="photo-add">
      <span>+</span>
      <input type="file" accept="image/*" onchange="addPhotoToForm(this)" style="display:none" multiple>
    </label>
    <label class="photo-add add-camera-only">
      <span>&#x1F4F7;</span>
      <input type="file" accept="image/*" capture="environment" onchange="addPhotoToForm(this)" style="display:none">
    </label>`;
}

/* ── Ingredient / Direction editors ── */
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

/* ── Save recipe ── */
async function saveRecipe(e, recipeId) {
  e.preventDefault();
  const isNew = !recipeId;
  const catCheckboxes = document.querySelectorAll('input[name="cats"]:checked');
  const catIds = Array.from(catCheckboxes).map(cb => cb.value);
  const tagStr = document.getElementById('editTags').value;
  const tagNames = tagStr ? tagStr.split(',').map(t => t.trim()).filter(Boolean) : [];

  _editDirections.forEach((d,i) => d.step = i+1);

  // Filter out blob URLs from photos (those are pending local files)
  const savedPhotos = _editPhotos.filter(u => !u.startsWith('blob:'));

  const body = {
    title: document.getElementById('editTitle').value,
    description: document.getElementById('editDescription').value,
    servings: parseInt(document.getElementById('editServings').value) || null,
    prep_time_minutes: parseInt(document.getElementById('editPrep').value) || null,
    cook_time_minutes: parseInt(document.getElementById('editCook').value) || null,
    total_time_minutes: parseInt(document.getElementById('editTotal').value) || null,
    source_url: (document.getElementById('editSourceUrl') || {}).value || null,
    ingredients: _editIngredients,
    directions: _editDirections,
    notes: document.getElementById('editNotes').value,
    category_ids: catIds,
    tag_names: tagNames,
    photo_urls: savedPhotos,
  };

  try {
    let savedId;
    if (isNew) {
      // Check for duplicates
      const dupCheck = await api.post('/api/check-duplicate', { title: body.title, ingredients: body.ingredients });
      if (dupCheck.has_duplicates) {
        showDuplicateModalForCreate(body, dupCheck.duplicates[0], async () => {
          try {
            const res = await api.post('/api/recipes', body);
            await uploadPendingPhotos(res.id);
            toast('Recipe created!', 'success');
            app.goto(`recipe/${res.id}`);
          } catch(err2) { toast(err2.message, 'error'); }
        });
        return;
      }
      const res = await api.post('/api/recipes', body);
      savedId = res.id;
      toast('Recipe created!', 'success');
    } else {
      await api.put(`/api/recipes/${recipeId}`, body);
      savedId = recipeId;
      toast('Recipe saved!', 'success');
    }

    // Upload any pending local photos
    await uploadPendingPhotos(savedId);
    app.goto(`recipe/${savedId}`);
  } catch(err) { toast(err.message, 'error'); }
}

async function uploadPendingPhotos(recipeId) {
  if (!window._pendingPhotoFiles || !window._pendingPhotoFiles.length) return;
  for (const file of window._pendingPhotoFiles) {
    try {
      await api.upload(`/api/recipes/${recipeId}/photo`, file);
    } catch(e) { console.error('Photo upload failed:', e); }
  }
  window._pendingPhotoFiles = [];
}

window.renderRecipeEdit = renderRecipeEdit;
window.renderAddRecipePage = renderAddRecipePage;
window.handlePhotoCapture = handlePhotoCapture;
window.handleUrlImport = handleUrlImport;
window.startManualRecipe = startManualRecipe;
window.addPhotoToForm = addPhotoToForm;
window.removePhoto = removePhoto;
window.addIngredient = addIngredient;
window.removeIng = removeIng;
window.updateIng = updateIng;
window.addDirection = addDirection;
window.removeDir = removeDir;
window.updateDir = updateDir;
window.saveRecipe = saveRecipe;
