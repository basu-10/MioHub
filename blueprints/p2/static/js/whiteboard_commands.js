/**
 * Whiteboard Command System Module
 * Implements undo/redo functionality with command pattern
 */

/**
 * Deep clone helper function
 * @param {*} value - Value to clone
 * @returns {*} - Cloned value
 */
function structuredCloneSafe(value) {
  if (window.structuredClone) {
    return structuredClone(value);
  }
  return JSON.parse(JSON.stringify(value));
}

/**
 * Find object by ID in the objects array
 * @param {number} id - Object ID
 * @returns {Object|undefined} - Found object or undefined
 */
function findById(id) {
  const objects = window.objects || [];
  return objects.find(o => o.id === id);
}

/**
 * Apply a command to modify the state
 * @param {Object} cmd - Command object
 */
function applyCommand(cmd) {
  const objects = window.objects || [];
  
  switch(cmd.type) {
    case "add":
      objects.push(structuredCloneSafe(cmd.object));
      break;
      
    case "delete":
      const deleteIndex = objects.findIndex(o => o.id === cmd.object.id);
      if (deleteIndex !== -1) {
        objects.splice(deleteIndex, 1);
      }
      break;
      
    case "updateProps": {
      const obj = findById(cmd.id);
      if (obj && obj.props) {
        Object.assign(obj.props, cmd.next);
      }
      break;
    }
    
    case "updateRoot": {
      const obj = findById(cmd.id);
      if (obj) {
        Object.assign(obj, cmd.next);
      }
      break;
    }
    
    case "batch":
      if (Array.isArray(cmd.commands)) {
        cmd.commands.forEach(applyCommand);
      }
      break;
  }
}

/**
 * Apply the inverse of a command (for undo)
 * @param {Object} cmd - Command object
 */
function applyInverse(cmd) {
  const objects = window.objects || [];
  
  switch(cmd.type) {
    case "add":
      const addIndex = objects.findIndex(o => o.id === cmd.object.id);
      if (addIndex !== -1) {
        objects.splice(addIndex, 1);
      }
      break;
      
    case "delete":
      objects.push(structuredCloneSafe(cmd.object));
      break;
      
    case "updateProps": {
      const obj = findById(cmd.id);
      if (obj && obj.props) {
        Object.assign(obj.props, cmd.prev);
      }
      break;
    }
    
    case "updateRoot": {
      const obj = findById(cmd.id);
      if (obj) {
        Object.assign(obj, cmd.prev);
      }
      break;
    }
    
    case "batch":
      if (Array.isArray(cmd.commands)) {
        // Apply batch commands in reverse order for undo
        for (let i = cmd.commands.length - 1; i >= 0; i--) {
          applyInverse(cmd.commands[i]);
        }
      }
      break;
  }
}

/**
 * Execute a command and add it to undo stack
 * @param {Object} cmd - Command object
 */
function executeCommand(cmd) {
  if (!window.undoStack || !window.redoStack) {
    console.error('Undo/redo stacks not initialized');
    return;
  }
  
  applyCommand(cmd);
  window.undoStack.push(cmd);
  window.redoStack = [];
  
  // Enforce undo history limit (default 50, configurable via MAX_UNDO_HISTORY)
  const maxHistory = window.MAX_UNDO_HISTORY || 50;
  if (window.undoStack.length > maxHistory) {
    window.undoStack.shift(); // Remove oldest action
  }
  
  // Mark as having unsaved changes
  if (window.hasUnsavedChanges !== undefined) {
    window.hasUnsavedChanges = true;
  }
  
  if (window.redraw) {
    window.redraw();
  }
}

/**
 * Commit a command that has already been applied (for live edits)
 * @param {Object} cmd - Command object
 */
