/**
 * Clipboard Operations Module
 * Handles cut, copy, paste, delete, and clear clipboard functionality
 * for both single-click and batch (Ctrl+click) operations in folder_view.
 * 
 * Dependencies:
 * - Bootstrap 5.3.3+ (for modals)
 * - TelemetryPanel (optional, for status notifications)
 * - Material Icons (for UI elements)
 * 
 * Usage:
 * 1. Include this file after DOM is ready
 * 2. Ensure action bar partial and batch operations partial are loaded
 * 3. Call ClipboardOperations.init() to initialize all handlers
 */

const ClipboardOperations = (function() {
  'use strict';

  // ==================== STATE MANAGEMENT ====================
  let clipboard = null;
  const CLIPBOARD_KEY = 'p2_clipboard';
  
  // Operation lock to prevent race conditions
  let operationInProgress = false;
  
  // References to UI elements
  let actionButtons = {};
  let batchButtons = {};
  let batchOperations = null;
  let batchCount = null;
  
  // Security configuration
  const MAX_BATCH_SIZE = 100; // Prevent memory exhaustion
  const MAX_CLIPBOARD_AGE = 24 * 60 * 60 * 1000; // 24 hours in ms
  const ALLOWED_ITEM_TYPES = [
    'folder', 'note', 'board', 'file', 
    // File types (matching VALID_FILE_TYPES in models.py)
    'proprietary_note', 'proprietary_whiteboard', 'proprietary_blocks', 
    'proprietary_infinite_whiteboard', 'proprietary_graph',
    'markdown', 'code', 'todo', 'diagram', 'table', 'blocks', 'timeline', 'pdf',
    // Legacy aliases
    'book'
  ];

  const SECTION_CONFIGS = {
    'proprietary_graph': {
      sectionId: 'graph-workspaces',
      navLabel: 'Graph Workspaces',
      navIcon: 'device_hub'
    },
    'proprietary_infinite_whiteboard': {
      sectionId: 'infinite-whiteboards',
      navLabel: 'Infinite Whiteboards',
      navIcon: 'grid_on'
    }
  };
  
  function getClassWithPrefix(element, prefix, fallback) {
    if (!element) return fallback;
    const match = Array.from(element.classList || []).find(cls => cls.startsWith(prefix));
    return match || fallback;
  }
  
  function updateNavPillCount(sectionId, count, labelOverride) {
    if (!sectionId) return;
    const pill = document.querySelector(`.nav-pill[data-section-id="${sectionId}"]`) || document.querySelector(`.nav-pill[onclick*="scrollToSection('${sectionId}')"]`);
    if (!pill) return;
  
    if (typeof count === 'number' && count <= 0) {
      pill.remove();
      return;
    }
  
    const textSpan = pill.querySelector('span');
    if (!textSpan) return;
  
    const baseLabel = labelOverride || pill.dataset.label || textSpan.textContent.replace(/\s*\(.*\)$/, '').trim() || sectionId;
    pill.dataset.label = baseLabel;
    pill.dataset.sectionId = sectionId;
  
    if (typeof count === 'number') {
      textSpan.textContent = `${baseLabel} (${count})`;
    }
  }
  
  function ensureNavPill(sectionId, label, icon, count) {
    const navContainer = document.querySelector('.section-nav');
    if (!navContainer || !sectionId) return;
  
    const existing = navContainer.querySelector(`.nav-pill[data-section-id="${sectionId}"]`) || navContainer.querySelector(`.nav-pill[onclick*="scrollToSection('${sectionId}')"]`);
    if (existing) {
      existing.dataset.sectionId = sectionId;
      existing.dataset.label = existing.dataset.label || label || sectionId;
      updateNavPillCount(sectionId, typeof count === 'number' ? count : undefined, label);
      return;
    }
  
    const pill = document.createElement('div');
    pill.className = 'nav-pill';
    pill.dataset.sectionId = sectionId;
    if (label) {
      pill.dataset.label = label;
    }
    pill.setAttribute('onclick', `scrollToSection('${sectionId}')`);
    pill.innerHTML = `<i class="material-icons">${icon || 'insert_drive_file'}</i><span>${label || sectionId} (${count ?? 0})</span>`;
  
    const topBtn = navContainer.querySelector('.nav-top-btn');
    navContainer.insertBefore(pill, topBtn || null);
  }
  
  function ensureSectionForType(config) {
    if (!config || !config.sectionId) return null;
    let section = document.getElementById(config.sectionId);
    if (section) return section;
  
    const container = document.getElementById('mainContent') || document.querySelector('.container-fluid') || document.body;
    const referenceGrid = document.querySelector('.content-grid');
    const lgCols = getClassWithPrefix(referenceGrid, 'row-cols-lg-', 'row-cols-lg-3');
    const mdCols = getClassWithPrefix(referenceGrid, 'row-cols-md-', 'row-cols-md-2');
    const gapClass = getClassWithPrefix(referenceGrid, 'g-', 'g-4');
    const viewMode = referenceGrid?.dataset.viewMode || 'grid';
    const cardSize = referenceGrid?.dataset.cardSize || 'normal';
  
    section = document.createElement('div');
    section.className = 'section-container files-section';
    section.id = config.sectionId;
    section.innerHTML = `
      <div class="section-header files-header">
        <h3 class="section-title">
          <i class="material-icons">${config.navIcon || 'insert_drive_file'}</i>
          ${config.navLabel || config.sectionId}
          <span class="count-badge">0</span>
        </h3>
      </div>
      <div class="content-grid row row-cols-1 ${mdCols} ${lgCols} ${gapClass}" data-view-mode="${viewMode}" data-card-size="${cardSize}"></div>
    `;
  
    const contextMenu = document.getElementById('context-menu');
    if (contextMenu && contextMenu.parentNode === container) {
      container.insertBefore(section, contextMenu);
    } else {
      container.appendChild(section);
    }
  
    ensureNavPill(config.sectionId, config.navLabel, config.navIcon, 0);
    return section;
  }

  // ==================== SECURITY UTILITIES ====================
  
  /**
   * Sanitize text to prevent XSS attacks
   * @param {string} text - The text to sanitize
   * @returns {string} - Sanitized text
   */
  function sanitizeText(text) {
    if (typeof text !== 'string') return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
  
  /**
   * Validate item type against whitelist
   * @param {string} type - The item type to validate
   * @returns {boolean} - True if valid
   */
  function isValidItemType(type) {
    return ALLOWED_ITEM_TYPES.includes(type);
  }
  
  /**
   * Validate numeric ID
   * @param {*} id - The ID to validate
   * @returns {boolean} - True if valid
   */
  function isValidId(id) {
    const numId = parseInt(id, 10);
    return !isNaN(numId) && numId > 0 && numId < 2147483647; // MySQL INT max
  }
  
  /**
   * Get CSRF token from meta tag or cookie
   * @returns {string|null} - CSRF token or null
   */
  function getCSRFToken() {
    // Try meta tag first
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) return metaTag.getAttribute('content');
    
    // Try cookie
    const match = document.cookie.match(/csrf_token=([^;]+)/);
    return match ? match[1] : null;
  }
  
  /**
   * Validate clipboard data structure
   * @param {Object} data - Clipboard data to validate
   * @returns {boolean} - True if valid
   */
  function validateClipboardData(data) {
    if (!data || typeof data !== 'object') return false;
    
    // Check timestamp if present
    if (data.timestamp) {
      const age = Date.now() - data.timestamp;
      if (age > MAX_CLIPBOARD_AGE) return false;
    }
    
    // Validate single item clipboard
    if (data.type && data.id) {
      if (!isValidItemType(data.type)) return false;
      if (!isValidId(data.id)) return false;
      if (!['cut', 'copy'].includes(data.action)) return false;
      return true;
    }
    
    // Validate batch clipboard
    if (data.items && Array.isArray(data.items)) {
      if (data.items.length === 0 || data.items.length > MAX_BATCH_SIZE) return false;
      if (!['cut', 'copy'].includes(data.action)) return false;
      
      for (const item of data.items) {
        if (!isValidItemType(item.type)) return false;
        if (!isValidId(item.id)) return false;
      }
      return true;
    }
    
    return false;
  }
  
  /**
   * Safe DOM query with null check
   * @param {string} selector - CSS selector
   * @param {Element} parent - Parent element (optional)
   * @returns {Element|null} - Found element or null
   */
  function safeQuery(selector, parent = document) {
    try {
      return parent.querySelector(selector);
    } catch (e) {
      console.error('Invalid selector:', selector, e);
      return null;
    }
  }
  
  /**
   * Safe DOM query all with null check
   * @param {string} selector - CSS selector
   * @param {Element} parent - Parent element (optional)
   * @returns {NodeList} - Found elements or empty NodeList
   */
  function safeQueryAll(selector, parent = document) {
    try {
      return parent.querySelectorAll(selector);
    } catch (e) {
      console.error('Invalid selector:', selector, e);
      return [];
    }
  }

  // ==================== INITIALIZATION ====================
  
  /**
   * Initialize the clipboard operations module
   * Sets up event listeners and loads saved clipboard state
   */
  function init() {
    try {
      if (typeof bootstrap === 'undefined') {
        console.error('ClipboardOperations: Bootstrap is required but not found');
        return;
      }

      // Get references to action bar buttons (single selection)
      actionButtons = {
        cut: safeQuery('#btn-cut'),
        copy: safeQuery('#btn-copy'),
        paste: safeQuery('#btn-paste'),
        delete: safeQuery('#btn-delete')
      };

      // Get references to batch operation buttons
      batchButtons = {
        cut: safeQuery('#btn-batch-cut'),
        copy: safeQuery('#btn-batch-copy'),
        paste: safeQuery('#btn-batch-paste'),
        clearClipboard: safeQuery('#btn-clear-clipboard'),
        pin: safeQuery('#btn-batch-pin'),
        send: safeQuery('#btn-batch-send'),
        public: safeQuery('#btn-batch-public'),
        delete: safeQuery('#btn-batch-delete'),
        clear: safeQuery('#btn-clear-batch')
      };

      console.log('ClipboardOperations: Batch buttons found:', {
        cut: !!batchButtons.cut,
        copy: !!batchButtons.copy,
        paste: !!batchButtons.paste,
        clearClipboard: !!batchButtons.clearClipboard,
        pin: !!batchButtons.pin,
        public: !!batchButtons.public,
        delete: !!batchButtons.delete,
        clear: !!batchButtons.clear
      });

      batchOperations = safeQuery('#batch-operations');
      batchCount = safeQuery('#batch-count');

      // Initialize window.batchSelected if not already defined
      if (!window.batchSelected) {
        window.batchSelected = [];
      }

      // Setup event listeners
      setupSingleOperationListeners();
      setupBatchOperationListeners();
      setupContextMenuListeners();

      // Load saved clipboard state
      loadClipboard();
      
      // Initialize batch UI to correct state (hide if nothing selected)
      updateBatchUI();

      console.log('ClipboardOperations: Initialized successfully');
    } catch (error) {
      console.error('ClipboardOperations: Initialization failed:', error);
    }
  }

  // ==================== CLIPBOARD STORAGE ====================

  /**
   * Load clipboard state from sessionStorage
   * Restores visual indicators for cut items
   */
  function loadClipboard() {
    try {
      const stored = sessionStorage.getItem(CLIPBOARD_KEY);
      if (!stored) return;
      
      const parsed = JSON.parse(stored);
      
      // Validate clipboard data before using
      if (!validateClipboardData(parsed)) {
        console.warn('Invalid clipboard data detected, clearing');
        sessionStorage.removeItem(CLIPBOARD_KEY);
        return;
      }
      
      clipboard = parsed;
      updatePasteButton();
      
      // Don't automatically show batch operations bar on load
      // It will be shown by updateBatchUI() when user selects items
      // Just ensure paste button state is correct
      if (clipboard && clipboard.items && clipboard.items.length > 0) {
        if (batchButtons.paste) {
          batchButtons.paste.disabled = false;
        }
      }
      
      // Apply cut styling to items in clipboard
      if (clipboard && clipboard.action === 'cut') {
        if (clipboard.items) {
          // Batch cut
          clipboard.items.forEach(item => {
            // Sanitize for selector safety
            const sanitizedType = CSS.escape(String(item.type));
            const sanitizedId = CSS.escape(String(item.id));
            const cutCard = safeQuery(`.item-card[data-type="${sanitizedType}"][data-id="${sanitizedId}"]`);
            if (cutCard) applyCutStyle(cutCard);
          });
        } else {
          // Single cut
          const sanitizedType = CSS.escape(String(clipboard.type));
          const sanitizedId = CSS.escape(String(clipboard.id));
          const cutCard = safeQuery(`.item-card[data-type="${sanitizedType}"][data-id="${sanitizedId}"]`);
          if (cutCard) applyCutStyle(cutCard);
        }
      }
    } catch (error) {
      console.error('Failed to load clipboard:', error);
      sessionStorage.removeItem(CLIPBOARD_KEY);
    }
  }

  /**
   * Save clipboard state to sessionStorage
   * Updates paste button state
   */
  function saveClipboard() {
    try {
      if (clipboard) {
        // Add timestamp for expiry checking
        clipboard.timestamp = Date.now();
        sessionStorage.setItem(CLIPBOARD_KEY, JSON.stringify(clipboard));
      } else {
        sessionStorage.removeItem(CLIPBOARD_KEY);
        safeQueryAll('.item-card').forEach(card => removeCutStyle(card));
      }
      updatePasteButton();
    } catch (error) {
      console.error('Failed to save clipboard:', error);
    }
  }

  /**
   * Update paste button enabled/disabled state across all UI locations
   * (action bar, batch operations, context menu, FAB)
   */
  function updatePasteButton() {
    const contextPasteItem = safeQuery('#context-paste-item');
    const contextClearItem = safeQuery('#context-clear-item');
    const fabPasteItem = safeQuery('#fab-paste-item');
    const fabClearItem = safeQuery('#fab-clear-item');
    
    if (clipboard) {
      if (clipboard.items && clipboard.items.length > 0) {
        // Batch clipboard
        if (batchButtons.paste) {
          batchButtons.paste.disabled = false;
        }
        if (batchButtons.clearClipboard) {
          batchButtons.clearClipboard.style.display = '';
        }
        if (contextPasteItem) contextPasteItem.style.display = 'block';
        if (contextClearItem) contextClearItem.style.display = 'block';
        if (fabPasteItem) fabPasteItem.classList.remove('hidden');
        if (fabClearItem) fabClearItem.classList.remove('hidden');
      } else {
        // Single item clipboard
        if (actionButtons.paste) {
          actionButtons.paste.disabled = false;
          actionButtons.paste.style.opacity = '1';
        }
        if (contextPasteItem) contextPasteItem.style.display = 'block';
        if (contextClearItem) contextClearItem.style.display = 'block';
        if (fabPasteItem) fabPasteItem.classList.remove('hidden');
        if (fabClearItem) fabClearItem.classList.remove('hidden');
      }
    } else {
      if (actionButtons.paste) {
        actionButtons.paste.disabled = true;
        actionButtons.paste.style.opacity = '0.5';
      }
      if (batchButtons.paste) {
        batchButtons.paste.disabled = true;
      }
      if (batchButtons.clearClipboard) {
        batchButtons.clearClipboard.style.display = 'none';
      }
      if (contextPasteItem) contextPasteItem.style.display = 'none';
      if (contextClearItem) contextClearItem.style.display = 'none';
      if (fabPasteItem) fabPasteItem.classList.add('hidden');
      if (fabClearItem) fabClearItem.classList.add('hidden');
    }
  }

  // ==================== VISUAL STYLING ====================

  /**
   * Apply visual styling to items that have been cut
   * @param {HTMLElement} card - The card element to style
   */
  function applyCutStyle(card) {
    card.style.opacity = '0.5';
    card.style.filter = 'grayscale(60%)';
    card.style.transition = 'all 0.2s ease';
  }

  /**
   * Remove cut styling from cards
   * @param {HTMLElement} card - The card element to unstyle
   */
  function removeCutStyle(card) {
    card.style.opacity = '';
    card.style.filter = '';
    card.style.transition = 'all 0.2s ease';
  }

  // ==================== CLIPBOARD CORE OPERATIONS ====================

  /**
   * Pure function to perform copy operation
   * @param {Array} items - Array of item objects [{type, id}, ...]
   * @returns {Object} Clipboard object that was created
   */
  function performCopy(items) {
    if (!items || items.length === 0) {
      console.warn('[COPY] No items provided');
      return null;
    }

    // Validate items
    for (const item of items) {
      if (!isValidItemType(item.type) || !isValidId(item.id)) {
        console.error('[COPY] Invalid item:', item);
        return null;
      }
    }

    // Create clipboard object
    clipboard = {
      action: 'copy',
      items: items.map(item => ({ type: item.type, id: item.id }))
    };
    saveClipboard();
    batchButtons.paste.disabled = false;

    // Dispatch custom event for context menu updates
    document.dispatchEvent(new CustomEvent('clipboardStateChanged', { detail: { hasClipboard: true, action: 'copy' } }));

    return clipboard;
  }

  /**
   * Pure function to perform cut operation
   * @param {Array} items - Array of item objects [{type, id, card}, ...]
   * @returns {Object} Clipboard object that was created
   */
  function performCut(items) {
    if (!items || items.length === 0) {
      console.warn('[CUT] No items provided');
      return null;
    }

    // Validate items
    for (const item of items) {
      if (!isValidItemType(item.type) || !isValidId(item.id)) {
        console.error('[CUT] Invalid item:', item);
        return null;
      }
    }

    // Clear old cut styles
    safeQueryAll('.item-card').forEach(card => removeCutStyle(card));

    // Create clipboard object
    clipboard = {
      action: 'cut',
      items: items.map(item => ({ type: item.type, id: item.id }))
    };
    saveClipboard();

    // Apply cut styling to cards
    items.forEach(item => {
      if (item.card) {
        applyCutStyle(item.card);
      } else {
        // Try to find card by data attributes
        const card = safeQuery(`.item-card[data-type="${CSS.escape(String(item.type))}"][data-id="${CSS.escape(String(item.id))}"]`);
        if (card) applyCutStyle(card);
      }
    });

    batchButtons.paste.disabled = false;

    // Dispatch custom event for context menu updates
    document.dispatchEvent(new CustomEvent('clipboardStateChanged', { detail: { hasClipboard: true, action: 'cut' } }));

    return clipboard;
  }

  // ==================== SINGLE ITEM OPERATIONS ====================

  function setupSingleOperationListeners() {
    // Cut button handler
    if (actionButtons.cut) {
      actionButtons.cut.addEventListener('click', function(e) {
        e.preventDefault();
        if (operationInProgress) {
          console.warn('Operation already in progress');
          return;
        }
        if (!window.selected) return;
        
        // Validate selection
        if (!isValidItemType(window.selected.type) || !isValidId(window.selected.id)) {
          console.error('Invalid selection data');
          return;
        }
        
        // Toggle cut if same item
        if (clipboard && clipboard.action === 'cut' && clipboard.items && clipboard.items.length === 1 && 
            clipboard.items[0].type === window.selected.type && clipboard.items[0].id === window.selected.id) {
          clipboard = null;
          saveClipboard();
          clearSelection();
          return;
        }
        
        // Use performCut function
        performCut([window.selected]);
        
        if (window.TelemetryPanel) {
          const itemName = window.selected.card.querySelector('.item-link')?.textContent?.trim() || `${window.selected.type} ${window.selected.id}`;
          window.TelemetryPanel.setIdle(`Cut ${itemName}`);
        }
        
        clearSelection();
      });
    }

    // Copy button handler
    if (actionButtons.copy) {
      actionButtons.copy.addEventListener('click', function(e) {
        e.preventDefault();
        if (operationInProgress) {
          console.warn('Operation already in progress');
          return;
        }
        if (!window.selected) return;
        
        // Validate selection
        if (!isValidItemType(window.selected.type) || !isValidId(window.selected.id)) {
          console.error('Invalid selection data');
          return;
        }
        
        // Use performCopy function
        performCopy([window.selected]);
        
        if (window.TelemetryPanel) {
          const itemName = window.selected.card.querySelector('.item-link')?.textContent?.trim() || `${window.selected.type} ${window.selected.id}`;
          window.TelemetryPanel.setIdle(`Copied ${itemName}`);
        }
        
        clearSelection();
      });
    }

    // Paste button handler
    if (actionButtons.paste) {
      actionButtons.paste.addEventListener('click', function(e) {
        e.preventDefault();
        if (operationInProgress) {
          console.warn('Operation already in progress');
          return;
        }
        if (!clipboard) return;
        
        const currentFolderId = parseInt(localStorage.getItem("currentFolderId"), 10);
        if (!isValidId(currentFolderId)) {
          console.error('Invalid folder ID');
          return;
        }
        performPaste(clipboard, currentFolderId);
      });
    }

    // Delete button handler
    if (actionButtons.delete) {
      actionButtons.delete.addEventListener('click', function(e) {
        e.preventDefault();
        if (operationInProgress) {
          console.warn('Operation already in progress');
          return;
        }
        if (!window.selected) return;
        
        // Validate selection
        if (!isValidItemType(window.selected.type) || !isValidId(window.selected.id)) {
          console.error('Invalid selection data');
          return;
        }
        
        const itemName = window.selected.card.querySelector('.item-link')?.textContent?.trim() || `${window.selected.type} ${window.selected.id}`;
        
        // Use new delete confirmation modal
        window.deleteModal.show(itemName, async () => {
          operationInProgress = true;
          
          // Show activity in telemetry
          if (window.TelemetryPanel) {
            window.TelemetryPanel.setActive(`Deleting ${itemName}...`);
          }
        
          let deleteUrl = '';
          if (window.selected.type === 'folder') deleteUrl = `/folders/delete/${window.selected.id}`;
          else if (window.selected.type === 'proprietary_note' || window.selected.type === 'note') deleteUrl = `/folders/delete_note/${window.selected.id}`;
          else if (window.selected.type === 'board') deleteUrl = `/folders/delete_board/${window.selected.id}`;
          else if (window.selected.type === 'file' || window.selected.type === 'proprietary_blocks' || window.selected.type === 'book' || window.selected.type === 'markdown' || window.selected.type === 'todo' || window.selected.type === 'diagram' || window.selected.type === 'table' || window.selected.type === 'blocks') deleteUrl = `/p2/files/${window.selected.id}/delete`;
          
          if (deleteUrl) {
            const formData = new FormData();
            const csrfToken = getCSRFToken();
            if (csrfToken) {
              formData.append('csrf_token', csrfToken);
            }
            
            fetch(deleteUrl, { 
              method: 'POST', 
              body: formData,
              headers: {
                'X-Requested-With': 'XMLHttpRequest'
              }
            })
              .then(response => response.json())
              .then(data => {
                if (data.success) {
                  // Remove the card from DOM
                  const cardToRemove = window.selected.card;
                  const parentGrid = cardToRemove.closest('.content-grid');
                  const colWrapper = cardToRemove.closest('.col');
                  
                  // Remove with animation
                  cardToRemove.style.transition = 'all 0.3s ease';
                  cardToRemove.style.opacity = '0';
                  cardToRemove.style.transform = 'scale(0.8)';
                  
                  setTimeout(() => {
                    if (colWrapper) {
                      colWrapper.remove();
                    } else {
                      cardToRemove.remove();
                    }
                    
                    // Update count badge if present
                    const section = parentGrid?.closest('.section-container');
                    if (section) {
                      const countBadge = section.querySelector('.count-badge');
                      if (countBadge) {
                        const currentCount = parseInt(countBadge.textContent) || 0;
                        const newCount = currentCount - 1;
                        countBadge.textContent = newCount;
                        
                        // Hide section if empty
                        if (newCount === 0) {
                          section.style.transition = 'all 0.3s ease';
                          section.style.opacity = '0';
                          setTimeout(() => section.remove(), 300);
                        }
                      }
                    }
                    
                    // Refresh telemetry data
                    if (window.TelemetryPanel) {
                      window.TelemetryPanel.refreshData();
                      window.TelemetryPanel.setIdle(`Deleted ${itemName}`);
                    }
                  }, 300);
                  
                  clearSelection();
                } else {
                  throw new Error(data.message || 'Delete failed');
                }
              })
              .catch(error => { 
                const errorMsg = `Failed to delete: ${sanitizeText(error.message)}`;
                if (window.TelemetryPanel) {
                  window.TelemetryPanel.setIdle(errorMsg);
                } else {
                  alert(errorMsg);
                }
                console.error('Delete error:', error); 
              })
              .finally(() => {
                operationInProgress = false;
              });
          } else {
            operationInProgress = false;
          }
        });
      });
    }
  }

  // ==================== BATCH OPERATIONS ====================

  function setupBatchOperationListeners() {
    // Batch cut button handler
    if (batchButtons.cut) {
      batchButtons.cut.addEventListener('click', function(e) {
        e.preventDefault();
        if (operationInProgress) {
          console.warn('Operation already in progress');
          return;
        }
        if (!window.batchSelected || window.batchSelected.length === 0) return;
        
        // Validate batch size
        if (window.batchSelected.length > MAX_BATCH_SIZE) {
          alert(`Cannot operate on more than ${MAX_BATCH_SIZE} items at once`);
          return;
        }
        
        // Validate all items
        for (const item of window.batchSelected) {
          if (!isValidItemType(item.type) || !isValidId(item.id)) {
            console.error('Invalid item in batch selection:', item);
            return;
          }
        }
        
        // Clear old cut styles
        safeQueryAll('.item-card').forEach(card => removeCutStyle(card));
        
        clipboard = {
          action: 'cut',
          items: window.batchSelected.map(item => ({ type: item.type, id: item.id }))
        };
        saveClipboard();
        
        // Apply cut styling with staggered animation
        window.batchSelected.forEach((item, index) => {
          if (item.card) {
            setTimeout(() => applyCutStyle(item.card), index * 30);
          }
        });
        
        // Note: Telemetry notification handled by keyboard shortcut handler to preserve count
        
        batchButtons.paste.disabled = false;
        clearBatchSelectionVisuals();
      });
    }

    // Batch copy button handler
    if (batchButtons.copy) {
      batchButtons.copy.addEventListener('click', function(e) {
        e.preventDefault();
        if (operationInProgress) {
          console.warn('Operation already in progress');
          return;
        }
        if (!window.batchSelected || window.batchSelected.length === 0) return;
        
        // Validate batch size
        if (window.batchSelected.length > MAX_BATCH_SIZE) {
          alert(`Cannot operate on more than ${MAX_BATCH_SIZE} items at once`);
          return;
        }
        
        // Use performCopy function
        performCopy(window.batchSelected);
        
        // Note: Telemetry notification handled by keyboard shortcut handler to preserve count
        
        batchButtons.paste.disabled = false;
        clearBatchSelectionVisuals();
      });
    }

    // Batch paste button handler
    if (batchButtons.paste) {
      batchButtons.paste.addEventListener('click', function(e) {
        e.preventDefault();
        if (operationInProgress) {
          console.warn('Operation already in progress');
          return;
        }
        if (!clipboard || !clipboard.items) return;
        
        const currentFolderId = parseInt(localStorage.getItem("currentFolderId"), 10);
        if (!isValidId(currentFolderId)) {
          console.error('Invalid folder ID');
          return;
        }
        
        operationInProgress = true;
        const formData = new FormData();
        formData.append('items', JSON.stringify(clipboard.items));
        formData.append('action', clipboard.action);
        formData.append('target_folder', currentFolderId.toString());
        formData.append('htmx', 'true'); // Signal backend to return HTML fragments
        
        const csrfToken = getCSRFToken();
        if (csrfToken) {
          formData.append('csrf_token', csrfToken);
        }
        
        const itemCount = clipboard.items.length;
        const action = clipboard.action === 'cut' ? 'Moving' : 'Copying';
        
        if (window.TelemetryPanel) {
          window.TelemetryPanel.setActive(`${action} ${itemCount} items...`);
        }
        
        fetch('/folders/batch_paste', {
          method: 'POST',
          body: formData,
          headers: { 
            'X-Requested-With': 'XMLHttpRequest',
            'HX-Request': 'true' // HTMX header
          }
        })
        .then(response => response.json())
        .then(data => {
          if (data.success) {
            // Use HTMX to load new items if HTML provided
            if (data.new_items_html && Array.isArray(data.new_items_html)) {
              console.log(`📦 Processing ${data.new_items_html.length} new items`);
              
              // Insert each new item with staggered animation
              data.new_items_html.forEach((itemHtml, index) => {
                if (itemHtml && itemHtml.html && itemHtml.type) {
                  setTimeout(() => {
                    console.log(`🎨 Inserting item ${index + 1}/${data.new_items_html.length}:`, itemHtml.type);
                    insertNewItemHTML(itemHtml.html, itemHtml.type);
                  }, index * 50); // Stagger by 50ms
                }
              });
              
              // For cut operations, remove original cards after inserting new ones
              if (clipboard.action === 'cut') {
                clipboard.items.forEach((item, index) => {
                  setTimeout(() => {
                    const sanitizedType = CSS.escape(String(item.type));
                    const sanitizedId = CSS.escape(String(item.id));
                    const card = safeQuery(`.item-card[data-type="${sanitizedType}"][data-id="${sanitizedId}"]`);
                    if (card) {
                      animateCardRemoval(card).then(() => {
                        card.remove();
                        updateSectionCounts();
                      });
                    }
                  }, index * 50 + 100);
                });
              }
              
              // Refresh telemetry after all items inserted
              if (window.TelemetryPanel && typeof window.TelemetryPanel.fetchData === 'function') {
                setTimeout(() => {
                  window.TelemetryPanel.fetchData();
                }, data.new_items_html.length * 50 + 200);
              }
            } else {
              console.warn('⚠️ No new_items_html in response, falling back to reload');
              window.location.reload();
              return;
            }
            
            // Clear clipboard after paste operation (only for cut operations)
            if (clipboard.action === 'cut') {
              clipboard = null;
              saveClipboard();
            }
            
            if (window.TelemetryPanel) {
              const msg = data.failed_count > 0 
                ? `${action} complete: ${data.success_count} succeeded, ${data.failed_count} failed`
                : `${action} ${data.success_count} items successfully`;
              window.TelemetryPanel.setIdle(msg);
            }
            
            // Clear batch selection after successful operation
            clearBatchSelectionVisuals();
          } else {
            throw new Error(data.message || 'Batch paste failed');
          }
        })
        .catch(error => {
          const errorMsg = `Failed to paste items: ${error.message}`;
          if (window.TelemetryPanel) {
            window.TelemetryPanel.setIdle(errorMsg);
          } else {
            alert(errorMsg);
          }
          console.error('Batch paste error:', error);
        })
        .finally(() => {
          operationInProgress = false;
        });
      });
    }

    // Batch delete button handler
    if (batchButtons.delete) {
      batchButtons.delete.addEventListener('click', function(e) {
        e.preventDefault();
        if (operationInProgress) {
          console.warn('Operation already in progress');
          return;
        }
        if (!window.batchSelected || window.batchSelected.length === 0) return;
        
        // Validate batch size
        if (window.batchSelected.length > MAX_BATCH_SIZE) {
          alert(`Cannot delete more than ${MAX_BATCH_SIZE} items at once`);
          return;
        }
        
        // Validate all items
        for (const item of window.batchSelected) {
          if (!isValidItemType(item.type) || !isValidId(item.id)) {
            console.error('Invalid item in batch selection:', item);
            return;
          }
        }
        
        const itemCount = window.batchSelected.length;
        const itemWord = itemCount === 1 ? 'item' : 'items';
        
        // Use new delete confirmation modal
        window.deleteModal.show(`${itemCount} ${itemWord}`, async () => {
          operationInProgress = true;
          const formData = new FormData();
          formData.append('items', JSON.stringify(window.batchSelected.map(item => ({ type: item.type, id: item.id }))));
          
          const csrfToken = getCSRFToken();
          if (csrfToken) {
            formData.append('csrf_token', csrfToken);
          }
          
          if (window.TelemetryPanel) {
            window.TelemetryPanel.setActive(`Deleting ${window.batchSelected.length} items...`);
          }
          
          fetch('/folders/batch_delete', {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
          })
          .then(response => response.json())
          .then(data => {
            if (data.success) {
              // Remove cards from grid view AND corresponding rows from table view
              window.batchSelected.forEach((item, index) => {
                if (item.card) {
                  setTimeout(() => {
                    animateCardRemoval(item.card).then(() => {
                      // Remove grid view card
                      const colWrapper = item.card.closest('.col');
                      if (colWrapper) colWrapper.remove();
                      else item.card.remove();
                      
                      // Also remove corresponding table row
                      const sanitizedType = CSS.escape(String(item.type));
                      const sanitizedId = CSS.escape(String(item.id));
                      const tableRow = safeQuery(`.item-row[data-type="${sanitizedType}"][data-id="${sanitizedId}"]`);
                      if (tableRow) {
                        tableRow.remove();
                      }
                      
                      // Update counts after last item
                      if (index === window.batchSelected.length - 1) {
                        updateSectionCounts();
                      }
                    });
                  }, index * 50);
                }
              });
              
              if (window.TelemetryPanel) {
                window.TelemetryPanel.setIdle(`Deleted ${window.batchSelected.length} items`);
                if (typeof window.TelemetryPanel.fetchData === 'function') {
                  window.TelemetryPanel.fetchData();
                }
              }
              
              clearBatchSelection();
            } else {
              throw new Error(data.message || 'Batch delete failed');
            }
          })
          .catch(error => {
            const errorMsg = `Failed to delete items: ${error.message}`;
            if (window.TelemetryPanel) {
              window.TelemetryPanel.setIdle(errorMsg);
            } else {
              alert(errorMsg);
            }
            console.error('Batch delete error:', error);
          })
          .finally(() => {
            operationInProgress = false;
          });
        });
      });
    }

    // Batch set public button handler (HTMX-based toggle)
    if (batchButtons.public) {
      console.log('[BATCH PUBLIC] Public button found, attaching event listener');
      batchButtons.public.addEventListener('click', function(e) {
        console.log('[BATCH PUBLIC] ========== PUBLIC BUTTON CLICKED ==========');
        console.log('[BATCH PUBLIC] Event:', e);
        console.log('[BATCH PUBLIC] Target:', e.target);
        
        console.log('[BATCH PUBLIC] Operation in progress?', operationInProgress);
        if (operationInProgress) {
          console.warn('[BATCH PUBLIC] Operation already in progress, aborting');
          e.preventDefault();
          return;
        }
        
        console.log('[BATCH PUBLIC] Batch selected items:', window.batchSelected);
        if (!window.batchSelected || window.batchSelected.length === 0) {
          console.warn('[BATCH PUBLIC] No items selected, aborting');
          e.preventDefault();
          return;
        }
        
        operationInProgress = true;
        const itemsToToggle = window.batchSelected.slice();
        console.log('[BATCH PUBLIC] Items to toggle:', itemsToToggle);
        console.log('[BATCH PUBLIC] Item count:', itemsToToggle.length);
        
        if (window.TelemetryPanel) {
          window.TelemetryPanel.setActive(`Toggling visibility for ${itemsToToggle.length} item${itemsToToggle.length > 1 ? 's' : ''}...`);
        }
        
        // Prepare items data for HTMX
        const items = itemsToToggle.map(item => ({
          type: item.type,
          id: item.id
        }));
        console.log('[BATCH PUBLIC] Prepared items for request:', items);
        console.log('[BATCH PUBLIC] Items JSON:', JSON.stringify(items));
        
        // Update hidden inputs for HTMX to include
        const itemsInput = document.getElementById('htmx-items-input');
        console.log('[BATCH PUBLIC] Items input element:', itemsInput);
        if (itemsInput) {
          itemsInput.value = JSON.stringify(items);
          console.log('[BATCH PUBLIC] Set items input value:', itemsInput.value);
        } else {
          console.error('[BATCH PUBLIC] htmx-items-input element not found!');
        }
        
        // Get current folder ID from session storage or page data
        const folderIdInput = document.getElementById('htmx-folder-id-input');
        console.log('[BATCH PUBLIC] Folder ID input element:', folderIdInput);
        const currentFolderId = localStorage.getItem('currentFolderId') || 
                               (folderIdInput ? folderIdInput.value : '');
        console.log('[BATCH PUBLIC] Current folder ID:', currentFolderId);
        if (folderIdInput) {
          folderIdInput.value = currentFolderId;
          console.log('[BATCH PUBLIC] Set folder ID input value:', folderIdInput.value);
        } else {
          console.error('[BATCH PUBLIC] htmx-folder-id-input element not found!');
        }
        
        // Let HTMX handle the request (button has hx-post attribute)
        console.log('[BATCH PUBLIC] Letting HTMX handle the request...');
        console.log('[BATCH PUBLIC] Button hx-post:', batchButtons.public.getAttribute('hx-post'));
        console.log('[BATCH PUBLIC] Button hx-swap:', batchButtons.public.getAttribute('hx-swap'));
        
        // Add HTMX event listeners for debugging
        document.body.addEventListener('htmx:beforeRequest', function beforeReq(evt) {
          if (evt.detail.elt === batchButtons.public) {
            console.log('[BATCH PUBLIC] HTMX beforeRequest event:', evt.detail);
            console.log('[BATCH PUBLIC] Request parameters:', evt.detail.parameters);
            document.body.removeEventListener('htmx:beforeRequest', beforeReq);
          }
        });
        
        document.body.addEventListener('htmx:afterRequest', function afterReq(evt) {
          if (evt.detail.elt === batchButtons.public) {
            console.log('[BATCH PUBLIC] HTMX afterRequest event:', evt.detail);
            console.log('[BATCH PUBLIC] Response status:', evt.detail.xhr.status);
            console.log('[BATCH PUBLIC] Response text preview:', evt.detail.xhr.responseText.substring(0, 500));
            document.body.removeEventListener('htmx:afterRequest', afterReq);
          }
        });
        
        // Reset operation flag after HTMX completes
        document.body.addEventListener('htmx:afterOnLoad', function resetFlag(evt) {
          if (evt.detail.elt === batchButtons.public) {
            console.log('[BATCH PUBLIC] HTMX afterOnLoad event - operation complete');
            operationInProgress = false;
            document.body.removeEventListener('htmx:afterOnLoad', resetFlag);
          }
        });
        
        console.log('[BATCH PUBLIC] Triggering HTMX request manually...');
        console.log('[BATCH PUBLIC] Items:', JSON.stringify(items));
        console.log('[BATCH PUBLIC] Folder ID:', currentFolderId);
        
        // CRITICAL: htmx.ajax() expects values as an OBJECT, not a string
        // Passing a string causes each character to be treated as a separate form field
        htmx.ajax('POST', '/folders/batch_toggle_public_htmx', {
          source: batchButtons.public,
          swap: 'none',
          target: batchButtons.public,
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
          },
          values: {
            items: JSON.stringify(items),
            folder_id: currentFolderId
          }
        }).then(() => {
          console.log('[BATCH PUBLIC] HTMX request completed - waiting for OOB swaps...');
          
          // Wait for HTMX OOB swaps to complete, then reattach event listeners to NEW cards only
          setTimeout(() => {
            console.log('[BATCH PUBLIC] Reattaching event listeners to updated cards...');
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
            
            console.log(`[BATCH PUBLIC] Event listeners reattached to ${reattachedCount} new cards (${allCards.length} total)`);
            
            // Clear batch selection after operation
            clearBatchSelection();
            
            if (window.TelemetryPanel) {
              window.TelemetryPanel.setIdle(`${items.length} item(s) visibility toggled`);
            }
            
            console.log('[BATCH PUBLIC] Public toggle operation complete - DOM updated via OOB swaps');
          }, 300); // Wait for OOB swaps to complete
        }).catch((err) => {
          console.error('[BATCH PUBLIC] HTMX request failed:', err);
          if (window.TelemetryPanel) {
            window.TelemetryPanel.setIdle('Public toggle operation failed');
          }
        });
        
        console.log('[BATCH PUBLIC] HTMX request triggered');
      });
    } else {
      console.warn('[BATCH PUBLIC] Button element #btn-batch-public not found!');
    }

    // Batch pin toggle button handler (HTMX-based)
    if (batchButtons.pin) {
      console.log('[BATCH PIN] Pin button found, attaching event listener');
      batchButtons.pin.addEventListener('click', function(e) {
        console.log('[BATCH PIN] ========== PIN BUTTON CLICKED ==========');
        console.log('[BATCH PIN] Event:', e);
        console.log('[BATCH PIN] Target:', e.target);
        
        console.log('[BATCH PIN] Operation in progress?', operationInProgress);
        if (operationInProgress) {
          console.warn('[BATCH PIN] Operation already in progress, aborting');
          e.preventDefault();
          return;
        }
        
        console.log('[BATCH PIN] Batch selected items:', window.batchSelected);
        if (!window.batchSelected || window.batchSelected.length === 0) {
          console.warn('[BATCH PIN] No items selected, aborting');
          e.preventDefault();
          return;
        }
        
        operationInProgress = true;
        const itemsToPin = window.batchSelected.slice();
        console.log('[BATCH PIN] Items to pin:', itemsToPin);
        console.log('[BATCH PIN] Item count:', itemsToPin.length);
        
        if (window.TelemetryPanel) {
          window.TelemetryPanel.setActive(`Toggling pin for ${itemsToPin.length} item${itemsToPin.length > 1 ? 's' : ''}...`);
        }
        
        // Prepare items data for HTMX
        const items = itemsToPin.map(item => ({
          type: item.type,
          id: item.id
        }));
        console.log('[BATCH PIN] Prepared items for request:', items);
        console.log('[BATCH PIN] Items JSON:', JSON.stringify(items));
        
        // Update hidden inputs for HTMX to include
        const itemsInput = document.getElementById('htmx-items-input');
        console.log('[BATCH PIN] Items input element:', itemsInput);
        if (itemsInput) {
          itemsInput.value = JSON.stringify(items);
          console.log('[BATCH PIN] Set items input value:', itemsInput.value);
        } else {
          console.error('[BATCH PIN] htmx-items-input element not found!');
        }
        
        // Get current folder ID from session storage or page data
        const folderIdInput = document.getElementById('htmx-folder-id-input');
        console.log('[BATCH PIN] Folder ID input element:', folderIdInput);
        const currentFolderId = localStorage.getItem('currentFolderId') || 
                               (folderIdInput ? folderIdInput.value : '');
        console.log('[BATCH PIN] Current folder ID:', currentFolderId);
        if (folderIdInput) {
          folderIdInput.value = currentFolderId;
          console.log('[BATCH PIN] Set folder ID input value:', folderIdInput.value);
        } else {
          console.error('[BATCH PIN] htmx-folder-id-input element not found!');
        }
        
        // Let HTMX handle the request (button has hx-post attribute)
        console.log('[BATCH PIN] Letting HTMX handle the request...');
        console.log('[BATCH PIN] Button hx-post:', batchButtons.pin.getAttribute('hx-post'));
        console.log('[BATCH PIN] Button hx-swap:', batchButtons.pin.getAttribute('hx-swap'));
        
        // Add HTMX event listeners for debugging
        document.body.addEventListener('htmx:beforeRequest', function beforeReq(evt) {
          if (evt.detail.elt === batchButtons.pin) {
            console.log('[BATCH PIN] HTMX beforeRequest event:', evt.detail);
            console.log('[BATCH PIN] Request parameters:', evt.detail.parameters);
            document.body.removeEventListener('htmx:beforeRequest', beforeReq);
          }
        });
        
        document.body.addEventListener('htmx:afterRequest', function afterReq(evt) {
          if (evt.detail.elt === batchButtons.pin) {
            console.log('[BATCH PIN] HTMX afterRequest event:', evt.detail);
            console.log('[BATCH PIN] Response status:', evt.detail.xhr.status);
            console.log('[BATCH PIN] Response text preview:', evt.detail.xhr.responseText.substring(0, 500));
            document.body.removeEventListener('htmx:afterRequest', afterReq);
          }
        });
        
        // Reset operation flag after HTMX completes
        document.body.addEventListener('htmx:afterOnLoad', function resetFlag(evt) {
          if (evt.detail.elt === batchButtons.pin) {
            console.log('[BATCH PIN] HTMX afterOnLoad event - operation complete');
            operationInProgress = false;
            document.body.removeEventListener('htmx:afterOnLoad', resetFlag);
          }
        });
        
        console.log('[BATCH PIN] Triggering HTMX request manually...');
        console.log('[BATCH PIN] Items:', JSON.stringify(items));
        console.log('[BATCH PIN] Folder ID:', currentFolderId);
        
        // CRITICAL: htmx.ajax() expects values as an OBJECT, not a string
        // Passing a string causes each character to be treated as a separate form field
        htmx.ajax('POST', '/folders/batch_toggle_pin_htmx', {
          source: batchButtons.pin,
          swap: 'none',
          target: batchButtons.pin,
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
          },
          values: {
            items: JSON.stringify(items),
            folder_id: currentFolderId
          }
        }).then(() => {
          console.log('[BATCH PIN] HTMX request completed - waiting for OOB swaps...');
          
          // Wait for HTMX OOB swaps to complete, then reattach event listeners to NEW cards only
          setTimeout(() => {
            console.log('[BATCH PIN] Reattaching event listeners to updated cards...');
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
            
            console.log(`[BATCH PIN] Event listeners reattached to ${reattachedCount} new cards (${allCards.length} total)`);
            
            // Clear batch selection after operation
            clearBatchSelection();
            
            if (window.TelemetryPanel) {
              window.TelemetryPanel.setIdle(`${items.length} item(s) pin toggled`);
            }
            
            console.log('[BATCH PIN] Pin operation complete - DOM updated via OOB swaps');
          }, 300); // Wait for OOB swaps to complete
        }).catch((err) => {
          console.error('[BATCH PIN] HTMX request failed:', err);
          if (window.TelemetryPanel) {
            window.TelemetryPanel.setIdle('Pin operation failed');
          }
        });
        
        console.log('[BATCH PIN] HTMX request triggered');
      });
    } else {
      console.warn('[BATCH PIN] Button element #btn-batch-pin not found!');
    }

    // Batch clear clipboard button handler (clears clipboard only)
    if (batchButtons.clearClipboard) {
      batchButtons.clearClipboard.addEventListener('click', function(e) {
        e.preventDefault();
        // Clear clipboard only (keep selection intact)
        clipboard = null;
        saveClipboard();
        batchButtons.paste.disabled = true;
        if (batchButtons.clearClipboard) {
          batchButtons.clearClipboard.style.display = 'none';
        }
        if (window.TelemetryPanel) {
          window.TelemetryPanel.setIdle('Clipboard cleared - you can now copy/cut again');
        }
      });
    }

    // Batch clear selection button handler (clears selection only)
    if (batchButtons.clear) {
      batchButtons.clear.addEventListener('click', function(e) {
        e.preventDefault();
        // Clear selection only (keep clipboard intact)
        clearBatchSelection();
        if (window.TelemetryPanel) {
          window.TelemetryPanel.setIdle('Selection cleared');
        }
      });
    }
  }

  // ==================== CONTEXT MENU OPERATIONS ====================

  function setupContextMenuListeners() {
    // Context menu paste function
    window.contextMenuPaste = function() {
      if (operationInProgress) {
        console.warn('Operation already in progress');
        return;
      }
      if (!clipboard) return;
      
      const currentFolderId = parseInt(localStorage.getItem("currentFolderId"), 10);
      const targetFolderId = window.targetFolderId || currentFolderId;
      
      if (!isValidId(targetFolderId)) {
        console.error('Invalid target folder ID');
        return;
      }
      
      performPaste(clipboard, targetFolderId);
    };

    // Context menu clear clipboard function
    window.contextMenuClearClipboard = function() {
      clipboard = null;
      saveClipboard();
      if (window.TelemetryPanel) {
        window.TelemetryPanel.setIdle('Clipboard cleared');
      }
    };
  }

  // ==================== CORE PASTE LOGIC ====================

  /**
   * Perform paste operation (move or copy) using HTMX for dynamic loading
   * @param {Object} clipboardData - The clipboard data object
   * @param {number} targetFolderId - The destination folder ID
   */
  function performPaste(clipboardData, targetFolderId) {
    if (!clipboardData) return;
    
    // Validate clipboard data
    if (!validateClipboardData(clipboardData)) {
      console.error('Invalid clipboard data');
      return;
    }
    
    // Validate target folder
    if (!isValidId(targetFolderId)) {
      console.error('Invalid target folder ID');
      return;
    }
    
    operationInProgress = true;
    
    let pasteUrl = '';
    const formData = new FormData();
    const itemName = `${clipboardData.type} ${clipboardData.id}`;
    
    // Build URL and form data
    if (clipboardData.action === 'cut') {
      if (clipboardData.type === 'folder') {
        pasteUrl = `/folders/move/${clipboardData.id}`;
      } else if (clipboardData.type === 'proprietary_note' || clipboardData.type === 'note') {
        pasteUrl = `/folders/move_note/${clipboardData.id}`;
      } else if (clipboardData.type === 'board') {
        pasteUrl = `/folders/move_board/${clipboardData.id}`;
      } else if (clipboardData.type === 'file' || clipboardData.type === 'proprietary_blocks' || clipboardData.type === 'book' || clipboardData.type === 'markdown' || clipboardData.type === 'todo' || clipboardData.type === 'diagram' || clipboardData.type === 'table' || clipboardData.type === 'blocks') {
        pasteUrl = `/p2/files/${clipboardData.id}/move`;
      }
    } else if (clipboardData.action === 'copy') {
      if (clipboardData.type === 'folder') {
        pasteUrl = `/folders/copy/${clipboardData.id}`;
      } else if (clipboardData.type === 'proprietary_note' || clipboardData.type === 'note') {
        pasteUrl = `/folders/duplicate_note/${clipboardData.id}`;
      } else if (clipboardData.type === 'board') {
        pasteUrl = `/folders/duplicate_board/${clipboardData.id}`;
      } else if (clipboardData.type === 'file' || clipboardData.type === 'proprietary_blocks' || clipboardData.type === 'book' || clipboardData.type === 'markdown' || clipboardData.type === 'todo' || clipboardData.type === 'diagram' || clipboardData.type === 'table' || clipboardData.type === 'blocks') {
        pasteUrl = `/p2/files/${clipboardData.id}/duplicate`;
      }
    }
    
    if (!pasteUrl) {
      operationInProgress = false;
      return;
    }
    
    formData.append('target_folder', targetFolderId.toString());
    formData.append('htmx', 'true'); // Signal backend to return HTML fragment
    
    const csrfToken = getCSRFToken();
    if (csrfToken) {
      formData.append('csrf_token', csrfToken);
    }
    
    // Show activity
    if (window.TelemetryPanel) {
      const action = clipboardData.action === 'cut' ? 'Moving' : 'Copying';
      window.TelemetryPanel.setActive(`${action} ${itemName}...`);
    }
    
    // Perform AJAX request
    fetch(pasteUrl, {
      method: 'POST',
      body: formData,
      headers: { 
        'X-Requested-With': 'XMLHttpRequest',
        'HX-Request': 'true' // HTMX header
      }
    })
    .then(response => response.json())
    .then(data => {
      console.log('🔍 Paste response received:', {
        success: data.success,
        hasNewItemHtml: !!data.new_item_html,
        itemType: clipboardData.type,
        action: clipboardData.action,
        htmlLength: data.new_item_html ? data.new_item_html.length : 0
      });
      
      if (data.success) {
        const sanitizedType = CSS.escape(String(clipboardData.type));
        const sanitizedId = CSS.escape(String(clipboardData.id));
        const card = safeQuery(`.item-card[data-type="${sanitizedType}"][data-id="${sanitizedId}"]`);
        
        if (clipboardData.action === 'cut') {
          // Remove card with animation
          if (card) {
            animateCardRemoval(card).then(() => {
              const colWrapper = card.closest('.col');
              if (colWrapper) colWrapper.remove();
              else card.remove();
              updateSectionCounts();
            });
          }
          
          // Insert new HTML in target folder for cut operation
          if (data.new_item_html) {
            console.log('🎨 Inserting new HTML after cut');
            insertNewItemHTML(data.new_item_html, clipboardData.type);
          }
          
          // Clear clipboard after cut
          clipboard = null;
          saveClipboard();
          
          if (window.TelemetryPanel) {
            window.TelemetryPanel.setIdle(data.message || 'Item moved');
            if (typeof window.TelemetryPanel.fetchData === 'function') {
              window.TelemetryPanel.fetchData();
            }
          }
        } else {
          // Copy - use HTMX to load the new item without page reload
          if (data.new_item_html) {
            console.log('✅ Using HTMX insertion for', clipboardData.type);
            // Insert new item HTML into appropriate section
            insertNewItemHTML(data.new_item_html, clipboardData.type);
            
            if (window.TelemetryPanel) {
              window.TelemetryPanel.setIdle(data.message || 'Item copied');
            }
          } else {
            console.warn('⚠️ No new_item_html in response, falling back to reload');
            setTimeout(() => {
              window.location.reload();
            }, 500);
            return;
          }
          
          // Keep clipboard for copy operations (allow multiple pastes)
        }
      } else {
        throw new Error(data.message || 'Paste failed');
      }
    })
    .catch(error => {
      const errorMsg = `Failed to paste: ${sanitizeText(error.message)}`;
      if (window.TelemetryPanel) {
        window.TelemetryPanel.setIdle(errorMsg);
      } else {
        alert(errorMsg);
      }
      console.error('Paste error:', error);
    })
    .finally(() => {
      operationInProgress = false;
    });
  }
  
  /**
   * Insert new item HTML into the appropriate section without page reload
   * @param {string} html - HTML string for the new item
   * @param {string} itemType - Type of item (folder, note, board, file, etc.)
   */
  function insertNewItemHTML(html, itemType) {
    console.log('🎨 insertNewItemHTML called:', {
      itemType,
      htmlLength: html ? html.length : 0,
      htmlPreview: html ? html.substring(0, 100) : 'null'
    });
    
    // CRITICAL: Parse HTML first to extract actual data-type from the card
    const temp = document.createElement('div');
    temp.innerHTML = html;
    const wrapperDiv = temp.firstElementChild;
    
    if (!wrapperDiv) {
      console.error('❌ Could not parse new item HTML');
      window.location.reload();
      return;
    }
    
    // Find the actual .item-card element (might be wrapped in col div)
    const actualCard = wrapperDiv.classList.contains('item-card') 
      ? wrapperDiv 
      : wrapperDiv.querySelector('.item-card');
    
    if (!actualCard) {
      console.error('❌ Could not find .item-card in HTML');
      window.location.reload();
      return;
    }
    
    // Extract actual type from data-file-type (for files) or data-type (for folders)
    const actualType = actualCard.dataset.fileType || actualCard.dataset.type || itemType;
    console.log('🔍 PASTE DEBUG - Extracted type from card:', actualType);
    console.log('🔍 PASTE DEBUG - Original param type:', itemType);
    console.log('🔍 PASTE DEBUG - Card element:', actualCard);
    console.log('🔍 PASTE DEBUG - Card data-type:', actualCard.dataset.type);
    console.log('🔍 PASTE DEBUG - Card data-file-type:', actualCard.dataset.fileType);
    console.log('🔍 PASTE DEBUG - All data attributes:', actualCard.dataset);
    
    // Map item types to section IDs
    const sectionMap = {
      'folder': 'folders',
      'note': 'notes',
      'board': 'boards',
      'book': 'combined',
      'markdown': 'markdown',
      'code': 'code',
      'todo': 'todo',
      'diagram': 'diagram',
      'table': 'table',
      'blocks': 'blocks',
      'proprietary_infinite_whiteboard': 'infinite-whiteboards',
      'proprietary_graph': 'graph-workspaces',
      'proprietary_note': 'notes',
      'proprietary_whiteboard': 'boards',
      'proprietary_blocks': 'combined',
      'file': 'markdown' // Default file type mapping
    };
    
    const config = SECTION_CONFIGS[actualType];
    const sectionId = (config && config.sectionId) || sectionMap[actualType] || 'folders';
    console.log('📍 Looking for section:', sectionId, 'for type:', actualType);
    
    let section = safeQuery(`#${sectionId}`);
    
    // If section doesn't exist, try legacy class-based selector
    if (!section) {
      console.log('⚠️ Section not found by ID, trying class-based selector');
      section = safeQuery(`.${sectionId}-section`);
    }

    if (!section && config) {
      console.log('ℹ️ Creating missing section for type via helper');
      section = ensureSectionForType(config);
    }
    
    if (!section) {
      console.error('❌ Section not found for type', actualType, 'falling back to reload');
      window.location.reload();
      return;
    }
    
    console.log('✅ Section found:', section);
    
    // Find the content grid within the section
    const contentGrid = section.querySelector('.content-grid');
    if (!contentGrid) {
      console.error('❌ Content grid not found, falling back to reload');
      window.location.reload();
      return;
    }
    
    console.log('✅ Content grid found:', contentGrid);
    
    // Item already parsed earlier (wrapperDiv contains the full structure)
    const newItem = wrapperDiv;
    
    // Add entrance animation
    newItem.style.opacity = '0';
    newItem.style.transform = 'scale(0.95) translateY(10px)';
    newItem.style.transition = 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)';
    
    // Insert at the beginning of the grid
    contentGrid.insertBefore(newItem, contentGrid.firstChild);
    console.log('✅ Item inserted into grid');
    
    // Trigger animation
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        newItem.style.opacity = '1';
        newItem.style.transform = 'scale(1) translateY(0)';
        console.log('🎬 Animation triggered');
      });
    });
    
    // Update count badge
    const countBadge = section.querySelector('.count-badge');
    if (countBadge) {
      const currentCount = parseInt(countBadge.textContent) || 0;
      countBadge.textContent = currentCount + 1;
      
      // Pulse animation on badge
      countBadge.style.transform = 'scale(1.2)';
      setTimeout(() => {
        countBadge.style.transform = 'scale(1)';
      }, 200);

      updateNavPillCount(section.id, currentCount + 1, config ? config.navLabel : undefined);
    }
    
    // CRITICAL FIX: Re-attach event listeners to the new card
    // This ensures Ctrl+A and click events work on newly pasted items
    const itemBody = newItem.querySelector('.item-body');
    if (itemBody) {
      if (typeof window.attachCardClickListeners === 'function') {
        console.log('✅ Attaching event listeners to new card');
        window.attachCardClickListeners(itemBody);
      } else {
        console.error('❌ attachCardClickListeners function not found on window object');
        console.log('Available window functions:', Object.keys(window).filter(k => k.includes('attach')));
      }
    } else {
      console.error('❌ Could not find .item-body in new card');
    }
    
    // Scroll to the new item smoothly
    setTimeout(() => {
      newItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 100);
  }

  // ==================== HELPER FUNCTIONS ====================

  /**
   * Animate card removal with smooth transition
   * @param {HTMLElement} card - The card element to animate
   * @returns {Promise} - Resolves when animation completes
   */
  function animateCardRemoval(card) {
    return new Promise(resolve => {
      card.style.transition = 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)';
      card.style.opacity = '0';
      card.style.transform = 'scale(0.9) translateY(-10px)';
      setTimeout(() => resolve(), 250);
    });
  }

  /**
   * Update section count badges after item removals
   * Hides empty sections
   */
  function updateSectionCounts() {
    safeQueryAll('.section-container').forEach(section => {
      // Count items in BOTH grid view (.item-card) and table view (.item-row)
      const gridCards = section.querySelectorAll('.content-grid .item-card');
      const tableRows = section.querySelectorAll('.table-view-container .item-row');
      
      // Use grid count as source of truth (both should have same count)
      const itemCount = gridCards.length;
      const countBadge = section.querySelector('.count-badge');
      
      if (countBadge) {
        countBadge.textContent = itemCount;
      }

      updateNavPillCount(section.id, itemCount);
      
      // Hide section if empty (no items in grid view) - matches single delete behavior
      if (itemCount === 0) {
        // Get preceding <hr> before animating section
        const prevHr = section.previousElementSibling;
        
        // Fade out animation
        section.style.transition = 'all 0.3s ease';
        section.style.opacity = '0';
        
        // Remove from DOM after animation completes
        setTimeout(() => {
          section.remove();
          // Also remove the <hr> separator if it exists
          if (prevHr && prevHr.tagName === 'HR') {
            prevHr.remove();
          }
        }, 300);
      }
    });
  }

  /**
   * Clear selection state
   * Used by action bar partial
   */
  function clearSelection() {
    if (window.selected && window.selected.card) {
      window.selected.card.classList.remove('selected-item');
    }
    window.selected = null;
    const actionBar = safeQuery('#action-bar');
    if (actionBar) actionBar.style.display = 'none';
  }

  /**
   * Clear batch selection
   * Removes all visual indicators and resets state
   */
  function clearBatchSelection() {
    window.batchSelected.forEach(item => {
      if (item.card) {
        item.card.classList.remove('batch-selected-item');
        const checkbox = item.card.querySelector('.batch-checkbox');
        if (checkbox) checkbox.remove();
      }
    });
    window.batchSelected = [];
    updateBatchUI();
  }

  /**
   * Clear batch selection visuals but keep batch UI visible for clipboard operations
   */
  function clearBatchSelectionVisuals() {
    window.batchSelected.forEach(item => {
      if (item.card) {
        item.card.classList.remove('batch-selected-item');
        const checkbox = item.card.querySelector('.batch-checkbox');
        if (checkbox) checkbox.remove();
      }
    });
    window.batchSelected = [];
    // Keep batch operations visible but update count to 0
    batchCount.textContent = '0';
    // Disable cut/copy/delete buttons since nothing is selected
    if (batchButtons.cut) batchButtons.cut.disabled = true;
    if (batchButtons.copy) batchButtons.copy.disabled = true;
    if (batchButtons.delete) batchButtons.delete.disabled = true;
    // Keep paste/clear buttons enabled since clipboard has data
    // (paste button state is managed separately based on clipboard content)
  }

  /**
   * Update batch operations UI based on selection state
   */
  function updateBatchUI() {
    const hasSelection = window.batchSelected && window.batchSelected.length > 0;
    const hasClipboard = clipboard && clipboard.items && clipboard.items.length > 0;
    
    if (hasSelection) {
      // Show batch operations bar with selection count
      batchOperations.style.cssText = 'display: flex !important;';
      batchCount.textContent = window.batchSelected.length;
      
      // Enable selection-based buttons
      if (batchButtons.cut) batchButtons.cut.disabled = false;
      if (batchButtons.copy) batchButtons.copy.disabled = false;
      if (batchButtons.delete) batchButtons.delete.disabled = false;
      if (batchButtons.pin) batchButtons.pin.disabled = false;
      if (batchButtons.send) batchButtons.send.disabled = false;
      if (batchButtons.public) batchButtons.public.disabled = false;
      
      // Paste button depends on clipboard state
      if (batchButtons.paste) {
        batchButtons.paste.disabled = !hasClipboard;
      }
      
      // Add visual indicator to selected cards
      window.batchSelected.forEach(item => {
        if (item.card) {
          item.card.classList.add('batch-selected-item');
          // Add checkbox if not present
          if (!item.card.querySelector('.batch-checkbox')) {
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.checked = true;
            checkbox.className = 'batch-checkbox';
            checkbox.style.cssText = 'position: absolute; top: 8px; left: 8px; z-index: 10; width: 20px; height: 20px; cursor: pointer;';
            item.card.style.position = 'relative';
            item.card.appendChild(checkbox);
            checkbox.addEventListener('change', function(e) {
              e.stopPropagation();
              if (!checkbox.checked) {
                removeBatchItem(item);
              }
            });
          }
        }
      });
    } else if (hasClipboard) {
      // Show batch operations bar with clipboard indicator but disable selection-based buttons
      batchOperations.style.cssText = 'display: flex !important;';
      batchCount.textContent = '0';
      
      // Disable selection-based buttons
      if (batchButtons.cut) batchButtons.cut.disabled = true;
      if (batchButtons.copy) batchButtons.copy.disabled = true;
      if (batchButtons.delete) batchButtons.delete.disabled = true;
      if (batchButtons.pin) batchButtons.pin.disabled = true;
      if (batchButtons.send) batchButtons.send.disabled = true;
      if (batchButtons.public) batchButtons.public.disabled = true;
      
      // Enable paste button since clipboard has content
      if (batchButtons.paste) {
        batchButtons.paste.disabled = false;
      }
      
      // Remove all batch checkboxes
      safeQueryAll('.batch-checkbox').forEach(cb => cb.remove());
      safeQueryAll('.batch-selected-item').forEach(el => el.classList.remove('batch-selected-item'));
    } else {
      // Hide batch operations bar completely
      batchOperations.style.cssText = 'display: none !important;';
      
      // Remove all batch checkboxes
      safeQueryAll('.batch-checkbox').forEach(cb => cb.remove());
      safeQueryAll('.batch-selected-item').forEach(el => el.classList.remove('batch-selected-item'));
    }
  }

  /**
   * Remove item from batch selection
   * @param {Object} item - Item object with type, id, and card properties
   */
  function removeBatchItem(item) {
    const index = window.batchSelected.findIndex(s => s.type === item.type && s.id === item.id);
    if (index !== -1) {
      window.batchSelected.splice(index, 1);
      if (item.card) {
        item.card.classList.remove('batch-selected-item');
        const checkbox = item.card.querySelector('.batch-checkbox');
        if (checkbox) checkbox.remove();
      }
      updateBatchUI();
    }
  }

  // ==================== PUBLIC API ====================

  return {
    init: init,
    loadClipboard: loadClipboard,
    saveClipboard: saveClipboard,
    updatePasteButton: updatePasteButton,
    updateBatchUI: updateBatchUI,
    performCopy: performCopy,
    performCut: performCut,
    clearClipboard: function() {
      clipboard = null;
      saveClipboard();
      // Update paste button state
      if (batchButtons.paste) {
        batchButtons.paste.disabled = true;
      }
      // Update batch UI to reflect new state
      updateBatchUI();
      // Trigger custom event for context menu updates
      document.dispatchEvent(new CustomEvent('clipboardStateChanged', { detail: { hasClipboard: false } }));
    },
    getClipboard: function() {
      return clipboard;
    },
    hasClipboard: function() {
      // Check both memory and localStorage
      if (clipboard && clipboard.items && clipboard.items.length > 0) {
        return true;
      }
      // Fallback: check localStorage
      try {
        const stored = localStorage.getItem(CLIPBOARD_KEY);
        if (stored) {
          const parsed = JSON.parse(stored);
          return parsed && parsed.items && parsed.items.length > 0;
        }
      } catch (e) {
        console.error('[CLIPBOARD] Error checking localStorage:', e);
      }
      return false;
    },
    triggerPaste: function(targetFolderId) {
      console.log('[CLIPBOARD] triggerPaste called with targetFolderId:', targetFolderId);
      
      // Trigger paste operation programmatically
      if (!clipboard || !clipboard.items || clipboard.items.length === 0) {
        console.warn('[CLIPBOARD] No clipboard data to paste');
        return;
      }
      
      console.log('[CLIPBOARD] Clipboard has', clipboard.items.length, 'items');
      
      // Store the target folder ID in localStorage for the paste handler
      if (targetFolderId) {
        localStorage.setItem('currentFolderId', targetFolderId.toString());
        console.log('[CLIPBOARD] Set currentFolderId in localStorage:', targetFolderId);
      }
      
      // Use the existing batch paste logic
      const btnBatchPaste = document.getElementById('btn-batch-paste');
      if (btnBatchPaste && !btnBatchPaste.disabled) {
        console.log('[CLIPBOARD] Clicking paste button');
        btnBatchPaste.click();
      } else {
        console.error('[CLIPBOARD] Paste button not available or disabled');
        console.error('[CLIPBOARD] Button:', btnBatchPaste, 'Disabled:', btnBatchPaste?.disabled);
        alert('Unable to paste at this time. Please try again.');
      }
    },
    isOperationInProgress: function() {
      return operationInProgress;
    },
    // Utility functions exposed for testing
    _test: {
      validateClipboardData: validateClipboardData,
      isValidItemType: isValidItemType,
      isValidId: isValidId,
      sanitizeText: sanitizeText
    }
  };
})();

