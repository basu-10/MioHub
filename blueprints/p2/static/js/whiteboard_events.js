/**
 * Whiteboard Event Handlers Module
 * Centralizes all canvas and keyboard event handling
 * 
 * This module manages:
 * - Canvas mouse/pointer events (down, move, up)
 * - Keyboard shortcuts
 * - Context menu (right-click)
 * - Clipboard operations
 * - Wheel events (zoom/scroll)
 */

// Event state
let ignoreNextCtxMenuClose = false;

/**
 * Convert screen coordinates to canvas coordinates
 * @param {Event} e - Mouse/pointer event
 * @returns {Object} - Canvas coordinates {x, y}
 */
function toCanvasXY(e) {
  const canvas = document.getElementById('board-canvas');
  const r = canvas.getBoundingClientRect();
  const x = (e.clientX - r.left) * (canvas.width / r.width);
  const y = (e.clientY - r.top) * (canvas.height / r.height);
  return {x, y};
}

/**
 * Position context menu at coordinates
 * @param {number} clientX - X coordinate
 * @param {number} clientY - Y coordinate
 */
function positionContextMenu(clientX, clientY) {
  const ctxMenu = document.getElementById('ctx-menu');
  if (!ctxMenu) return;
  
  let x = clientX;
  let y = clientY;
  
  const menuWidth = ctxMenu.offsetWidth || 200;
  const menuHeight = ctxMenu.offsetHeight || 300;
  
  if (x + menuWidth > window.innerWidth) {
    x = window.innerWidth - menuWidth - 10;
  }
  if (y + menuHeight > window.innerHeight) {
    y = window.innerHeight - menuHeight - 10;
  }
  
  ctxMenu.style.left = x + 'px';
  ctxMenu.style.top = y + 'px';
}

/**
 * Initialize all event listeners
 */
function initializeEventHandlers() {
  const canvas = document.getElementById('board-canvas');
  if (!canvas) {
    console.error('Canvas not found, cannot initialize event handlers');
    return;
  }
  
  // Keyboard events are initialized in main file due to complex dependencies
  // Canvas events will be initialized in main file
  // This module provides the helper functions used by those handlers
  
  console.log('Event handler module loaded');
}

// Auto-initialize on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeEventHandlers);
} else {
  initializeEventHandlers();
}

// Expose helper functions to window for event handlers
window.toCanvasXY = toCanvasXY;
window.positionContextMenu = positionContextMenu;
window.ignoreNextCtxMenuClose = ignoreNextCtxMenuClose;

// Export for use in main whiteboard
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    toCanvasXY,
    positionContextMenu,
    initializeEventHandlers
  };
}
