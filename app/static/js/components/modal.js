function showModal(title, bodyHtml, actions) {
  let overlay = document.getElementById('modalOverlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'modalOverlay';
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) closeModal(); };
    document.body.appendChild(overlay);
  }
  overlay.innerHTML = `
    <div class="modal">
      <h3 class="modal-title">${title}</h3>
      <div class="modal-body">${bodyHtml}</div>
      <div class="modal-actions">${actions || ''}</div>
    </div>`;
  requestAnimationFrame(() => overlay.classList.add('visible'));
}

function closeModal() {
  const overlay = document.getElementById('modalOverlay');
  if (overlay) { overlay.classList.remove('visible'); }
}

function toast(message, type = 'info') {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = message;
  container.appendChild(t);
  setTimeout(() => { t.remove(); }, 3500);
}

window.showModal = showModal;
window.closeModal = closeModal;
window.toast = toast;
