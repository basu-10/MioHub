/**
 * Infinite Whiteboard Tools Module
 * Handles tool management, toolbar state, and tool switching
 */

(function(window) {
    'use strict';

    window.InfiniteWhiteboard = window.InfiniteWhiteboard || {};
    const IWB = window.InfiniteWhiteboard;

    // Tool state
    IWB.currentTool = 'pen';
    IWB.color = '#14b8a6';
    IWB.size = 3;

    /**
     * Set active tool
     */
    IWB.setTool = function(tool, canvas) {
        IWB.currentTool = tool;
        
        // Update toolbar button states
        document.querySelectorAll('.tool-btn[data-tool]').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tool === tool);
        });
        
        // Show text toolbar when text tool is selected
        if (tool === 'text' && IWB.Toolbars && typeof IWB.Toolbars.showTextToolbar === 'function') {
            IWB.Toolbars.showTextToolbar();
        } else if (tool !== 'text' && IWB.Toolbars && typeof IWB.Toolbars.hideAll === 'function') {
            // Hide toolbars when switching away from text tool (unless something is selected)
            const hasSelection = typeof window.getSelectionCount === 'function' && window.getSelectionCount() > 0;
            if (!hasSelection) {
                IWB.Toolbars.hideAll();
            }
        }
        
        // Update cursor
        if (tool === 'pan') {
            canvas.style.cursor = 'grab';
        } else if (tool === 'select' || tool === 'rect-select') {
            canvas.style.cursor = 'default';
        } else if (tool === 'eraser') {
            canvas.style.cursor = 'crosshair';
        } else if (tool === 'text') {
            canvas.style.cursor = 'text';
        } else {
            canvas.style.cursor = 'crosshair';
        }
    };

    /**
     * Set color
     */
    IWB.setColor = function(newColor) {
        IWB.color = newColor;
        const colorPicker = document.getElementById('color-picker');
        if (colorPicker) {
            colorPicker.value = newColor;
        }
        
        // Update text color if currently editing text
        if (typeof IWB.updateTextColorFromToolbar === 'function') {
            IWB.updateTextColorFromToolbar(newColor);
        }
    };

    /**
     * Set size
     */
    IWB.setSize = function(newSize) {
        IWB.size = newSize;
        const sizeSlider = document.getElementById('size-slider');
        const sizeDisplay = document.getElementById('size-display');
        if (sizeSlider) {
            sizeSlider.value = newSize;
        }
        if (sizeDisplay) {
            sizeDisplay.textContent = newSize + 'px';
        }
    };

    /**
     * Initialize toolbar event listeners
     */
    IWB.initToolbar = function(canvas, onToolChange) {
        // Tool buttons
        document.querySelectorAll('.tool-btn[data-tool]').forEach(btn => {
            btn.addEventListener('click', () => {
                IWB.setTool(btn.dataset.tool, canvas);
                if (onToolChange) onToolChange();
            });
        });

        // Color picker - use 'input' event for real-time updates as user drags through colors
        const colorPicker = document.getElementById('color-picker');
        if (colorPicker) {
            const handleColorChange = (e) => {
                IWB.setColor(e.target.value);
                
                // Apply color change to selected object(s) if in select mode
                if (IWB.currentTool === 'select' && typeof window.applyColorToSelection === 'function') {
                    window.applyColorToSelection(e.target.value);
                }
                
                if (onToolChange) onToolChange();
            };
            
            // 'input' event fires in real-time as user drags through color picker
            colorPicker.addEventListener('input', handleColorChange);
            
            // 'change' event fires when user closes color picker (for browsers that don't support 'input' on color pickers)
            colorPicker.addEventListener('change', handleColorChange);
        }

        // Size slider
        const sizeSlider = document.getElementById('size-slider');
        const sizeDisplay = document.getElementById('size-display');
        if (sizeSlider) {
            sizeSlider.addEventListener('input', (e) => {
                const newSize = parseInt(e.target.value);
                IWB.setSize(newSize);
                
                // Apply width change to selected stroke(s) if in select mode
                if (IWB.currentTool === 'select' && typeof window.applyWidthToSelection === 'function') {
                    window.applyWidthToSelection(newSize);
                }
                
                if (onToolChange) onToolChange();
            });
        }
    };

    /**
     * Check if current tool is a drawing tool
     */
    IWB.isDrawingTool = function() {
        return ['pen', 'marker', 'highlighter', 'eraser'].includes(IWB.currentTool);
    };

    /**
     * Check if space key should enable pan mode
     */
    IWB.shouldPan = function() {
        return IWB.spacePressed || IWB.currentTool === 'pan';
    };

    console.log('Infinite Whiteboard Tools module loaded');

})(window);