// Expose to window for global access
window.ClipboardOperations = ClipboardOperations;
console.log('[CLIPBOARD] ClipboardOperations module loaded and exposed to window');

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', ClipboardOperations.init);
} else {
  ClipboardOperations.init();
}

// HTMX Integration: Attach event listeners to dynamically inserted content
// This ensures newly pasted items respond to clicks, Ctrl+A, etc.
if (typeof htmx !== 'undefined') {
  document.body.addEventListener('htmx:afterSwap', function(event) {
    console.log('🔄 HTMX afterSwap event detected, re-attaching listeners');
    
    // Find all item-body elements in the swapped content
    const swappedElement = event.detail.target;
    if (swappedElement) {
      const itemBodies = swappedElement.querySelectorAll('.item-body');
      if (itemBodies.length > 0 && typeof window.attachCardClickListeners === 'function') {
        console.log(`✅ Re-attaching listeners to ${itemBodies.length} new items`);
        itemBodies.forEach(window.attachCardClickListeners);
      }
    }
  });
  
  // Also handle htmx:load for content loaded via hx-get/hx-post
  document.body.addEventListener('htmx:load', function(event) {
    const loadedElement = event.detail.elt;
    if (loadedElement && loadedElement.classList.contains('item-card')) {
      const itemBody = loadedElement.querySelector('.item-body');
      if (itemBody && typeof window.attachCardClickListeners === 'function') {
        console.log('✅ Attaching listener to HTMX-loaded item');
        window.attachCardClickListeners(itemBody);
      }
    }
  });
} else {
  console.warn('⚠️ HTMX not loaded, dynamic content listeners may not work');
}