function commitAppliedChange(cmd) {
  if (!window.undoStack || !window.redoStack) {
    console.error('Undo/redo stacks not initialized');
    return;
  }
  
  window.undoStack.push(cmd);
  window.redoStack = [];
  
  // Enforce undo history limit (default 50, configurable via MAX_UNDO_HISTORY)
  const maxHistory = window.MAX_UNDO_HISTORY || 50;
  if (window.undoStack.length > maxHistory) {
    window.undoStack.shift(); // Remove oldest action
  }
  
  // Mark as having unsaved changes
  if (window.hasUnsavedChanges !== undefined) {
    window.hasUnsavedChanges = true;
  }
  
  if (window.redraw) {
    window.redraw();
  }
}

/**
 * Undo the last command
 */
function undo() {
  if (!window.undoStack || !window.redoStack) {
    console.error('Undo/redo stacks not initialized');
    return;
  }
  
  const cmd = window.undoStack.pop();
  if (!cmd) return;
  
  applyInverse(cmd);
  window.redoStack.push(cmd);
  
  if (window.redraw) {
    window.redraw();
  }
}

/**
 * Redo the last undone command
 */
function redo() {
  if (!window.undoStack || !window.redoStack) {
    console.error('Undo/redo stacks not initialized');
    return;
  }
  
  const cmd = window.redoStack.pop();
  if (!cmd) return;
  
  applyCommand(cmd);
  window.undoStack.push(cmd);
  
  if (window.redraw) {
    window.redraw();
  }
}

/**
 * Add an object to the canvas
 * @param {Object} obj - Object to add
 */
function addObject(obj) {
  executeCommand({ type: "add", object: obj });
}

/**
 * Remove an object from the canvas by reference
 * @param {Object} obj - Object to remove
 */
function removeByIdCmd(obj) {
  executeCommand({ type: "delete", object: structuredCloneSafe(obj) });
}

/**
 * Clear undo/redo stacks
 */
function clearHistory() {
  if (window.undoStack) window.undoStack = [];
  if (window.redoStack) window.redoStack = [];
}

/**
 * Get undo/redo stack sizes
 * @returns {Object} - {undoCount, redoCount}
 */
function getHistoryStatus() {
  return {
    undoCount: window.undoStack ? window.undoStack.length : 0,
    redoCount: window.redoStack ? window.redoStack.length : 0
  };
}

/**
 * Initialize undo/redo button states
 */
function updateUndoRedoButtons() {
  const undoBtn = document.getElementById('undo-btn');
  const redoBtn = document.getElementById('redo-btn');
  
  if (undoBtn) {
    undoBtn.disabled = !window.undoStack || window.undoStack.length === 0;
  }
  
  if (redoBtn) {
    redoBtn.disabled = !window.redoStack || window.redoStack.length === 0;
  }
}

/**
 * Initialize command system event listeners
 */
function initializeCommandSystem() {
  const undoBtn = document.getElementById('undo-btn');
  const redoBtn = document.getElementById('redo-btn');
  
  if (undoBtn) {
    undoBtn.addEventListener('click', undo);
  }
  
  if (redoBtn) {
    redoBtn.addEventListener('click', redo);
  }
  
  // Update button states whenever commands are executed
  const originalExecuteCommand = executeCommand;
  window.executeCommand = function(cmd) {
    originalExecuteCommand(cmd);
    updateUndoRedoButtons();
  };
  
  const originalUndo = undo;
  window.undo = function() {
    originalUndo();
    updateUndoRedoButtons();
  };
  
  const originalRedo = redo;
  window.redo = function() {
    originalRedo();
    updateUndoRedoButtons();
  };
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    initializeCommandSystem();
    updateUndoRedoButtons();
  });
} else {
  initializeCommandSystem();
  updateUndoRedoButtons();
}

// Export for use in main whiteboard
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    structuredCloneSafe,
    findById,
    applyCommand,
    applyInverse,
    executeCommand,
    commitAppliedChange,
    undo,
    redo,
    addObject,
    removeByIdCmd,
    clearHistory,
    getHistoryStatus,
    updateUndoRedoButtons,
    initializeCommandSystem
  };
}
