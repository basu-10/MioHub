/**
 * Infinite Whiteboard Stroke & Shape Transform Module
 * Handles resizing for strokes and shapes with 8-handle bounding box
 * Stroke thickness remains constant, only dimensions change
 */

(function(window) {
    'use strict';

    window.InfiniteWhiteboard = window.InfiniteWhiteboard || {};
    const IWB = window.InfiniteWhiteboard;

    // Transform state
    const strokeTransformState = {
        resizeMode: null,          // 'nw', 'ne', 'sw', 'se', 'n', 's', 'e', 'w'
        resizeStartPos: null,      // World coordinates at start
        resizeStartBounds: null,   // Original bounds {x, y, w, h}
        selectedObjectId: null,
        originalPath: null,        // For strokes
        originalShapeData: null    // For shapes
    };

    // Handle size - clickable region for resize handles
    const HANDLE_SIZE = 12;
    const HANDLE_OFFSET = HANDLE_SIZE / 2;

    /**
     * Get resize handles for a stroke or shape object (8 handles around bounding box)
     */
    IWB.getStrokeResizeHandles = function(obj) {
        if (!obj || (obj.type !== 'stroke' && obj.type !== 'shape')) return [];

        const bounds = typeof IWB.getBounds === 'function' ? IWB.getBounds(obj) : null;
        if (!bounds) return [];

        const x = bounds.x;
        const y = bounds.y;
        const w = bounds.w;
        const h = bounds.h;

        // 8 resize handle positions
        const handlePositions = [
            { type: 'nw', cx: x, cy: y },
            { type: 'n',  cx: x + w/2, cy: y },
            { type: 'ne', cx: x + w, cy: y },
            { type: 'e',  cx: x + w, cy: y + h/2 },
            { type: 'se', cx: x + w, cy: y + h },
            { type: 's',  cx: x + w/2, cy: y + h },
            { type: 'sw', cx: x, cy: y + h },
            { type: 'w',  cx: x, cy: y + h/2 }
        ];

        return handlePositions.map(handle => ({
            type: handle.type,
            cx: handle.cx,
            cy: handle.cy,
            x: handle.cx - HANDLE_OFFSET,
            y: handle.cy - HANDLE_OFFSET,
            w: HANDLE_SIZE,
            h: HANDLE_SIZE
        }));
    };

    /**
     * Check if a point is inside a handle
     */
    IWB.isPointInStrokeHandle = function(worldX, worldY, handle) {
        if (!handle) return false;
        return worldX >= handle.x && worldX <= handle.x + handle.w &&
               worldY >= handle.y && worldY <= handle.y + handle.h;
    };

    /**
     * Find which handle (if any) is at the given point
     */
    IWB.findStrokeHandleAtPoint = function(worldX, worldY, obj) {
        if (!obj || (obj.type !== 'stroke' && obj.type !== 'shape')) return null;

        const handles = IWB.getStrokeResizeHandles(obj);
        for (const handle of handles) {
            if (IWB.isPointInStrokeHandle(worldX, worldY, handle)) {
                return handle;
            }
        }

        return null;
    };

    /**
     * Start resize operation
     */
    IWB.startStrokeResize = function(obj, handleType, worldPos) {
        if (!obj || !handleType || !worldPos) return false;
        if (obj.type !== 'stroke' && obj.type !== 'shape') return false;

        const bounds = typeof IWB.getBounds === 'function' ? IWB.getBounds(obj) : null;
        if (!bounds) return false;

        strokeTransformState.resizeMode = handleType;
        strokeTransformState.resizeStartPos = { x: worldPos.x, y: worldPos.y };
        strokeTransformState.resizeStartBounds = {
            x: bounds.x,
            y: bounds.y,
            w: bounds.w,
            h: bounds.h
        };
        strokeTransformState.selectedObjectId = obj.id;

        // Store original data
        if (obj.type === 'stroke' && obj.path) {
            strokeTransformState.originalPath = JSON.parse(JSON.stringify(obj.path));
        } else if (obj.type === 'shape') {
            strokeTransformState.originalShapeData = {
                x: obj.x,
                y: obj.y,
                w: obj.w,
                h: obj.h,
                startX: obj.startX,
                startY: obj.startY,
                endX: obj.endX,
                endY: obj.endY
            };
        }

        console.log('[STROKE_TRANSFORM] Started resize:', handleType);
        return true;
    };

    /**
     * Update resize operation
     */
    IWB.updateStrokeResize = function(obj, worldPos) {
        if (!strokeTransformState.resizeMode || !strokeTransformState.resizeStartPos) return false;
        if (!obj || obj.id !== strokeTransformState.selectedObjectId) return false;

        const dx = worldPos.x - strokeTransformState.resizeStartPos.x;
        const dy = worldPos.y - strokeTransformState.resizeStartPos.y;
        const orig = strokeTransformState.resizeStartBounds;
        const handle = strokeTransformState.resizeMode;

        // Calculate new bounds based on handle
        let newX = orig.x;
        let newY = orig.y;
        let newW = orig.w;
        let newH = orig.h;

        switch (handle) {
            case 'nw':
                newX = orig.x + dx;
                newY = orig.y + dy;
                newW = orig.w - dx;
                newH = orig.h - dy;
                break;
            case 'ne':
                newY = orig.y + dy;
                newW = orig.w + dx;
                newH = orig.h - dy;
                break;
            case 'sw':
                newX = orig.x + dx;
                newW = orig.w - dx;
                newH = orig.h + dy;
                break;
            case 'se':
                newW = orig.w + dx;
                newH = orig.h + dy;
                break;
            case 'n':
                newY = orig.y + dy;
                newH = orig.h - dy;
                break;
            case 's':
                newH = orig.h + dy;
                break;
            case 'e':
                newW = orig.w + dx;
                break;
            case 'w':
                newX = orig.x + dx;
                newW = orig.w - dx;
                break;
        }

        // Prevent negative or too-small dimensions
        const MIN_SIZE = 10;
        if (newW < MIN_SIZE || newH < MIN_SIZE) return false;

        // Calculate scale factors
        const scaleX = newW / orig.w;
        const scaleY = newH / orig.h;

        // Apply transformation based on object type
        if (obj.type === 'stroke' && strokeTransformState.originalPath) {
            // Scale stroke path points
            obj.path = strokeTransformState.originalPath.map(pt => {
                // Calculate relative position in original bounds
                const relX = (pt.x - orig.x) / orig.w;
                const relY = (pt.y - orig.y) / orig.h;
                
                // Apply to new bounds
                return {
                    x: newX + relX * newW,
                    y: newY + relY * newH
                };
            });
        } else if (obj.type === 'shape' && strokeTransformState.originalShapeData) {
            // For shapes, scale dimensions
            obj.x = newX;
            obj.y = newY;
            obj.w = newW;
            obj.h = newH;

            // Update connector endpoints if they exist
            if (strokeTransformState.originalShapeData.startX !== undefined) {
                const origData = strokeTransformState.originalShapeData;
                
                // Scale start point
                const relStartX = (origData.startX - orig.x) / orig.w;
                const relStartY = (origData.startY - orig.y) / orig.h;
                obj.startX = newX + relStartX * newW;
                obj.startY = newY + relStartY * newH;
                
                // Scale end point
                const relEndX = (origData.endX - orig.x) / orig.w;
                const relEndY = (origData.endY - orig.y) / orig.h;
                obj.endX = newX + relEndX * newW;
                obj.endY = newY + relEndY * newH;
            }
        }

        return true;
    };

    /**
     * End resize operation
     */
    IWB.endStrokeResize = function() {
        if (!strokeTransformState.resizeMode) return null;

        const result = {
            objectId: strokeTransformState.selectedObjectId,
            oldBounds: strokeTransformState.resizeStartBounds,
            originalPath: strokeTransformState.originalPath,
            originalShapeData: strokeTransformState.originalShapeData
        };

        strokeTransformState.resizeMode = null;
        strokeTransformState.resizeStartPos = null;
        strokeTransformState.resizeStartBounds = null;
        strokeTransformState.selectedObjectId = null;
        strokeTransformState.originalPath = null;
        strokeTransformState.originalShapeData = null;

        console.log('[STROKE_TRANSFORM] Ended resize');
        return result;
    };

    /**
     * Check if currently in stroke/shape transform mode
     */
    IWB.isStrokeTransformActive = function() {
        return !!strokeTransformState.resizeMode;
    };

    /**
     * Cancel any active stroke/shape transform
     */
    IWB.cancelStrokeTransform = function() {
        strokeTransformState.resizeMode = null;
        strokeTransformState.resizeStartPos = null;
        strokeTransformState.resizeStartBounds = null;
        strokeTransformState.selectedObjectId = null;
        strokeTransformState.originalPath = null;
        strokeTransformState.originalShapeData = null;
    };

    /**
     * Draw stroke/shape resize handles
     */
    IWB.drawStrokeTransformHandles = function(ctx, obj) {
        if (!ctx || !obj) return;
        if (obj.type !== 'stroke' && obj.type !== 'shape') return;

        ctx.save();

        // Draw bounding box
        const bounds = typeof IWB.getBounds === 'function' ? IWB.getBounds(obj) : null;
        if (!bounds) {
            ctx.restore();
            return;
        }

        ctx.strokeStyle = '#14b8a6';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.strokeRect(bounds.x, bounds.y, bounds.w, bounds.h);
        ctx.setLineDash([]);

        // Draw resize handles
        const handles = IWB.getStrokeResizeHandles(obj);
        handles.forEach(handle => {
            ctx.fillStyle = '#14b8a6';
            ctx.strokeStyle = '#0f766e';
            ctx.lineWidth = 2;

            // Corner handles are circles, edge handles are squares
            if (['nw', 'ne', 'sw', 'se'].includes(handle.type)) {
                ctx.beginPath();
                ctx.arc(handle.cx, handle.cy, HANDLE_SIZE / 2, 0, Math.PI * 2);
                ctx.fill();
                ctx.stroke();
            } else {
                ctx.fillRect(handle.x, handle.y, handle.w, handle.h);
                ctx.strokeRect(handle.x, handle.y, handle.w, handle.h);
            }
        });

        ctx.restore();
    };

    /**
     * Get cursor style for handle type
     */
    IWB.getCursorForStrokeHandle = function(handleType) {
        const cursorMap = {
            'nw': 'nw-resize',
            'ne': 'ne-resize',
            'sw': 'sw-resize',
            'se': 'se-resize',
            'n': 'n-resize',
            's': 's-resize',
            'e': 'e-resize',
            'w': 'w-resize'
        };
        return cursorMap[handleType] || 'default';
    };

    console.log('[STROKE_TRANSFORM] Stroke & Shape Transform module loaded');

})(window);
