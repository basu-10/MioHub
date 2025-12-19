/**
 * Folder Operations Module
 * Centralized module for all file/folder operations in folder_view
 * 
 * Provides both individual and batch operations for:
 * - Delete
 * - Toggle public/private
 * - Send to users
 * - Pin/Unpin
 * - Cut/Copy/Paste
 * - Rename
 * - Download
 * 
 * Dependencies:
 * - Bootstrap 5.3.3+ (for modals)
 * - HTMX 1.9.10+ (for AJAX operations)
 * - TelemetryPanel (optional, for status notifications)
 * - Material Icons (for UI elements)
 * 
 * Integration:
 * - Individual operations: Called from preview panel (folder_view_preview_panel_partial.html)
 * - Batch operations: Called from batch operations bar (folder_view_batch_operations_partial.html)
 * 
 * @version 1.0.0
 * @date 2024-12-14
 */

const FolderOperations = (function() {
  'use strict';

  // ==================== CONFIGURATION ====================
  const ALLOWED_ITEM_TYPES = [
    'folder', 'note', 'board', 'file', 'book', 'markdown', 
    'todo', 'diagram', 'table', 'blocks', 'code', 'pdf',
    'proprietary_infinite_whiteboard', 'proprietary_graph'
  ];

  // ==================== INDIVIDUAL OPERATIONS ====================

  /**
   * Delete a single item (from preview panel)
   * @param {Object} item - Item object with {type, id, card}
   * @param {string} itemName - Display name of the item
   */
  function deleteItem(item, itemName) {
    if (!item) {
      console.warn('[DELETE] No item provided');
      return;
    }

    console.log('[DELETE] Attempting to delete item:', item);
    console.log('[DELETE] Item type:', item.type);
    console.log('[DELETE] Item id:', item.id);
    console.log('[DELETE] Item name:', itemName);

    if (!confirm(`Are you sure you want to delete "${itemName}"?`)) {
      console.log('[DELETE] User cancelled deletion');
      return;
    }

    if (window.TelemetryPanel) {
      window.TelemetryPanel.setActive(`Deleting ${itemName}...`);
    }

    // Delete via direct API call (don't use batch button to avoid timing issues)
    const formData = new FormData();
    const itemsPayload = [{ type: item.type, id: item.id }];
    console.log('[DELETE] Payload:', itemsPayload);
    formData.append('items', JSON.stringify(itemsPayload));

    console.log('[DELETE] Sending request to /folders/batch_delete');
    fetch('/folders/batch_delete', {
      method: 'POST',
      body: formData,
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => {
      console.log('[DELETE] Response status:', response.status);
      return response.json();
    })
    .then(data => {
      console.log('[DELETE] Response data:', data);
      if (data.success) {
        // Remove card from DOM
        if (item.card) {
          const colWrapper = item.card.closest('.col');
          if (colWrapper) {
            console.log('[DELETE] Removing col wrapper');
            colWrapper.remove();
          } else {
            console.log('[DELETE] Removing card directly');
            item.card.remove();
          }
          
          // Also remove corresponding table row
          const tableRow = document.querySelector(`.item-row[data-type="${item.type}"][data-id="${item.id}"]`);
          if (tableRow) {
            console.log('[DELETE] Removing table row');
            tableRow.remove();
          }
        }

        if (window.TelemetryPanel) {
          window.TelemetryPanel.setIdle(`Deleted ${itemName}`);
          if (typeof window.TelemetryPanel.fetchData === 'function') {
            window.TelemetryPanel.fetchData();
          }
        }
        console.log('[DELETE] Delete successful');
      } else {
        throw new Error(data.message || 'Delete failed');
      }
    })
    .catch(error => {
      console.error('[DELETE] Failed:', error);
      if (window.TelemetryPanel) {
        window.TelemetryPanel.setIdle(`Delete failed: ${error.message}`);
      } else {
        alert(`Failed to delete: ${error.message}`);
      }
    });
  }

  /**
   * Toggle public/private status for a single item (from preview panel)
   * @param {Object} item - Item object with {type, id, card}
   */
  function updateCardPublicBadge(type, id, isPublic, cardElement = null) {
    // Build selector for matching card in the grid
    let selector;
    if (type === 'note' || type === 'board' || type === 'folder') {
      selector = `[data-type="${type}"][data-id="${id}"]`;
    } else if (type === 'file') {
      selector = `[data-type="file"][data-id="${id}"]`;
    } else {
      selector = `[data-type="${type}"][data-id="${id}"], [data-type="file"][data-id="${id}"]`;
    }

    // Try to find card: use passed element if connected, otherwise query
    const card = (cardElement && cardElement.isConnected) ? cardElement : 
                 (document.querySelector(selector) || document.querySelector(`[data-id="${id}"]`));
                 
    if (!card) {
      console.warn('[TOGGLE PUBLIC] Card not found for update', { type, id });
      return;
    }

    // Update dataset state
    card.dataset.isPublic = isPublic ? '1' : '0';

    // Ensure badge container exists
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
        badge.innerHTML = '<i class="material-icons" aria-hidden="true">public</i><span class="visually-hidden">Public</span>';
        // Prepend to ensure it appears before type badge
        badgeContainer.prepend(badge);
      }
    } else {
      const badge = badgeContainer.querySelector('.public-badge');
      if (badge) {
        badge.remove();
      }
    }
  }

  // Track last public toggle so we can re-apply after HTMX swaps
  let lastPublicToggleState = null;

  function togglePublicItem(item) {
    if (!item) {
      console.warn('[TOGGLE PUBLIC] No item provided');
      return;
    }

    const isPublic = item.card?.dataset.isPublic === '1' || item.card?.dataset.isPublic === 'true';
    console.log('[TOGGLE PUBLIC] Current state:', isPublic);

    if (window.TelemetryPanel) {
      window.TelemetryPanel.setActive(`${isPublic ? 'Making private' : 'Making public'}...`);
    }

    const items = [{ type: item.type, id: item.id }];
    const folderIdInput = document.getElementById('htmx-folder-id-input');
    const currentFolderId = localStorage.getItem('currentFolderId') || 
                           (folderIdInput ? folderIdInput.value : '');

    const publicButton = document.getElementById('btn-batch-public');
    if (!publicButton) {
      console.error('[TOGGLE PUBLIC] Public button not found');
      return;
    }

    // Optimistically update the card immediately for instant feedback
    const newPublicState = !isPublic;
    lastPublicToggleState = { type: item.type, id: item.id, isPublic: newPublicState };
    updateCardPublicBadge(item.type, item.id, newPublicState, item.card);

    // Dispatch custom event immediately for preview panel to refresh instantly
    document.dispatchEvent(new CustomEvent('previewItemPublicChanged', {
      detail: {
        type: item.type,
        id: item.id,
        isPublic: newPublicState
      }
    }));
    console.log('[TOGGLE PUBLIC] Dispatched optimistic previewItemPublicChanged event');

    // Use HTMX ajax with proper object values
    htmx.ajax('POST', '/folders/batch_toggle_public_htmx', {
      source: publicButton,
      swap: 'none',
      target: publicButton,
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      values: {
        items: JSON.stringify(items),
        folder_id: currentFolderId
      }
    }).then(() => {
      // Wait for HTMX OOB swaps to complete, then reattach listeners
      setTimeout(() => {
        reattachEventListeners();
        
        // Clear batch selection
        if (window.batchSelected) {
          window.batchSelected = [];
        }

        if (window.TelemetryPanel) {
          window.TelemetryPanel.setIdle(isPublic ? 'Made private' : 'Made public');
        }
        
        // Re-dispatch event to ensure consistency after HTMX swap
        document.dispatchEvent(new CustomEvent('previewItemPublicChanged', {
          detail: {
            type: item.type,
            id: item.id,
            isPublic: newPublicState
          }
        }));
      }, 300);
    }).catch((err) => {
      console.error('[TOGGLE PUBLIC] HTMX request failed:', err);
      if (window.TelemetryPanel) {
        window.TelemetryPanel.setIdle('Public toggle failed');
      }

      // Revert optimistic update on failure
      updateCardPublicBadge(item.type, item.id, isPublic, item.card);
      lastPublicToggleState = null;
      
      // Revert preview panel state
      document.dispatchEvent(new CustomEvent('previewItemPublicChanged', {
        detail: {
          type: item.type,
          id: item.id,
          isPublic: isPublic
        }
      }));
    });
  }

  // After HTMX swaps (including OOB), re-apply the last public toggle to the new DOM
  document.body.addEventListener('htmx:afterSwap', function() {
    if (lastPublicToggleState) {
      const { type, id, isPublic } = lastPublicToggleState;
      updateCardPublicBadge(type, id, isPublic);
    }
    
    if (lastPinToggleState) {
      const { type, id, isPinned } = lastPinToggleState;
      updateCardPinBadge(type, id, isPinned);
    }
  });

  function updateCardPinBadge(type, id, isPinned, cardElement = null) {
    // Build selector for matching card in the grid
    let selector;
    if (type === 'note' || type === 'board' || type === 'folder') {
      selector = `[data-type="${type}"][data-id="${id}"]`;
    } else if (type === 'file') {
      selector = `[data-type="file"][data-id="${id}"]`;
    } else {
      selector = `[data-type="${type}"][data-id="${id}"], [data-type="file"][data-id="${id}"]`;
    }

    // Try to find card: use passed element if connected, otherwise query
    const card = (cardElement && cardElement.isConnected) ? cardElement : 
                 (document.querySelector(selector) || document.querySelector(`[data-id="${id}"]`));
                 
    if (!card) {
      console.warn('[TOGGLE PIN] Card not found for update', { type, id });
      return;
    }

    // Update dataset state
    card.dataset.isPinned = isPinned ? '1' : '0';

    // Ensure badge container exists
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
        // Prepend to ensure it appears before type badge
        badgeContainer.prepend(badge);
      }
    } else {
      const badge = badgeContainer.querySelector('.pin-badge');
      if (badge) {
        badge.remove();
      }
    }
  }

  // Track last pin toggle so we can re-apply after HTMX swaps
  let lastPinToggleState = null;

  /**
   * Toggle pin status for a single item (from preview panel)
   * @param {Object} item - Item object with {type, id, card}
   */
  function togglePinItem(item) {
    if (!item) {
      console.warn('[TOGGLE PIN] No item provided');
      return;
    }

    // Skip folders
    if (item.type === 'folder') {
      console.log('[TOGGLE PIN] Skipping folder');
      if (window.TelemetryPanel) {
        window.TelemetryPanel.setIdle('Folders cannot be pinned');
      }
      return;
    }

    const isPinned = item.card?.dataset.isPinned === '1' || item.card?.dataset.isPinned === 'true';
    console.log('[TOGGLE PIN] Current state:', isPinned);

    if (window.TelemetryPanel) {
      window.TelemetryPanel.setActive(`${isPinned ? 'Unpinning' : 'Pinning'} item...`);
    }

    const items = [{ type: item.type, id: item.id }];
    const folderIdInput = document.getElementById('htmx-folder-id-input');
    const currentFolderId = localStorage.getItem('currentFolderId') || 
                           (folderIdInput ? folderIdInput.value : '');

    const pinButton = document.getElementById('btn-batch-pin');
    if (!pinButton) {
      console.error('[TOGGLE PIN] Pin button not found');
      return;
    }

    // Optimistically update the card immediately for instant feedback
    const newPinState = !isPinned;
    lastPinToggleState = { type: item.type, id: item.id, isPinned: newPinState };
    updateCardPinBadge(item.type, item.id, newPinState, item.card);

    // Dispatch custom event immediately for preview panel to refresh instantly
    document.dispatchEvent(new CustomEvent('previewItemPinChanged', {
      detail: {
        type: item.type,
        id: item.id,
        isPinned: newPinState
      }
    }));
    console.log('[TOGGLE PIN] Dispatched optimistic previewItemPinChanged event');

    // Use HTMX ajax with proper object values
    htmx.ajax('POST', '/folders/batch_toggle_pin_htmx', {
      source: pinButton,
      swap: 'none',
      target: pinButton,
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      values: {
        items: JSON.stringify(items),
        folder_id: currentFolderId
      }
    }).then(() => {
      // Wait for HTMX OOB swaps to complete, then reattach listeners
      setTimeout(() => {
        reattachEventListeners();

        // Clear batch selection
        if (window.batchSelected) {
          window.batchSelected = [];
        }

        if (window.TelemetryPanel) {
          window.TelemetryPanel.setIdle(isPinned ? 'Item unpinned' : 'Item pinned');
        }

        // Re-dispatch event to ensure consistency after HTMX swap
        document.dispatchEvent(new CustomEvent('previewItemPinChanged', {
          detail: {
            type: item.type,
            id: item.id,
            isPinned: newPinState
          }
        }));
      }, 300);
    }).catch((err) => {
      console.error('[TOGGLE PIN] HTMX request failed:', err);
      if (window.TelemetryPanel) {
        window.TelemetryPanel.setIdle('Pin operation failed');
      }

      // Revert optimistic update on failure
      updateCardPinBadge(item.type, item.id, isPinned, item.card);
      lastPinToggleState = null;

      // Revert preview panel state
      document.dispatchEvent(new CustomEvent('previewItemPinChanged', {
        detail: {
          type: item.type,
          id: item.id,
          isPinned: isPinned
        }
      }));
    });
  }

  /**
   * Send a single item to another user (from preview panel)
   * @param {Object} item - Item object with {type, id, card}
   */
  function sendItem(item) {
    if (!item) {
      console.warn('[SEND] No item provided');
      return;
    }

    const modal = document.getElementById('sendToModal');
    if (!modal) {
      console.warn('[SEND] sendToModal not found');
      return;
    }

    const resolvedType = (item.type === 'file' && item.card?.dataset.fileType)
      ? item.card.dataset.fileType
      : item.type;
    const itemId = item.id;
    const title = item.card?.querySelector('.item-link')?.textContent?.trim() || `${resolvedType} ${itemId}`;
    const description = `Select a pinned user to send "${title}" to:`;
    const payloadItems = [{ type: resolvedType, id: itemId }];

    if (typeof window.openSendToModalWithItems === 'function') {
      window.openSendToModalWithItems(payloadItems, { mode: 'single', description });
    } else {
      // Fallback: configure modal inline
      modal.dataset.batchMode = 'false';
      modal.dataset.batchItems = '[]';
      modal.dataset.selectedType = resolvedType;
      modal.dataset.selectedId = itemId;
      const descEl = document.getElementById('sendToModalDescription');
      if (descEl) {
        descEl.textContent = description;
      }
      if (modal.parentElement !== document.body) {
        document.body.appendChild(modal);
      }
      modal.style.zIndex = '3000';
      try {
        bootstrap.Modal.getOrCreateInstance(modal).show();
      } catch (err) {
        try {
          const bs = new bootstrap.Modal(modal);
          bs.show();
        } catch (e) {
          console.error('[SEND] Unable to open send modal', e);
        }
      }
    }
  }

  /**
   * Rename a single item (from preview panel)
   * @param {Object} item - Item object with {type, id, card}
   */
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
    } else if (item.type === 'note') {
      const link = item.card.querySelector('.card-title a.item-link');
      const currentName = link ? link.textContent.trim() : '';
      const currentDescription = item.card.dataset.noteDescription || '';
      if (window.openRenameNoteDescModal) {
        window.openRenameNoteDescModal(item.id, currentName, currentDescription);
      }
    } else if (item.type === 'board' || item.type === 'whiteboard') {
      const link = item.card.querySelector('.card-title a.item-link');
      const currentName = link ? link.textContent.trim() : '';
      const currentDescription = item.card.dataset.boardDescription || '';
      if (window.openRenameBoardDescModal) {
        window.openRenameBoardDescModal(item.id, currentName, currentDescription);
      }
    } else {
      // Files (markdown, todo, diagram, table, blocks, book, etc.)
      const link = item.card.querySelector('.card-title a.item-link');
      const currentName = link ? link.textContent.trim() : '';
      const currentDescription = item.card.dataset.fileDescription || '';
      if (window.openRenameFileDescModal) {
        window.openRenameFileDescModal(item.id, currentName, currentDescription);
      }
    }
  }

  /**
   * Copy a single item to clipboard (from preview panel)
   * @param {Object} item - Item object with {type, id, card}
   */
  function copyItem(item) {
    if (!item) {
      console.warn('[COPY] No item provided');
      return;
    }

    // Use batch copy functionality
    window.batchSelected = [item];
    const btnBatchCopy = document.getElementById('btn-batch-copy');
    if (btnBatchCopy) {
      btnBatchCopy.click();
      window.batchSelected = [];
    }

    if (window.TelemetryPanel) {
      window.TelemetryPanel.setIdle('Item copied to clipboard');
    }
  }

  /**
   * Cut a single item to clipboard (from preview panel)
   * @param {Object} item - Item object with {type, id, card}
   */
  function cutItem(item) {
    if (!item) {
      console.warn('[CUT] No item provided');
      return;
    }

    // Use batch cut functionality
    window.batchSelected = [item];
    const btnBatchCut = document.getElementById('btn-batch-cut');
    if (btnBatchCut) {
      btnBatchCut.click();
      window.batchSelected = [];
    }

    if (window.TelemetryPanel) {
      window.TelemetryPanel.setIdle('Item cut to clipboard');
    }
  }

  /**
   * Download a single item (from preview panel)
   * @param {Object} item - Item object with {type, id, card}
   * @param {string} itemName - Display name for the download
   */
  function downloadItem(item, itemName) {
    if (!item) {
      console.warn('[DOWNLOAD] No item provided');
      return;
    }

    // Show download format modal (defined in preview panel)
    if (typeof window.showDownloadModal === 'function') {
      window.showDownloadModal(item, itemName);
    } else {
      console.error('[DOWNLOAD] showDownloadModal function not found');
    }
  }

  // ==================== BATCH OPERATIONS ====================

  /**
   * Delete multiple items (from batch operations bar)
   * @param {Array} items - Array of item objects [{type, id, card}, ...]
   */
  function batchDelete(items) {
    if (!items || items.length === 0) {
      console.warn('[BATCH DELETE] No items provided');
      return;
    }

    const itemCount = items.length;
    const itemWord = itemCount === 1 ? 'item' : 'items';
    
    if (!confirm(`Are you sure you want to delete ${itemCount} ${itemWord}?`)) {
      return;
    }

    if (window.TelemetryPanel) {
      window.TelemetryPanel.setActive(`Deleting ${itemCount} ${itemWord}...`);
    }

    // Build request payload
    const payload = items.map(item => ({ type: item.type, id: item.id }));
    const folderIdInput = document.getElementById('htmx-folder-id-input');
    const currentFolderId = localStorage.getItem('currentFolderId') || 
                           (folderIdInput ? folderIdInput.value : '');

    // Send delete request
    fetch('/folders/batch_delete_htmx', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: JSON.stringify({
        items: payload,
        folder_id: currentFolderId
      })
    })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        // Remove deleted items from DOM
        items.forEach(item => {
          if (item.card) {
            const col = item.card.closest('.col');
            if (col) col.remove();
            else item.card.remove();
          }
        });

        // Clear batch selection
        window.batchSelected = [];
        if (typeof window.updateBatchUI === 'function') {
          window.updateBatchUI();
        }

        if (window.TelemetryPanel) {
          window.TelemetryPanel.setIdle(`Deleted ${itemCount} ${itemWord}`);
        }
      } else {
        throw new Error(data.error || 'Delete failed');
      }
    })
    .catch(error => {
      console.error('[BATCH DELETE] Failed:', error);
      if (window.TelemetryPanel) {
        window.TelemetryPanel.setIdle(`Delete failed: ${error.message}`);
      }
      alert(`Failed to delete items: ${error.message}`);
    });
  }

  /**
   * Toggle public/private for multiple items (from batch operations bar)
   * @param {Array} items - Array of item objects [{type, id, card}, ...]
   */
  function batchTogglePublic(items) {
    if (!items || items.length === 0) {
      console.warn('[BATCH PUBLIC] No items provided');
      return;
    }

    const itemCount = items.length;
    if (window.TelemetryPanel) {
      window.TelemetryPanel.setActive(`Toggling public status for ${itemCount} items...`);
    }

    const payload = items.map(item => ({ type: item.type, id: item.id }));
    const folderIdInput = document.getElementById('htmx-folder-id-input');
    const currentFolderId = localStorage.getItem('currentFolderId') || 
                           (folderIdInput ? folderIdInput.value : '');

    const publicButton = document.getElementById('btn-batch-public');
    if (!publicButton) {
      console.error('[BATCH PUBLIC] Public button not found');
      return;
    }

    htmx.ajax('POST', '/folders/batch_toggle_public_htmx', {
      source: publicButton,
      swap: 'none',
      target: publicButton,
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      values: {
        items: JSON.stringify(payload),
        folder_id: currentFolderId
      }
    }).then(() => {
      setTimeout(() => {
        reattachEventListeners();
        
        // Clear batch selection
        if (window.batchSelected) {
          window.batchSelected = [];
        }

        if (window.TelemetryPanel) {
          window.TelemetryPanel.setIdle(`Updated ${itemCount} items`);
        }
      }, 300);
    }).catch((err) => {
      console.error('[BATCH PUBLIC] HTMX request failed:', err);
      if (window.TelemetryPanel) {
        window.TelemetryPanel.setIdle('Public toggle failed');
      }
    });
  }

  /**
   * Toggle pin status for multiple items (from batch operations bar)
   * @param {Array} items - Array of item objects [{type, id, card}, ...]
   */
  function batchTogglePin(items) {
    if (!items || items.length === 0) {
      console.warn('[BATCH PIN] No items provided');
      return;
    }

    // Filter out folders (folders cannot be pinned)
    const pinnableItems = items.filter(item => item.type !== 'folder');
    if (pinnableItems.length === 0) {
      if (window.TelemetryPanel) {
        window.TelemetryPanel.setIdle('Folders cannot be pinned');
      }
      return;
    }

    const itemCount = pinnableItems.length;
    if (window.TelemetryPanel) {
      window.TelemetryPanel.setActive(`Toggling pin status for ${itemCount} items...`);
    }

    const payload = pinnableItems.map(item => ({ type: item.type, id: item.id }));
    const folderIdInput = document.getElementById('htmx-folder-id-input');
    const currentFolderId = localStorage.getItem('currentFolderId') || 
                           (folderIdInput ? folderIdInput.value : '');

    const pinButton = document.getElementById('btn-batch-pin');
    if (!pinButton) {
      console.error('[BATCH PIN] Pin button not found');
      return;
    }

    htmx.ajax('POST', '/folders/batch_toggle_pin_htmx', {
      source: pinButton,
      swap: 'none',
      target: pinButton,
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      values: {
        items: JSON.stringify(payload),
        folder_id: currentFolderId
      }
    }).then(() => {
      setTimeout(() => {
        reattachEventListeners();

        // Clear batch selection
        if (window.batchSelected) {
          window.batchSelected = [];
        }

        if (window.TelemetryPanel) {
          window.TelemetryPanel.setIdle(`Updated ${itemCount} items`);
        }
      }, 300);
    }).catch((err) => {
      console.error('[BATCH PIN] HTMX request failed:', err);
      if (window.TelemetryPanel) {
        window.TelemetryPanel.setIdle('Pin operation failed');
      }
    });
  }

  /**
   * Send multiple items to another user (from batch operations bar)
   * @param {Array} items - Array of item objects [{type, id, card}, ...]
   */
  function batchSend(items) {
    if (!items || items.length === 0) {
      console.warn('[BATCH SEND] No items provided');
      return;
    }

    const itemCount = items.length;
    const description = `Select a pinned user to send ${itemCount} item${itemCount > 1 ? 's' : ''} to:`;
    
    const payloadItems = items.map(item => {
      const resolvedType = (item.type === 'file' && item.card?.dataset.fileType)
        ? item.card.dataset.fileType
        : item.type;
      return { type: resolvedType, id: item.id };
    });

    if (typeof window.openSendToModalWithItems === 'function') {
      window.openSendToModalWithItems(payloadItems, { mode: 'batch', description });
    } else {
      // Fallback: configure modal inline
      const modal = document.getElementById('sendToModal');
      if (!modal) {
        console.error('[BATCH SEND] sendToModal not found');
        return;
      }

      modal.dataset.batchMode = 'true';
      modal.dataset.batchItems = JSON.stringify(payloadItems);
      const descEl = document.getElementById('sendToModalDescription');
      if (descEl) {
        descEl.textContent = description;
      }
      if (modal.parentElement !== document.body) {
        document.body.appendChild(modal);
      }
      modal.style.zIndex = '3000';
      const bs = new bootstrap.Modal(modal);
      bs.show();
    }
  }

  /**
   * Copy multiple items to clipboard (from batch operations bar)
   * @param {Array} items - Array of item objects [{type, id, card}, ...]
   */
  function batchCopy(items) {
    if (!items || items.length === 0) {
      console.warn('[BATCH COPY] No items provided');
      return;
    }

    const btnBatchCopy = document.getElementById('btn-batch-copy');
    if (btnBatchCopy) {
      btnBatchCopy.click();
    }
  }

  /**
   * Cut multiple items to clipboard (from batch operations bar)
   * @param {Array} items - Array of item objects [{type, id, card}, ...]
   */
  function batchCut(items) {
    if (!items || items.length === 0) {
      console.warn('[BATCH CUT] No items provided');
      return;
    }

    const btnBatchCut = document.getElementById('btn-batch-cut');
    if (btnBatchCut) {
      btnBatchCut.click();
    }
  }

  /**
   * Paste items from clipboard (from batch operations bar)
   */
  function batchPaste() {
    const btnBatchPaste = document.getElementById('btn-batch-paste');
    if (btnBatchPaste) {
      btnBatchPaste.click();
    }
  }

  // ==================== UTILITY FUNCTIONS ====================

  /**
   * Reattach event listeners to updated cards after HTMX operations
   * Only attaches to cards that don't have listeners yet
   */
  function reattachEventListeners() {
    console.log('[FOLDER OPS] Reattaching event listeners to updated cards...');
    const allCards = document.querySelectorAll('.item-card .item-body, .item-row .item-body');
    let reattachedCount = 0;

    allCards.forEach(itemBody => {
      // Only attach to cards that DON'T have listeners yet
      if (!itemBody.hasAttribute('data-listeners-attached')) {
        if (typeof window.attachCardClickListeners === 'function') {
          window.attachCardClickListeners(itemBody);
          reattachedCount++;
        }
      }
    });

    console.log(`[FOLDER OPS] Event listeners reattached to ${reattachedCount} new cards (${allCards.length} total)`);
  }

  /**
   * Validate item type
   * @param {string} type - Item type to validate
   * @returns {boolean} True if valid
   */
  function isValidItemType(type) {
    return ALLOWED_ITEM_TYPES.includes(type);
  }

  /**
   * Get current folder ID from various sources
   * @returns {string} Current folder ID
   */
  function getCurrentFolderId() {
    const folderIdInput = document.getElementById('htmx-folder-id-input');
    return localStorage.getItem('currentFolderId') || 
           (folderIdInput ? folderIdInput.value : '');
  }

  // ==================== PUBLIC API ====================

  return {
    // Individual operations (called from preview panel)
    deleteItem: deleteItem,
    togglePublicItem: togglePublicItem,
    togglePinItem: togglePinItem,
    sendItem: sendItem,
    renameItem: renameItem,
    copyItem: copyItem,
    cutItem: cutItem,
    downloadItem: downloadItem,

    // Batch operations (called from batch operations bar)
    batchDelete: batchDelete,
    batchTogglePublic: batchTogglePublic,
    batchTogglePin: batchTogglePin,
    batchSend: batchSend,
    batchCopy: batchCopy,
    batchCut: batchCut,
    batchPaste: batchPaste,

    // Utility functions
    isValidItemType: isValidItemType,
    getCurrentFolderId: getCurrentFolderId,
    reattachEventListeners: reattachEventListeners
  };
})();

// Expose globally for template access
window.FolderOperations = FolderOperations;

console.log('[FOLDER OPS] Module loaded and ready');
