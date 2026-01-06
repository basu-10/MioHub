/**
 * Clipboard Operations Module
 * Single-item copy/cut/paste helpers for folder view and preview panel.
 */

const ClipboardOperations = (function() {
  'use strict';

  // ==================== STATE ====================
  const CLIPBOARD_KEY = 'p2_clipboard';
  const MAX_CLIPBOARD_AGE = 24 * 60 * 60 * 1000; // 24 hours
  const ALLOWED_ITEM_TYPES = [
    'folder', 'note', 'board', 'file',
    'proprietary_note', 'proprietary_whiteboard', 'proprietary_blocks',
    'proprietary_infinite_whiteboard', 'proprietary_graph',
    'markdown', 'code', 'todo', 'diagram', 'table', 'blocks', 'timeline', 'pdf',
    'book'
  ];

  const SECTION_CONFIGS = {
    proprietary_graph: { sectionId: 'graph-workspaces', navLabel: 'Graph Workspaces', navIcon: 'device_hub' },
    proprietary_infinite_whiteboard: { sectionId: 'infinite-whiteboards', navLabel: 'Infinite Whiteboards', navIcon: 'grid_on' }
  };

  let clipboard = null;
  let operationInProgress = false;
  let actionButtons = {};

  // ==================== INIT ====================
  function init() {
    actionButtons = {
      copy: document.getElementById('btn-copy'),
      cut: document.getElementById('btn-cut'),
      paste: document.getElementById('btn-paste'),
      clearClipboard: document.getElementById('btn-clear-clipboard')
    };

    loadClipboard();
    attachActionListeners();
    setupContextMenuListeners();
    updatePasteButton();
  }

  function attachActionListeners() {
    if (actionButtons.copy) {
      actionButtons.copy.addEventListener('click', (e) => {
        e.preventDefault();
        if (window.selected) performCopy([window.selected]);
      });
    }

    if (actionButtons.cut) {
      actionButtons.cut.addEventListener('click', (e) => {
        e.preventDefault();
        if (window.selected) performCut([window.selected]);
      });
    }

    if (actionButtons.paste) {
      actionButtons.paste.addEventListener('click', (e) => {
        e.preventDefault();
        triggerPaste();
      });
    }

    if (actionButtons.clearClipboard) {
      actionButtons.clearClipboard.addEventListener('click', (e) => {
        e.preventDefault();
        clearClipboard();
      });
    }
  }

  // ==================== PUBLIC OPERATIONS ====================
  function performCopy(items) {
    const normalized = normalizeItems(items);
    if (normalized.length === 0) return false;

    clearCutStyles();
    clipboard = {
      action: 'copy',
      items: normalized,
      timestamp: Date.now()
    };
    saveClipboard();
    updatePasteButton();
    notifyClipboardChange(true);
    if (window.TelemetryPanel) {
      window.TelemetryPanel.setIdle('Item copied to clipboard');
    }
    return true;
  }

  function performCut(items) {
    const normalized = normalizeItems(items);
    if (normalized.length === 0) return false;

    clearCutStyles();
    applyCutStyles(items);
    clipboard = {
      action: 'cut',
      items: normalized,
      timestamp: Date.now()
    };
    saveClipboard();
    updatePasteButton();
    notifyClipboardChange(true);
    if (window.TelemetryPanel) {
      window.TelemetryPanel.setIdle('Item cut to clipboard');
    }
    return true;
  }

  function triggerPaste(targetFolderId) {
    if (!clipboard || !clipboard.items || clipboard.items.length === 0) return;

    const folderId = parseInt(targetFolderId || localStorage.getItem('currentFolderId'), 10);
    if (!isValidId(folderId)) {
      console.error('[CLIPBOARD] Invalid target folder id');
      return;
    }

    performPaste(clipboard, folderId);
  }

  function clearClipboard() {
    clipboard = null;
    saveClipboard();
    clearCutStyles();
    updatePasteButton();
    notifyClipboardChange(false);
    if (window.TelemetryPanel) {
      window.TelemetryPanel.setIdle('Clipboard cleared');
    }
  }

  // ==================== PASTE FLOW ====================
  function performPaste(clipboardData, targetFolderId) {
    if (operationInProgress) return;
    if (!validateClipboardData(clipboardData)) return;
    if (!isValidId(targetFolderId)) return;

    const item = clipboardData.items[0];
    if (!item) return;

    const pasteUrl = buildPasteUrl(clipboardData.action, item.type, item.id);
    if (!pasteUrl) return;

    operationInProgress = true;

    const formData = new FormData();
    formData.append('target_folder', targetFolderId.toString());
    formData.append('htmx', 'true');

    const csrfToken = getCSRFToken();
    if (csrfToken) formData.append('csrf_token', csrfToken);

    if (window.TelemetryPanel) {
      const verb = clipboardData.action === 'cut' ? 'Moving' : 'Copying';
      window.TelemetryPanel.setActive(`${verb} ${item.type}...`);
    }

    fetch(pasteUrl, {
      method: 'POST',
      body: formData,
      headers: { 'X-Requested-With': 'XMLHttpRequest', 'HX-Request': 'true' }
    })
      .then((response) => response.json())
      .then((data) => {
        if (!data.success) throw new Error(data.message || 'Paste failed');

        if (clipboardData.action === 'cut') {
          removeOriginalCard(item);
          if (data.new_item_html) insertNewItemHTML(data.new_item_html, item.type);
          clearCutStyles();
          // Keep clipboard until user clears it so multiple pastes are allowed across folders
          clipboard = { ...clipboardData, timestamp: Date.now() };
          saveClipboard();
          notifyClipboardChange(true);
        } else if (data.new_item_html) {
          insertNewItemHTML(data.new_item_html, item.type);
        }

        if (window.TelemetryPanel) {
          const msg = clipboardData.action === 'cut' ? 'Item moved' : 'Item copied';
          window.TelemetryPanel.setIdle(data.message || msg);
          if (typeof window.TelemetryPanel.fetchData === 'function') {
            window.TelemetryPanel.fetchData();
          }
        }
        updatePasteButton();
      })
      .catch((error) => {
        const errorMsg = `Failed to paste: ${sanitizeText(error.message)}`;
        if (window.TelemetryPanel) {
          window.TelemetryPanel.setIdle(errorMsg);
        } else {
          alert(errorMsg);
        }
        console.error('[CLIPBOARD] Paste error:', error);
      })
      .finally(() => {
        operationInProgress = false;
      });
  }

  function buildPasteUrl(action, type, id) {
    if (!action || !type || !isValidId(id)) return '';

    if (action === 'cut') {
      if (type === 'folder') return `/folders/move/${id}`;
      if (type === 'proprietary_note' || type === 'note') return `/folders/move_note/${id}`;
      if (type === 'board' || type === 'proprietary_whiteboard') return `/folders/move_board/${id}`;
      return `/p2/files/${id}/move`;
    }

    if (action === 'copy') {
      if (type === 'folder') return `/folders/copy/${id}`;
      if (type === 'proprietary_note' || type === 'note') return `/folders/duplicate_note/${id}`;
      if (type === 'board' || type === 'proprietary_whiteboard') return `/folders/duplicate_board/${id}`;
      return `/p2/files/${id}/duplicate`;
    }

    return '';
  }

  function removeOriginalCard(item) {
    const safeType = CSS.escape(String(item.type));
    const safeId = CSS.escape(String(item.id));
    const card = document.querySelector(`.item-card[data-type="${safeType}"][data-id="${safeId}"]`);
    if (!card) return;

    animateCardRemoval(card).then(() => {
      const col = card.closest('.col');
      if (col) col.remove();
      else card.remove();
      updateSectionCounts();
    });
  }

  function insertNewItemHTML(html, itemType) {
    const temp = document.createElement('div');
    temp.innerHTML = html;
    const wrapper = temp.firstElementChild;
    if (!wrapper) return window.location.reload();

    const card = wrapper.classList.contains('item-card') ? wrapper : wrapper.querySelector('.item-card');
    if (!card) return window.location.reload();

    const actualType = card.dataset.fileType || card.dataset.type || itemType;
    const sectionId = resolveSectionId(actualType);
    const section = document.getElementById(sectionId) || document.querySelector(`.${sectionId}-section`);
    if (!section) return window.location.reload();

    const grid = section.querySelector('.content-grid');
    if (!grid) return window.location.reload();

    wrapper.style.opacity = '0';
    wrapper.style.transform = 'scale(0.95) translateY(10px)';
    wrapper.style.transition = 'all 0.35s ease';
    grid.insertBefore(wrapper, grid.firstChild);

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        wrapper.style.opacity = '1';
        wrapper.style.transform = 'scale(1) translateY(0)';
      });
    });

    const badge = section.querySelector('.count-badge');
    if (badge) {
      const current = parseInt(badge.textContent, 10) || 0;
      badge.textContent = current + 1;
      badge.style.transform = 'scale(1.2)';
      setTimeout(() => { badge.style.transform = 'scale(1)'; }, 180);
      updateNavPillCount(section.id, current + 1, SECTION_CONFIGS[actualType]?.navLabel);
    }

    const body = wrapper.querySelector('.item-body');
    if (body && typeof window.attachCardClickListeners === 'function') {
      window.attachCardClickListeners(body);
    }

    setTimeout(() => {
      wrapper.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 120);
  }

  // ==================== HELPERS ====================
  function normalizeItems(items) {
    if (!Array.isArray(items)) return [];
    return items
      .map((item) => ({ type: item?.type, id: parseInt(item?.id, 10), card: item?.card || null }))
      .filter((item) => isValidItemType(item.type) && isValidId(item.id))
      .slice(0, 1); // single-item support
  }

  function isValidItemType(type) {
    return ALLOWED_ITEM_TYPES.includes(type);
  }

  function isValidId(id) {
    return Number.isInteger(id) && id > 0;
  }

  function validateClipboardData(data) {
    if (!data || !Array.isArray(data.items) || data.items.length === 0) return false;
    if (data.action !== 'copy' && data.action !== 'cut') return false;
    return data.items.every((i) => isValidItemType(i.type) && isValidId(i.id));
  }

  function loadClipboard() {
    try {
      const stored = localStorage.getItem(CLIPBOARD_KEY);
      if (!stored) return;

      const parsed = JSON.parse(stored);
      if (!validateClipboardData(parsed)) return;

      if (parsed.timestamp && Date.now() - parsed.timestamp > MAX_CLIPBOARD_AGE) {
        localStorage.removeItem(CLIPBOARD_KEY);
        return;
      }

      clipboard = parsed;
      updatePasteButton();
    } catch (e) {
      console.error('[CLIPBOARD] Failed to load clipboard:', e);
    }
  }

  function saveClipboard() {
    try {
      if (!clipboard) {
        localStorage.removeItem(CLIPBOARD_KEY);
        return;
      }
      const payload = { ...clipboard, timestamp: Date.now() };
      localStorage.setItem(CLIPBOARD_KEY, JSON.stringify(payload));
    } catch (e) {
      console.error('[CLIPBOARD] Failed to save clipboard:', e);
    }
  }

  function updatePasteButton() {
    const hasClipboard = !!(clipboard && clipboard.items && clipboard.items.length > 0);
    if (actionButtons.paste) {
      actionButtons.paste.disabled = !hasClipboard;
    }
    document.dispatchEvent(new CustomEvent('clipboardStateChanged', { detail: { hasClipboard } }));
  }

  function notifyClipboardChange(hasClipboard) {
    document.dispatchEvent(new CustomEvent('clipboardStateChanged', { detail: { hasClipboard } }));
  }

  function setupContextMenuListeners() {
    window.contextMenuPaste = function() {
      if (operationInProgress) return;
      const currentFolderId = parseInt(localStorage.getItem('currentFolderId'), 10);
      const targetFolderId = window.targetFolderId || currentFolderId;
      triggerPaste(targetFolderId);
    };

    window.contextMenuClearClipboard = function() {
      clearClipboard();
    };
  }

  function applyCutStyles(items) {
    items.forEach((item) => {
      if (item?.card) item.card.classList.add('cut-item');
    });
  }

  function clearCutStyles() {
    document.querySelectorAll('.cut-item').forEach((el) => el.classList.remove('cut-item'));
  }

  function updateNavPillCount(sectionId, count, labelOverride) {
    if (!sectionId) return;
    const pill = document.querySelector(`.nav-pill[data-section-id="${sectionId}"]`) || document.querySelector(`.nav-pill[onclick*="scrollToSection('${sectionId}')"]`);
    if (!pill) return;

    const label = labelOverride || pill.dataset.navLabel || pill.textContent.trim();
    const badge = pill.querySelector('.pill-count');
    if (badge) {
      badge.textContent = count;
    } else {
      const span = document.createElement('span');
      span.className = 'pill-count';
      span.textContent = count;
      pill.appendChild(span);
    }

    if (label) {
      pill.setAttribute('title', `${label} (${count})`);
    }
  }

  function updateSectionCounts() {
    document.querySelectorAll('.section-container').forEach((section) => {
      const count = section.querySelectorAll('.content-grid .item-card').length;
      const badge = section.querySelector('.count-badge');
      if (badge) badge.textContent = count;
      updateNavPillCount(section.id, count);
      if (count === 0) {
        const prevHr = section.previousElementSibling;
        section.style.transition = 'all 0.3s ease';
        section.style.opacity = '0';
        setTimeout(() => {
          section.remove();
          if (prevHr && prevHr.tagName === 'HR') prevHr.remove();
        }, 300);
      }
    });
  }

  function resolveSectionId(itemType) {
    if (SECTION_CONFIGS[itemType]) return SECTION_CONFIGS[itemType].sectionId;
    const map = {
      folder: 'folders',
      note: 'notes',
      proprietary_note: 'notes',
      board: 'boards',
      proprietary_whiteboard: 'boards',
      book: 'combined',
      proprietary_blocks: 'combined',
      markdown: 'markdown',
      code: 'code',
      todo: 'todo',
      diagram: 'diagram',
      table: 'table',
      blocks: 'blocks',
      proprietary_infinite_whiteboard: 'infinite-whiteboards',
      proprietary_graph: 'graph-workspaces',
      file: 'markdown'
    };
    return map[itemType] || 'folders';
  }

  function animateCardRemoval(card) {
    return new Promise((resolve) => {
      card.style.transition = 'all 0.25s ease';
      card.style.opacity = '0';
      card.style.transform = 'scale(0.9) translateY(-10px)';
      setTimeout(resolve, 250);
    });
  }

  function sanitizeText(text) {
    if (!text) return '';
    return String(text).replace(/[<>]/g, '');
  }

  function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute('content');
    const input = document.querySelector('input[name="csrf_token"]');
    return input ? input.value : '';
  }

  // ==================== PUBLIC API ====================
  return {
    init,
    performCopy,
    performCut,
    triggerPaste,
    clearClipboard,
    hasClipboard: () => !!(clipboard && clipboard.items && clipboard.items.length > 0),
    getClipboard: () => clipboard,
    isOperationInProgress: () => operationInProgress,
    loadClipboard,
    saveClipboard,
    updatePasteButton,
    _test: { validateClipboardData, isValidItemType, isValidId, sanitizeText }
  };
})();

window.ClipboardOperations = ClipboardOperations;
console.log('[CLIPBOARD] ClipboardOperations module loaded');

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', ClipboardOperations.init);
} else {
  ClipboardOperations.init();
}

if (typeof htmx !== 'undefined') {
  document.body.addEventListener('htmx:afterSwap', (event) => {
    const target = event.detail.target;
    if (!target) return;
    const bodies = target.querySelectorAll('.item-body');
    if (bodies.length && typeof window.attachCardClickListeners === 'function') {
      bodies.forEach(window.attachCardClickListeners);
    }
  });

  document.body.addEventListener('htmx:load', (event) => {
    const elt = event.detail.elt;
    if (elt && elt.classList.contains('item-card')) {
      const body = elt.querySelector('.item-body');
      if (body && typeof window.attachCardClickListeners === 'function') {
        window.attachCardClickListeners(body);
      }
    }
  });
}
