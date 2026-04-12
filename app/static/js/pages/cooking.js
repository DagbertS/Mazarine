async function renderCookingMode(recipeId) {
  window._currentPage = 'cooking';
  const content = document.getElementById('pageContent');
  try {
    const data = await api.get(`/api/recipes/${recipeId}/cook`);
    const ingredients = data.ingredients || [];
    const directions = data.directions || [];

    content.innerHTML = `
      <div class="cooking-mode" id="cookingMode">
        <div class="cooking-header">
          <div class="cooking-title">${esc(data.title)}</div>
          <div class="flex gap-1" style="align-items:center">
            <div class="scaler" style="background:#2A2A2A">
              <button onclick="cookScale(-1,'${recipeId}')" style="border-color:#555;color:var(--text-light)">-</button>
              <span class="value" id="cookServings" style="color:var(--text-light)">${data.servings || '?'}</span>
              <button onclick="cookScale(1,'${recipeId}')" style="border-color:#555;color:var(--text-light)">+</button>
            </div>
            <button class="btn btn-sm" style="border-color:#555;color:var(--text-light)" onclick="app.goto('recipe/${recipeId}')">Exit</button>
          </div>
        </div>
        <div class="cooking-body">
          <div class="cooking-ingredients" id="cookIngredients">
            <div class="recipe-section-title" style="color:var(--text-muted)">Ingredients</div>
            ${ingredients.map(i => `
              <label class="ingredient-check" style="border-color:#333;color:var(--text-light)">
                <input type="checkbox" onchange="this.parentElement.classList.toggle('checked')">
                <span class="qty-unit">${esc(i.qty)}${i.unit ? ' '+esc(i.unit) : ''}</span>
                <span>${esc(i.name)}</span>
              </label>`).join('')}
          </div>
          <div class="cooking-steps">
            <div class="cooking-step-number" id="cookStepNum">1</div>
            <div class="cooking-step-text" id="cookStepText">${directions.length ? esc(directions[0].text) : 'No directions'}</div>
            ${directions.length && directions[0].timer_minutes ? `
              <button class="btn mt-2" style="border-color:#555;color:var(--text-light)" id="cookTimerBtn"
                      onclick="startTimer('Step 1', ${directions[0].timer_minutes})">
                Start Timer (${directions[0].timer_minutes}m)
              </button>` : ''}
            <div class="cooking-nav">
              <button class="btn" onclick="cookPrev()">Previous</button>
              <button class="btn" onclick="cookNext()">Next</button>
            </div>
          </div>
        </div>
        <div class="cooking-progress" id="cookProgress">
          ${directions.map((d,i) => `<div class="cooking-dot ${i===0?'active':''}" onclick="cookGoTo(${i})"></div>`).join('')}
        </div>
      </div>`;

    window._cookData = { directions, ingredients, currentStep: 0, recipeId };

    // Keep screen on
    if ('wakeLock' in navigator) {
      try { window._wakeLock = await navigator.wakeLock.request('screen'); } catch(e) {}
    }
  } catch(e) { content.innerHTML = `<p style="padding:2rem;color:white;background:#1A1A1A;min-height:100vh">Error: ${esc(e.message)}</p>`; }
}

function cookGoTo(step) {
  const d = window._cookData;
  if (!d || step < 0 || step >= d.directions.length) return;
  d.currentStep = step;
  document.getElementById('cookStepNum').textContent = step + 1;
  document.getElementById('cookStepText').textContent = d.directions[step].text;
  const dots = document.querySelectorAll('.cooking-dot');
  dots.forEach((dot, i) => {
    dot.className = 'cooking-dot';
    if (i < step) dot.classList.add('done');
    if (i === step) dot.classList.add('active');
  });
  const timerBtn = document.getElementById('cookTimerBtn');
  if (d.directions[step].timer_minutes) {
    if (!timerBtn) {
      const nav = document.querySelector('.cooking-nav');
      const btn = document.createElement('button');
      btn.id = 'cookTimerBtn';
      btn.className = 'btn mt-2';
      btn.style.cssText = 'border-color:#555;color:var(--text-light)';
      btn.textContent = `Start Timer (${d.directions[step].timer_minutes}m)`;
      btn.onclick = () => startTimer(`Step ${step+1}`, d.directions[step].timer_minutes);
      nav.parentElement.insertBefore(btn, nav);
    } else {
      timerBtn.textContent = `Start Timer (${d.directions[step].timer_minutes}m)`;
      timerBtn.onclick = () => startTimer(`Step ${step+1}`, d.directions[step].timer_minutes);
    }
  } else if (timerBtn) {
    timerBtn.remove();
  }
}

function cookNext() { const d = window._cookData; if (d) cookGoTo(d.currentStep + 1); }
function cookPrev() { const d = window._cookData; if (d) cookGoTo(d.currentStep - 1); }

async function cookScale(delta, recipeId) {
  const el = document.getElementById('cookServings');
  let s = parseInt(el.textContent) || 1;
  s = Math.max(1, s + delta);
  el.textContent = s;
  try {
    const data = await api.get(`/api/recipes/${recipeId}/cook?servings=${s}`);
    const container = document.getElementById('cookIngredients');
    container.innerHTML = `
      <div class="recipe-section-title" style="color:var(--text-muted)">Ingredients</div>
      ${data.ingredients.map(i => `
        <label class="ingredient-check" style="border-color:#333;color:var(--text-light)">
          <input type="checkbox" onchange="this.parentElement.classList.toggle('checked')">
          <span class="qty-unit">${esc(i.qty)}${i.unit ? ' '+esc(i.unit) : ''}</span>
          <span>${esc(i.name)}</span>
        </label>`).join('')}`;
  } catch(e) { toast(e.message, 'error'); }
}

window.renderCookingMode = renderCookingMode;
window.cookGoTo = cookGoTo;
window.cookNext = cookNext;
window.cookPrev = cookPrev;
window.cookScale = cookScale;
