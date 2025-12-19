/**
 * Infinite Whiteboard Drawing Module
 * Handles drawing operations: pen, marker, highlighter, eraser
 */

(function(window) {
    'use strict';

    window.InfiniteWhiteboard = window.InfiniteWhiteboard || {};
    const IWB = window.InfiniteWhiteboard;

    // Drawing state
    IWB.drawing = false;
    IWB.currentStroke = null;

    const rotatePoint = (x, y, cx, cy, angle) => {
        const cos = Math.cos(angle);
        const sin = Math.sin(angle);
        const dx = x - cx;
        const dy = y - cy;
        return {
            x: cx + dx * cos - dy * sin,
            y: cy + dx * sin + dy * cos
        };
    };

    /**
     * Start a new stroke
     */
    IWB.startStroke = function(worldX, worldY) {
        IWB.drawing = true;
        IWB.currentStroke = [{ x: worldX, y: worldY }];
    };

    /**
     * Add point to current stroke
     */
    IWB.addToStroke = function(worldX, worldY) {
        if (IWB.drawing && IWB.currentStroke) {
            IWB.currentStroke.push({ x: worldX, y: worldY });
            return true;
        }
        return false;
    };

    /**
     * End current stroke and create object
     */
    IWB.endStroke = function(currentTool, color, size, nextObjectId) {
        if (!IWB.drawing || !IWB.currentStroke || IWB.currentStroke.length < 2) {
            IWB.drawing = false;
            IWB.currentStroke = null;
            return null;
        }

        // Don't create an object for eraser strokes
        if (currentTool === 'eraser') {
            IWB.drawing = false;
            IWB.currentStroke = null;
            return null;
        }

        const newObj = {
            id: nextObjectId,
            type: 'stroke',
            strokeType: currentTool,
            color: color,
            size: size,
            path: IWB.currentStroke
        };

        IWB.drawing = false;
        IWB.currentStroke = null;

        return newObj;
    };

    /**
     * Draw an object on canvas
     */
    IWB.drawObject = function(ctx, obj) {
        if (obj.type === 'stroke') {
            ctx.save();
            ctx.lineJoin = 'round';
            ctx.lineCap = 'round';
            ctx.strokeStyle = obj.color || '#14b8a6';
            ctx.lineWidth = obj.size || 3;
            
            // Apply transparency for marker/highlighter
            if (obj.strokeType === 'highlighter') {
                ctx.globalAlpha = 0.4;
            } else if (obj.strokeType === 'marker') {
                ctx.globalAlpha = 0.6;
            }
            
            ctx.beginPath();
            const path = obj.path || [];
            if (path.length > 0) {
                ctx.moveTo(path[0].x, path[0].y);
                for (let i = 1; i < path.length; i++) {
                    ctx.lineTo(path[i].x, path[i].y);
                }
            }
            ctx.stroke();
            ctx.restore();
        } else if (obj.type === 'shape') {
            // Delegate to shapes module if available
            if (typeof IWB.drawShape === 'function') {
                IWB.drawShape(ctx, obj);
            }
        } else if (obj.type === 'image' && obj.imageElement) {
            const rotation = obj.rotation || 0;
            const flipH = obj.flipH ? -1 : 1;
            const flipV = obj.flipV ? -1 : 1;
            const centerX = (obj.x || 0) + (obj.w || 0) / 2;
            const centerY = (obj.y || 0) + (obj.h || 0) / 2;
            ctx.save();
            ctx.translate(centerX, centerY);
            if (rotation) ctx.rotate(rotation);
            ctx.scale(flipH, flipV);
            ctx.drawImage(obj.imageElement, -(obj.w || 0) / 2, -(obj.h || 0) / 2, obj.w || 0, obj.h || 0);
            ctx.restore();
        } else if (obj.type === 'text') {
            // Delegate to text module if available
            if (typeof IWB.drawTextObject === 'function') {
                IWB.drawTextObject(ctx, obj);
            }
        }
    };

    /**
     * Draw current stroke being drawn
     */
    IWB.drawCurrentStroke = function(ctx, color, size, currentTool) {
        if (!IWB.currentStroke || !IWB.currentStroke.length) return;
        
        ctx.save();
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';
        
        // Eraser uses destination-out composition mode
        if (currentTool === 'eraser') {
            ctx.globalCompositeOperation = 'destination-out';
            ctx.strokeStyle = 'rgba(0,0,0,1)';
            ctx.lineWidth = size * 2; // Make eraser wider
        } else {
            ctx.strokeStyle = color;
            ctx.lineWidth = size;
            
            if (currentTool === 'highlighter') {
                ctx.globalAlpha = 0.4;
            } else if (currentTool === 'marker') {
                ctx.globalAlpha = 0.6;
            }
        }
        
        ctx.beginPath();
        ctx.moveTo(IWB.currentStroke[0].x, IWB.currentStroke[0].y);
        for (let i = 1; i < IWB.currentStroke.length; i++) {
            ctx.lineTo(IWB.currentStroke[i].x, IWB.currentStroke[i].y);
        }
        ctx.stroke();
        ctx.restore();
    };

    /**
     * Render all objects
     */
    IWB.renderObjects = function(ctx, objects) {
        objects.forEach(obj => {
            // Skip objects on hidden layers
            if (typeof IWB.shouldRenderObject === 'function' && !IWB.shouldRenderObject(obj)) {
                return;
            }
            IWB.drawObject(ctx, obj);
        });
    };

    /**
     * Check if eraser path intersects with an object
     */
    IWB.isEraserIntersecting = function(eraserPath, obj) {
        if (!eraserPath || eraserPath.length === 0) return false;
        
        const eraserRadius = 20; // Eraser detection radius
        
        if (obj.type === 'stroke') {
            const path = obj.path || [];
            // Check if any point in the eraser path is close to any point in the stroke
            for (let ep of eraserPath) {
                for (let sp of path) {
                    const dx = ep.x - sp.x;
                    const dy = ep.y - sp.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    // If within erasing distance
                    if (dist < eraserRadius) {
                        return true;
                    }
                }
            }
        } else if (obj.type === 'image' || obj.type === 'text' || obj.type === 'shape') {
            // For bounded objects (image, text, shape), check if eraser path intersects bounds
            const bounds = IWB.getBounds(obj);
            
            // Check if any point in the eraser path is within the object's bounds
            for (let ep of eraserPath) {
                if (ep.x >= bounds.x - eraserRadius && 
                    ep.x <= bounds.x + bounds.w + eraserRadius &&
                    ep.y >= bounds.y - eraserRadius && 
                    ep.y <= bounds.y + bounds.h + eraserRadius) {
                    return true;
                }
            }
        }
        return false;
    };

    /**
     * Handle eraser - remove intersecting objects
     */
    IWB.handleEraser = function(eraserPath, objects) {
        if (!eraserPath || eraserPath.length === 0) return { objects, erased: [] };
        
        const erasedObjects = [];
        const remainingObjects = objects.filter(obj => {
            if (IWB.isEraserIntersecting(eraserPath, obj)) {
                erasedObjects.push(obj);
                return false;
            }
            return true;
        });
        
        return { objects: remainingObjects, erased: erasedObjects };
    };

    /**
     * Get bounds of an object
     */
    IWB.getBounds = function(obj) {
        if (obj.type === 'stroke') {
            const path = obj.path || [];
            if (path.length === 0) return { x: 0, y: 0, w: 0, h: 0 };
            
            const xs = path.map(p => p.x);
            const ys = path.map(p => p.y);
            const minX = Math.min(...xs);
            const maxX = Math.max(...xs);
            const minY = Math.min(...ys);
            const maxY = Math.max(...ys);
            
            return {
                x: minX,
                y: minY,
                w: maxX - minX,
                h: maxY - minY
            };
        } else if (obj.type === 'shape') {
            // Shapes have simple rectangular bounds
            return {
                x: obj.x || 0,
                y: obj.y || 0,
                w: obj.w || 0,
                h: obj.h || 0
            };
        } else if (obj.type === 'image') {
            const base = {
                x: obj.x || 0,
                y: obj.y || 0,
                w: obj.w || 0,
                h: obj.h || 0
            };
            const rotation = obj.rotation || 0;
            if (!rotation) {
                return base;
            }
            const corners = [
                { x: base.x, y: base.y },
                { x: base.x + base.w, y: base.y },
                { x: base.x + base.w, y: base.y + base.h },
                { x: base.x, y: base.y + base.h }
            ];
            const center = {
                x: base.x + base.w / 2,
                y: base.y + base.h / 2
            };
            const rotated = corners.map(pt => rotatePoint(pt.x, pt.y, center.x, center.y, rotation));
            const xs = rotated.map(pt => pt.x);
            const ys = rotated.map(pt => pt.y);
            const minX = Math.min(...xs);
            const maxX = Math.max(...xs);
            const minY = Math.min(...ys);
            const maxY = Math.max(...ys);
            return { x: minX, y: minY, w: maxX - minX, h: maxY - minY };
        } else if (obj.type === 'text') {
            // Delegate to text module if available
            if (typeof IWB.getTextBounds === 'function') {
                return IWB.getTextBounds(obj);
            }
            // Fallback
            return {
                x: obj.x || 0,
                y: obj.y || 0,
                w: obj.width || 100,
                h: obj.height || 30
            };
        }
        return { x: 0, y: 0, w: 0, h: 0 };
    };

    /**
     * Check if point is inside object bounds
     */
    IWB.isPointInObject = function(x, y, obj) {
        const bounds = IWB.getBounds(obj);
        return x >= bounds.x && x <= bounds.x + bounds.w &&
               y >= bounds.y && y <= bounds.y + bounds.h;
    };

    /**
     * Find object at point (topmost)
     */
    IWB.findObjectAtPoint = function(x, y, objects) {
        const ordered = typeof IWB.getObjectsInLayerOrder === 'function'
            ? IWB.getObjectsInLayerOrder(objects)
            : [...objects];

        for (let i = ordered.length - 1; i >= 0; i--) {
            if (IWB.isPointInObject(x, y, ordered[i])) {
                return ordered[i];
            }
        }
        return null;
    };

    /**
     * Move object by offset
     */
    IWB.moveObject = function(obj, dx, dy) {
        if (obj.type === 'stroke' && obj.path) {
            // Store old path before moving
            const oldPath = JSON.parse(JSON.stringify(obj.path));
            
            // Move all points in the path
            obj.path = obj.path.map(p => ({
                x: p.x + dx,
                y: p.y + dy
            }));
            
            return oldPath;
        } else if (obj.type === 'shape') {
            // Store old position before moving
            const oldPos = { x: obj.x, y: obj.y };
            
            // Move shape
            obj.x += dx;
            obj.y += dy;
            
            return oldPos;
        } else if (obj.type === 'image') {
            // Store old position before moving
            const oldPos = { x: obj.x, y: obj.y };
            
            // Move image
            obj.x += dx;
            obj.y += dy;
            
            return oldPos;
        } else if (obj.type === 'text') {
            // Store old position before moving
            const oldPos = { x: obj.x, y: obj.y };
            
            // Move text
            obj.x += dx;
            obj.y += dy;
            
            return oldPos;
        }
        return null;
    };

    console.log('Infinite Whiteboard Drawing module loaded');

})(window);
