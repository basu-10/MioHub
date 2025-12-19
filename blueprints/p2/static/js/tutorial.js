/**
 * Shepherd.js Tutorial System for MioNote, MioDraw, and Folder View
 * Provides guided tours for new users with option to retrigger
 */

// Tutorial configuration constants
const TUTORIAL_CONFIG = {
  useModalOverlay: true,
  defaultStepOptions: {
    cancelIcon: {
      enabled: true
    },
    classes: 'shepherd-theme-mio',
    scrollTo: { behavior: 'smooth', block: 'center' }
  }
};

// LocalStorage keys for tracking tutorial completion
const STORAGE_KEYS = {
  noteEditor: 'mionote_tutorial_completed',
  whiteboard: 'miodraw_tutorial_completed',
  folderView: 'folder_tutorial_completed'
};

/**
 * MioNote Note Editor Tutorial
 */
function createNoteEditorTour() {
  const tour = new Shepherd.Tour(TUTORIAL_CONFIG);

  tour.addStep({
    id: 'welcome',
    text: `
      <div class="tutorial-step">
        <h3 class="mb-3">📝 Welcome to MioNote!</h3>
        <p>MioNote is your powerful markdown note editor with advanced features. Let's take a quick tour to get you started.</p>
        <p class="text-muted small mb-0">This tutorial takes about 2 minutes.</p>
      </div>
    `,
    buttons: [
      {
        text: 'Skip Tour',
        action: tour.complete,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Start Tour',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'title-input',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">📌 Note Title</h4>
        <p>Give your note a descriptive title here. This helps you find it later in your folder structure.</p>
      </div>
    `,
    attachTo: {
      element: 'input[name="title"]',
      on: 'bottom'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'summernote-toolbar',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">🎨 Rich Text Toolbar</h4>
        <p>Format your text with these powerful tools:</p>
        <ul class="small mb-0">
          <li><strong>Text styles:</strong> Bold, italic, underline</li>
          <li><strong>Lists:</strong> Bullets and numbered lists</li>
          <li><strong>Tables:</strong> Create structured data</li>
          <li><strong>Media:</strong> Insert images, links, and videos</li>
        </ul>
      </div>
    `,
    attachTo: {
      element: '.note-toolbar',
      on: 'bottom'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'editor-area',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">✍️ Writing Area</h4>
        <p>Start typing your notes here. Your work is <strong>auto-saved every 2 seconds</strong> as you type.</p>
        <p class="small text-muted mb-0">💡 Tip: No need to worry about losing your work!</p>
      </div>
    `,
    attachTo: {
      element: '.note-editable',
      on: 'top'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'floating-toolbar',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">🧰 Quick Actions Toolbar</h4>
        <p>Access powerful utilities:</p>
        <ul class="small mb-2">
          <li><strong>💾 Save:</strong> Manual save (or press Ctrl+S)</li>
          <li><strong>🧮 Eval:</strong> Calculate selected math expressions</li>
          <li><strong>🔍 Find/Replace:</strong> Search and replace text</li>
          <li><strong>📊 Table Format:</strong> Format tabular data</li>
          <li><strong>📖 Help:</strong> View all shortcuts</li>
        </ul>
        <p class="small text-muted mb-0">💡 This toolbar floats at the bottom-right corner.</p>
      </div>
    `,
    attachTo: {
      element: '.floating-toolbar',
      on: 'left'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'save-button',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">💾 Manual Save</h4>
        <p>Click here to save immediately, or use <kbd>Ctrl+S</kbd> (Windows) / <kbd>Cmd+S</kbd> (Mac).</p>
        <p class="small text-muted mb-0">Auto-save runs every 2 seconds after you stop typing.</p>
      </div>
    `,
    attachTo: {
      element: '#saveBtn',
      on: 'left'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'eval-button',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">🧮 Calculator Integration</h4>
        <p><strong>How to use:</strong></p>
        <ol class="small mb-2">
          <li>Select a math expression in your note (e.g., "15 * 8 + 12")</li>
          <li>Click this button</li>
          <li>The result replaces your selection!</li>
        </ol>
        <p class="small text-muted mb-0">Powered by Calculator++ product.</p>
      </div>
    `,
    attachTo: {
      element: '#evalBtn',
      on: 'left'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'table-button',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">📊 Table Formatter</h4>
        <p><strong>Perfect for terminal output!</strong></p>
        <ol class="small mb-2">
          <li>Copy terminal output or select tabular text</li>
          <li>Click this button</li>
          <li>Choose your delimiter (whitespace, tab, comma, etc.)</li>
          <li>Get a perfectly formatted aligned table!</li>
        </ol>
        <p class="small text-muted mb-0">💡 Great for formatting command outputs and data columns.</p>
      </div>
    `,
    attachTo: {
      element: '#insertTableBtn',
      on: 'left'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'pin-button',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">📌 Pin Toolbar</h4>
        <p>Click here to pin this toolbar to the top of your screen. It will stay visible as you scroll through long documents.</p>
        <p class="small text-muted mb-0">💡 Toggle anytime to switch between floating and pinned modes.</p>
      </div>
    `,
    attachTo: {
      element: '#pinBtn',
      on: 'left'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'find-replace',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">🔍 Find & Replace</h4>
        <p>Search and replace text across your entire note with advanced options:</p>
        <ul class="small mb-0">
          <li>Match case</li>
          <li>Match whole words</li>
          <li>Replace next or replace all</li>
        </ul>
      </div>
    `,
    attachTo: {
      element: '#findReplaceBtn',
      on: 'left'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'scroll-controls',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">⬆️⬇️ Quick Navigation</h4>
        <p>Jump to the top or bottom of your document instantly with these buttons.</p>
        <p class="small text-muted mb-0">Useful for long documents!</p>
      </div>
    `,
    attachTo: {
      element: '#scrollTopBtn',
      on: 'left'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'word-count',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">📊 Word & Character Count</h4>
        <p>Track your writing progress in real-time. Updates automatically as you type.</p>
      </div>
    `,
    attachTo: {
      element: '#wordCount',
      on: 'top'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'keyboard-shortcuts',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">⌨️ Essential Keyboard Shortcuts</h4>
        <ul class="small mb-2">
          <li><kbd>Ctrl+S</kbd> - Save note</li>
          <li><kbd>Ctrl+Shift+V</kbd> - Paste as plain text</li>
          <li><kbd>Ctrl+Z</kbd> / <kbd>Ctrl+Y</kbd> - Undo / Redo</li>
        </ul>
        <p class="small text-muted mb-0">💡 Click the <strong>Help</strong> button (❓) to see all shortcuts!</p>
      </div>
    `,
    attachTo: {
      element: '#helpBtn',
      on: 'left'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'completion',
    text: `
      <div class="tutorial-step">
        <h3 class="mb-3">🎉 You're All Set!</h3>
        <p class="mb-3">You now know how to use MioNote like a pro!</p>
        <div class="alert alert-info small mb-3">
          <strong>💡 Pro Tips:</strong>
          <ul class="mb-0 mt-2">
            <li>Your notes auto-save every 2 seconds</li>
            <li>Tables can be edited by clicking cells</li>
            <li>Images are automatically resized to fit</li>
            <li>Use the 📖 Help button anytime to replay this tour</li>
          </ul>
        </div>
        <p class="small text-muted mb-0">Happy note-taking! ✨</p>
      </div>
    `,
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Finish',
        action: tour.complete
      }
    ]
  });

  return tour;
}

/**
 * MioDraw Whiteboard Tutorial
 */
function createWhiteboardTour() {
  const tour = new Shepherd.Tour(TUTORIAL_CONFIG);

  tour.addStep({
    id: 'welcome',
    text: `
      <div class="tutorial-step">
        <h3 class="mb-3">🎨 Welcome to MioDraw!</h3>
        <p>MioDraw is your infinite canvas for sketching, diagramming, and visual thinking. Let's explore its powerful features!</p>
        <p class="text-muted small mb-0">This tutorial takes about 3 minutes.</p>
      </div>
    `,
    buttons: [
      {
        text: 'Skip Tour',
        action: tour.complete,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Start Tour',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'canvas-area',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">🖼️ Canvas Area</h4>
        <p>This is your drawing canvas. It's organized into pages that you can add, navigate, and manage.</p>
        <p class="small text-muted mb-0">💡 Click anywhere to start drawing with the selected tool!</p>
      </div>
    `,
    attachTo: {
      element: '#whiteboard-canvas',
      on: 'top'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'drawing-tools',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">✏️ Drawing Tools</h4>
        <p>Choose from various tools:</p>
        <ul class="small mb-2">
          <li><strong>Select:</strong> Click and move objects</li>
          <li><strong>Pen:</strong> Freehand drawing</li>
          <li><strong>Highlighter:</strong> Transparent overlay</li>
          <li><strong>Eraser:</strong> Remove strokes</li>
          <li><strong>Text:</strong> Add typed text (Ctrl+T or Ctrl+Shift+T)</li>
          <li><strong>Shapes:</strong> Rectangles, circles, lines, arrows</li>
        </ul>
        <p class="small text-muted mb-0">Each tool remembers its color and size settings!</p>
      </div>
    `,
    attachTo: {
      element: '.toolbar-section:first-child',
      on: 'bottom'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'color-size',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">🎨 Colors & Sizes</h4>
        <p>Customize your tools:</p>
        <ul class="small mb-0">
          <li><strong>Color picker:</strong> Choose any color</li>
          <li><strong>Size slider:</strong> Adjust stroke width</li>
          <li><strong>Color palette:</strong> Quick access to common colors</li>
        </ul>
      </div>
    `,
    attachTo: {
      element: 'input[type="color"]',
      on: 'bottom'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'pages',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">📄 Page Management</h4>
        <p>Organize your work across multiple pages:</p>
        <ul class="small mb-2">
          <li><strong>Ctrl+E:</strong> Add a new page at cursor</li>
          <li><strong>Navigation:</strong> Use arrow buttons to move between pages</li>
          <li><strong>Page counter:</strong> Shows current page and total</li>
        </ul>
        <p class="small text-muted mb-0">💡 Each page is independent with its own content!</p>
      </div>
    `,
    attachTo: {
      element: '#prevPageBtn',
      on: 'bottom'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'clipboard',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">📋 Copy, Cut & Paste</h4>
        <p>Standard clipboard operations work:</p>
        <ul class="small mb-2">
          <li><kbd>Ctrl+C</kbd> - Copy selected objects</li>
          <li><kbd>Ctrl+X</kbd> - Cut selected objects</li>
          <li><kbd>Ctrl+V</kbd> - Paste (works across pages!)</li>
          <li><strong>Right-click:</strong> Paste at cursor location</li>
        </ul>
        <p class="small text-muted mb-0">💡 You can paste images and text from your system clipboard too!</p>
      </div>
    `,
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'undo-redo',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">↶↷ Undo & Redo</h4>
        <p>Made a mistake? No problem!</p>
        <ul class="small mb-0">
          <li><kbd>Ctrl+Z</kbd> - Undo last action</li>
          <li><kbd>Ctrl+Y</kbd> - Redo undone action</li>
        </ul>
      </div>
    `,
    attachTo: {
      element: '#undoBtn',
      on: 'bottom'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'layers',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">🎭 Layers & Objects</h4>
        <p>Manage object stacking order:</p>
        <ul class="small mb-2">
          <li><strong>Layers panel:</strong> View all objects on current page</li>
          <li><strong>Bring to front / Send to back:</strong> Change z-order</li>
          <li><strong>Layer up / Layer down:</strong> Fine-tune positioning</li>
        </ul>
        <p class="small text-muted mb-0">Click objects in the layer list to select them on canvas!</p>
      </div>
    `,
    attachTo: {
      element: '#layerToggleBtn',
      on: 'left'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'selection',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">🎯 Selection Tools</h4>
        <p>Multiple ways to select objects:</p>
        <ul class="small mb-2">
          <li><strong>Click:</strong> Select single object</li>
          <li><strong>Rectangle tool:</strong> Drag to select multiple objects</li>
          <li><strong>Ctrl+Click:</strong> Add/remove from selection</li>
          <li><strong>Delete key:</strong> Remove selected objects</li>
        </ul>
        <p class="small text-muted mb-0">💡 Selected objects show resize handles and can be moved with arrow keys!</p>
      </div>
    `,
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'keyboard-shortcuts',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">⌨️ Essential Keyboard Shortcuts</h4>
        <ul class="small mb-2">
          <li><kbd>Ctrl+S</kbd> - Save whiteboard</li>
          <li><kbd>Ctrl+E</kbd> - Insert new page</li>
          <li><kbd>Ctrl+T</kbd> - Insert text</li>
          <li><kbd>Ctrl+I</kbd> - Insert image</li>
          <li><kbd>Delete</kbd> - Delete selected</li>
          <li><kbd>Arrow keys</kbd> - Move selected objects</li>
          <li><kbd>Shift+Arrow</kbd> - Move faster</li>
        </ul>
        <p class="small text-muted mb-0">💡 Click the keyboard icon in the toolbar to see all shortcuts!</p>
      </div>
    `,
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'save',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">💾 Saving Your Work</h4>
        <p>Click the save button or press <kbd>Ctrl+S</kbd> to save your whiteboard.</p>
        <p class="small text-muted mb-0">All pages and objects are preserved!</p>
      </div>
    `,
    attachTo: {
      element: '#saveWhiteboardBtn',
      on: 'left'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'completion',
    text: `
      <div class="tutorial-step">
        <h3 class="mb-3">🎉 Ready to Create!</h3>
        <p class="mb-3">You're now ready to use MioDraw like a pro!</p>
        <div class="alert alert-info small mb-3">
          <strong>💡 Pro Tips:</strong>
          <ul class="mb-0 mt-2">
            <li>Double-click text objects to edit them</li>
            <li>Shift+Drag to maintain aspect ratio when resizing</li>
            <li>Use flowchart tools for quick diagrams</li>
            <li>Text wraps automatically based on settings</li>
          </ul>
        </div>
        <p class="small text-muted mb-0">Happy drawing! ✨</p>
      </div>
    `,
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Finish',
        action: tour.complete
      }
    ]
  });

  return tour;
}

/**
 * Folder View Tutorial
 */
function createFolderViewTour() {
  const tour = new Shepherd.Tour(TUTORIAL_CONFIG);

  tour.addStep({
    id: 'welcome',
    text: `
      <div class="tutorial-step">
        <h3 class="mb-3">📁 Welcome to MioNote Dashboard!</h3>
        <p>This is your central hub for organizing notes, whiteboards, and combined documents. Let's explore how to navigate and manage your content!</p>
        <p class="text-muted small mb-0">This tutorial takes about 2 minutes.</p>
      </div>
    `,
    buttons: [
      {
        text: 'Skip Tour',
        action: tour.complete,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Start Tour',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'breadcrumb',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">🧭 Breadcrumb Navigation</h4>
        <p>Shows your current location in the folder hierarchy. Click any folder name to jump to that level.</p>
        <p class="small text-muted mb-0">💡 Always know where you are in your folder structure!</p>
      </div>
    `,
    attachTo: {
      element: '.breadcrumb, nav[aria-label="breadcrumb"]',
      on: 'bottom'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'create-buttons',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">➕ Create New Content</h4>
        <p>Use these buttons to create:</p>
        <ul class="small mb-2">
          <li><strong>📝 New Note:</strong> Create a MioNote text document</li>
          <li><strong>🎨 New Board:</strong> Create a MioDraw whiteboard</li>
          <li><strong>📋 New Work:</strong> Create a MioBook combined document</li>
          <li><strong>📁 New Folder:</strong> Organize your content</li>
        </ul>
        <p class="small text-muted mb-0">All items are created in the current folder.</p>
      </div>
    `,
    attachTo: {
      element: '.btn-success:first-of-type, [href*="new_note"]',
      on: 'bottom'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'folder-tree',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">🌳 Folder Tree</h4>
        <p>Navigate your folder hierarchy:</p>
        <ul class="small mb-2">
          <li><strong>Click folders:</strong> View their contents</li>
          <li><strong>Nested structure:</strong> Organize deeply</li>
          <li><strong>Icons:</strong> Identify content types at a glance</li>
        </ul>
        <p class="small text-muted mb-0">💡 Create subfolders to keep related content together!</p>
      </div>
    `,
    attachTo: {
      element: '.folder-item:first-child, .list-group-item:first-child',
      on: 'right'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'content-list',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">📄 Content List</h4>
        <p>View all items in the current folder:</p>
        <ul class="small mb-2">
          <li><strong>📝 Notes:</strong> Text documents (MioNote)</li>
          <li><strong>🎨 Boards:</strong> Whiteboards (MioDraw)</li>
          <li><strong>📋 Works:</strong> Combined documents (MioBook)</li>
          <li><strong>📁 Folders:</strong> Subfolders</li>
        </ul>
        <p class="small text-muted mb-0">Click any item to open and edit it.</p>
      </div>
    `,
    attachTo: {
      element: '.table, .content-list',
      on: 'top'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'action-buttons',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">⚙️ Item Actions</h4>
        <p>Each item has action buttons:</p>
        <ul class="small mb-2">
          <li><strong>✏️ Edit:</strong> Open the item</li>
          <li><strong>🗑️ Delete:</strong> Remove the item (with confirmation)</li>
          <li><strong>📤 Share:</strong> Share with other users (if available)</li>
        </ul>
        <p class="small text-muted mb-0">💡 Deleted items are permanently removed!</p>
      </div>
    `,
    attachTo: {
      element: '.btn-group:first-of-type, .action-buttons:first-of-type',
      on: 'left'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'search',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">🔍 Search</h4>
        <p>Find your content quickly by searching for titles or content.</p>
        <p class="small text-muted mb-0">Search works across all folders!</p>
      </div>
    `,
    attachTo: {
      element: 'input[type="search"], input[placeholder*="Search"]',
      on: 'bottom'
    },
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'folder-operations',
    text: `
      <div class="tutorial-step">
        <h4 class="mb-2">📁 Folder Management</h4>
        <p>Organize your workspace:</p>
        <ul class="small mb-2">
          <li><strong>Create subfolders:</strong> Nested organization</li>
          <li><strong>Move items:</strong> Drag and drop (if enabled)</li>
          <li><strong>Delete folders:</strong> Removes all contents recursively</li>
        </ul>
        <p class="small text-warning mb-0">⚠️ Deleting a folder deletes all its contents!</p>
      </div>
    `,
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Next',
        action: tour.next
      }
    ]
  });

  tour.addStep({
    id: 'completion',
    text: `
      <div class="tutorial-step">
        <h3 class="mb-3">🎉 You're Ready to Organize!</h3>
        <p class="mb-3">You now know how to navigate and manage your MioNote workspace!</p>
        <div class="alert alert-info small mb-3">
          <strong>💡 Organization Tips:</strong>
          <ul class="mb-0 mt-2">
            <li>Create folders for projects or topics</li>
            <li>Use descriptive names for easy searching</li>
            <li>Group related notes, boards, and works together</li>
            <li>Regularly review and clean up old content</li>
          </ul>
        </div>
        <p class="small text-muted mb-0">Happy organizing! ✨</p>
      </div>
    `,
    buttons: [
      {
        text: 'Back',
        action: tour.back,
        classes: 'shepherd-button-secondary'
      },
      {
        text: 'Finish',
        action: tour.complete
      }
    ]
  });

  return tour;
}

/**
 * Initialize and start the appropriate tutorial based on page context
 */
function initializeTutorialSystem() {
  // Detect which page we're on
  const isNoteEditor = document.getElementById('editor') !== null;
  const isWhiteboard = document.getElementById('board-canvas') !== null;
  const isFolderView = document.querySelector('.breadcrumb, nav[aria-label="breadcrumb"]') !== null && !isNoteEditor && !isWhiteboard;

  let tour = null;
  let storageKey = null;

  if (isNoteEditor) {
    tour = createNoteEditorTour();
    storageKey = STORAGE_KEYS.noteEditor;
  } else if (isWhiteboard) {
    tour = createWhiteboardTour();
    storageKey = STORAGE_KEYS.whiteboard;
  } else if (isFolderView) {
    tour = createFolderViewTour();
    storageKey = STORAGE_KEYS.folderView;
  }

  if (!tour || !storageKey) {
    console.log('Tutorial system: No matching page context found');
    return null;
  }

  // Set up completion handler
  tour.on('complete', () => {
    localStorage.setItem(storageKey, 'true');
    if (window.showToast) {
      window.showToast('Tutorial completed! You can replay it anytime from the Help button.', 'success', 3000);
    }
  });

  tour.on('cancel', () => {
    localStorage.setItem(storageKey, 'true');
  });

  // Auto-start if not completed
  const hasCompleted = localStorage.getItem(storageKey) === 'true';
  if (!hasCompleted) {
    // Delay to ensure page is fully loaded
    setTimeout(() => {
      tour.start();
    }, 1000);
  }

  // Return tour object so it can be triggered manually
  return tour;
}

/**
 * Manually trigger the tutorial (for Help button)
 */
function startTutorial() {
  const isNoteEditor = document.getElementById('editor') !== null;
  const isWhiteboard = document.getElementById('board-canvas') !== null;
  const isFolderView = document.querySelector('.breadcrumb, nav[aria-label="breadcrumb"]') !== null && !isNoteEditor && !isWhiteboard;

  let tour = null;

  if (isNoteEditor) {
    tour = createNoteEditorTour();
  } else if (isWhiteboard) {
    tour = createWhiteboardTour();
  } else if (isFolderView) {
    tour = createFolderViewTour();
  }

  if (tour) {
    tour.start();
  } else {
    if (window.showToast) {
      window.showToast('No tutorial available for this page.', 'warning', 2000);
    }
  }
}

/**
 * Reset all tutorials (for testing or user preference)
 */
function resetAllTutorials() {
  Object.values(STORAGE_KEYS).forEach(key => {
    localStorage.removeItem(key);
  });
  if (window.showToast) {
    window.showToast('All tutorials reset! Refresh the page to see them again.', 'info', 3000);
  }
}

// Export functions for use in HTML pages
window.initializeTutorialSystem = initializeTutorialSystem;
window.startTutorial = startTutorial;
window.resetAllTutorials = resetAllTutorials;
