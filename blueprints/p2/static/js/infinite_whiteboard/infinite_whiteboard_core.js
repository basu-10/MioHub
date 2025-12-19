/**
 * Infinite Whiteboard Core Module
 * Handles viewport, zoom, pan, grid, and coordinate transformations
 */

(function(window) {
    'use strict';

    // Viewport state
    window.InfiniteWhiteboard = window.InfiniteWhiteboard || {};
    const IWB = window.InfiniteWhiteboard;

    // Core state
    IWB.viewportX = 0;
    IWB.viewportY = 0;
    IWB.zoom = 1.0;
    IWB.MIN_ZOOM = 0.1;
    IWB.MAX_ZOOM = 5.0;
    IWB.VIRTUAL_WIDTH = 10000;
    IWB.VIRTUAL_HEIGHT = 10000;

    // Pan state
    IWB.isPanning = false;
    IWB.panStart = null;
    IWB.spacePressed = false;

    // Prevent canvas hotkeys from firing while typing in form fields
    IWB.shouldIgnoreHotkeys = function(event) {
        const target = event && event.target ? event.target : document.activeElement;
        if (!target) return false;

        const tag = target.tagName;
        const type = (target.type || '').toLowerCase();
        const textLikeInput = tag === 'INPUT' && ['text', 'search', 'email', 'url', 'tel', 'number', 'password'].includes(type);
        const genericInput = tag === 'TEXTAREA' || tag === 'SELECT' || tag === 'BUTTON';
        const isEditable = target.isContentEditable || !!(target.closest && target.closest('[contenteditable="true"]'));

        // Allow opting-in to hotkeys with data-allow-hotkeys="true"
        const allowsHotkeys = target.dataset && target.dataset.allowHotkeys === 'true';

        return !allowsHotkeys && (textLikeInput || genericInput || isEditable);
    };

    /**
     * Apply viewport transformation to canvas context
     */
    IWB.applyTransform = function(ctx) {
        ctx.save();
        ctx.translate(-IWB.viewportX, -IWB.viewportY);
        ctx.scale(IWB.zoom, IWB.zoom);
    };

    /**
     * Reset viewport transformation
     */
    IWB.resetTransform = function(ctx) {
        ctx.restore();
    };

    /**
     * Convert screen coordinates to world coordinates
     */
    IWB.screenToWorld = function(screenX, screenY) {
        return {
            x: (screenX + IWB.viewportX) / IWB.zoom,
            y: (screenY + IWB.viewportY) / IWB.zoom
        };
    };

    /**
     * Convert world coordinates to screen coordinates
     */
    IWB.worldToScreen = function(worldX, worldY) {
        return {
            x: worldX * IWB.zoom - IWB.viewportX,
            y: worldY * IWB.zoom - IWB.viewportY
        };
    };

    /**
     * Draw grid on canvas
     */
    IWB.drawGrid = function(ctx, canvas) {
        const gridSize = 50;
        const startX = Math.floor(IWB.viewportX / IWB.zoom / gridSize) * gridSize;
        const startY = Math.floor(IWB.viewportY / IWB.zoom / gridSize) * gridSize;
        const endX = startX + (canvas.width / IWB.zoom) + gridSize;
        const endY = startY + (canvas.height / IWB.zoom) + gridSize;
        
        ctx.strokeStyle = 'rgba(20, 184, 166, 0.1)';
        ctx.lineWidth = 1 / IWB.zoom;
        
        ctx.beginPath();
        for (let x = startX; x < endX; x += gridSize) {
            ctx.moveTo(x, startY);
            ctx.lineTo(x, endY);
        }
        for (let y = startY; y < endY; y += gridSize) {
            ctx.moveTo(startX, y);
            ctx.lineTo(endX, y);
        }
        ctx.stroke();
    };

    /**
     * Zoom at a specific screen point
     */
    IWB.zoomAt = function(screenX, screenY, factor) {
        const worldPos = IWB.screenToWorld(screenX, screenY);
        
        const newZoom = Math.max(IWB.MIN_ZOOM, Math.min(IWB.MAX_ZOOM, IWB.zoom * factor));
        
        // Adjust viewport to keep world position under cursor
        IWB.viewportX = worldPos.x * newZoom - screenX;
        IWB.viewportY = worldPos.y * newZoom - screenY;
        
        IWB.zoom = newZoom;
    };

    /**
     * Zoom in at canvas center
     */
    IWB.zoomIn = function(canvas) {
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        IWB.zoomAt(centerX, centerY, 1.2);
    };

    /**
     * Zoom out at canvas center
     */
    IWB.zoomOut = function(canvas) {
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        IWB.zoomAt(centerX, centerY, 0.8);
    };

    /**
     * Zoom to fit all objects in the viewport
     */
    IWB.zoomAll = function(canvas, objects) {
        if (!objects || objects.length === 0) {
            // No objects - reset to default view
            IWB.zoom = 1.0;
            IWB.viewportX = 0;
            IWB.viewportY = 0;
            return;
        }

        // Calculate bounding box of all objects
        let minX = Infinity, minY = Infinity;
        let maxX = -Infinity, maxY = -Infinity;

        objects.forEach(obj => {
            if (obj.type === 'stroke' && obj.path && obj.path.length > 0) {
                obj.path.forEach(pt => {
                    minX = Math.min(minX, pt.x);
                    minY = Math.min(minY, pt.y);
                    maxX = Math.max(maxX, pt.x);
                    maxY = Math.max(maxY, pt.y);
                });
            } else if (obj.type === 'image') {
                const x = obj.x || 0;
                const y = obj.y || 0;
                const w = obj.w || 0;
                const h = obj.h || 0;
                minX = Math.min(minX, x);
                minY = Math.min(minY, y);
                maxX = Math.max(maxX, x + w);
                maxY = Math.max(maxY, y + h);
            } else if (obj.type === 'text') {
                const x = obj.x || 0;
                const y = obj.y || 0;
                const w = obj.width || 200;
                const h = obj.height || 50;
                minX = Math.min(minX, x);
                minY = Math.min(minY, y);
                maxX = Math.max(maxX, x + w);
                maxY = Math.max(maxY, y + h);
            } else if (obj.type === 'shape') {
                const x = obj.x || 0;
                const y = obj.y || 0;
                const w = obj.w || 0;
                const h = obj.h || 0;
                minX = Math.min(minX, x);
                minY = Math.min(minY, y);
                maxX = Math.max(maxX, x + w);
                maxY = Math.max(maxY, y + h);
            }
        });

        // Add padding around content (10% of viewport size)
        const padding = Math.min(canvas.width, canvas.height) * 0.1;
        const contentWidth = maxX - minX;
        const contentHeight = maxY - minY;

        if (contentWidth <= 0 || contentHeight <= 0) {
            // Invalid bounds - reset to default
            IWB.zoom = 1.0;
            IWB.viewportX = 0;
            IWB.viewportY = 0;
            return;
        }

        // Calculate zoom to fit content in viewport
        const zoomX = (canvas.width - padding * 2) / contentWidth;
        const zoomY = (canvas.height - padding * 2) / contentHeight;
        const targetZoom = Math.min(zoomX, zoomY);

        // Clamp zoom to allowed range
        IWB.zoom = Math.max(IWB.MIN_ZOOM, Math.min(IWB.MAX_ZOOM, targetZoom));

        // Center content in viewport
        const contentCenterX = (minX + maxX) / 2;
        const contentCenterY = (minY + maxY) / 2;
        IWB.viewportX = contentCenterX * IWB.zoom - canvas.width / 2;
        IWB.viewportY = contentCenterY * IWB.zoom - canvas.height / 2;
    };

    /**
     * Start panning
     */
    IWB.startPan = function(clientX, clientY, canvas) {
        IWB.isPanning = true;
        IWB.panStart = { x: clientX, y: clientY };
        canvas.style.cursor = 'grabbing';
    };

    /**
     * Update pan position
     */
    IWB.updatePan = function(clientX, clientY) {
        if (!IWB.isPanning || !IWB.panStart) return false;
        
        const dx = clientX - IWB.panStart.x;
        const dy = clientY - IWB.panStart.y;
        IWB.viewportX -= dx;
        IWB.viewportY -= dy;
        IWB.panStart = { x: clientX, y: clientY };
        
        return true;
    };

    /**
     * End panning
     */
    IWB.endPan = function(canvas, currentTool) {
        IWB.isPanning = false;
        IWB.panStart = null;
        canvas.style.cursor = IWB.spacePressed || currentTool === 'pan' ? 'grab' : 'crosshair';
    };

    /**
     * Update status bar with current position and zoom
     */
    IWB.updateStatus = function(canvas, objectCount, selectedObject, allObjects) {
        const centerWorld = IWB.screenToWorld(canvas.width / 2, canvas.height / 2);
        const zoomPercent = Math.round(IWB.zoom * 100);
        const statusbar = document.getElementById('statusbar');
        
        if (statusbar) {
            let statusText = `Infinite Whiteboard - ${objectCount} objects | ` +
                           `Pan: Space + Drag or Mouse Wheel | Zoom: Ctrl + Wheel | ` +
                           `Position: (${Math.round(centerWorld.x)}, ${Math.round(centerWorld.y)}) | ` +
                           `Zoom: ${zoomPercent}%`;
            
            // If object is selected, append layer information
            if (selectedObject) {
                const getLayerValue = (obj) => Number.isFinite(obj?.layer) ? obj.layer : 0;
                const layerLabel = getLayerValue(selectedObject);
                
                statusText += ` | Selected: ${selectedObject.type} #${selectedObject.id} - Layer ${layerLabel}`;
            }
            
            statusbar.textContent = statusText;
        }
    };

    console.log('Infinite Whiteboard Core module loaded');

})(window);
