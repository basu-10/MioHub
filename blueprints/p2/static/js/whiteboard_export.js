/**
 * Whiteboard Export/Import Module
 * Handles saving, loading, and exporting whiteboard data
 * 
 * This module manages:
 * - Server save operations (AJAX)
 * - JSON export/import
 * - PDF export (multi-page)
 * - PNG export (single page)
 * - File download utilities
 */

/**
 * Save whiteboard to server via AJAX
 * Shows loading overlay, handles timeouts, updates form action for new boards
 * 
 * @returns {Promise<void>}
 */
async function saveToServer() {
  // Show loading overlay
  const loadingOverlay = document.getElementById('save-loading-overlay');
  if (loadingOverlay) loadingOverlay.style.display = 'flex';
  
  console.log('=== SAVE BUTTON CLICKED ===');
  console.log('Current objects before save:', window.objects);
  console.log('Current objects count:', window.objects?.length);
  
  // Log detailed object summary
  if (window.objects && window.objects.length > 0) {
    console.log('OBJECTS SUMMARY:');
    window.objects.forEach((obj, index) => {
      console.log(`  [${index}] ID: ${obj.id}, Type: ${obj.type}, Layer: ${obj.layer}`);
      if (obj.type === 'stroke' && obj.props?.path) {
        console.log(`    - Stroke with ${obj.props.path.length} points, color: ${obj.props.color}, size: ${obj.props.size}`);
      } else if (obj.type === 'text' && obj.props?.text) {
        console.log(`    - Text: "${obj.props.text}" at (${obj.props.x}, ${obj.props.y}), size: ${obj.props.fontSize}`);
      } else if (obj.props) {
        console.log(`    - Props keys: ${Object.keys(obj.props).join(', ')}`);
      }
    });
  } else {
    console.log('NO OBJECTS TO SAVE!');
  }
  
  window.saveCurrentPageState();
  console.log('Current page state saved, pages:', window.pages);
  console.log('Current page objects after saveCurrentPageState:', window.pages[window.currentPageIndex]?.objects);
  
  // Log summary of all pages
  console.log('PAGES SUMMARY:');
  window.pages?.forEach((page, index) => {
    console.log(`  Page ${index + 1} (ID: ${page.id}): ${page.objects?.length || 0} objects`);
    if (page.objects && page.objects.length > 0) {
      page.objects.forEach((obj, objIndex) => {
        console.log(`    [${objIndex}] ${obj.type} (ID: ${obj.id})`);
      });
    }
  });
  
  const payloadData = {
    version: 3,
    pages: window.pages,
    currentPageIndex: window.currentPageIndex,
    nextPageId: window.nextPageId,
    nextObjectId: window.nextObjectId
  };
  
  console.log('PAYLOAD DATA BEFORE STRINGIFY:', payloadData);
  
  const payload = JSON.stringify(payloadData);
  
  console.log('Payload created, length:', payload.length);
  console.log('Payload preview:', payload.substring(0, 500));
  
  // Sync the visible title input with the hidden form input
  const visibleTitle = document.getElementById('board-title')?.value || 'Whiteboard';
  const titleInput = document.getElementById('title-input');
  const contentInput = document.getElementById('content-input');
  
  if (titleInput) titleInput.value = visibleTitle;
  if (contentInput) contentInput.value = payload;
  
  const form = document.getElementById('save-form');
  if (!form) {
    console.error('Save form not found');
    if (loadingOverlay) loadingOverlay.style.display = 'none';
    return;
  }
  
  console.log('Form action:', form.action);
  
  try {
    const fm = new FormData();
    fm.append('title', visibleTitle);
    fm.append('content', payload);
    fm.append('generate_thumbnail', 'true'); // CRITICAL: Flag for manual save to generate thumbnail
    const folderIdInput = document.getElementById('folder-id-input');
    if (folderIdInput) fm.append('folder_id', folderIdInput.value);
    
    console.log('Sending AJAX request to:', form.action);
    console.log('Payload size (bytes):', payload.length);
    
    // Add timeout for large requests - increased for server idle scenarios
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 120000); // 120 second timeout
    
    const res = await fetch(form.action, {
      method: 'POST',
      body: fm,
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      signal: controller.signal
    });
    
    clearTimeout(timeoutId);
    console.log('Response status:', res.status);
    
    if (res.ok) {
      const responseData = await res.json();
      console.log('Save response:', responseData);
      
      // If this was a new board creation, update the form action for future saves
      if (responseData.board_id && form.action.includes('/new')) {
        const newAction = form.action.replace('/new', `/edit/${responseData.board_id}`);
        form.action = newAction;
        console.log('Updated form action to:', newAction);
        
        // Also update the browser URL to the edit page
        const newUrl = window.location.origin + `/boards/edit/${responseData.board_id}`;
        window.history.replaceState({}, '', newUrl);
        console.log('Updated browser URL to:', newUrl);
      }
      
      if (window.showSaveSuccess) {
        window.showSaveSuccess(payload.length);
      }
      if (loadingOverlay) loadingOverlay.style.display = 'none';
    } else {
      console.error('AJAX failed with status:', res.status);
      const errorText = await res.text();
      console.error('Error response:', errorText);
      
      if (res.status === 413) {
        if (window.TelemetryPanel) {
          window.TelemetryPanel.setIdle('Save failed: content too large');
        } else {
          alert('Error: Board content too large. Try reducing image quality or removing some images.');
        }
        if (loadingOverlay) loadingOverlay.style.display = 'none';
        return;
      }
      
      console.log('Falling back to form submit');
      if (loadingOverlay) loadingOverlay.style.display = 'none';
      form.submit();
    }
  } catch (e) {
    console.error('Save error:', e);
    
    if (e.name === 'AbortError') {
      if (window.TelemetryPanel) {
        window.TelemetryPanel.setIdle('Save timeout: content too large');
      } else {
        alert('Save timeout: Board content too large. Try reducing image quality or removing some images.');
      }
      if (loadingOverlay) loadingOverlay.style.display = 'none';
      return;
    }
    
    if (window.TelemetryPanel) {
      window.TelemetryPanel.setIdle('Save failed, trying alternative method...');
    } else {
      alert('Save failed. Trying alternative method...');
    }
    if (loadingOverlay) loadingOverlay.style.display = 'none';
    form.submit();
  }
}

