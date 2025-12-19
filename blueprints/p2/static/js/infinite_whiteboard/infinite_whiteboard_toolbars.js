// ============================================================================
// INFINITE WHITEBOARD - CONTEXT-SENSITIVE TOOLBARS MODULE
// ============================================================================
// Manages dynamic toolbar visibility based on selection type:
// - Image Toolbar: Flip, rotate, duplicate, delete + layer manipulation
// - Stroke Toolbar: Stroke options, duplicate, delete + layer manipulation
// - Shape Toolbar: Shape options, duplicate, delete + layer manipulation
// - Multi-Selection Toolbar: Common operations + layer manipulation
// ============================================================================

(function() {
    'use strict';

    const Toolbars = {
        // Toolbar element references (set after DOM loads)
        imageToolbar: null,
        strokeToolbar: null,
        shapeToolbar: null,
        multiSelectionToolbar: null,
        textToolbar: null,
        
        // Initialize toolbar references
        init: function() {
            this.imageToolbar = document.getElementById('image-toolbar');
            this.strokeToolbar = document.getElementById('stroke-toolbar');
            this.shapeToolbar = document.getElementById('shape-toolbar');
            this.multiSelectionToolbar = document.getElementById('multi-selection-toolbar');
            this.textToolbar = document.getElementById('text-toolbar');
            
            console.log('[TOOLBARS] Initialized context-sensitive toolbars');
        },
        
        // Hide all context toolbars
        hideAll: function() {
            if (this.imageToolbar) this.imageToolbar.classList.remove('visible');
            if (this.strokeToolbar) this.strokeToolbar.classList.remove('visible');
            if (this.shapeToolbar) this.shapeToolbar.classList.remove('visible');
            if (this.multiSelectionToolbar) this.multiSelectionToolbar.classList.remove('visible');
            if (this.textToolbar) this.textToolbar.classList.remove('visible');
        },
        
        // Show image toolbar (single image selected)
        showImageToolbar: function() {
            this.hideAll();
            if (this.imageToolbar) {
                this.imageToolbar.classList.add('visible');
                console.log('[TOOLBARS] Showing image toolbar');
            }
        },
        
        // Show stroke toolbar (single or multiple strokes selected)
        showStrokeToolbar: function() {
            this.hideAll();
            if (this.strokeToolbar) {
                this.strokeToolbar.classList.add('visible');
                console.log('[TOOLBARS] Showing stroke toolbar');
            }
        },
        
        // Show shape toolbar (single or multiple shapes selected)
        showShapeToolbar: function() {
            this.hideAll();
            if (this.shapeToolbar) {
                this.shapeToolbar.classList.add('visible');
                console.log('[TOOLBARS] Showing shape toolbar');
            }
        },
        
        // Show multi-selection toolbar (mixed selection)
        showMultiSelectionToolbar: function() {
            this.hideAll();
            if (this.multiSelectionToolbar) {
                this.multiSelectionToolbar.classList.add('visible');
                console.log('[TOOLBARS] Showing multi-selection toolbar');
            }
        },
        
        // Show text toolbar (text tool active or text object selected)
        showTextToolbar: function() {
            this.hideAll();
            if (this.textToolbar) {
                this.textToolbar.classList.add('visible');
                console.log('[TOOLBARS] Showing text toolbar');
                // Update toolbar state to reflect current text properties
                if (typeof window.updateTextToolbarState === 'function') {
                    window.updateTextToolbarState();
                }
            }
        },
        
        // Update toolbar visibility based on current selection
        updateForSelection: function(selectedObject, selectionCount, selectedObjects) {
            console.log('[TOOLBARS] Updating for selection:', {
                count: selectionCount,
                primaryType: selectedObject?.type
            });
            
            // No selection - hide all
            if (selectionCount === 0) {
                this.hideAll();
                return;
            }
            
            // Single selection
            if (selectionCount === 1 && selectedObject) {
                if (selectedObject.type === 'image') {
                    this.showImageToolbar();
                } else if (selectedObject.type === 'stroke') {
                    this.showStrokeToolbar();
                } else if (selectedObject.type === 'shape') {
                    this.showShapeToolbar();
                } else if (selectedObject.type === 'text') {
                    this.showTextToolbar();
                }
                return;
            }
            
            // Multiple selection
            if (selectionCount > 1 && selectedObjects) {
                // Check if all selected objects are of the same type
                const types = new Set(selectedObjects.map(obj => obj.type));
                
                if (types.size === 1) {
                    // All same type
                    const type = types.values().next().value;
                    if (type === 'stroke') {
                        this.showStrokeToolbar();
                    } else if (type === 'shape') {
                        this.showShapeToolbar();
                    } else if (type === 'image') {
                        // Multiple images - show multi-selection toolbar (no flip/rotate for multiple)
                        this.showMultiSelectionToolbar();
                    }
                } else {
                    // Mixed types - show multi-selection toolbar
                    this.showMultiSelectionToolbar();
                }
                return;
            }
            
            // Fallback - hide all
            this.hideAll();
        }
    };
    
    // Export to global namespace
    if (!window.InfiniteWhiteboard) {
        window.InfiniteWhiteboard = {};
    }
    window.InfiniteWhiteboard.Toolbars = Toolbars;
    
    console.log('[MODULE] Infinite Whiteboard Toolbars module loaded');
})();
