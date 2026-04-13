/**
 * Show a side-by-side comparison modal when a potential duplicate is detected.
 * Allows user to: keep existing, replace with new, or keep both.
 */

let _pendingImportData = null;
let _pendingDuplicateMatch = null;

function showDuplicateModal(importedRecipe, duplicateMatch) {
  _pendingImportData = importedRecipe;
  _pendingDuplicateMatch = duplicateMatch;

  const existing = duplicateMatch.existing_recipe;
  const score = Math.round(duplicateMatch.score * 100);
  const existingPhoto = existing.photo_urls && existing.photo_urls.length ? existing.photo_urls[0] : null;
  const newPhoto = importedRecipe.photo_urls && importedRecipe.photo_urls.length ? importedRecipe.photo_urls[0] : null;

  const existingIngs = (existing.ingredients || []).slice(0, 8);
  const newIngs = (importedRecipe.ingredients || []).slice(0, 8);

  // Remove any existing overlay
  const old = document.getElementById('duplicateOverlay');
  if (old) old.remove();

  const overlay = document.createElement('div');
  overlay.id = 'duplicateOverlay';
  overlay.className = 'modal-overlay visible';
  overlay.style.cssText = 'z-index:600;';
  overlay.onclick = (e) => { if (e.target === overlay) closeDuplicateModal(); };

  overlay.innerHTML = `
    <div class="modal" style="max-width:900px;width:95%;max-height:90vh;overflow-y:auto">
      <div style="text-align:center;margin-bottom:1.5rem">
        <div style="font-size:2rem;margin-bottom:0.5rem">&#x26A0;</div>
        <h3 class="modal-title" style="margin-bottom:0.25rem">Potential Duplicate Found</h3>
        <p class="text-muted text-sm">${score}% match — Compare both recipes below and choose what to do</p>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-bottom:1.5rem">
        <!-- EXISTING RECIPE -->
        <div style="border:2px solid var(--border);border-radius:var(--radius-lg);overflow:hidden">
          <div style="background:var(--bg-sidebar);padding:0.6rem 1rem;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.1em;font-weight:600;color:var(--text-muted)">
            Already in your collection
          </div>
          ${existingPhoto ? `<img src="${existingPhoto}" style="width:100%;aspect-ratio:16/9;object-fit:cover" alt="">` : ''}
          <div style="padding:1rem">
            <h4 style="font-family:var(--font-serif);font-size:1.1rem;margin-bottom:0.5rem">${esc(existing.title)}</h4>
            ${existing.description ? `<p class="text-sm text-muted" style="margin-bottom:0.75rem;font-style:italic">${esc(existing.description).substring(0, 120)}${existing.description.length > 120 ? '...' : ''}</p>` : ''}
            <div class="text-xs text-muted" style="display:flex;gap:1rem;margin-bottom:0.75rem">
              ${existing.servings ? `<span>${existing.servings} servings</span>` : ''}
              ${existing.total_time_minutes ? `<span>${existing.total_time_minutes} min</span>` : ''}
              ${existing.source_name ? `<span>${esc(existing.source_name)}</span>` : ''}
            </div>
            <div class="text-xs" style="color:var(--text-secondary)">
              <strong>Ingredients:</strong><br>
              ${existingIngs.map(i => `${i.qty || ''} ${i.unit || ''} ${esc(i.name || '')}`).join('<br>')}
              ${existing.ingredients && existing.ingredients.length > 8 ? `<br><em>+${existing.ingredients.length - 8} more</em>` : ''}
            </div>
            ${Object.keys(existing.nutrition || {}).length ? `
              <div class="text-xs mt-1" style="color:var(--text-muted)">
                Nutrition: ${existing.nutrition.calories || '?'} cal, ${existing.nutrition.protein || '?'}g protein
              </div>` : ''}
          </div>
        </div>

        <!-- NEW RECIPE -->
        <div style="border:2px solid var(--accent);border-radius:var(--radius-lg);overflow:hidden">
          <div style="background:var(--accent);padding:0.6rem 1rem;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.1em;font-weight:600;color:white">
            New import
          </div>
          ${newPhoto ? `<img src="${newPhoto}" style="width:100%;aspect-ratio:16/9;object-fit:cover" alt="">` : ''}
          <div style="padding:1rem">
            <h4 style="font-family:var(--font-serif);font-size:1.1rem;margin-bottom:0.5rem">${esc(importedRecipe.title)}</h4>
            ${importedRecipe.description ? `<p class="text-sm text-muted" style="margin-bottom:0.75rem;font-style:italic">${esc(importedRecipe.description).substring(0, 120)}${importedRecipe.description.length > 120 ? '...' : ''}</p>` : ''}
            <div class="text-xs text-muted" style="display:flex;gap:1rem;margin-bottom:0.75rem">
              ${importedRecipe.servings ? `<span>${importedRecipe.servings} servings</span>` : ''}
              ${importedRecipe.total_time_minutes ? `<span>${importedRecipe.total_time_minutes} min</span>` : ''}
              ${importedRecipe.source_name ? `<span>${esc(importedRecipe.source_name)}</span>` : ''}
            </div>
            <div class="text-xs" style="color:var(--text-secondary)">
              <strong>Ingredients:</strong><br>
              ${newIngs.map(i => `${i.qty || ''} ${i.unit || ''} ${esc(i.name || '')}`).join('<br>')}
              ${importedRecipe.ingredients && importedRecipe.ingredients.length > 8 ? `<br><em>+${importedRecipe.ingredients.length - 8} more</em>` : ''}
            </div>
          </div>
        </div>
      </div>

      <!-- ACTIONS -->
      <div style="display:flex;gap:0.75rem;justify-content:center;padding-top:1rem;border-top:1px solid var(--border)">
        <button class="btn" onclick="duplicateAction('keep_existing')" title="Discard the new import">
          Keep Existing
        </button>
        <button class="btn btn-accent" onclick="duplicateAction('replace')" title="Replace the existing recipe with this new one">
          Replace with New
        </button>
        <button class="btn btn-primary" onclick="duplicateAction('keep_both')" title="Save the new recipe alongside the existing one">
          Keep Both
        </button>
        <button class="btn" onclick="closeDuplicateModal()" style="border:none;color:var(--text-muted)">
          Cancel
        </button>
      </div>
    </div>`;

  document.body.appendChild(overlay);
}

