/**
 * Infinite Whiteboard Minimap Module
 * Handles minimap rendering and viewport indicator
 */

(function(window) {
    'use strict';

    window.InfiniteWhiteboard = window.InfiniteWhiteboard || {};
    const IWB = window.InfiniteWhiteboard;

    // Minimap drag state
    let minimapDragging = false;
    let minimapDragStart = null;

    /**
     * Update minimap with current objects and viewport
     */
    IWB.updateMinimap = function(minimapCanvas, minimapCtx, canvas, objects, color) {
        const VIRTUAL_WIDTH = IWB.VIRTUAL_WIDTH || 10000;
        const scale = 200 / VIRTUAL_WIDTH;
        
        // Clear minimap
        minimapCtx.fillStyle = 'rgba(10, 10, 11, 0.8)';
        minimapCtx.fillRect(0, 0, 200, 150);
        
        // Draw objects on minimap
        minimapCtx.save();
        minimapCtx.scale(scale, scale * (150 / 200)); // Adjust for aspect ratio
        
        objects.forEach(obj => {
            if (obj.type === 'stroke' && obj.path) {
                minimapCtx.strokeStyle = obj.color || color;
                minimapCtx.lineWidth = 2;
                minimapCtx.beginPath();
                const path = obj.path;
                if (path.length > 0) {
                    minimapCtx.moveTo(path[0].x, path[0].y);
                    for (let i = 1; i < path.length; i++) {
                        minimapCtx.lineTo(path[i].x, path[i].y);
                    }
                }
                minimapCtx.stroke();
            }
        });
        
        minimapCtx.restore();
        
        // Draw viewport indicator
        const viewportIndicator = document.getElementById('viewport-indicator');
        if (viewportIndicator) {
            const viewportWidth = (canvas.width / IWB.zoom) * scale;
            const viewportHeight = (canvas.height / IWB.zoom) * scale * (150 / 200);
            const viewportLeft = (IWB.viewportX / IWB.zoom) * scale;
            const viewportTop = (IWB.viewportY / IWB.zoom) * scale * (150 / 200);
            
            viewportIndicator.style.left = viewportLeft + 'px';
            viewportIndicator.style.top = viewportTop + 'px';
            viewportIndicator.style.width = viewportWidth + 'px';
            viewportIndicator.style.height = viewportHeight + 'px';
        }
    };

    /**
     * Initialize minimap drag handlers
     */
    IWB.initMinimapDrag = function(canvas) {
        const viewportIndicator = document.getElementById('viewport-indicator');
        const minimapElement = document.getElementById('minimap');
        
        if (!viewportIndicator || !minimapElement) return;

        // Mouse down on viewport indicator
        viewportIndicator.addEventListener('mousedown', (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            minimapDragging = true;
            viewportIndicator.classList.add('dragging');
            
            // Get mouse position relative to minimap
            const rect = minimapElement.getBoundingClientRect();
            minimapDragStart = {
                x: e.clientX - rect.left,
                y: e.clientY - rect.top
            };
            
            console.log('[MINIMAP] Started dragging viewport indicator');
        });

        // Mouse move - update viewport position
        document.addEventListener('mousemove', (e) => {
            if (!minimapDragging) return;
            
            const rect = minimapElement.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            
            // Calculate scale factors
            const VIRTUAL_WIDTH = IWB.VIRTUAL_WIDTH || 10000;
            const minimapScale = 200 / VIRTUAL_WIDTH;
            const aspectScale = 150 / 200;
            
            // Calculate viewport dimensions in minimap space
            const viewportWidth = (canvas.width / IWB.zoom) * minimapScale;
            const viewportHeight = (canvas.height / IWB.zoom) * minimapScale * aspectScale;
            
            // Calculate new viewport position (centered on mouse)
            let newViewportLeft = mouseX - viewportWidth / 2;
            let newViewportTop = mouseY - viewportHeight / 2;
            
            // Clamp to minimap bounds
            newViewportLeft = Math.max(0, Math.min(200 - viewportWidth, newViewportLeft));
            newViewportTop = Math.max(0, Math.min(150 - viewportHeight, newViewportTop));
            
            // Convert minimap coordinates back to world coordinates
            IWB.viewportX = (newViewportLeft / minimapScale) * IWB.zoom;
            IWB.viewportY = (newViewportTop / (minimapScale * aspectScale)) * IWB.zoom;
            
            // Request render to update canvas
            if (typeof IWB.requestRender === 'function') {
                IWB.requestRender();
            }
        });

        // Mouse up - end dragging
        document.addEventListener('mouseup', () => {
            if (minimapDragging) {
                minimapDragging = false;
                viewportIndicator.classList.remove('dragging');
                minimapDragStart = null;
                console.log('[MINIMAP] Finished dragging viewport indicator');
            }
        });
    };

    console.log('Infinite Whiteboard Minimap module loaded');

})(window);
