/**
 * Whiteboard Text Handling Module
 * Manages text wrapping, multi-page text distribution, and text editor
 * 
 * This module handles:
 * - Word-based text wrapping (autoWrapTextByWords)
 * - Line-based text splitting for pagination (splitTextByLines)
 * - Multi-page text distribution (addTextAcrossPages)
 * - Text editor overlay (openTextEditor, closeTextEditor)
 */

/**
 * Wrap text by words per line
 * Preserves paragraph structure (empty lines, newlines)
 * 
 * @param {string} text - Text to wrap
 * @param {number} maxWords - Maximum words per line
 * @returns {string} - Wrapped text with newlines
 */
function autoWrapTextByWords(text, maxWords) {
  if (!maxWords || maxWords <= 0) return text;

  return text
    .split("\n")
    .map(paragraph => {
      // Handle empty lines - preserve them
      if (paragraph.trim() === '') return paragraph;
      
      const words = paragraph.split(/\s+/).filter(word => word.length > 0);
      if (words.length === 0) return paragraph;
      
      // Group words into chunks of maxWords
      let result = [];
      for (let i = 0; i < words.length; i += maxWords) {
        result.push(words.slice(i, i + maxWords).join(" "));
      }
      return result.join("\n");
    })
    .join("\n");
}

/**
 * Split text into page chunks by line count
 * 
 * @param {string} text - Text to split (already wrapped)
 * @param {number} maxLinesPerPage - Maximum lines per page
 * @returns {Array<string>} - Array of text chunks (one per page)
 */
function splitTextByLines(text, maxLinesPerPage = 25) {
  console.log('=== SPLIT BY LINES DEBUG ===');
  console.log('Input text lines:', text.split('\n').length);
  console.log('maxLinesPerPage:', maxLinesPerPage);
  
  // Split text into lines while preserving original formatting
  const lines = text.split('\n');
  
  console.log('Total lines to split:', lines.length);
  
  // If total lines fit in one page, return as single chunk
  if (lines.length <= maxLinesPerPage) {
    console.log('Fits in one page, returning single chunk');
    return [text];
  }
  
  console.log('Multiple pages needed, splitting...');
  
  // Split lines into page chunks
  const pageChunks = [];
  for (let i = 0; i < lines.length; i += maxLinesPerPage) {
    const pageLines = lines.slice(i, i + maxLinesPerPage);
    pageChunks.push(pageLines.join('\n'));
    console.log(`Chunk ${pageChunks.length}: ${pageLines.length} lines`);
  }
  
  console.log('Final chunks:', pageChunks.length);
  return pageChunks;
}

/**
 * Add text across multiple pages if needed
 * Uses global userPrefs settings for wrapping and pagination
 * 
 * @param {string} text - Text to add
 * @param {number} fontSize - Font size in pixels
 * @param {number} startX - Starting X coordinate
 * @param {number} startY - Starting Y coordinate
 * @returns {number} - Number of pages created (0 if cancelled)
 */
function addTextAcrossPages(text, fontSize, startX = 50, startY = 160) {
  // Get current settings from modal - make sure they're loaded
  console.log('=== SETTINGS CHECK ===');
  console.log('userPrefs object:', window.userPrefs);
  console.log('userPrefs.maxWordsPerLine:', window.userPrefs?.maxWordsPerLine);
  console.log('userPrefs.maxLinesPerPage:', window.userPrefs?.maxLinesPerPage);
  
  const maxWordsPerLine = window.userPrefs?.maxWordsPerLine || 10;
  const maxLinesPerPage = window.userPrefs?.maxLinesPerPage || 25;
  
  console.log('=== TEXT SPLITTING DEBUG ===');
  console.log('Using maxWordsPerLine:', maxWordsPerLine);
  console.log('Using maxLinesPerPage:', maxLinesPerPage);
  console.log('Original text lines:', text.split('\n').length);
  
  // First apply word wrapping to break long lines
  const wrappedText = autoWrapTextByWords(text, maxWordsPerLine);
  
  console.log('After word wrapping lines:', wrappedText.split('\n').length);
  console.log('Wrapped text preview:', wrappedText.substring(0, 200));
  
  const chunks = splitTextByLines(wrappedText, maxLinesPerPage);
  
  console.log('Number of chunks:', chunks.length);
  console.log('Chunk lengths:', chunks.map(c => c.split('\n').length));
  
  if (chunks.length === 1) {
    // Single page - add normally with current settings stored
    window.addObject({
      id: window.nextObjectId++,
      type: "text",
      layer: window.BASE_OBJECT_LAYER,
      props: {
        text: chunks[0],
        x: startX,
        y: startY,
        fontSize: fontSize,
        color: window.color,
        maxWordsPerLine: maxWordsPerLine,
        maxLinesPerPage: maxLinesPerPage
      }
    });
    return 1;
  }
  
  // Multiple pages needed - confirm with user
  const totalLines = wrappedText.split('\n').length;
  const confirmed = confirm(
    `This text will be split across multiple pages.\n\n` +
    `Original text lines: ${text.split('\n').length}\n` +
    `After word wrapping (${maxWordsPerLine} words/line): ${totalLines} lines\n` +
    `Pages needed: ${chunks.length}\n` +
    `Lines per page: ${maxLinesPerPage}\n\n` +
    `Continue?`
  );
  
  if (!confirmed) return 0;
  
  // Save current state
  window.saveCurrentPageState();
  
  // Add text to current page (first chunk) with settings stored
  window.addObject({
    id: window.nextObjectId++,
    type: "text",
    layer: window.BASE_OBJECT_LAYER,
    props: {
      text: chunks[0],
      x: startX,
      y: startY,
      fontSize: fontSize,
      color: window.color,
      maxWordsPerLine: maxWordsPerLine,
      maxLinesPerPage: maxLinesPerPage
    }
  });
  
  // Create new pages for remaining chunks
  for (let i = 1; i < chunks.length; i++) {
    // Save current page state before creating new page
    window.saveCurrentPageState();
    
    // Create new page using Ctrl+E functionality
    const newPage = window.createNewPage();
    window.pages.splice(window.currentPageIndex + 1, 0, newPage);
    window.currentPageIndex = window.currentPageIndex + 1;
    
    // Load the new page
    window.loadPageState(window.currentPageIndex);
    
    // Add text chunk to new page with settings stored
    window.addObject({
      id: window.nextObjectId++,
      type: "text",
      layer: window.BASE_OBJECT_LAYER,
      props: {
        text: chunks[i],
        x: startX,
        y: startY,
        fontSize: fontSize,
        color: window.color,
        maxWordsPerLine: maxWordsPerLine,
        maxLinesPerPage: maxLinesPerPage
      }
    });
  }
  
  // Update page display
  window.updatePageDisplay();
  window.redraw();
  
  return chunks.length;
}

