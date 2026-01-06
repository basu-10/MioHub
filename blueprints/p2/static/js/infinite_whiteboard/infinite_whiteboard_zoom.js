/**
 * Infinite Whiteboard Zoom Controls Module
 * Handles zoom button interactions and keyboard shortcuts
 */

(function(window) {
    'use strict';

    window.InfiniteWhiteboard = window.InfiniteWhiteboard || {};
    const IWB = window.InfiniteWhiteboard;

    // Zoom window state
    let isZoomWindowMode = false;
    let zoomWindowStart = null;
    let zoomWindowOverlay = null;
    let storedCanvas = null;

    /**
     * Initialize zoom controls
     */
    IWB.initZoomControls = function(canvas, renderCallback, getObjectsCallback) {
        if (!canvas || typeof renderCallback !== 'function') {
            console.error('[ZOOM] Canvas or render callback not provided');
            return;
        }

        console.log('[ZOOM] Initializing zoom controls');

        // Store callbacks for internal use
        IWB._zoomRenderCallback = renderCallback;
        IWB._getObjectsCallback = getObjectsCallback || function() { return window.objects || []; };
        storedCanvas = canvas;

        // Bind zoom button click handlers by ID
        const zoomInBtn = document.getElementById('zoom-in-btn');
        const zoomOutBtn = document.getElementById('zoom-out-btn');
        const zoomAllBtn = document.getElementById('zoom-all-btn');
        const zoomWindowBtn = document.getElementById('zoom-window-btn');
        const zoomResetBtn = document.getElementById('zoom-reset-btn');

        if (zoomInBtn) {
            zoomInBtn.onclick = function(e) {
                e.preventDefault();
                IWB.handleZoomIn(canvas);
            };
            console.log('[ZOOM] Zoom In button bound');
        } else {
            console.warn('[ZOOM] Zoom In button not found');
        }

        if (zoomOutBtn) {
            zoomOutBtn.onclick = function(e) {
                e.preventDefault();
                IWB.handleZoomOut(canvas);
            };
            console.log('[ZOOM] Zoom Out button bound');
        } else {
            console.warn('[ZOOM] Zoom Out button not found');
        }

        if (zoomAllBtn) {
            zoomAllBtn.onclick = function(e) {
                e.preventDefault();
                IWB.handleZoomAll(canvas);
            };
            console.log('[ZOOM] Zoom All button bound');
        } else {
            console.warn('[ZOOM] Zoom All button not found');
        }

        if (zoomWindowBtn) {
            zoomWindowBtn.onclick = function(e) {
                e.preventDefault();
                IWB.toggleZoomWindowMode();
            };
            console.log('[ZOOM] Zoom Window button bound');
        } else {
            console.warn('[ZOOM] Zoom Window button not found');
        }

        if (zoomResetBtn) {
            zoomResetBtn.onclick = function(e) {
                e.preventDefault();
                IWB.setZoomPercentage(100, canvas);
            };
            console.log('[ZOOM] Zoom 100% button bound');
        } else {
            console.warn('[ZOOM] Zoom 100% button not found');
        }

        // Initialize keyboard shortcuts
        IWB.initZoomKeyboardShortcuts(canvas);
    };

    /**
     * Handle zoom in button click
     */
    IWB.handleZoomIn = function(canvas) {
        if (!canvas) return;
        
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        IWB.zoomAt(centerX, centerY, 1.2);
        
        if (IWB._zoomRenderCallback) {
            IWB._zoomRenderCallback();
        }
        
        console.log('[ZOOM] Zoomed in to', Math.round(IWB.zoom * 100) + '%');
    };

    /**
     * Handle zoom out button click
     */
    IWB.handleZoomOut = function(canvas) {
        if (!canvas) return;
        
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        IWB.zoomAt(centerX, centerY, 0.8);
        
        if (IWB._zoomRenderCallback) {
            IWB._zoomRenderCallback();
        }
        
        console.log('[ZOOM] Zoomed out to', Math.round(IWB.zoom * 100) + '%');
    };

    /**
     * Handle zoom all button click
     */
    IWB.handleZoomAll = function(canvas) {
        if (!canvas) return;
        
        // Get objects using the callback function
        const objects = IWB._getObjectsCallback ? IWB._getObjectsCallback() : (window.objects || []);
        
        console.log('[ZOOM] Zooming to fit', objects.length, 'objects');
        
        IWB.zoomAll(canvas, objects);
        
        if (IWB._zoomRenderCallback) {
            IWB._zoomRenderCallback();
        }
        
        console.log('[ZOOM] Zoomed to fit all objects at', Math.round(IWB.zoom * 100) + '%');
    };

    /**
     * Initialize keyboard shortcuts for zoom
     */
    IWB.initZoomKeyboardShortcuts = function(canvas) {
        document.addEventListener('keydown', function(e) {
            if (IWB.shouldIgnoreHotkeys && IWB.shouldIgnoreHotkeys(e)) return;

            // Plus/Equals key (with or without Ctrl) - Zoom In
            if ((e.key === '+' || e.key === '=') && !e.shiftKey) {
                e.preventDefault();
                IWB.handleZoomIn(canvas);
            }
            
            // Minus key (with or without Ctrl) - Zoom Out
            if (e.key === '-' && !e.shiftKey) {
                e.preventDefault();
                IWB.handleZoomOut(canvas);
            }
            
            // 0 key (with or without Ctrl) - Zoom All
            if (e.key === '0' && !e.shiftKey) {
                e.preventDefault();
                IWB.handleZoomAll(canvas);
            }
            
            // W key - Zoom Window
            if ((e.key === 'w' || e.key === 'W') && !e.ctrlKey && !e.shiftKey && !e.altKey && !e.metaKey) {
                e.preventDefault();
                IWB.toggleZoomWindowMode();
            }
            
            // Escape key - Cancel zoom window mode
            if (e.key === 'Escape' && isZoomWindowMode) {
                e.preventDefault();
                IWB.cancelZoomWindow();
            }
        });

        console.log('[ZOOM] Keyboard shortcuts initialized: +/= (zoom in), - (zoom out), 0 (zoom all), W (zoom window)');
    };

    /**
     * Toggle zoom window mode
     */
    IWB.toggleZoomWindowMode = function() {
        isZoomWindowMode = !isZoomWindowMode;
        
        const zoomWindowBtn = document.getElementById('zoom-window-btn');
        if (zoomWindowBtn) {
            if (isZoomWindowMode) {
                zoomWindowBtn.classList.add('active');
                console.log('[ZOOM] Zoom Window mode activated - draw a rectangle');
            } else {
                zoomWindowBtn.classList.remove('active');
                console.log('[ZOOM] Zoom Window mode deactivated');
            }
        }
        
        if (!isZoomWindowMode) {
            IWB.cancelZoomWindow();
        }
    };

    /**
     * Cancel zoom window mode
     */
    IWB.cancelZoomWindow = function() {
        isZoomWindowMode = false;
        zoomWindowStart = null;
        
        const zoomWindowBtn = document.getElementById('zoom-window-btn');
        if (zoomWindowBtn) {
            zoomWindowBtn.classList.remove('active');
        }
        
        if (zoomWindowOverlay && zoomWindowOverlay.parentNode) {
            zoomWindowOverlay.parentNode.removeChild(zoomWindowOverlay);
            zoomWindowOverlay = null;
        }
        
        console.log('[ZOOM] Zoom Window cancelled');
    };

    /**
     * Start drawing zoom window rectangle
     */
    IWB.startZoomWindow = function(screenX, screenY) {
        if (!isZoomWindowMode) return false;
        
        const worldPos = IWB.screenToWorld(screenX, screenY);
        zoomWindowStart = { 
            screenX: screenX, 
            screenY: screenY,
            worldX: worldPos.x, 
            worldY: worldPos.y 
        };
        
        // Create overlay element
        if (!zoomWindowOverlay) {
            zoomWindowOverlay = document.createElement('div');
            zoomWindowOverlay.style.position = 'fixed';
            zoomWindowOverlay.style.border = '2px solid #14b8a6';
            zoomWindowOverlay.style.background = 'rgba(20, 184, 166, 0.15)';
            zoomWindowOverlay.style.pointerEvents = 'none';
            zoomWindowOverlay.style.zIndex = '998';
            zoomWindowOverlay.style.boxShadow = '0 0 12px rgba(20, 184, 166, 0.5)';
            document.body.appendChild(zoomWindowOverlay);
        }
        
        zoomWindowOverlay.style.display = 'block';
        zoomWindowOverlay.style.left = screenX + 'px';
        zoomWindowOverlay.style.top = screenY + 'px';
        zoomWindowOverlay.style.width = '0px';
        zoomWindowOverlay.style.height = '0px';
        
        return true;
    };

    /**
     * Update zoom window rectangle during drag
     */
    IWB.updateZoomWindow = function(screenX, screenY) {
        if (!isZoomWindowMode || !zoomWindowStart || !zoomWindowOverlay) return false;
        
        const left = Math.min(screenX, zoomWindowStart.screenX);
        const top = Math.min(screenY, zoomWindowStart.screenY);
        const width = Math.abs(screenX - zoomWindowStart.screenX);
        const height = Math.abs(screenY - zoomWindowStart.screenY);
        
        zoomWindowOverlay.style.left = left + 'px';
        zoomWindowOverlay.style.top = top + 'px';
        zoomWindowOverlay.style.width = width + 'px';
        zoomWindowOverlay.style.height = height + 'px';
        
        return true;
    };

    /**
     * Complete zoom window and zoom to the selected area
     */
    IWB.completeZoomWindow = function(screenX, screenY) {
        if (!isZoomWindowMode || !zoomWindowStart || !storedCanvas) return false;
        
        // Calculate world coordinates for the rectangle
        const worldEnd = IWB.screenToWorld(screenX, screenY);
        
        const worldLeft = Math.min(zoomWindowStart.worldX, worldEnd.x);
        const worldTop = Math.min(zoomWindowStart.worldY, worldEnd.y);
        const worldWidth = Math.abs(worldEnd.x - zoomWindowStart.worldX);
        const worldHeight = Math.abs(worldEnd.y - zoomWindowStart.worldY);
        
        // Ignore very small rectangles (likely accidental clicks)
        if (worldWidth < 10 || worldHeight < 10) {
            console.log('[ZOOM] Rectangle too small, ignoring');
            IWB.cancelZoomWindow();
            return false;
        }
        
        // Calculate zoom to fit the rectangle in the viewport
        const canvasWidth = storedCanvas.width;
        const canvasHeight = storedCanvas.height;
        
        // Add some padding (5% of viewport)
        const padding = Math.min(canvasWidth, canvasHeight) * 0.05;
        
        const zoomX = (canvasWidth - padding * 2) / worldWidth;
        const zoomY = (canvasHeight - padding * 2) / worldHeight;
        const targetZoom = Math.min(zoomX, zoomY);
        
        // Clamp zoom to allowed range
        const newZoom = Math.max(IWB.MIN_ZOOM, Math.min(IWB.MAX_ZOOM, targetZoom));
        
        // Center the rectangle in the viewport
        const centerX = worldLeft + worldWidth / 2;
        const centerY = worldTop + worldHeight / 2;
        
        IWB.viewportX = centerX * newZoom - canvasWidth / 2;
        IWB.viewportY = centerY * newZoom - canvasHeight / 2;
        IWB.zoom = newZoom;
        
        console.log('[ZOOM] Zoomed to window:', Math.round(newZoom * 100) + '%');
        
        // Render the changes
        if (IWB._zoomRenderCallback) {
            IWB._zoomRenderCallback();
        }
        
        // Clean up
        IWB.cancelZoomWindow();
        
        return true;
    };

    /**
     * Check if zoom window mode is active
     */
    IWB.isZoomWindowActive = function() {
        return isZoomWindowMode;
    };

    /**
     * Check if currently drawing zoom window
     */
    IWB.isDrawingZoomWindow = function() {
        return isZoomWindowMode && zoomWindowStart !== null;
    };

    /**
     * Get current zoom percentage
     */
    IWB.getZoomPercentage = function() {
        return Math.round(IWB.zoom * 100);
    };

    /**
     * Set zoom to specific percentage
     */
    IWB.setZoomPercentage = function(percentage, canvas) {
        if (!canvas || typeof percentage !== 'number') return;
        
        const targetZoom = percentage / 100;
        const clampedZoom = Math.max(IWB.MIN_ZOOM, Math.min(IWB.MAX_ZOOM, targetZoom));
        
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        const worldPos = IWB.screenToWorld(centerX, centerY);
        
        IWB.viewportX = worldPos.x * clampedZoom - centerX;
        IWB.viewportY = worldPos.y * clampedZoom - centerY;
        IWB.zoom = clampedZoom;
        
        if (IWB._zoomRenderCallback) {
            IWB._zoomRenderCallback();
        }
        
        console.log('[ZOOM] Set zoom to', percentage + '%');
    };

    console.log('Infinite Whiteboard Zoom module loaded');

})(window);
