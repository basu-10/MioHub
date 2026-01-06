/**
 * Folder Operations Module
 * Single-item actions for delete, public/pin toggle, send, rename, copy/cut, download.
 */

const FolderOperations = (function() {
  'use strict';

  const ALLOWED_ITEM_TYPES = [
    'folder', 'note', 'board', 'file', 'book', 'markdown',
    'todo', 'diagram', 'table', 'blocks', 'code', 'pdf',
    'proprietary_infinite_whiteboard', 'proprietary_graph',
    'proprietary_note', 'proprietary_whiteboard', 'proprietary_blocks'
  ];

  let lastPublicToggleState = null;
  let lastPinToggleState = null;

  function deleteItem(item, itemName) {
    if (!item) {
      console.warn('[DELETE] No item provided');
      return;
    }

    window.deleteModal.show(itemName, async () => {
      if (window.TelemetryPanel) {
        window.TelemetryPanel.setActive(`Deleting ${itemName}...`);
      }

      const formData = new FormData();
      formData.append('items', JSON.stringify([{ type: item.type, id: item.id }]));

      fetch('/folders/batch_delete', {
        method: 'POST',
        body: formData,
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      })
        .then((response) => response.json())
        .then((data) => {
          if (!data.success) throw new Error(data.message || 'Delete failed');

          if (item.card) {
            const colWrapper = item.card.closest('.col');
            if (colWrapper) colWrapper.remove();
            else item.card.remove();

            const tableRow = document.querySelector(`.item-row[data-type="${item.type}"][data-id="${item.id}"]`);
            if (tableRow) tableRow.remove();
          }

          if (window.TelemetryPanel) {
            window.TelemetryPanel.setIdle(`Deleted ${itemName}`);
            if (typeof window.TelemetryPanel.fetchData === 'function') {
              window.TelemetryPanel.fetchData();
            }
          }
        })
        .catch((error) => {
          console.error('[DELETE] Failed:', error);
          if (window.TelemetryPanel) {
            window.TelemetryPanel.setIdle(`Delete failed: ${error.message}`);
          } else {
            alert(`Failed to delete: ${error.message}`);
          }
        });
    });
  }

  function togglePublicItem(item) {
    if (!item) return;

    const isPublic = item.card?.dataset.isPublic === '1' || item.card?.dataset.isPublic === 'true';
    const newPublicState = !isPublic;
    lastPublicToggleState = { type: item.type, id: item.id, isPublic: newPublicState };

    updateCardPublicBadge(item.type, item.id, newPublicState, item.card);
    document.dispatchEvent(new CustomEvent('previewItemPublicChanged', {
      detail: { type: item.type, id: item.id, isPublic: newPublicState }
    }));

    const folderIdInput = document.getElementById('htmx-folder-id-input');
    const currentFolderId = localStorage.getItem('currentFolderId') || (folderIdInput ? folderIdInput.value : '');
    const payload = [{ type: item.type, id: item.id }];

    if (window.TelemetryPanel) {
      window.TelemetryPanel.setActive(`${isPublic ? 'Making private' : 'Making public'}...`);
    }

    htmx.ajax('POST', '/folders/batch_toggle_public_htmx', {
      source: document.body,
      swap: 'none',
      target: 'body',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      values: {
        items: JSON.stringify(payload),
        folder_id: currentFolderId
      }
    }).then(() => {
      setTimeout(() => {
        reattachEventListeners();
        if (window.TelemetryPanel) {
          window.TelemetryPanel.setIdle(isPublic ? 'Made private' : 'Made public');
        }
      }, 300);
    }).catch((err) => {
      console.error('[TOGGLE PUBLIC] Failed:', err);
      updateCardPublicBadge(item.type, item.id, isPublic, item.card);
      lastPublicToggleState = null;
      document.dispatchEvent(new CustomEvent('previewItemPublicChanged', {
        detail: { type: item.type, id: item.id, isPublic: isPublic }
      }));
      if (window.TelemetryPanel) {
        window.TelemetryPanel.setIdle('Public toggle failed');
      }
    });
  }

  function togglePinItem(item) {
    if (!item) return;
    if (item.type === 'folder') {
      if (window.TelemetryPanel) window.TelemetryPanel.setIdle('Folders cannot be pinned');
      return;
    }

    const isPinned = item.card?.dataset.isPinned === '1' || item.card?.dataset.isPinned === 'true';
    const newPinState = !isPinned;
    lastPinToggleState = { type: item.type, id: item.id, isPinned: newPinState };

    updateCardPinBadge(item.type, item.id, newPinState, item.card);
    document.dispatchEvent(new CustomEvent('previewItemPinChanged', {
      detail: { type: item.type, id: item.id, isPinned: newPinState }
    }));

    const folderIdInput = document.getElementById('htmx-folder-id-input');
    const currentFolderId = localStorage.getItem('currentFolderId') || (folderIdInput ? folderIdInput.value : '');
    const payload = [{ type: item.type, id: item.id }];

    if (window.TelemetryPanel) {
      window.TelemetryPanel.setActive(`${isPinned ? 'Unpinning' : 'Pinning'} item...`);
    }

    htmx.ajax('POST', '/folders/batch_toggle_pin_htmx', {
      source: document.body,
      swap: 'none',
      target: 'body',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      values: {
        items: JSON.stringify(payload),
        folder_id: currentFolderId
      }
    }).then(() => {
      setTimeout(() => {
        reattachEventListeners();
        if (window.TelemetryPanel) {
          window.TelemetryPanel.setIdle(isPinned ? 'Item unpinned' : 'Item pinned');
        }
      }, 300);
    }).catch((err) => {
      console.error('[TOGGLE PIN] Failed:', err);
      updateCardPinBadge(item.type, item.id, isPinned, item.card);
      lastPinToggleState = null;
      document.dispatchEvent(new CustomEvent('previewItemPinChanged', {
        detail: { type: item.type, id: item.id, isPinned: isPinned }
      }));
      if (window.TelemetryPanel) {
        window.TelemetryPanel.setIdle('Pin operation failed');
      }
    });
  }

  function sendItem(item) {
    if (!item) return;

    const modal = document.getElementById('sendToModal');
    if (!modal) return;

    const resolvedType = item.type === 'file' && item.card?.dataset.fileType ? item.card.dataset.fileType : item.type;
    const itemId = item.id;
    const title = item.card?.querySelector('.item-link')?.textContent?.trim() || `${resolvedType} ${itemId}`;
    const description = `Select a pinned user to send "${title}" to:`;
    const payloadItems = [{ type: resolvedType, id: itemId }];

    if (typeof window.openSendToModalWithItems === 'function') {
      window.openSendToModalWithItems(payloadItems, { mode: 'single', description });
      return;
    }

    modal.dataset.batchMode = 'false';
    modal.dataset.batchItems = '[]';
    modal.dataset.selectedType = resolvedType;
    modal.dataset.selectedId = itemId;
    const descEl = document.getElementById('sendToModalDescription');
    if (descEl) descEl.textContent = description;
    if (modal.parentElement !== document.body) {
      document.body.appendChild(modal);
    }
    modal.style.zIndex = '3000';
    try {
      bootstrap.Modal.getOrCreateInstance(modal).show();
    } catch (err) {
      try { new bootstrap.Modal(modal).show(); } catch (e) {}
    }
  }

  function renameItem(item) {
    if (!item || !item.card) {
      console.warn('[RENAME] No item or card provided');
      return;
    }

    if (item.type === 'folder') {
      const folderName = item.card.dataset.folderName || '';
      const folderDescription = item.card.dataset.folderDescription || '';
      if (window.openRenameFolderDescModal) {
        window.openRenameFolderDescModal(item.id, folderName, folderDescription);
      }
      return;
    }

    if (item.type === 'proprietary_note') {
      const link = item.card.querySelector('.card-title a.item-link');
      const currentName = link ? link.textContent.trim() : '';
      const currentDescription = item.card.dataset.noteDescription || '';
      if (window.openRenameNoteDescModal) {
        window.openRenameNoteDescModal(item.id, currentName, currentDescription);
      }
      return;
    }

    if (item.type === 'proprietary_whiteboard') {
      const link = item.card.querySelector('.card-title a.item-link');
      const currentName = link ? link.textContent.trim() : '';
      const currentDescription = item.card.dataset.boardDescription || '';
      if (window.openRenameBoardDescModal) {
        window.openRenameBoardDescModal(item.id, currentName, currentDescription);
      }
      return;
    }

    const link = item.card.querySelector('.card-title a.item-link');
    const currentName = link ? link.textContent.trim() : '';
    const currentDescription = item.card.dataset.fileDescription || '';
    if (window.openRenameFileDescModal) {
      window.openRenameFileDescModal(item.id, currentName, currentDescription);
    }
  }

  function copyItem(item) {
    if (!item) return;
    if (window.ClipboardOperations?.performCopy) {
      window.ClipboardOperations.performCopy([item]);
      if (window.TelemetryPanel) window.TelemetryPanel.setIdle('Item copied to clipboard');
    } else {
      alert('Copy functionality not ready. Please refresh the page.');
    }
  }

  function cutItem(item) {
    if (!item) return;
    if (window.ClipboardOperations?.performCut) {
      window.ClipboardOperations.performCut([item]);
      if (window.TelemetryPanel) window.TelemetryPanel.setIdle('Item cut to clipboard');
    } else {
      console.error('[CUT] ClipboardOperations.performCut not available');
    }
  }

  function downloadItem(item, itemName) {
    if (!item) return;
    if (typeof window.showDownloadModal === 'function') {
      window.showDownloadModal(item, itemName);
    } else {
      console.error('[DOWNLOAD] showDownloadModal function not found');
    }
  }

  function updateCardPublicBadge(type, id, isPublic, cardElement = null) {
    let selector;
    if (type === 'folder') {
      selector = `[data-type="folder"][data-id="${id}"]`;
    } else if (type === 'proprietary_note' || type === 'note') {
      selector = `[data-type="${type}"][data-id="${id}"]`;
    } else if (type === 'proprietary_whiteboard' || type === 'board') {
      selector = `[data-type="${type}"][data-id="${id}"]`;
    } else {
      selector = `[data-id="${id}"]`;
    }

    const card = (cardElement && cardElement.isConnected) ? cardElement : document.querySelector(selector);
    if (!card) return;

    card.dataset.isPublic = isPublic ? '1' : '0';
    let badgeContainer = card.querySelector('.badge-container');
    if (!badgeContainer) {
      badgeContainer = document.createElement('div');
      badgeContainer.className = 'badge-container';
      card.insertAdjacentElement('afterbegin', badgeContainer);
    }

    if (isPublic) {
      if (!badgeContainer.querySelector('.public-badge')) {
        const badge = document.createElement('span');
        badge.className = 'public-badge';
        badge.textContent = 'Public';
        badgeContainer.prepend(badge);
      }
    } else {
      const badge = badgeContainer.querySelector('.public-badge');
      if (badge) badge.remove();
    }
  }

  function updateCardPinBadge(type, id, isPinned, cardElement = null) {
    let selector;
    if (type === 'proprietary_note' || type === 'proprietary_whiteboard' || type === 'folder') {
      selector = `[data-type="${type}"][data-id="${id}"]`;
    } else if (type === 'file') {
      selector = `[data-type="file"][data-id="${id}"]`;
    } else {
      selector = `[data-type="${type}"][data-id="${id}"]`;
    }

    const card = (cardElement && cardElement.isConnected) ? cardElement : document.querySelector(selector);
    if (!card) return;

    card.dataset.isPinned = isPinned ? '1' : '0';
    let badgeContainer = card.querySelector('.badge-container');
    if (!badgeContainer) {
      badgeContainer = document.createElement('div');
      badgeContainer.className = 'badge-container';
      card.insertAdjacentElement('afterbegin', badgeContainer);
    }

    if (isPinned) {
      if (!badgeContainer.querySelector('.pin-badge')) {
        const badge = document.createElement('span');
        badge.className = 'pin-badge';
        badge.innerHTML = '<i class="material-icons" aria-hidden="true">push_pin</i><span class="visually-hidden">Pinned</span>';
        badgeContainer.prepend(badge);
      }
    } else {
      const badge = badgeContainer.querySelector('.pin-badge');
      if (badge) badge.remove();
    }
  }

  function reattachEventListeners() {
    const allCards = document.querySelectorAll('.item-card .item-body, .item-row .item-body');
    allCards.forEach((itemBody) => {
      if (!itemBody.hasAttribute('data-listeners-attached') && typeof window.attachCardClickListeners === 'function') {
        window.attachCardClickListeners(itemBody);
      }
    });
  }

  function isValidItemType(type) {
    return ALLOWED_ITEM_TYPES.includes(type);
  }

  function getCurrentFolderId() {
    const folderIdInput = document.getElementById('htmx-folder-id-input');
    return localStorage.getItem('currentFolderId') || (folderIdInput ? folderIdInput.value : '');
  }

  return {
    deleteItem,
    togglePublicItem,
    togglePinItem,
    sendItem,
    renameItem,
    copyItem,
    cutItem,
    downloadItem,
    isValidItemType,
    getCurrentFolderId,
    reattachEventListeners
  };
})();

window.FolderOperations = FolderOperations;
console.log('[FOLDER OPS] Module loaded and ready');