/**
 * Export whiteboard as JSON file
 * Offers choice to include undo/redo history
 */
function exportJSON() {
  window.saveCurrentPageState();
  const choice = confirm("OK = Save with history\nCancel = Save without history");
  let data;
  
  if (choice) {
    // Include full history
    data = {
      version: 3,
      pages: window.pages,
      currentPageIndex: window.currentPageIndex,
      nextPageId: window.nextPageId,
      nextObjectId: window.nextObjectId
    };
  } else {
    // Exclude undo/redo stacks
    data = {
      version: 3,
      pages: window.pages.map(page => ({
        id: page.id,
        objects: page.objects
      })),
      currentPageIndex: window.currentPageIndex,
      nextPageId: window.nextPageId,
      nextObjectId: window.nextObjectId
    };
  }

  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'multi-page-whiteboard.json';
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Import whiteboard from JSON file
 * Triggers file input click
 */
function importJSON() {
  const importFile = document.getElementById('importFile');
  if (!importFile) {
    console.error('Import file input not found');
    return;
  }
  importFile.value = "";
  importFile.click();
}

/**
 * Handle imported JSON file
 * Parses and loads multi-page or legacy single-page format
 * 
 * @param {Event} evt - File input change event
 */
function handleImportFile(evt) {
  const file = evt.target.files[0];
  if (!file) return;
  
  const reader = new FileReader();
  reader.onload = e => {
    try {
      const data = JSON.parse(e.target.result);

      if (data.pages && Array.isArray(data.pages)) {
        // Multi-page format
        window.pages = data.pages.map(page => ({
          id: page.id,
          objects: page.objects || [],
          undoStack: page.undoStack || [],
          redoStack: page.redoStack || []
        }));
        window.currentPageIndex = Math.max(0, Math.min(data.currentPageIndex || 0, window.pages.length - 1));
        window.nextPageId = data.nextPageId || (window.pages.reduce((m, p) => Math.max(m, p.id || 0), 0) + 1) || 1;
        window.nextObjectId = data.nextObjectId || 1;
        
        if (window.pages.length === 0) {
          window.pages = [window.createNewPage()];
          window.currentPageIndex = 0;
        }
        
      } else if (data.objects && Array.isArray(data.objects)) {
        // Legacy single-page format
        window.pages = [{
          id: window.nextPageId++,
          objects: data.objects,
          undoStack: data.undoStack || [],
          redoStack: data.redoStack || []
        }];
        window.currentPageIndex = 0;
        window.nextObjectId = data.nextId || (data.objects.reduce((m, o) => Math.max(m, o.id || 0), 0) + 1) || 1;
        
      } else {
        if (window.TelemetryPanel) {
          window.TelemetryPanel.setIdle('Invalid file format');
        } else {
          alert("Invalid file format.");
        }
        return;
      }

      window.loadPageState(window.currentPageIndex);
      window.updatePageControls();
    } catch (err) {
      if (window.TelemetryPanel) {
        window.TelemetryPanel.setIdle('Error reading JSON file');
      } else {
        alert("Error reading JSON: " + err);
      }
    }
  };
  reader.readAsText(file);
}

/**
 * Export current page as PNG image
 */
function exportPNG() {
  window.redraw();
  const canvas = document.getElementById('board-canvas');
  if (!canvas) {
    console.error('Canvas not found');
    return;
  }
  
  const data = canvas.toDataURL('image/png');
  const a = document.createElement('a');
  a.href = data;
  a.download = `page-${window.currentPageIndex + 1}.png`;
  a.click();
}

/**
 * Export all pages as PDF
 * Each page becomes a separate PDF page with title and page number
 * 
 * @returns {Promise<void>}
 */
async function printToPDF() {
  try {
    // Save current page before starting
    window.saveCurrentPageState();
    
    // Get the board title
    const boardTitle = document.getElementById('board-title')?.value || 'Whiteboard';
    
    // Get canvas dimensions
    const canvas = document.getElementById('board-canvas');
    if (!canvas) {
      console.error('Canvas not found');
      return;
    }
    
    const canvasWidth = canvas.width;
    const canvasHeight = canvas.height;
    
    // Create PDF document with landscape orientation to better fit canvas
    const { jsPDF } = window.jspdf;
    if (!jsPDF) {
      if (window.TelemetryPanel) {
        window.TelemetryPanel.setIdle('PDF library not loaded');
      } else {
        alert('PDF library not loaded. Please refresh the page.');
      }
      return;
    }
    
    const pdf = new jsPDF({
      orientation: canvasWidth > canvasHeight ? 'landscape' : 'portrait',
      unit: 'mm',
      format: 'a4'
    });
    
    // Get PDF dimensions
    const pdfWidth = pdf.internal.pageSize.getWidth();
    const pdfHeight = pdf.internal.pageSize.getHeight();
    
    // Calculate scale to fit canvas in PDF while maintaining aspect ratio
    const scaleX = pdfWidth / canvasWidth;
    const scaleY = pdfHeight / canvasHeight;
    const scale = Math.min(scaleX, scaleY) * 0.9; // 0.9 to add some margin
    
    const scaledWidth = canvasWidth * scale;
    const scaledHeight = canvasHeight * scale;
    
    // Center the image on the page
    const offsetX = (pdfWidth - scaledWidth) / 2;
    const offsetY = (pdfHeight - scaledHeight) / 2;
    
    // Store original page index
    const originalPageIndex = window.currentPageIndex;
    
    // Process each page
    for (let i = 0; i < window.pages.length; i++) {
      // Switch to the page
      window.switchToPage(i);
      
      // Force a redraw to ensure current content is rendered
      window.redraw();
      
      // Wait a bit for rendering to complete
      await new Promise(resolve => setTimeout(resolve, 100));
      
      // Convert canvas to image data
      const imgData = canvas.toDataURL('image/png', 1.0);
      
      // Add new page if not the first page
      if (i > 0) {
        pdf.addPage();
      }
      
      // Add title at the top of each page
      pdf.setFontSize(12);
      pdf.setTextColor(0, 0, 0);
      pdf.text(`${boardTitle}`, 10, 10);
      
      // Add the canvas image
      pdf.addImage(imgData, 'PNG', offsetX, offsetY + 15, scaledWidth, scaledHeight);
      
      // Add page number at bottom
      pdf.setFontSize(10);
      pdf.text(`Page ${i + 1}`, pdfWidth - 20, pdfHeight - 5);
    }
    
    // Return to original page
    window.switchToPage(originalPageIndex);
    
    // Save the PDF
    const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
    pdf.save(`${boardTitle}_${timestamp}.pdf`);
    
    // Show success message
    if (window.TelemetryPanel) {
      window.TelemetryPanel.setIdle(`PDF exported (${window.pages.length} pages)`);
    } else {
      alert(`PDF exported successfully!\n${window.pages.length} page(s) included.`);
    }
    
  } catch (error) {
    console.error('PDF export error:', error);
    if (window.TelemetryPanel) {
      window.TelemetryPanel.setIdle('PDF export failed');
    } else {
      alert('Error exporting PDF: ' + error.message);
    }
  }
}

/**
 * Initialize export/import event listeners
 */
function initializeExportImport() {
  const saveBtn = document.getElementById('save-btn');
  const exportPngBtn = document.getElementById('export-png');
  const printPdfBtn = document.getElementById('print-pdf');
  const importFileInput = document.getElementById('importFile');
  
  if (saveBtn) {
    saveBtn.addEventListener('click', saveToServer);
  }
  
  if (exportPngBtn) {
    exportPngBtn.addEventListener('click', exportPNG);
  }
  
  if (printPdfBtn) {
    printPdfBtn.addEventListener('click', printToPDF);
  }
  
  if (importFileInput) {
    importFileInput.addEventListener('change', handleImportFile);
  }
  
  console.log('Export/import event listeners initialized');
}

// Auto-initialize on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeExportImport);
} else {
  initializeExportImport();
}

// Expose functions to window for main whiteboard
window.saveToServer = saveToServer;
window.exportJSON = exportJSON;
window.importJSON = importJSON;
window.handleImportFile = handleImportFile;
window.exportPNG = exportPNG;
window.printToPDF = printToPDF;

// Export for use in main whiteboard
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    saveToServer,
    exportJSON,
    importJSON,
    handleImportFile,
    exportPNG,
    printToPDF,
    initializeExportImport
  };
}