function closeDuplicateModal() {
  const overlay = document.getElementById('duplicateOverlay');
  if (overlay) overlay.remove();
  _pendingImportData = null;
  _pendingDuplicateMatch = null;
}

async function duplicateAction(action) {
  if (!_pendingImportData) return;

  const data = _pendingImportData;
  const match = _pendingDuplicateMatch;
  closeDuplicateModal();

  if (action === 'keep_existing') {
    toast('Import cancelled — keeping existing recipe', 'info');
    return;
  }

  if (action === 'replace') {
    toast('Replacing existing recipe...', 'info');
    try {
      const result = await api.post('/api/import', {
        url: data.source_url,
        auto_save: false,
        force_save: true,
        replace_id: match.existing_id,
      });
      if (result.id) {
        toast(`Replaced with: ${result.title}`, 'success');
        app.goto(`recipe/${result.id}`);
      } else {
        toast('Replaced successfully', 'success');
        app.goto('recipes');
      }
    } catch (e) {
      toast(e.message, 'error');
    }
    return;
  }

  if (action === 'keep_both') {
    toast('Saving new recipe...', 'info');
    try {
      const result = await api.post('/api/import', {
        url: data.source_url,
        auto_save: false,
        force_save: true,
      });
      if (result.id) {
        toast(`Saved: ${result.title}`, 'success');
        app.goto(`recipe/${result.id}`);
      } else {
        toast('Saved successfully', 'success');
        app.goto('recipes');
      }
    } catch (e) {
      toast(e.message, 'error');
    }
    return;
  }
}

/**
 * Show duplicate modal for manual recipe creation.
 * Called before saving a new recipe from the edit form.
 */
function showDuplicateModalForCreate(newRecipeData, duplicateMatch, saveCallback) {
  _pendingImportData = newRecipeData;
  _pendingDuplicateMatch = duplicateMatch;

  // Reuse the same modal but override the action buttons
  showDuplicateModal(newRecipeData, duplicateMatch);

  // Override the actions for manual create
  const overlay = document.getElementById('duplicateOverlay');
  if (!overlay) return;

  const actionsDiv = overlay.querySelector('div[style*="justify-content:center"]');
  if (actionsDiv) {
    actionsDiv.innerHTML = `
      <button class="btn" onclick="closeDuplicateModal()" title="Go back to editing">
        Cancel
      </button>
      <button class="btn btn-accent" onclick="closeDuplicateModal();duplicateCreateReplace('${duplicateMatch.existing_id}')"
              title="Replace the existing recipe with your new version">
        Replace Existing
      </button>
      <button class="btn btn-primary" onclick="closeDuplicateModal();duplicateCreateKeepBoth()"
              title="Save as a new recipe alongside the existing one">
        Keep Both
      </button>`;
  }

  // Store the save callback for later
  window._duplicateCreateCallback = saveCallback;
}

async function duplicateCreateReplace(existingId) {
  if (window._duplicateCreateCallback) {
    // Delete existing first, then save new
    try {
      await api.del(`/api/recipes/${existingId}`);
    } catch(e) { /* ignore if already gone */ }
    window._duplicateCreateCallback();
  }
}

function duplicateCreateKeepBoth() {
  if (window._duplicateCreateCallback) {
    window._duplicateCreateCallback();
  }
}

window.showDuplicateModal = showDuplicateModal;
window.closeDuplicateModal = closeDuplicateModal;
window.duplicateAction = duplicateAction;
window.showDuplicateModalForCreate = showDuplicateModalForCreate;
window.duplicateCreateReplace = duplicateCreateReplace;
window.duplicateCreateKeepBoth = duplicateCreateKeepBoth;