/**
 * Open text editor overlay for editing text object
 * 
 * @param {Object} textObj - Text object to edit
 */
function openTextEditor(textObj) {
  const textEditorOverlay = document.getElementById('text-editor-overlay');
  const textEditorTextarea = document.getElementById('text-editor-textarea');
  
  if (!textEditorOverlay || !textEditorTextarea) {
    console.error('Text editor elements not found');
    return;
  }
  
  window.editingTextId = textObj.id;
  const objText = textObj.props?.text || textObj.text || '';
  textEditorTextarea.value = objText;
  textEditorOverlay.style.display = 'flex';
  setTimeout(() => { 
    textEditorTextarea.focus(); 
    textEditorTextarea.select(); 
  }, 100);
}

/**
 * Close text editor overlay
 * 
 * @param {boolean} save - Whether to save changes
 */
function closeTextEditor(save = false) {
  const textEditorOverlay = document.getElementById('text-editor-overlay');
  const textEditorTextarea = document.getElementById('text-editor-textarea');
  
  if (save && window.editingTextId) {
    const o = window.findById(window.editingTextId);
    if (o) {
      const newText = textEditorTextarea.value.trim();

      // Always use global settings from settings modal
      console.log('=== TEXT EDITOR SAVE ===');
      console.log('Using global settings from settings modal');
      console.log('userPrefs.maxWordsPerLine:', window.userPrefs?.maxWordsPerLine);
      console.log('userPrefs.maxLinesPerPage:', window.userPrefs?.maxLinesPerPage);

      // Remove the original text object
      const index = window.objects.findIndex(obj => obj.id === window.editingTextId);
      if (index !== -1) {
        window.objects.splice(index, 1);
      }

      // Use the existing addTextAcrossPages function with global settings
      const objFontSize = o.props?.fontSize || o.fontSize || 24;
      const objX = o.props?.x || o.x || 0;
      const objY = o.props?.y || o.y || 0;
      addTextAcrossPages(newText, objFontSize, objX, objY);
    }
  }
  
  textEditorOverlay.style.display = 'none';
  window.editingTextId = null;
  textEditorTextarea.value = '';
}

/**
 * Initialize text editor event listeners
 */
function initializeTextEditor() {
  const textEditorSave = document.getElementById('text-editor-save');
  const textEditorCancel = document.getElementById('text-editor-cancel');
  const textEditorOverlay = document.getElementById('text-editor-overlay');
  const textEditorTextarea = document.getElementById('text-editor-textarea');
  
  if (textEditorSave) {
    textEditorSave.addEventListener('click', () => closeTextEditor(true));
  }
  
  if (textEditorCancel) {
    textEditorCancel.addEventListener('click', () => closeTextEditor(false));
  }
  
  if (textEditorOverlay) {
    textEditorOverlay.addEventListener('click', (e) => { 
      if (e.target === textEditorOverlay) closeTextEditor(false); 
    });
  }
  
  if (textEditorTextarea) {
    textEditorTextarea.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeTextEditor(false);
      else if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) closeTextEditor(true);
    });
  }
  
  console.log('Text editor event listeners initialized');
}

// Auto-initialize on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeTextEditor);
} else {
  initializeTextEditor();
}

// Expose functions to window for main whiteboard
window.autoWrapTextByWords = autoWrapTextByWords;
window.splitTextByLines = splitTextByLines;
window.addTextAcrossPages = addTextAcrossPages;
window.openTextEditor = openTextEditor;
window.closeTextEditor = closeTextEditor;

// Export for use in main whiteboard
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    autoWrapTextByWords,
    splitTextByLines,
    addTextAcrossPages,
    openTextEditor,
    closeTextEditor,
    initializeTextEditor
  };
}
