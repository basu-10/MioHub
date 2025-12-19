/**
 * Whiteboard Page Management Module
 * Handles multi-page functionality, page navigation, and page state management
 */

// Page state
let pages = [];
let currentPageIndex = 0;
let nextPageId = 1;

/**
 * Create a new page object
 * @returns {Object} - New page object
 */
function createNewPage() {
  const page = {
    id: nextPageId++,
    objects: [],
    undoStack: [],
    redoStack: []
  };
  return page;
}

/**
 * Save current page state to pages array
 */
function saveCurrentPageState() {
  if (pages.length > 0 && currentPageIndex < pages.length) {
    const structuredCloneSafe = window.structuredCloneSafe || 
                                  ((v) => JSON.parse(JSON.stringify(v)));
    
    pages[currentPageIndex].objects = structuredCloneSafe(window.objects || []);
    pages[currentPageIndex].undoStack = structuredCloneSafe(window.undoStack || []);
    pages[currentPageIndex].redoStack = structuredCloneSafe(window.redoStack || []);
  }
}

/**
 * Load page state from pages array
 * @param {number} pageIndex - Index of page to load
 */
function loadPageState(pageIndex) {
  console.log('=== LOADING PAGE STATE ===');
  console.log('Loading page index:', pageIndex);
  console.log('Total pages:', pages.length);
  
  if (pageIndex < 0 || pageIndex >= pages.length) {
    console.log('ERROR: Invalid page index!');
    return;
  }
  
  const page = pages[pageIndex];
  console.log('Loading page data:', page);
  console.log('Page objects:', page.objects);
  console.log('Page objects count:', page.objects?.length || 0);
  
  const structuredCloneSafe = window.structuredCloneSafe || 
                                ((v) => JSON.parse(JSON.stringify(v)));
  
  window.objects = structuredCloneSafe(page.objects);
  window.undoStack = structuredCloneSafe(page.undoStack);
  window.redoStack = structuredCloneSafe(page.redoStack);
  
  console.log('After cloning - objects:', window.objects);
  console.log('After cloning - objects count:', window.objects.length);
  
  window.selectedId = null;
  if (window.resetUIControls) {
    window.resetUIControls();
  }
  console.log('Calling redraw...');
  if (window.redraw) {
    window.redraw();
  }
  console.log('redraw() completed');
}

/**
 * Switch to a different page
 * @param {number} pageIndex - Index of page to switch to
 */
function switchToPage(pageIndex) {
  if (pageIndex === currentPageIndex) return;
  if (pageIndex < 0 || pageIndex >= pages.length) return;
  
  saveCurrentPageState();
  currentPageIndex = pageIndex;
  loadPageState(pageIndex);
  updatePageControls();
}

/**
 * Add a new page at the end
 */
function addNewPage() {
  saveCurrentPageState();
  const newPage = createNewPage();
  pages.push(newPage);
  currentPageIndex = pages.length - 1;
  loadPageState(currentPageIndex);
  updatePageControls();
}

/**
 * Insert a new page after the current page
 */
function insertPageAtCurrentLocation() {
  saveCurrentPageState();
  const newPage = createNewPage();
  // Insert after current page
  pages.splice(currentPageIndex + 1, 0, newPage);
  currentPageIndex = currentPageIndex + 1;
  loadPageState(currentPageIndex);
  updatePageControls();
}

/**
 * Delete the current page
 */
function deleteCurrentPage() {
  if (pages.length <= 1) {
    alert("Cannot delete the last page.");
    return;
  }
  
  if (!confirm(`Delete page ${currentPageIndex + 1}?`)) return;
  
  pages.splice(currentPageIndex, 1);
  
  if (currentPageIndex >= pages.length) {
    currentPageIndex = pages.length - 1;
  }
  
  loadPageState(currentPageIndex);
  updatePageControls();
}

/**
 * Update page control UI elements
 */
function updatePageControls() {
  const pageInfo = document.getElementById('page-info');
  const prevBtn = document.getElementById('prev-page');
  const nextBtn = document.getElementById('next-page');
  const deleteBtn = document.getElementById('delete-page');
  
  if (pageInfo) {
    pageInfo.textContent = `${currentPageIndex + 1} / ${pages.length}`;
  }
  
  if (prevBtn) {
    prevBtn.disabled = currentPageIndex <= 0;
  }
  
  if (nextBtn) {
    nextBtn.disabled = currentPageIndex >= pages.length - 1;
  }
  
  if (deleteBtn) {
    deleteBtn.disabled = pages.length <= 1;
  }
}

/**
 * Navigate to previous page
 */
function previousPage() {
  if (currentPageIndex > 0) {
    switchToPage(currentPageIndex - 1);
  }
}

/**
 * Navigate to next page
 */
function nextPage() {
  if (currentPageIndex < pages.length - 1) {
    switchToPage(currentPageIndex + 1);
  }
}

/**
 * Get current page data for export
 * @returns {Object} - Page data
 */
function getPageData() {
  saveCurrentPageState();
  return {
    version: 3,
    pages: pages,
    currentPageIndex: currentPageIndex,
    nextPageId: nextPageId,
    nextObjectId: window.nextObjectId || 1
  };
}

