/**
 * Infinite Whiteboard Undo/Redo Module
 * Handles undo/redo functionality for infinite whiteboard
 */

(function(window) {
    'use strict';

    window.InfiniteWhiteboard = window.InfiniteWhiteboard || {};
    const IWB = window.InfiniteWhiteboard;

    // Configuration
    const MAX_UNDO_LIMIT = 100; // Prevent memory leaks from unlimited stack growth

    // Undo/redo stacks
    IWB.undoStack = [];
    IWB.redoStack = [];

    const sortIfLayered = (items) => {
        if (IWB.sortObjectsByLayerInPlace && Array.isArray(items)) {
            IWB.sortObjectsByLayerInPlace(items);
        }
        return items;
    };

    /**
     * Add action to undo stack
     */
    IWB.addToUndoStack = function(action) {
        // Optimize image storage - store only references, not full data URIs
        if (action.type === 'add' && action.object && action.object.type === 'image') {
            // Create lightweight copy without imageElement and with minimal data
            action.object = {
                ...action.object,
                imageElement: null, // Remove DOM element
                // Keep src reference for reconstruction, but note: data URIs still stored
                // For further optimization, consider storing only image ID and fetching on undo
            };
        }
        
        // Enforce history limit to prevent memory leaks
        if (IWB.undoStack.length >= MAX_UNDO_LIMIT) {
            // Remove oldest entry when limit reached
            IWB.undoStack.shift();
            console.log(`[UNDO] History limit reached (${MAX_UNDO_LIMIT}), removed oldest entry`);
        }
        
        IWB.undoStack.push(action);
        IWB.redoStack = []; // Clear redo stack when new action is added
        
        // Notify UI to update button states
        if (typeof IWB.updateUndoRedoButtons === 'function') {
            IWB.updateUndoRedoButtons();
        }
    };

    /**
     * Undo last action
     */
    IWB.undo = function(objects) {
        const action = IWB.undoStack.pop();
        if (!action) return objects;
        
        if (action.type === 'add') {
            // Remove the object that was added
            objects = objects.filter(o => o.id !== action.object.id);
            IWB.redoStack.push(action);
            
            // Update button states
            if (typeof IWB.updateUndoRedoButtons === 'function') {
                IWB.updateUndoRedoButtons();
            }
        } else if (action.type === 'delete') {
            // Re-add the deleted object
            // Reconstruct imageElement if this is an image
            if (action.object.type === 'image' && action.object.src && !action.object.imageElement) {
                const img = new Image();
                img.src = action.object.src;
                action.object.imageElement = img;
                img.onload = () => {
                    if (typeof IWB.requestRender === 'function') {
                        IWB.requestRender();
                    }
                };
            }
            objects.push(action.object);
            IWB.redoStack.push(action);
            
            // Update button states
            if (typeof IWB.updateUndoRedoButtons === 'function') {
                IWB.updateUndoRedoButtons();
            }
        } else if (action.type === 'move') {
            // Restore old position for strokes
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.path) {
                obj.path = action.oldPath;
            }
            IWB.redoStack.push(action);
        } else if (action.type === 'moveImage') {
            // Restore old position for images
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.type === 'image') {
                obj.x = action.oldPos.x;
                obj.y = action.oldPos.y;
            }
            IWB.redoStack.push(action);
        } else if (action.type === 'moveText') {
            // Restore old position for text
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.type === 'text') {
                obj.x = action.oldPos.x;
                obj.y = action.oldPos.y;
            }
            IWB.redoStack.push(action);
        } else if (action.type === 'moveShape') {
            // Restore old position for shape
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.type === 'shape') {
                obj.x = action.oldPos.x;
                obj.y = action.oldPos.y;
            }
            IWB.redoStack.push(action);
        } else if (action.type === 'layer') {
            // Handle layer operations (bring to front, send to back, move up/down)
            if (IWB.applyLayerUndo) {
                IWB.applyLayerUndo(action, objects);
            }
            IWB.redoStack.push(action);
        } else if (action.type === 'transform') {
            // Handle multi-select transform operations (move, rotate, mirror)
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && action.before) {
                // Restore the before geometry
                if (action.before.type === 'stroke' && obj.path) {
                    obj.path = JSON.parse(JSON.stringify(action.before.path || []));
                } else if (action.before.type === 'image') {
                    obj.x = action.before.x || 0;
                    obj.y = action.before.y || 0;
                    obj.w = action.before.w || 0;
                    obj.h = action.before.h || 0;
                    obj.rotation = action.before.rotation || 0;
                    obj.flipH = action.before.flipH || false;
                    obj.flipV = action.before.flipV || false;
                } else if (action.before.type === 'shape') {
                    obj.x = action.before.x || 0;
                    obj.y = action.before.y || 0;
                    obj.w = action.before.w || 0;
                    obj.h = action.before.h || 0;
                    obj.rotation = action.before.rotation || 0;
                    obj.flipH = action.before.flipH || false;
                    obj.flipV = action.before.flipV || false;
                    if (action.before.startX !== undefined) {
                        obj.startX = action.before.startX;
                        obj.startY = action.before.startY;
                        obj.endX = action.before.endX;
                        obj.endY = action.before.endY;
                    }
                } else if (action.before.type === 'text') {
                    obj.x = action.before.x || 0;
                    obj.y = action.before.y || 0;
                    obj.width = action.before.w || obj.width || 100;
                    obj.height = action.before.h || obj.height || 50;
                    obj.rotation = action.before.rotation || 0;
                    obj.flipH = action.before.flipH || false;
                    obj.flipV = action.before.flipV || false;
                }
            }
            IWB.redoStack.push(action);
        } else if (action.type === 'batch_delete') {
            // Restore all deleted objects from batch clear
            if (Array.isArray(action.objects)) {
                objects.push(...action.objects);
            }
            IWB.redoStack.push(action);
        } else if (action.type === 'imageResize') {
            // Restore old image bounds
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.type === 'image' && action.oldBounds) {
                obj.x = action.oldBounds.x;
                obj.y = action.oldBounds.y;
                obj.w = action.oldBounds.w;
                obj.h = action.oldBounds.h;
            }
            IWB.redoStack.push(action);
        } else if (action.type === 'imageRotate') {
            // Restore old image rotation
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.type === 'image') {
                obj.rotation = action.oldRotation || 0;
            }
            IWB.redoStack.push(action);
        } else if (action.type === 'imageFlip') {
            // Restore old image flip state
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.type === 'image') {
                if (action.axis === 'horizontal') {
                    obj.flipH = action.oldFlip;
                } else if (action.axis === 'vertical') {
                    obj.flipV = action.oldFlip;
                }
            }
            IWB.redoStack.push(action);
        } else if (action.type === 'imageReset') {
            // Restore old transform state
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.type === 'image' && action.oldState) {
                obj.rotation = action.oldState.rotation || 0;
                obj.flipH = action.oldState.flipH || false;
                obj.flipV = action.oldState.flipV || false;
            }
            IWB.redoStack.push(action);
        } else if (action.type === 'textFormat') {
            // Restore old text formatting
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.type === 'text' && action.property) {
                obj[action.property] = action.oldValue;
                // Update dimensions if needed
                if (typeof IWB.updateTextDimensions === 'function') {
                    IWB.updateTextDimensions(obj);
                }
            }
            IWB.redoStack.push(action);
        } else if (action.type === 'colorChange') {
            // Restore old color for stroke or text
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && (obj.type === 'stroke' || obj.type === 'text' || obj.type === 'shape')) {
                obj.color = action.oldColor;
            }
            IWB.redoStack.push(action);
        } else if (action.type === 'widthChange') {
            // Restore old width for stroke or shape
            const obj = objects.find(o => o.id === action.objectId);
            if (obj) {
                if (obj.type === 'stroke') {
                    obj.size = action.oldWidth;
                } else if (obj.type === 'shape') {
                    obj.strokeWidth = action.oldWidth;
                }
            }
            IWB.redoStack.push(action);
        } else if (action.type === 'strokeResize') {
            // Restore old stroke path
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.type === 'stroke' && action.oldPath) {
                obj.path = JSON.parse(JSON.stringify(action.oldPath));
            }
            IWB.redoStack.push(action);
        } else if (action.type === 'shapeResize') {
            // Restore old shape dimensions
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.type === 'shape' && action.oldData) {
                obj.x = action.oldData.x;
                obj.y = action.oldData.y;
                obj.w = action.oldData.w;
                obj.h = action.oldData.h;
                if (action.oldData.startX !== undefined) {
                    obj.startX = action.oldData.startX;
                    obj.startY = action.oldData.startY;
                    obj.endX = action.oldData.endX;
                    obj.endY = action.oldData.endY;
                }
            }
            IWB.redoStack.push(action);
        } else if (action.type === 'textEdit') {
            // Restore old text content
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.type === 'text') {
                obj.text = action.oldText;
                // Update dimensions for the old text
                if (typeof IWB.updateTextDimensions === 'function') {
                    IWB.updateTextDimensions(obj);
                }
            }
            IWB.redoStack.push(action);
        }
        
        // Update button states after undo
        if (typeof IWB.updateUndoRedoButtons === 'function') {
            IWB.updateUndoRedoButtons();
        }
        
        return sortIfLayered(objects);
    };

    /**
     * Redo last undone action
     */
    IWB.redo = function(objects) {
        const action = IWB.redoStack.pop();
        if (!action) return objects;
        
        if (action.type === 'add') {
            // Re-add the object
            // Reconstruct imageElement if this is an image
            if (action.object.type === 'image' && action.object.src && !action.object.imageElement) {
                const img = new Image();
                img.src = action.object.src;
                action.object.imageElement = img;
                img.onload = () => {
                    if (typeof IWB.requestRender === 'function') {
                        IWB.requestRender();
                    }
                };
            }
            objects.push(action.object);
            IWB.undoStack.push(action);
            
            // Update button states
            if (typeof IWB.updateUndoRedoButtons === 'function') {
                IWB.updateUndoRedoButtons();
            }
        } else if (action.type === 'delete') {
            // Re-delete the object
            objects = objects.filter(o => o.id !== action.object.id);
            IWB.undoStack.push(action);
        } else if (action.type === 'move') {
            // Restore new position for strokes
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.path) {
                obj.path = action.newPath;
            }
            IWB.undoStack.push(action);
        } else if (action.type === 'moveImage') {
            // Restore new position for images
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.type === 'image') {
                obj.x = action.newPos.x;
                obj.y = action.newPos.y;
            }
            IWB.undoStack.push(action);
        } else if (action.type === 'moveText') {
            // Restore new position for text
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.type === 'text') {
                obj.x = action.newPos.x;
                obj.y = action.newPos.y;
            }
            IWB.undoStack.push(action);
        } else if (action.type === 'moveShape') {
            // Restore new position for shape
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.type === 'shape') {
                obj.x = action.newPos.x;
                obj.y = action.newPos.y;
            }
            IWB.undoStack.push(action);
        } else if (action.type === 'layer') {
            // Handle layer operations (bring to front, send to back, move up/down)
            if (IWB.applyLayerRedo) {
                IWB.applyLayerRedo(action, objects);
            }
            IWB.undoStack.push(action);
        } else if (action.type === 'transform') {
            // Handle multi-select transform operations (move, rotate, mirror)
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && action.after) {
                // Apply the after geometry
                if (action.after.type === 'stroke' && obj.path) {
                    obj.path = JSON.parse(JSON.stringify(action.after.path || []));
                } else if (action.after.type === 'image') {
                    obj.x = action.after.x || 0;
                    obj.y = action.after.y || 0;
                    obj.w = action.after.w || 0;
                    obj.h = action.after.h || 0;
                    obj.rotation = action.after.rotation || 0;
                    obj.flipH = action.after.flipH || false;
                    obj.flipV = action.after.flipV || false;
                } else if (action.after.type === 'shape') {
                    obj.x = action.after.x || 0;
                    obj.y = action.after.y || 0;
                    obj.w = action.after.w || 0;
                    obj.h = action.after.h || 0;
                    obj.rotation = action.after.rotation || 0;
                    obj.flipH = action.after.flipH || false;
                    obj.flipV = action.after.flipV || false;
                    if (action.after.startX !== undefined) {
                        obj.startX = action.after.startX;
                        obj.startY = action.after.startY;
                        obj.endX = action.after.endX;
                        obj.endY = action.after.endY;
                    }
                } else if (action.after.type === 'text') {
                    obj.x = action.after.x || 0;
                    obj.y = action.after.y || 0;
                    obj.width = action.after.w || obj.width || 100;
                    obj.height = action.after.h || obj.height || 50;
                    obj.rotation = action.after.rotation || 0;
                    obj.flipH = action.after.flipH || false;
                    obj.flipV = action.after.flipV || false;
                }
            }
            IWB.undoStack.push(action);
        } else if (action.type === 'batch_delete') {
            // Re-delete all objects from batch clear
            if (Array.isArray(action.objects)) {
                const ids = action.objects.map(o => o.id);
                objects = objects.filter(o => !ids.includes(o.id));
            }
            IWB.undoStack.push(action);
        } else if (action.type === 'imageResize') {
            // Restore new image bounds
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.type === 'image' && action.newBounds) {
                obj.x = action.newBounds.x;
                obj.y = action.newBounds.y;
                obj.w = action.newBounds.w;
                obj.h = action.newBounds.h;
            }
            IWB.undoStack.push(action);
        } else if (action.type === 'imageRotate') {
            // Restore new image rotation
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.type === 'image') {
                obj.rotation = action.newRotation || 0;
            }
            IWB.undoStack.push(action);
        } else if (action.type === 'imageFlip') {
            // Restore new image flip state
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.type === 'image') {
                if (action.axis === 'horizontal') {
                    obj.flipH = action.newFlip;
                } else if (action.axis === 'vertical') {
                    obj.flipV = action.newFlip;
                }
            }
            IWB.undoStack.push(action);
        } else if (action.type === 'imageReset') {
            // Reset transform state (redo means reset again)
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.type === 'image') {
                obj.rotation = 0;
                obj.flipH = false;
                obj.flipV = false;
            }
            IWB.undoStack.push(action);
        } else if (action.type === 'textFormat') {
            // Apply new text formatting
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.type === 'text' && action.property) {
                obj[action.property] = action.newValue;
                // Update dimensions if needed
                if (typeof IWB.updateTextDimensions === 'function') {
                    IWB.updateTextDimensions(obj);
                }
            }
            IWB.undoStack.push(action);
        } else if (action.type === 'colorChange') {
            // Restore new color for stroke or text
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && (obj.type === 'stroke' || obj.type === 'text' || obj.type === 'shape')) {
                obj.color = action.newColor;
            }
            IWB.undoStack.push(action);
        } else if (action.type === 'widthChange') {
            // Restore new width for stroke or shape
            const obj = objects.find(o => o.id === action.objectId);
            if (obj) {
                if (obj.type === 'stroke') {
                    obj.size = action.newWidth;
                } else if (obj.type === 'shape') {
                    obj.strokeWidth = action.newWidth;
                }
            }
            IWB.undoStack.push(action);
        } else if (action.type === 'strokeResize') {
            // Restore new stroke path
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.type === 'stroke' && action.newPath) {
                obj.path = JSON.parse(JSON.stringify(action.newPath));
            }
            IWB.undoStack.push(action);
        } else if (action.type === 'shapeResize') {
            // Restore new shape dimensions
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.type === 'shape' && action.newData) {
                obj.x = action.newData.x;
                obj.y = action.newData.y;
                obj.w = action.newData.w;
                obj.h = action.newData.h;
                if (action.newData.startX !== undefined) {
                    obj.startX = action.newData.startX;
                    obj.startY = action.newData.startY;
                    obj.endX = action.newData.endX;
                    obj.endY = action.newData.endY;
                }
            }
            IWB.undoStack.push(action);
        } else if (action.type === 'textEdit') {
            // Restore new text content
            const obj = objects.find(o => o.id === action.objectId);
            if (obj && obj.type === 'text') {
                obj.text = action.newText;
                // Update dimensions for the new text
                if (typeof IWB.updateTextDimensions === 'function') {
                    IWB.updateTextDimensions(obj);
                }
            }
            IWB.undoStack.push(action);
        }
        
        // Update button states after redo
        if (typeof IWB.updateUndoRedoButtons === 'function') {
            IWB.updateUndoRedoButtons();
        }
        
        return sortIfLayered(objects);
    };

    /**
     * Clear all objects
     */
    IWB.clearAll = function(objects) {
        if (objects.length === 0) return objects;
        
        if (confirm('Clear all objects?')) {
            // Save all objects to undo stack as batch delete
            const deleteAction = {
                type: 'batch_delete',
                objects: [...objects]
            };
            IWB.undoStack.push(deleteAction);
            IWB.redoStack = [];
            return [];
        }
        
        return objects;
    };

    /**
     * Get undo/redo stack sizes (for UI feedback)
     */
    IWB.getUndoRedoState = function() {
        return {
            canUndo: IWB.undoStack.length > 0,
            canRedo: IWB.redoStack.length > 0,
            undoCount: IWB.undoStack.length,
            redoCount: IWB.redoStack.length
        };
    };

    /**
     * Update undo/redo button states in the UI
     */
    IWB.updateUndoRedoButtons = function() {
        const state = IWB.getUndoRedoState();
        
        // Find undo/redo buttons by their onclick attributes
        const undoBtn = Array.from(document.querySelectorAll('.tool-btn')).find(
            btn => btn.getAttribute('onclick') === 'undo()'
        );
        const redoBtn = Array.from(document.querySelectorAll('.tool-btn')).find(
            btn => btn.getAttribute('onclick') === 'redo()'
        );
        
        if (undoBtn) {
            undoBtn.disabled = !state.canUndo;
            undoBtn.style.opacity = state.canUndo ? '1' : '0.4';
            undoBtn.style.cursor = state.canUndo ? 'pointer' : 'not-allowed';
            undoBtn.title = state.canUndo 
                ? `Undo (Ctrl+Z) - ${state.undoCount} action${state.undoCount !== 1 ? 's' : ''} available`
                : 'Undo (Ctrl+Z) - No actions to undo';
        }
        
        if (redoBtn) {
            redoBtn.disabled = !state.canRedo;
            redoBtn.style.opacity = state.canRedo ? '1' : '0.4';
            redoBtn.style.cursor = state.canRedo ? 'pointer' : 'not-allowed';
            redoBtn.title = state.canRedo 
                ? `Redo (Ctrl+Y) - ${state.redoCount} action${state.redoCount !== 1 ? 's' : ''} available`
                : 'Redo (Ctrl+Y) - No actions to redo';
        }
    };

    /**
     * Initialize keyboard shortcuts for undo/redo
     */
    IWB.initUndoRedoShortcuts = function(onUndo, onRedo) {
        document.addEventListener('keydown', (e) => {
            if (IWB.shouldIgnoreHotkeys && IWB.shouldIgnoreHotkeys(e)) return;

            // Undo (Ctrl+Z)
            if (e.ctrlKey && e.key === 'z' && !e.shiftKey) {
                e.preventDefault();
                if (onUndo) onUndo();
            }
            // Redo (Ctrl+Y)
            if (e.ctrlKey && e.key === 'y') {
                e.preventDefault();
                if (onRedo) onRedo();
            }
        });
    };

    console.log('Infinite Whiteboard Undo module loaded');

})(window);
