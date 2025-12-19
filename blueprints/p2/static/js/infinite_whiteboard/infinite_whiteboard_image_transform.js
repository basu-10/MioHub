/**
 * Infinite Whiteboard Image Transform Module
 * Handles image resizing, cropping, rotation, and flipping
 */

(function(window) {
    'use strict';

    window.InfiniteWhiteboard = window.InfiniteWhiteboard || {};
    const IWB = window.InfiniteWhiteboard;

    // Transform state for image manipulation
    const imageTransformState = {
        resizeMode: null,          // 'nw', 'ne', 'sw', 'se', 'n', 's', 'e', 'w'
        resizeStartPos: null,      // World coordinates at start
        resizeStartBounds: null,   // Original bounds {x, y, w, h}
        rotateMode: false,
        rotateStartAngle: 0,
        rotateCenter: null,
        cropMode: false,
        cropRect: null,            // {x, y, w, h} in image local coordinates
        selectedImageId: null,
        originalImageData: null,   // For crop operation
        maintainAspectRatio: false // Shift key state
    };

    // Handle size - clickable region for resize handles
    const HANDLE_SIZE = 12;
    const HANDLE_OFFSET = HANDLE_SIZE / 2;

    /**
     * Rotate a point around a center
     */
    const rotatePoint = function(px, py, cx, cy, angle) {
        if (!angle) return { x: px, y: py };
        const cos = Math.cos(angle);
        const sin = Math.sin(angle);
        const dx = px - cx;
        const dy = py - cy;
        return {
            x: cx + dx * cos - dy * sin,
            y: cy + dx * sin + dy * cos
        };
    };

    /**
     * Get resize handles for an image object (rotated with image)
     */
    IWB.getImageResizeHandles = function(imageObj) {
        if (!imageObj || imageObj.type !== 'image') return [];

        const x = imageObj.x || 0;
        const y = imageObj.y || 0;
        const w = imageObj.w || 0;
        const h = imageObj.h || 0;
        const rotation = imageObj.rotation || 0;
        const centerX = x + w / 2;
        const centerY = y + h / 2;

        // 8 resize handles positions (before rotation)
        const handlePositions = [
            { type: 'nw', lx: x, ly: y },
            { type: 'n',  lx: x + w/2, ly: y },
            { type: 'ne', lx: x + w, ly: y },
            { type: 'e',  lx: x + w, ly: y + h/2 },
            { type: 'se', lx: x + w, ly: y + h },
            { type: 's',  lx: x + w/2, ly: y + h },
            { type: 'sw', lx: x, ly: y + h },
            { type: 'w',  lx: x, ly: y + h/2 }
        ];

        // Rotate each handle around image center
        return handlePositions.map(handle => {
            const rotated = rotatePoint(handle.lx, handle.ly, centerX, centerY, rotation);
            return {
                type: handle.type,
                cx: rotated.x,
                cy: rotated.y,
                x: rotated.x - HANDLE_OFFSET,
                y: rotated.y - HANDLE_OFFSET,
                w: HANDLE_SIZE,
                h: HANDLE_SIZE
            };
        });
    };

    /**
     * Get rotation handle for an image object (rotated with image)
     */
    IWB.getImageRotationHandle = function(imageObj) {
        if (!imageObj || imageObj.type !== 'image') return null;

        const x = imageObj.x || 0;
        const y = imageObj.y || 0;
        const w = imageObj.w || 0;
        const h = imageObj.h || 0;
        const rotation = imageObj.rotation || 0;
        const centerX = x + w / 2;
        const centerY = y + h / 2;

        // Rotation handle 40px above the top edge (before rotation)
        const localHandleX = x + w / 2;
        const localHandleY = y - 40;

        // Rotate handle position around image center
        const rotated = rotatePoint(localHandleX, localHandleY, centerX, centerY, rotation);

        return {
            type: 'rotate',
            cx: rotated.x,
            cy: rotated.y,
            x: rotated.x - 12,
            y: rotated.y - 12,
            w: 24,
            h: 24
        };
    };

    /**
     * Check if a point is inside a handle
     */
    IWB.isPointInHandle = function(worldX, worldY, handle) {
        if (!handle) return false;
        return worldX >= handle.x && worldX <= handle.x + handle.w &&
               worldY >= handle.y && worldY <= handle.y + handle.h;
    };

    /**
     * Find which handle (if any) is at the given point
     */
    IWB.findImageHandleAtPoint = function(worldX, worldY, imageObj) {
        if (!imageObj || imageObj.type !== 'image') return null;

        // Check rotation handle first
        const rotHandle = IWB.getImageRotationHandle(imageObj);
        if (rotHandle && IWB.isPointInHandle(worldX, worldY, rotHandle)) {
            return rotHandle;
        }

        // Check resize handles
        const resizeHandles = IWB.getImageResizeHandles(imageObj);
        for (const handle of resizeHandles) {
            if (IWB.isPointInHandle(worldX, worldY, handle)) {
                return handle;
            }
        }

        return null;
    };

    /**
     * Start resize operation
     */
    IWB.startImageResize = function(imageObj, handleType, worldPos) {
        if (!imageObj || !handleType || !worldPos) return false;

        imageTransformState.resizeMode = handleType;
        imageTransformState.resizeStartPos = { x: worldPos.x, y: worldPos.y };
        imageTransformState.resizeStartBounds = {
            x: imageObj.x,
            y: imageObj.y,
            w: imageObj.w,
            h: imageObj.h
        };
        imageTransformState.selectedImageId = imageObj.id;

        console.log('[IMAGE_TRANSFORM] Started resize:', handleType);
        return true;
    };

    /**
     * Update resize operation
     */
    IWB.updateImageResize = function(imageObj, worldPos, shiftKey) {
        if (!imageTransformState.resizeMode || !imageTransformState.resizeStartPos) return false;
        if (!imageObj || imageObj.id !== imageTransformState.selectedImageId) return false;

        const orig = imageTransformState.resizeStartBounds;
        const handle = imageTransformState.resizeMode;
        const rotation = imageObj.rotation || 0;

        // Transform mouse position into image's local coordinate space (inverse rotation)
        const origCenterX = orig.x + orig.w / 2;
        const origCenterY = orig.y + orig.h / 2;
        
        // Inverse rotate the current mouse position
        const invRotatedCurrent = rotatePoint(worldPos.x, worldPos.y, origCenterX, origCenterY, -rotation);
        // Inverse rotate the start position
        const invRotatedStart = rotatePoint(
            imageTransformState.resizeStartPos.x,
            imageTransformState.resizeStartPos.y,
            origCenterX,
            origCenterY,
            -rotation
        );
        
        // Calculate delta in local (unrotated) space
        const dx = invRotatedCurrent.x - invRotatedStart.x;
        const dy = invRotatedCurrent.y - invRotatedStart.y;

        let newX = orig.x;
        let newY = orig.y;
        let newW = orig.w;
        let newH = orig.h;

        // Calculate aspect ratio if shift is held
        const aspectRatio = orig.w / orig.h;

        // Apply resize based on handle type
        switch (handle) {
            case 'nw':
                newX = orig.x + dx;
                newY = orig.y + dy;
                newW = orig.w - dx;
                newH = orig.h - dy;
                if (shiftKey) {
                    // Maintain aspect ratio from top-left
                    const avgScale = ((orig.w - dx) / orig.w + (orig.h - dy) / orig.h) / 2;
                    newW = orig.w * avgScale;
                    newH = orig.h * avgScale;
                    newX = orig.x + orig.w - newW;
                    newY = orig.y + orig.h - newH;
                }
                break;
            case 'ne':
                newY = orig.y + dy;
                newW = orig.w + dx;
                newH = orig.h - dy;
                if (shiftKey) {
                    const avgScale = ((orig.w + dx) / orig.w + (orig.h - dy) / orig.h) / 2;
                    newW = orig.w * avgScale;
                    newH = orig.h * avgScale;
                    newY = orig.y + orig.h - newH;
                }
                break;
            case 'sw':
                newX = orig.x + dx;
                newW = orig.w - dx;
                newH = orig.h + dy;
                if (shiftKey) {
                    const avgScale = ((orig.w - dx) / orig.w + (orig.h + dy) / orig.h) / 2;
                    newW = orig.w * avgScale;
                    newH = orig.h * avgScale;
                    newX = orig.x + orig.w - newW;
                }
                break;
            case 'se':
                newW = orig.w + dx;
                newH = orig.h + dy;
                if (shiftKey) {
                    const avgScale = ((orig.w + dx) / orig.w + (orig.h + dy) / orig.h) / 2;
                    newW = orig.w * avgScale;
                    newH = orig.h * avgScale;
                }
                break;
            case 'n':
                newY = orig.y + dy;
                newH = orig.h - dy;
                if (shiftKey) {
                    newW = newH * aspectRatio;
                    newX = orig.x + (orig.w - newW) / 2;
                }
                break;
            case 's':
                newH = orig.h + dy;
                if (shiftKey) {
                    newW = newH * aspectRatio;
                    newX = orig.x + (orig.w - newW) / 2;
                }
                break;
            case 'e':
                newW = orig.w + dx;
                if (shiftKey) {
                    newH = newW / aspectRatio;
                    newY = orig.y + (orig.h - newH) / 2;
                }
                break;
            case 'w':
                newX = orig.x + dx;
                newW = orig.w - dx;
                if (shiftKey) {
                    newH = newW / aspectRatio;
                    newY = orig.y + (orig.h - newH) / 2;
                }
                break;
        }

        // Prevent negative dimensions
        const MIN_SIZE = 10;
        if (newW < MIN_SIZE || newH < MIN_SIZE) return false;

        // Apply new bounds
        imageObj.x = newX;
        imageObj.y = newY;
        imageObj.w = newW;
        imageObj.h = newH;

        return true;
    };

    /**
     * End resize operation
     */
    IWB.endImageResize = function() {
        if (!imageTransformState.resizeMode) return null;

        const result = {
            imageId: imageTransformState.selectedImageId,
            oldBounds: imageTransformState.resizeStartBounds
        };

        imageTransformState.resizeMode = null;
        imageTransformState.resizeStartPos = null;
        imageTransformState.resizeStartBounds = null;
        imageTransformState.selectedImageId = null;

        console.log('[IMAGE_TRANSFORM] Ended resize');
        return result;
    };

    /**
     * Start rotation operation
     */
    IWB.startImageRotation = function(imageObj, worldPos) {
        if (!imageObj || !worldPos) return false;

        const centerX = imageObj.x + imageObj.w / 2;
        const centerY = imageObj.y + imageObj.h / 2;

        imageTransformState.rotateMode = true;
        imageTransformState.rotateCenter = { x: centerX, y: centerY };
        imageTransformState.rotateStartAngle = Math.atan2(
            worldPos.y - centerY,
            worldPos.x - centerX
        );
        imageTransformState.selectedImageId = imageObj.id;
        imageTransformState.resizeStartBounds = {
            x: imageObj.x,
            y: imageObj.y,
            w: imageObj.w,
            h: imageObj.h,
            rotation: imageObj.rotation || 0
        };

        console.log('[IMAGE_TRANSFORM] Started rotation');
        return true;
    };

    /**
     * Update rotation operation
     */
    IWB.updateImageRotation = function(imageObj, worldPos, shiftKey) {
        if (!imageTransformState.rotateMode || !imageTransformState.rotateCenter) return false;
        if (!imageObj || imageObj.id !== imageTransformState.selectedImageId) return false;

        const center = imageTransformState.rotateCenter;
        const currentAngle = Math.atan2(
            worldPos.y - center.y,
            worldPos.x - center.x
        );

        let deltaAngle = currentAngle - imageTransformState.rotateStartAngle;

        // Snap to 15° increments if shift is held
        if (shiftKey) {
            const snapAngle = Math.PI / 12; // 15 degrees
            deltaAngle = Math.round(deltaAngle / snapAngle) * snapAngle;
        }

        const originalRotation = imageTransformState.resizeStartBounds.rotation || 0;
        imageObj.rotation = originalRotation + deltaAngle;

        return true;
    };

    /**
     * End rotation operation
     */
    IWB.endImageRotation = function() {
        if (!imageTransformState.rotateMode) return null;

        const result = {
            imageId: imageTransformState.selectedImageId,
            oldRotation: imageTransformState.resizeStartBounds.rotation
        };

        imageTransformState.rotateMode = false;
        imageTransformState.rotateStartAngle = 0;
        imageTransformState.rotateCenter = null;
        imageTransformState.selectedImageId = null;
        imageTransformState.resizeStartBounds = null;

        console.log('[IMAGE_TRANSFORM] Ended rotation');
        return result;
    };

    /**
     * Flip image horizontally
     */
    IWB.flipImageHorizontal = function(imageObj) {
        if (!imageObj || imageObj.type !== 'image') return false;
        imageObj.flipH = !imageObj.flipH;
        console.log('[IMAGE_TRANSFORM] Flipped horizontal:', imageObj.flipH);
        return true;
    };

    /**
     * Flip image vertically
     */
    IWB.flipImageVertical = function(imageObj) {
        if (!imageObj || imageObj.type !== 'image') return false;
        imageObj.flipV = !imageObj.flipV;
        console.log('[IMAGE_TRANSFORM] Flipped vertical:', imageObj.flipV);
        return true;
    };

    /**
     * Reset image transformations (rotation and flips)
     */
    IWB.resetImageTransform = function(imageObj) {
        if (!imageObj || imageObj.type !== 'image') return false;
        imageObj.rotation = 0;
        imageObj.flipH = false;
        imageObj.flipV = false;
        console.log('[IMAGE_TRANSFORM] Reset transformations');
        return true;
    };

    /**
     * Get rotated bounding box for an image
     * Returns the axis-aligned bounding box that contains the rotated image
     */
    IWB.getRotatedImageBounds = function(imageObj) {
        if (!imageObj || imageObj.type !== 'image') return null;

        const x = imageObj.x || 0;
        const y = imageObj.y || 0;
        const w = imageObj.w || 0;
        const h = imageObj.h || 0;
        const rotation = imageObj.rotation || 0;

        if (!rotation) {
            return { x, y, w, h };
        }

        const centerX = x + w / 2;
        const centerY = y + h / 2;

        // Four corners of the unrotated rectangle
        const corners = [
            { x: x, y: y },
            { x: x + w, y: y },
            { x: x + w, y: y + h },
            { x: x, y: y + h }
        ];

        // Rotate all corners
        const rotatedCorners = corners.map(corner => 
            rotatePoint(corner.x, corner.y, centerX, centerY, rotation)
        );

        // Find min/max to get axis-aligned bounding box
        const xs = rotatedCorners.map(c => c.x);
        const ys = rotatedCorners.map(c => c.y);
        const minX = Math.min(...xs);
        const minY = Math.min(...ys);
        const maxX = Math.max(...xs);
        const maxY = Math.max(...ys);

        return {
            x: minX,
            y: minY,
            w: maxX - minX,
            h: maxY - minY
        };
    };

    /**
     * Check if currently in image transform mode
     */
    IWB.isImageTransformActive = function() {
        return !!(imageTransformState.resizeMode || imageTransformState.rotateMode);
    };

    /**
     * Cancel any active image transform
     */
    IWB.cancelImageTransform = function() {
        imageTransformState.resizeMode = null;
        imageTransformState.resizeStartPos = null;
        imageTransformState.resizeStartBounds = null;
        imageTransformState.rotateMode = false;
        imageTransformState.rotateStartAngle = 0;
        imageTransformState.rotateCenter = null;
        imageTransformState.selectedImageId = null;
    };

    /**
     * Draw image resize/rotation handles
     */
    IWB.drawImageTransformHandles = function(ctx, imageObj) {
        if (!ctx || !imageObj || imageObj.type !== 'image') return;

        ctx.save();

        const centerX = imageObj.x + imageObj.w / 2;
        const centerY = imageObj.y + imageObj.h / 2;

        // Draw resize handles
        const handles = IWB.getImageResizeHandles(imageObj);
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

        // Draw rotation handle
        const rotHandle = IWB.getImageRotationHandle(imageObj);
        if (rotHandle) {
            // Draw line from image center to rotation handle
            ctx.strokeStyle = '#14b8a6';
            ctx.lineWidth = 2;
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.moveTo(centerX, centerY);
            ctx.lineTo(rotHandle.cx, rotHandle.cy);
            ctx.stroke();
            ctx.setLineDash([]);

            // Draw rotation handle circle
            ctx.fillStyle = '#0a0a0b';
            ctx.strokeStyle = '#14b8a6';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(rotHandle.cx, rotHandle.cy, 12, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();

            // Draw rotation icon (curved arrow)
            ctx.strokeStyle = '#14b8a6';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(rotHandle.cx, rotHandle.cy, 6, -Math.PI / 4, Math.PI * 1.25, false);
            // Arrow head
            const arrowX = rotHandle.cx + Math.cos(Math.PI * 1.25) * 6;
            const arrowY = rotHandle.cy + Math.sin(Math.PI * 1.25) * 6;
            ctx.moveTo(arrowX, arrowY);
            ctx.lineTo(arrowX - 3, arrowY - 2);
            ctx.moveTo(arrowX, arrowY);
            ctx.lineTo(arrowX + 1, arrowY - 3);
            ctx.stroke();
        }

        ctx.restore();
    };

    /**
     * Get cursor style for handle type
     */
    IWB.getCursorForHandle = function(handleType) {
        const cursorMap = {
            'nw': 'nw-resize',
            'ne': 'ne-resize',
            'sw': 'sw-resize',
            'se': 'se-resize',
            'n': 'n-resize',
            's': 's-resize',
            'e': 'e-resize',
            'w': 'w-resize',
            'rotate': 'grab'
        };
        return cursorMap[handleType] || 'default';
    };

    console.log('[IMAGE_TRANSFORM] Image Transform module loaded');

})(window);