/**
 * Load page data from import
 * @param {Object} data - Imported page data
 */
function loadPageData(data) {
  if (data.pages && Array.isArray(data.pages)) {
    pages = data.pages.map(page => ({
      id: page.id,
      objects: page.objects || [],
      undoStack: page.undoStack || [],
      redoStack: page.redoStack || []
    }));
    currentPageIndex = Math.max(0, Math.min(data.currentPageIndex || 0, pages.length - 1));
    nextPageId = data.nextPageId || (pages.reduce((m, p) => Math.max(m, p.id || 0), 0) + 1) || 1;
    if (window.nextObjectId !== undefined && data.nextObjectId) {
      window.nextObjectId = data.nextObjectId;
    }
    
    if (pages.length === 0) {
      pages = [createNewPage()];
      currentPageIndex = 0;
    }
    
    loadPageState(currentPageIndex);
    updatePageControls();
  }
}

/**
 * Initialize page management event listeners
 */
function initializePageManagement() {
  const prevBtn = document.getElementById('prev-page');
  const nextBtn = document.getElementById('next-page');
  const addBtn = document.getElementById('add-page');
  const deleteBtn = document.getElementById('delete-page');
  
  if (prevBtn) {
    prevBtn.addEventListener('click', previousPage);
  }
  
  if (nextBtn) {
    nextBtn.addEventListener('click', nextPage);
  }
  
  if (addBtn) {
    addBtn.addEventListener('click', insertPageAtCurrentLocation);
  }
  
  if (deleteBtn) {
    deleteBtn.addEventListener('click', deleteCurrentPage);
  }
  
  // Keyboard shortcuts for page navigation
  document.addEventListener('keydown', (e) => {
    // Ctrl+Left/Right for page navigation
    if (e.ctrlKey && e.key === 'ArrowLeft') {
      e.preventDefault();
      previousPage();
    } else if (e.ctrlKey && e.key === 'ArrowRight') {
      e.preventDefault();
      nextPage();
    }
  });
}

/**
 * Initialize pages from server data
 * @param {string|Object} initialData - Initial board data
 */
function initializePagesFromData(initialData) {
  try {
    const parsed = typeof initialData === 'string' ? JSON.parse(initialData) : initialData;
    console.log('=== LOADING BOARD DATA ===');
    console.log('Parsed board data:', parsed);
    
    if (parsed) {
      if (parsed.pages && Array.isArray(parsed.pages) && parsed.pages.length > 0) {
        // Multi-page format (current format)
        console.log('Loading multi-page format, pages:', parsed.pages);
        console.log('Number of pages:', parsed.pages.length);
        
        pages = parsed.pages;
        currentPageIndex = Math.max(0, Math.min(parsed.currentPageIndex || 0, pages.length - 1));
        nextPageId = parsed.nextPageId || (pages.reduce((m, p) => Math.max(m, p.id || 0), 0) + 1) || 1;
        if (window.nextObjectId !== undefined) {
          window.nextObjectId = parsed.nextObjectId || 1;
        }
        
        console.log('Set currentPageIndex to:', currentPageIndex);
        console.log('Set nextPageId to:', nextPageId);
        
        if (pages.length > 0) {
          console.log('Loading page state for index:', currentPageIndex);
          loadPageState(currentPageIndex);
        } else {
          console.log('Pages array is empty, creating new page');
          pages = [createNewPage()];
          currentPageIndex = 0;
          loadPageState(0);
        }
      } else if (parsed.objects) {
        // Legacy format
        console.log('Loading legacy format, objects count:', parsed.objects.length);
        pages = [{
          id: nextPageId++,
          objects: parsed.objects || [],
          undoStack: parsed.undoStack || [],
          redoStack: parsed.redoStack || []
        }];
        currentPageIndex = 0;
        if (window.nextObjectId !== undefined) {
          window.nextObjectId = (parsed.objects.reduce((m, o) => Math.max(m, o.id || 0), 0) + 1) || 1;
        }
        console.log('Created page with objects:', parsed.objects.length);
        loadPageState(0);
      }
    } else {
      // No data - create first page
      console.log('No data, creating new page');
      pages = [createNewPage()];
      currentPageIndex = 0;
      loadPageState(0);
    }
  } catch(e) {
    console.error('Error loading board data:', e);
    pages = [createNewPage()];
    currentPageIndex = 0;
    loadPageState(0);
  }
  updatePageControls();
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializePageManagement);
} else {
  initializePageManagement();
}

// Expose to window for module access
window.pages = pages;
window.currentPageIndex = currentPageIndex;
window.nextPageId = nextPageId;

// Export for use in main whiteboard
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    pages,
    currentPageIndex,
    nextPageId,
    createNewPage,
    saveCurrentPageState,
    loadPageState,
    switchToPage,
    addNewPage,
    insertPageAtCurrentLocation,
    deleteCurrentPage,
    updatePageControls,
    previousPage,
    nextPage,
    getPageData,
    loadPageData,
    initializePageManagement,
    initializePagesFromData
  };
}
