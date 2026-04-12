async function renderShoppingPage() {
  window._currentPage = 'shopping';
  const content = document.getElementById('pageContent');
  content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
  try {
    const data = await api.get('/api/shopping/lists');
    const lists = data.lists || [];

    content.innerHTML = `
      <div class="content">
        <div class="page-header">
          <div>
            <h1>Shopping Lists</h1>
            <p class="page-subtitle">${lists.length} list${lists.length !== 1 ? 's' : ''}</p>
          </div>
          <button class="btn btn-primary" onclick="createShoppingList()">New List</button>
        </div>
        ${lists.length ? lists.map(l => `
          <div class="stat-card" style="cursor:pointer;margin-bottom:1rem" onclick="openShoppingList('${l.id}')">
            <div class="flex-between">
              <div>
                <h3>${esc(l.name)}</h3>
                <p class="text-sm text-muted">${l.item_count || 0} items &middot; ${l.checked_count || 0} checked</p>
              </div>
              <div class="flex gap-1">
                <button class="btn btn-sm btn-danger" onclick="event.stopPropagation();deleteShoppingList('${l.id}')">Delete</button>
              </div>
            </div>
            ${l.item_count ? `<div style="background:var(--border-light);height:4px;border-radius:2px;margin-top:0.75rem">
              <div style="background:var(--success);height:100%;border-radius:2px;width:${Math.round((l.checked_count/l.item_count)*100)}%"></div>
            </div>` : ''}
          </div>`).join('')
        : `<div class="empty-state">
            <div class="icon">&#x1F6D2;</div>
            <h3>No shopping lists yet</h3>
            <p>Create a list or add ingredients from a recipe</p>
          </div>`}
      </div>`;
  } catch(e) { content.innerHTML = `<p style="padding:2rem">Error: ${esc(e.message)}</p>`; }
}

async function openShoppingList(listId) {
  const content = document.getElementById('pageContent');
  content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
  try {
    const data = await api.get(`/api/shopping/lists/${listId}/items`);
    const grouped = data.grouped || {};
    const aisles = Object.keys(grouped).sort();

    content.innerHTML = `
      <div class="content">
        <div class="page-header">
          <div>
            <a href="#" onclick="renderShoppingPage()" class="text-sm text-muted">&larr; All Lists</a>
            <h1>Shopping List</h1>
          </div>
          <div class="flex gap-1">
            <button class="btn btn-sm" onclick="showAddItemModal('${listId}')">+ Add Item</button>
            <button class="btn btn-sm" onclick="uncheckAll('${listId}')">Uncheck All</button>
          </div>
        </div>
        <div class="shopping-list">
          ${aisles.length ? aisles.map(aisle => `
            <div class="shopping-aisle">
              <div class="shopping-aisle-title">${esc(aisle)}</div>
              ${grouped[aisle].map(item => `
                <div class="shopping-item ${item.checked ? 'checked' : ''}" id="item-${item.id}">
                  <input type="checkbox" ${item.checked ? 'checked' : ''}
                         onchange="toggleShopItem('${item.id}',this.checked,'${listId}')">
                  <span class="shopping-qty">${item.quantity ? item.quantity : ''} ${item.unit || ''}</span>
                  <span class="shopping-name">${esc(item.name)}</span>
                  ${item.recipe_title ? `<span class="shopping-recipe">${esc(item.recipe_title)}</span>` : ''}
                  <button class="btn-icon" onclick="deleteShopItem('${item.id}','${listId}')">&#x2715;</button>
                </div>`).join('')}
            </div>`).join('')
          : `<div class="empty-state">
              <div class="icon">&#x2705;</div>
              <h3>List is empty</h3>
              <p>Add items manually or from a recipe</p>
            </div>`}
        </div>
      </div>`;
  } catch(e) { content.innerHTML = `<p style="padding:2rem">Error: ${esc(e.message)}</p>`; }
}

async function toggleShopItem(itemId, checked, listId) {
  try {
    await api.put(`/api/shopping/items/${itemId}`, { checked });
    const el = document.getElementById(`item-${itemId}`);
    if (el) el.classList.toggle('checked', checked);
  } catch(e) { toast(e.message, 'error'); }
}

async function deleteShopItem(itemId, listId) {
  try {
    await api.del(`/api/shopping/items/${itemId}`);
    openShoppingList(listId);
  } catch(e) { toast(e.message, 'error'); }
}

async function uncheckAll(listId) {
  try {
    const data = await api.get(`/api/shopping/lists/${listId}/items`);
    for (const item of data.items) {
      if (item.checked) await api.put(`/api/shopping/items/${item.id}`, { checked: false });
    }
    openShoppingList(listId);
  } catch(e) { toast(e.message, 'error'); }
}

function showAddItemModal(listId) {
  showModal('Add Item',
    `<div class="form-row">
       <div class="form-group">
         <label class="form-label">Quantity</label>
         <input class="form-input" id="shopQty" type="number" step="any">
       </div>
       <div class="form-group">
         <label class="form-label">Unit</label>
         <input class="form-input" id="shopUnit" placeholder="e.g. kg, pcs">
       </div>
     </div>
     <div class="form-group">
       <label class="form-label">Item Name</label>
       <input class="form-input" id="shopName" required>
     </div>`,
    `<button class="btn" onclick="closeModal()">Cancel</button>
     <button class="btn btn-primary" onclick="addShopItem('${listId}')">Add</button>`);
}

async function addShopItem(listId) {
  const name = document.getElementById('shopName').value;
  if (!name) return;
  try {
    await api.post(`/api/shopping/lists/${listId}/items`, {
      name,
      quantity: parseFloat(document.getElementById('shopQty').value) || null,
      unit: document.getElementById('shopUnit').value || null,
    });
    closeModal();
    openShoppingList(listId);
  } catch(e) { toast(e.message, 'error'); }
}

async function createShoppingList() {
  showModal('New Shopping List',
    `<div class="form-group">
       <label class="form-label">Name</label>
       <input class="form-input" id="newListName" value="Shopping List" required>
     </div>`,
    `<button class="btn" onclick="closeModal()">Cancel</button>
     <button class="btn btn-primary" onclick="doCreateList()">Create</button>`);
}

async function doCreateList() {
  const name = document.getElementById('newListName').value;
  try {
    await api.post('/api/shopping/lists', { name });
    closeModal();
    toast('List created', 'success');
    renderShoppingPage();
  } catch(e) { toast(e.message, 'error'); }
}

async function deleteShoppingList(listId) {
  if (!confirm('Delete this list?')) return;
  try {
    await api.del(`/api/shopping/lists/${listId}`);
    toast('List deleted', 'success');
    renderShoppingPage();
  } catch(e) { toast(e.message, 'error'); }
}

window.renderShoppingPage = renderShoppingPage;
window.openShoppingList = openShoppingList;
window.toggleShopItem = toggleShopItem;
window.deleteShopItem = deleteShopItem;
window.uncheckAll = uncheckAll;
window.showAddItemModal = showAddItemModal;
window.addShopItem = addShopItem;
window.createShoppingList = createShoppingList;
window.doCreateList = doCreateList;
window.deleteShoppingList = deleteShoppingList;
