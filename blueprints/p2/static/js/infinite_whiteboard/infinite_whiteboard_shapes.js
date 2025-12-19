/**
 * Infinite Whiteboard Shapes Module
 * Handles shape creation and rendering: flowcharts, connectors, industry icons
 */

(function(window) {
    'use strict';

    window.InfiniteWhiteboard = window.InfiniteWhiteboard || {};
    const IWB = window.InfiniteWhiteboard;

    // Shape state
    IWB.shapeStart = null;
    IWB.currentShape = null;
    IWB.currentShapeType = null;

    /**
     * Recently Used Shapes - localStorage key
     */
    const RECENT_SHAPES_KEY = 'iwb_recent_shapes';
    const MAX_RECENT_SHAPES = 6;

    /**
     * Get recently used shapes from localStorage
     */
    IWB.getRecentShapes = function() {
        try {
            const stored = localStorage.getItem(RECENT_SHAPES_KEY);
            if (stored) {
                const parsed = JSON.parse(stored);
                // Ensure it's an array and limit to MAX_RECENT_SHAPES
                if (Array.isArray(parsed)) {
                    return parsed.slice(0, MAX_RECENT_SHAPES);
                }
            }
        } catch (e) {
            console.warn('Error reading recent shapes:', e);
        }
        return [];
    };

    /**
     * Track shape usage - adds to recent shapes list
     */
    IWB.trackShapeUsage = function(shapeType) {
        try {
            let recent = IWB.getRecentShapes();
            
            // Remove if already exists (to move to front)
            recent = recent.filter(s => s !== shapeType);
            
            // Add to front
            recent.unshift(shapeType);
            
            // Keep only top MAX_RECENT_SHAPES
            recent = recent.slice(0, MAX_RECENT_SHAPES);
            
            // Save to localStorage
            localStorage.setItem(RECENT_SHAPES_KEY, JSON.stringify(recent));
        } catch (e) {
            console.warn('Error saving recent shapes:', e);
        }
    };

    /**
     * Get shape info (name and icon) from shape type
     */
    IWB.getShapeInfo = function(shapeType) {
        for (const category in IWB.SHAPE_CATEGORIES) {
            const shapes = IWB.SHAPE_CATEGORIES[category].shapes;
            if (shapes[shapeType]) {
                return {
                    type: shapeType,
                    name: shapes[shapeType].name,
                    icon: shapes[shapeType].icon,
                    category: category
                };
            }
        }
        return null;
    };

    /**
     * Shape categories and definitions
     */
    IWB.SHAPE_CATEGORIES = {
        flowchart: {
            name: 'Flowchart',
            shapes: {
                'process': { name: 'Process', icon: '▭' },
                'decision': { name: 'Decision', icon: '◇' },
                'terminator': { name: 'Start/End', icon: '⬭' },
                'data': { name: 'Data', icon: '▱' },
                'document': { name: 'Document', icon: '📄' },
                'predefinedProcess': { name: 'Predefined', icon: '▯' },
                'manualInput': { name: 'Manual Input', icon: '⏢' },
                'preparation': { name: 'Preparation', icon: '⬠' }
            }
        },
        connectors: {
            name: 'Connectors',
            shapes: {
                'arrow': { name: 'Arrow', icon: '→' },
                'doubleArrow': { name: 'Double Arrow', icon: '↔' },
                'line': { name: 'Line', icon: '─' },
                'curvedArrow': { name: 'Squiggly Arrow', icon: '↝' },
                'elbowArrowHV': { name: 'Elbow Arrow H→V', icon: '⌐→' },
                'elbowArrowVH': { name: 'Elbow Arrow V→H', icon: '└→' },
                'dashedArrow': { name: 'Dashed Arrow', icon: '⇢' },
                'thickArrow': { name: 'Thick Arrow', icon: '⯈' },
                'circleArrow': { name: 'Circle Arrow', icon: '⊙→' },
                'diamondArrow': { name: 'Diamond Arrow', icon: '◇→' },
                'squareArrow': { name: 'Square Arrow', icon: '□→' },
                'ballHead': { name: 'Ball Head', icon: '○→' },
                'doubleBallHead': { name: 'Double Ball', icon: '○↔○' }
            }
        },
        industry: {
            name: 'Industry',
            shapes: {
                'database': { name: 'Database', icon: '🗄️' },
                'server': { name: 'Server', icon: '🖥️' },
                'cloud': { name: 'Cloud', icon: '☁️' },
                'user': { name: 'User', icon: '👤' },
                'building': { name: 'Building', icon: '🏢' },
                'factory': { name: 'Factory', icon: '🏭' },
                'mobile': { name: 'Mobile', icon: '📱' },
                'laptop': { name: 'Laptop', icon: '💻' }
            }
        },
        callouts: {
            name: 'Callouts',
            shapes: {
                'thought': { name: 'Thought Bubble', icon: '💭' },
                'speech': { name: 'Speech Bubble', icon: '💬' },
                'callout': { name: 'Callout', icon: '📢' },
                'note': { name: 'Sticky Note', icon: '📝' }
            }
        }
    };

    /**
     * Start drawing a shape
     */
    IWB.startShape = function(worldX, worldY, shapeType) {
        IWB.shapeStart = { x: worldX, y: worldY };
        IWB.currentShapeType = shapeType;
        IWB.currentShape = {
            x: worldX,
            y: worldY,
            w: 0,
            h: 0
        };
    };

    /**
     * Update shape while dragging
     */
    IWB.updateShape = function(worldX, worldY, maintainAspect = false) {
        if (!IWB.shapeStart || !IWB.currentShape) return false;

        let w = worldX - IWB.shapeStart.x;
        let h = worldY - IWB.shapeStart.y;

        // Maintain aspect ratio if Shift key is held
        if (maintainAspect) {
            const size = Math.max(Math.abs(w), Math.abs(h));
            w = w < 0 ? -size : size;
            h = h < 0 ? -size : size;
        }

        // Update shape dimensions
        IWB.currentShape.x = w < 0 ? IWB.shapeStart.x + w : IWB.shapeStart.x;
        IWB.currentShape.y = h < 0 ? IWB.shapeStart.y + h : IWB.shapeStart.y;
        IWB.currentShape.w = Math.abs(w);
        IWB.currentShape.h = Math.abs(h);
        
        // Store the actual current end position (for connectors)
        IWB.currentShape.endX = worldX;
        IWB.currentShape.endY = worldY;

        return true;
    };

    /**
     * Finish drawing shape and create object
     */
    IWB.endShape = function(color, strokeWidth, nextObjectId) {
        if (!IWB.currentShape || !IWB.currentShapeType) {
            IWB.shapeStart = null;
            IWB.currentShape = null;
            IWB.currentShapeType = null;
            return null;
        }

        // Minimum size check (prevent tiny shapes)
        // For connectors (arrows, lines), check distance instead of width/height to allow straight lines
        const isConnector = IWB.currentShapeType && (
            IWB.currentShapeType.includes('arrow') || 
            IWB.currentShapeType === 'line' || 
            IWB.currentShapeType.includes('ball')
        );
        
        if (isConnector) {
            // For connectors, check minimum distance (allows horizontal and vertical lines)
            const distance = Math.sqrt(IWB.currentShape.w * IWB.currentShape.w + IWB.currentShape.h * IWB.currentShape.h);
            if (distance < 10) {
                IWB.shapeStart = null;
                IWB.currentShape = null;
                IWB.currentShapeType = null;
                return null;
            }
        } else {
            // For regular shapes, require both width and height
            if (IWB.currentShape.w < 10 || IWB.currentShape.h < 10) {
                IWB.shapeStart = null;
                IWB.currentShape = null;
                IWB.currentShapeType = null;
                return null;
            }
        }

        const newObj = {
            id: nextObjectId,
            type: 'shape',
            shapeType: IWB.currentShapeType,
            x: IWB.currentShape.x,
            y: IWB.currentShape.y,
            w: IWB.currentShape.w,
            h: IWB.currentShape.h,
            color: color,
            strokeWidth: strokeWidth,
            filled: false, // Can be toggled later
            // Store actual start/end points for connectors
            startX: IWB.shapeStart.x,
            startY: IWB.shapeStart.y,
            endX: IWB.currentShape.endX || (IWB.shapeStart.x + IWB.currentShape.w),
            endY: IWB.currentShape.endY || (IWB.shapeStart.y + IWB.currentShape.h)
        };

        // Track shape usage for recently used section
        IWB.trackShapeUsage(IWB.currentShapeType);

        IWB.shapeStart = null;
        IWB.currentShape = null;
        IWB.currentShapeType = null;

        return newObj;
    };

    /**
     * Draw a shape object
     */
    IWB.drawShape = function(ctx, obj) {
        if (obj.type !== 'shape') return;

        ctx.save();
        ctx.strokeStyle = obj.color || '#14b8a6';
        ctx.lineWidth = obj.strokeWidth || 2;
        ctx.fillStyle = obj.filled ? (obj.fillColor || obj.color || '#14b8a6') : 'transparent';

        const x = obj.x;
        const y = obj.y;
        const w = obj.w;
        const h = obj.h;

        switch (obj.shapeType) {
            // FLOWCHART SHAPES
            case 'process':
                ctx.beginPath();
                ctx.rect(x, y, w, h);
                if (obj.filled) ctx.fill();
                ctx.stroke();
                break;

            case 'decision':
                ctx.beginPath();
                ctx.moveTo(x + w / 2, y);
                ctx.lineTo(x + w, y + h / 2);
                ctx.lineTo(x + w / 2, y + h);
                ctx.lineTo(x, y + h / 2);
                ctx.closePath();
                if (obj.filled) ctx.fill();
                ctx.stroke();
                break;

            case 'terminator':
                const radius = Math.min(w, h) / 2;
                ctx.beginPath();
                ctx.moveTo(x + radius, y);
                ctx.lineTo(x + w - radius, y);
                ctx.arcTo(x + w, y, x + w, y + radius, radius);
                ctx.lineTo(x + w, y + h - radius);
                ctx.arcTo(x + w, y + h, x + w - radius, y + h, radius);
                ctx.lineTo(x + radius, y + h);
                ctx.arcTo(x, y + h, x, y + h - radius, radius);
                ctx.lineTo(x, y + radius);
                ctx.arcTo(x, y, x + radius, y, radius);
                ctx.closePath();
                if (obj.filled) ctx.fill();
                ctx.stroke();
                break;

            case 'data':
                ctx.beginPath();
                const skew = w * 0.15;
                ctx.moveTo(x + skew, y);
                ctx.lineTo(x + w, y);
                ctx.lineTo(x + w - skew, y + h);
                ctx.lineTo(x, y + h);
                ctx.closePath();
                if (obj.filled) ctx.fill();
                ctx.stroke();
                break;

            case 'document':
                ctx.beginPath();
                ctx.moveTo(x, y);
                ctx.lineTo(x + w, y);
                ctx.lineTo(x + w, y + h - h * 0.15);
                ctx.bezierCurveTo(
                    x + w * 0.75, y + h,
                    x + w * 0.25, y + h - h * 0.3,
                    x, y + h - h * 0.15
                );
                ctx.closePath();
                if (obj.filled) ctx.fill();
                ctx.stroke();
                break;

            case 'predefinedProcess':
                ctx.beginPath();
                ctx.rect(x, y, w, h);
                if (obj.filled) ctx.fill();
                ctx.stroke();
                // Double lines on sides
                ctx.beginPath();
                ctx.moveTo(x + w * 0.1, y);
                ctx.lineTo(x + w * 0.1, y + h);
                ctx.moveTo(x + w * 0.9, y);
                ctx.lineTo(x + w * 0.9, y + h);
                ctx.stroke();
                break;

            case 'manualInput':
                ctx.beginPath();
                ctx.moveTo(x, y + h * 0.2);
                ctx.lineTo(x + w, y);
                ctx.lineTo(x + w, y + h);
                ctx.lineTo(x, y + h);
                ctx.closePath();
                if (obj.filled) ctx.fill();
                ctx.stroke();
                break;

            case 'preparation':
                const hexOffset = h / 2;
                ctx.beginPath();
                ctx.moveTo(x + hexOffset, y);
                ctx.lineTo(x + w - hexOffset, y);
                ctx.lineTo(x + w, y + h / 2);
                ctx.lineTo(x + w - hexOffset, y + h);
                ctx.lineTo(x + hexOffset, y + h);
                ctx.lineTo(x, y + h / 2);
                ctx.closePath();
                if (obj.filled) ctx.fill();
                ctx.stroke();
                break;

            // CONNECTORS - Use actual start/end coordinates for proper directional drawing
            case 'arrow':
                IWB.drawArrow(ctx, obj.startX || x, obj.startY || (y + h / 2), obj.endX || (x + w), obj.endY || (y + h / 2), obj.strokeWidth);
                break;

            case 'doubleArrow':
                IWB.drawDoubleArrow(ctx, obj.startX || x, obj.startY || (y + h / 2), obj.endX || (x + w), obj.endY || (y + h / 2), obj.strokeWidth);
                break;

            case 'line':
                ctx.beginPath();
                ctx.moveTo(obj.startX || x, obj.startY || (y + h / 2));
                ctx.lineTo(obj.endX || (x + w), obj.endY || (y + h / 2));
                ctx.stroke();
                break;

            case 'curvedArrow':
                const curveAmount = Math.sqrt(Math.pow(obj.endX - obj.startX, 2) + Math.pow(obj.endY - obj.startY, 2)) / 4;
                IWB.drawCurvedArrow(ctx, obj.startX || x, obj.startY || (y + h / 2), obj.endX || (x + w), obj.endY || (y + h / 2), curveAmount || (w / 4), obj.strokeWidth);
                break;

            case 'elbowArrowHV':
                IWB.drawElbowArrowHV(ctx, obj.startX || x, obj.startY || (y + h / 2), obj.endX || (x + w), obj.endY || (y + h / 2), obj.strokeWidth);
                break;

            case 'elbowArrowVH':
                IWB.drawElbowArrowVH(ctx, obj.startX || x, obj.startY || (y + h / 2), obj.endX || (x + w), obj.endY || (y + h / 2), obj.strokeWidth);
                break;

            case 'dashedArrow':
                IWB.drawDashedArrow(ctx, obj.startX || x, obj.startY || (y + h / 2), obj.endX || (x + w), obj.endY || (y + h / 2), obj.strokeWidth);
                break;

            case 'thickArrow':
                IWB.drawThickArrow(ctx, obj.startX || x, obj.startY || (y + h / 2), obj.endX || (x + w), obj.endY || (y + h / 2), obj.strokeWidth);
                break;

            case 'circleArrow':
                IWB.drawCircleArrow(ctx, obj.startX || x, obj.startY || (y + h / 2), obj.endX || (x + w), obj.endY || (y + h / 2), obj.strokeWidth);
                break;

            case 'diamondArrow':
                IWB.drawDiamondArrow(ctx, obj.startX || x, obj.startY || (y + h / 2), obj.endX || (x + w), obj.endY || (y + h / 2), obj.strokeWidth);
                break;

            case 'squareArrow':
                IWB.drawSquareArrow(ctx, obj.startX || x, obj.startY || (y + h / 2), obj.endX || (x + w), obj.endY || (y + h / 2), obj.strokeWidth);
                break;

            case 'ballHead':
                IWB.drawBallHeadLine(ctx, obj.startX || x, obj.startY || (y + h / 2), obj.endX || (x + w), obj.endY || (y + h / 2), obj.strokeWidth);
                break;

            case 'doubleBallHead':
                IWB.drawDoubleBallHeadLine(ctx, obj.startX || x, obj.startY || (y + h / 2), obj.endX || (x + w), obj.endY || (y + h / 2), obj.strokeWidth);
                break;

            // INDUSTRY ICONS
            case 'database':
                IWB.drawDatabase(ctx, x, y, w, h, obj.filled);
                break;

            case 'server':
                IWB.drawServer(ctx, x, y, w, h, obj.filled);
                break;

            case 'cloud':
                IWB.drawCloud(ctx, x, y, w, h, obj.filled);
                break;

            case 'user':
                IWB.drawUser(ctx, x, y, w, h, obj.filled);
                break;

            case 'building':
                IWB.drawBuilding(ctx, x, y, w, h, obj.filled);
                break;

            case 'factory':
                IWB.drawFactory(ctx, x, y, w, h, obj.filled);
                break;

            case 'mobile':
                IWB.drawMobile(ctx, x, y, w, h, obj.filled);
                break;

            case 'laptop':
                IWB.drawLaptop(ctx, x, y, w, h, obj.filled);
                break;

            // CALLOUTS
            case 'thought':
                IWB.drawThoughtBubble(ctx, x, y, w, h, obj.filled);
                break;

            case 'speech':
                IWB.drawSpeechBubble(ctx, x, y, w, h, obj.filled);
                break;

            case 'callout':
                IWB.drawCallout(ctx, x, y, w, h, obj.filled);
                break;

            case 'note':
                IWB.drawStickyNote(ctx, x, y, w, h, obj.filled);
                break;
        }

        ctx.restore();
    };

    // ========================================================================
    // CONNECTOR DRAWING HELPERS
    // ========================================================================

    IWB.drawArrow = function(ctx, x1, y1, x2, y2, lineWidth) {
        const dx = x2 - x1;
        const dy = y2 - y1;
        const distance = Math.sqrt(dx * dx + dy * dy);
        const headLength = Math.min(20, distance / 4);
        const angle = Math.atan2(dy, dx);

        // Draw line
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();

        // Draw arrowhead (filled triangle)
        ctx.save();
        ctx.fillStyle = ctx.strokeStyle;
        ctx.beginPath();
        ctx.moveTo(x2, y2);
        ctx.lineTo(x2 - headLength * Math.cos(angle - Math.PI / 6), y2 - headLength * Math.sin(angle - Math.PI / 6));
        ctx.lineTo(x2 - headLength * Math.cos(angle + Math.PI / 6), y2 - headLength * Math.sin(angle + Math.PI / 6));
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    };

    IWB.drawDoubleArrow = function(ctx, x1, y1, x2, y2, lineWidth) {
        const dx = x2 - x1;
        const dy = y2 - y1;
        const distance = Math.sqrt(dx * dx + dy * dy);
        const headLength = Math.min(20, distance / 4);
        const angle = Math.atan2(dy, dx);

        // Draw line
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();

        ctx.save();
        ctx.fillStyle = ctx.strokeStyle;

        // Left arrowhead
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x1 + headLength * Math.cos(angle - Math.PI / 6), y1 + headLength * Math.sin(angle - Math.PI / 6));
        ctx.lineTo(x1 + headLength * Math.cos(angle + Math.PI / 6), y1 + headLength * Math.sin(angle + Math.PI / 6));
        ctx.closePath();
        ctx.fill();

        // Right arrowhead
        ctx.beginPath();
        ctx.moveTo(x2, y2);
        ctx.lineTo(x2 - headLength * Math.cos(angle - Math.PI / 6), y2 - headLength * Math.sin(angle - Math.PI / 6));
        ctx.lineTo(x2 - headLength * Math.cos(angle + Math.PI / 6), y2 - headLength * Math.sin(angle + Math.PI / 6));
        ctx.closePath();
        ctx.fill();
        
        ctx.restore();
    };

    IWB.drawCurvedArrow = function(ctx, x1, y1, x2, y2, curve, lineWidth) {
        // Calculate distance and angle
        const dx = x2 - x1;
        const dy = y2 - y1;
        const distance = Math.sqrt(dx * dx + dy * dy);
        const angle = Math.atan2(dy, dx);
        const perpAngle = angle + Math.PI / 2;
        
        // Fixed wave properties
        const waveLength = 60; // Fixed wavelength in pixels
        const waveAmplitude = 25; // Fixed wave height in pixels
        const numWaves = Math.max(1, Math.floor(distance / waveLength));
        
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        
        // Draw smooth wavy line using multiple bezier curves
        for (let i = 0; i < numWaves; i++) {
            const t1 = i / numWaves;
            const t2 = (i + 0.5) / numWaves;
            const t3 = (i + 1) / numWaves;
            
            // Points along the straight line
            const p1x = x1 + dx * t1;
            const p1y = y1 + dy * t1;
            const p2x = x1 + dx * t2;
            const p2y = y1 + dy * t2;
            const p3x = x1 + dx * t3;
            const p3y = y1 + dy * t3;
            
            // Offset control point perpendicular to line (alternating sides)
            const side = (i % 2 === 0) ? 1 : -1;
            const cp1x = p2x + Math.cos(perpAngle) * waveAmplitude * side;
            const cp1y = p2y + Math.sin(perpAngle) * waveAmplitude * side;
            
            ctx.quadraticCurveTo(cp1x, cp1y, p3x, p3y);
        }
        
        ctx.stroke();

        // Draw arrowhead at the end
        const headLength = Math.min(20, distance / 4);
        // Calculate tangent for last wave segment
        const t = 0.95;
        const lastWaveT = (numWaves - 1) / numWaves;
        const lastP2x = x1 + dx * (lastWaveT + 0.5 / numWaves);
        const lastP2y = y1 + dy * (lastWaveT + 0.5 / numWaves);
        const lastSide = ((numWaves - 1) % 2 === 0) ? 1 : -1;
        const lastCpx = lastP2x + Math.cos(perpAngle) * waveAmplitude * lastSide;
        const lastCpy = lastP2y + Math.sin(perpAngle) * waveAmplitude * lastSide;
        
        // Approximate tangent at end
        const endAngle = Math.atan2(y2 - lastCpy, x2 - lastCpx);

        ctx.save();
        ctx.fillStyle = ctx.strokeStyle;
        ctx.beginPath();
        ctx.moveTo(x2, y2);
        ctx.lineTo(x2 - headLength * Math.cos(endAngle - Math.PI / 6), y2 - headLength * Math.sin(endAngle - Math.PI / 6));
        ctx.lineTo(x2 - headLength * Math.cos(endAngle + Math.PI / 6), y2 - headLength * Math.sin(endAngle + Math.PI / 6));
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    };

    IWB.drawElbowArrowHV = function(ctx, x1, y1, x2, y2, lineWidth) {
        // Horizontal then Vertical: draws horizontal from start, then vertical to end
        const dx = x2 - x1;
        const dy = y2 - y1;
        const distance = Math.sqrt(dx * dx + dy * dy);
        const headLength = Math.min(20, distance / 4);
        
        // Calculate elbow point - go horizontal to x2, then vertical to y2
        const elbowX = x2;
        const elbowY = y1;
        
        // Rounded corner radius (adaptive based on distance)
        const cornerRadius = Math.min(20, Math.abs(dx) / 4, Math.abs(dy) / 4);

        // Draw the elbow path with rounded corner
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        
        // Horizontal segment (stop before corner)
        const stopX = elbowX - Math.sign(dx) * cornerRadius;
        ctx.lineTo(stopX, y1);
        
        // Rounded corner using arcTo
        ctx.arcTo(elbowX, elbowY, elbowX, y2, cornerRadius);
        
        // Vertical segment to end point
        ctx.lineTo(x2, y2);
        ctx.stroke();

        // Calculate angle for arrowhead (vertical direction)
        const endAngle = Math.atan2(y2 - elbowY, x2 - elbowX);

        // Draw arrowhead at the end
        ctx.save();
        ctx.fillStyle = ctx.strokeStyle;
        ctx.beginPath();
        ctx.moveTo(x2, y2);
        ctx.lineTo(x2 - headLength * Math.cos(endAngle - Math.PI / 6), y2 - headLength * Math.sin(endAngle - Math.PI / 6));
        ctx.lineTo(x2 - headLength * Math.cos(endAngle + Math.PI / 6), y2 - headLength * Math.sin(endAngle + Math.PI / 6));
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    };

    IWB.drawElbowArrowVH = function(ctx, x1, y1, x2, y2, lineWidth) {
        // Vertical then Horizontal: draws vertical from start, then horizontal to end
        const dx = x2 - x1;
        const dy = y2 - y1;
        const distance = Math.sqrt(dx * dx + dy * dy);
        const headLength = Math.min(20, distance / 4);
        
        // Calculate elbow point - go vertical to y2, then horizontal to x2
        const elbowX = x1;
        const elbowY = y2;
        
        // Rounded corner radius (adaptive based on distance)
        const cornerRadius = Math.min(20, Math.abs(dx) / 4, Math.abs(dy) / 4);

        // Draw the elbow path with rounded corner
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        
        // Vertical segment (stop before corner)
        const stopY = elbowY - Math.sign(dy) * cornerRadius;
        ctx.lineTo(x1, stopY);
        
        // Rounded corner using arcTo
        ctx.arcTo(elbowX, elbowY, x2, elbowY, cornerRadius);
        
        // Horizontal segment to end point
        ctx.lineTo(x2, y2);
        ctx.stroke();

        // Calculate angle for arrowhead (horizontal direction)
        const endAngle = Math.atan2(y2 - elbowY, x2 - elbowX);

        // Draw arrowhead at the end
        ctx.save();
        ctx.fillStyle = ctx.strokeStyle;
        ctx.beginPath();
        ctx.moveTo(x2, y2);
        ctx.lineTo(x2 - headLength * Math.cos(endAngle - Math.PI / 6), y2 - headLength * Math.sin(endAngle - Math.PI / 6));
        ctx.lineTo(x2 - headLength * Math.cos(endAngle + Math.PI / 6), y2 - headLength * Math.sin(endAngle + Math.PI / 6));
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    };

    IWB.drawDashedArrow = function(ctx, x1, y1, x2, y2, lineWidth) {
        const dx = x2 - x1;
        const dy = y2 - y1;
        const distance = Math.sqrt(dx * dx + dy * dy);
        const headLength = Math.min(20, distance / 4);
        const angle = Math.atan2(dy, dx);

        // Draw dashed line
        ctx.save();
        ctx.setLineDash([10, 5]); // 10px dash, 5px gap
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
        ctx.restore();

        // Draw solid arrowhead
        ctx.save();
        ctx.fillStyle = ctx.strokeStyle;
        ctx.beginPath();
        ctx.moveTo(x2, y2);
        ctx.lineTo(x2 - headLength * Math.cos(angle - Math.PI / 6), y2 - headLength * Math.sin(angle - Math.PI / 6));
        ctx.lineTo(x2 - headLength * Math.cos(angle + Math.PI / 6), y2 - headLength * Math.sin(angle + Math.PI / 6));
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    };

    IWB.drawThickArrow = function(ctx, x1, y1, x2, y2, lineWidth) {
        const dx = x2 - x1;
        const dy = y2 - y1;
        const distance = Math.sqrt(dx * dx + dy * dy);
        const angle = Math.atan2(dy, dx);
        
        const shaftWidth = Math.max(lineWidth * 3, 12);
        const headWidth = shaftWidth * 2;
        const headLength = Math.min(30, distance / 3);
        
        ctx.save();
        ctx.fillStyle = ctx.strokeStyle;
        ctx.beginPath();
        
        // Calculate perpendicular offset
        const perpX = -Math.sin(angle);
        const perpY = Math.cos(angle);
        
        // Shaft start (left side)
        ctx.moveTo(x1 + perpX * shaftWidth / 2, y1 + perpY * shaftWidth / 2);
        
        // Shaft end (left side)
        const shaftEndX = x2 - Math.cos(angle) * headLength;
        const shaftEndY = y2 - Math.sin(angle) * headLength;
        ctx.lineTo(shaftEndX + perpX * shaftWidth / 2, shaftEndY + perpY * shaftWidth / 2);
        
        // Head left corner
        ctx.lineTo(shaftEndX + perpX * headWidth / 2, shaftEndY + perpY * headWidth / 2);
        
        // Arrow point
        ctx.lineTo(x2, y2);
        
        // Head right corner
        ctx.lineTo(shaftEndX - perpX * headWidth / 2, shaftEndY - perpY * headWidth / 2);
        
        // Shaft end (right side)
        ctx.lineTo(shaftEndX - perpX * shaftWidth / 2, shaftEndY - perpY * shaftWidth / 2);
        
        // Shaft start (right side)
        ctx.lineTo(x1 - perpX * shaftWidth / 2, y1 - perpY * shaftWidth / 2);
        
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    };

    IWB.drawCircleArrow = function(ctx, x1, y1, x2, y2, lineWidth) {
        const dx = x2 - x1;
        const dy = y2 - y1;
        const distance = Math.sqrt(dx * dx + dy * dy);
        const headLength = Math.min(20, distance / 4);
        const angle = Math.atan2(dy, dx);
        const circleRadius = Math.min(10, distance / 10);

        // Draw line from circle to end
        const lineStartX = x1 + Math.cos(angle) * circleRadius;
        const lineStartY = y1 + Math.sin(angle) * circleRadius;
        
        ctx.beginPath();
        ctx.moveTo(lineStartX, lineStartY);
        ctx.lineTo(x2, y2);
        ctx.stroke();

        // Draw circle at start
        ctx.save();
        ctx.fillStyle = ctx.strokeStyle;
        ctx.beginPath();
        ctx.arc(x1, y1, circleRadius, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

        // Draw arrowhead at end
        ctx.save();
        ctx.fillStyle = ctx.strokeStyle;
        ctx.beginPath();
        ctx.moveTo(x2, y2);
        ctx.lineTo(x2 - headLength * Math.cos(angle - Math.PI / 6), y2 - headLength * Math.sin(angle - Math.PI / 6));
        ctx.lineTo(x2 - headLength * Math.cos(angle + Math.PI / 6), y2 - headLength * Math.sin(angle + Math.PI / 6));
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    };

    IWB.drawDiamondArrow = function(ctx, x1, y1, x2, y2, lineWidth) {
        const dx = x2 - x1;
        const dy = y2 - y1;
        const distance = Math.sqrt(dx * dx + dy * dy);
        const headLength = Math.min(20, distance / 4);
        const angle = Math.atan2(dy, dx);
        const diamondSize = Math.min(12, distance / 8);

        // Draw line from diamond to end
        const lineStartX = x1 + Math.cos(angle) * diamondSize;
        const lineStartY = y1 + Math.sin(angle) * diamondSize;
        
        ctx.beginPath();
        ctx.moveTo(lineStartX, lineStartY);
        ctx.lineTo(x2, y2);
        ctx.stroke();

        // Draw diamond at start
        ctx.save();
        ctx.fillStyle = ctx.strokeStyle;
        ctx.beginPath();
        ctx.moveTo(x1 + Math.cos(angle) * diamondSize, y1 + Math.sin(angle) * diamondSize);
        ctx.lineTo(x1 - Math.sin(angle) * diamondSize / 2, y1 + Math.cos(angle) * diamondSize / 2);
        ctx.lineTo(x1 - Math.cos(angle) * diamondSize, y1 - Math.sin(angle) * diamondSize);
        ctx.lineTo(x1 + Math.sin(angle) * diamondSize / 2, y1 - Math.cos(angle) * diamondSize / 2);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        ctx.restore();

        // Draw arrowhead at end
        ctx.save();
        ctx.fillStyle = ctx.strokeStyle;
        ctx.beginPath();
        ctx.moveTo(x2, y2);
        ctx.lineTo(x2 - headLength * Math.cos(angle - Math.PI / 6), y2 - headLength * Math.sin(angle - Math.PI / 6));
        ctx.lineTo(x2 - headLength * Math.cos(angle + Math.PI / 6), y2 - headLength * Math.sin(angle + Math.PI / 6));
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    };

    IWB.drawSquareArrow = function(ctx, x1, y1, x2, y2, lineWidth) {
        const dx = x2 - x1;
        const dy = y2 - y1;
        const distance = Math.sqrt(dx * dx + dy * dy);
        const headLength = Math.min(20, distance / 4);
        const angle = Math.atan2(dy, dx);
        const squareSize = Math.min(10, distance / 10);

        // Draw line from square to end
        const lineStartX = x1 + Math.cos(angle) * squareSize;
        const lineStartY = y1 + Math.sin(angle) * squareSize;
        
        ctx.beginPath();
        ctx.moveTo(lineStartX, lineStartY);
        ctx.lineTo(x2, y2);
        ctx.stroke();

        // Draw square at start
        ctx.save();
        ctx.fillStyle = ctx.strokeStyle;
        ctx.translate(x1, y1);
        ctx.rotate(angle);
        ctx.beginPath();
        ctx.rect(-squareSize / 2, -squareSize / 2, squareSize, squareSize);
        ctx.fill();
        ctx.stroke();
        ctx.restore();

        // Draw arrowhead at end
        ctx.save();
        ctx.fillStyle = ctx.strokeStyle;
        ctx.beginPath();
        ctx.moveTo(x2, y2);
        ctx.lineTo(x2 - headLength * Math.cos(angle - Math.PI / 6), y2 - headLength * Math.sin(angle - Math.PI / 6));
        ctx.lineTo(x2 - headLength * Math.cos(angle + Math.PI / 6), y2 - headLength * Math.sin(angle + Math.PI / 6));
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    };

    IWB.drawBallHeadLine = function(ctx, x1, y1, x2, y2, lineWidth) {
        const dx = x2 - x1;
        const dy = y2 - y1;
        const distance = Math.sqrt(dx * dx + dy * dy);
        const ballRadius = Math.min(8, distance / 10);
        const angle = Math.atan2(dy, dx);
        
        // Start line after the ball
        const lineStartX = x1 + ballRadius * Math.cos(angle);
        const lineStartY = y1 + ballRadius * Math.sin(angle);

        // Draw line
        ctx.beginPath();
        ctx.moveTo(lineStartX, lineStartY);
        ctx.lineTo(x2, y2);
        ctx.stroke();

        // Draw ball at start
        ctx.save();
        ctx.fillStyle = ctx.strokeStyle;
        ctx.beginPath();
        ctx.arc(x1, y1, ballRadius, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    };

    IWB.drawDoubleBallHeadLine = function(ctx, x1, y1, x2, y2, lineWidth) {
        const dx = x2 - x1;
        const dy = y2 - y1;
        const distance = Math.sqrt(dx * dx + dy * dy);
        const ballRadius = Math.min(8, distance / 10);
        const angle = Math.atan2(dy, dx);
        
        // Line starts after first ball and ends before second ball
        const lineStartX = x1 + ballRadius * Math.cos(angle);
        const lineStartY = y1 + ballRadius * Math.sin(angle);
        const lineEndX = x2 - ballRadius * Math.cos(angle);
        const lineEndY = y2 - ballRadius * Math.sin(angle);

        // Draw line
        ctx.beginPath();
        ctx.moveTo(lineStartX, lineStartY);
        ctx.lineTo(lineEndX, lineEndY);
        ctx.stroke();

        ctx.save();
        ctx.fillStyle = ctx.strokeStyle;

        // Draw ball at start
        ctx.beginPath();
        ctx.arc(x1, y1, ballRadius, 0, Math.PI * 2);
        ctx.fill();

        // Draw ball at end
        ctx.beginPath();
        ctx.arc(x2, y2, ballRadius, 0, Math.PI * 2);
        ctx.fill();
        
        ctx.restore();
    };

    // ========================================================================
    // INDUSTRY ICON DRAWING HELPERS
    // ========================================================================

    IWB.drawDatabase = function(ctx, x, y, w, h, filled) {
        const ellipseH = h * 0.15;

        ctx.beginPath();
        ctx.ellipse(x + w / 2, y + ellipseH, w / 2, ellipseH, 0, 0, Math.PI * 2);
        if (filled) ctx.fill();
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(x, y + ellipseH);
        ctx.lineTo(x, y + h - ellipseH);
        ctx.moveTo(x + w, y + ellipseH);
        ctx.lineTo(x + w, y + h - ellipseH);
        ctx.stroke();

        ctx.beginPath();
        ctx.ellipse(x + w / 2, y + h - ellipseH, w / 2, ellipseH, 0, 0, Math.PI * 2);
        if (filled) ctx.fill();
        ctx.stroke();

        // Middle separator
        ctx.beginPath();
        ctx.ellipse(x + w / 2, y + h / 2, w / 2, ellipseH, 0, 0, Math.PI);
        ctx.stroke();
    };

    IWB.drawServer = function(ctx, x, y, w, h, filled) {
        const sectionH = h / 3;

        for (let i = 0; i < 3; i++) {
            const sY = y + i * sectionH;
            ctx.beginPath();
            ctx.rect(x, sY, w, sectionH);
            if (filled) ctx.fill();
            ctx.stroke();

            // LED indicators
            ctx.beginPath();
            ctx.arc(x + w * 0.15, sY + sectionH / 2, w * 0.05, 0, Math.PI * 2);
            ctx.fillStyle = '#00ff00';
            ctx.fill();
            ctx.strokeStyle = ctx.strokeStyle;
        }
    };

    IWB.drawCloud = function(ctx, x, y, w, h, filled) {
        ctx.beginPath();
        ctx.arc(x + w * 0.25, y + h * 0.4, w * 0.25, Math.PI * 0.5, Math.PI * 1.5);
        ctx.arc(x + w * 0.5, y + h * 0.25, w * 0.25, Math.PI * 1, Math.PI * 2);
        ctx.arc(x + w * 0.75, y + h * 0.4, w * 0.25, Math.PI * 1.5, Math.PI * 0.5);
        ctx.arc(x + w * 0.5, y + h * 0.7, w * 0.35, 0, Math.PI);
        ctx.closePath();
        if (filled) ctx.fill();
        ctx.stroke();
    };

    IWB.drawUser = function(ctx, x, y, w, h, filled) {
        const headRadius = Math.min(w, h) * 0.25;
        const bodyY = y + h * 0.4;

        ctx.beginPath();
        ctx.arc(x + w / 2, y + headRadius, headRadius, 0, Math.PI * 2);
        if (filled) ctx.fill();
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(x + w / 2, bodyY + headRadius, w * 0.4, Math.PI * 1.2, Math.PI * 1.8);
        ctx.lineTo(x + w / 2, y + h);
        ctx.lineTo(x + w / 2, bodyY + headRadius);
        ctx.closePath();
        if (filled) ctx.fill();
        ctx.stroke();
    };

    IWB.drawBuilding = function(ctx, x, y, w, h, filled) {
        ctx.beginPath();
        ctx.rect(x, y, w, h);
        if (filled) ctx.fill();
        ctx.stroke();

        const windowW = w / 5;
        const windowH = h / 7;
        for (let row = 0; row < 4; row++) {
            for (let col = 0; col < 3; col++) {
                ctx.beginPath();
                ctx.rect(x + windowW + col * windowW * 1.5, y + windowH + row * windowH * 1.5, windowW, windowH);
                ctx.stroke();
            }
        }
    };

    IWB.drawFactory = function(ctx, x, y, w, h, filled) {
        const roofH = h * 0.3;
        const chimneyW = w * 0.15;

        ctx.beginPath();
        ctx.moveTo(x, y + roofH);
        ctx.lineTo(x + w / 2, y);
        ctx.lineTo(x + w, y + roofH);
        ctx.lineTo(x + w, y + h);
        ctx.lineTo(x, y + h);
        ctx.closePath();
        if (filled) ctx.fill();
        ctx.stroke();

        ctx.beginPath();
        ctx.rect(x + w * 0.25, y - roofH / 2, chimneyW, roofH / 2);
        ctx.rect(x + w * 0.6, y - roofH / 3, chimneyW, roofH / 3);
        if (filled) ctx.fill();
        ctx.stroke();
    };

    IWB.drawMobile = function(ctx, x, y, w, h, filled) {
        const cornerRadius = Math.min(w, h) * 0.1;

        ctx.beginPath();
        ctx.roundRect(x, y, w, h, cornerRadius);
        if (filled) ctx.fill();
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(x + w / 2, y + h * 0.9, w * 0.08, 0, Math.PI * 2);
        ctx.stroke();

        ctx.beginPath();
        ctx.rect(x + w * 0.1, y + h * 0.05, w * 0.8, h * 0.75);
        ctx.stroke();
    };

    IWB.drawLaptop = function(ctx, x, y, w, h, filled) {
        const screenH = h * 0.65;

        ctx.beginPath();
        ctx.rect(x + w * 0.1, y, w * 0.8, screenH);
        if (filled) ctx.fill();
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(x, y + screenH);
        ctx.lineTo(x + w, y + screenH);
        ctx.lineTo(x + w * 0.95, y + h);
        ctx.lineTo(x + w * 0.05, y + h);
        ctx.closePath();
        if (filled) ctx.fill();
        ctx.stroke();
    };

    // ========================================================================
    // CALLOUT DRAWING HELPERS
    // ========================================================================

    IWB.drawThoughtBubble = function(ctx, x, y, w, h, filled) {
        ctx.beginPath();
        ctx.ellipse(x + w / 2, y + h * 0.4, w * 0.45, h * 0.35, 0, 0, Math.PI * 2);
        if (filled) ctx.fill();
        ctx.stroke();

        const bubble1R = w * 0.1;
        const bubble2R = w * 0.07;
        const bubble3R = w * 0.05;

        ctx.beginPath();
        ctx.arc(x + w * 0.2, y + h * 0.85, bubble1R, 0, Math.PI * 2);
        if (filled) ctx.fill();
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(x + w * 0.1, y + h * 0.95, bubble2R, 0, Math.PI * 2);
        if (filled) ctx.fill();
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(x + w * 0.05, y + h, bubble3R, 0, Math.PI * 2);
        if (filled) ctx.fill();
        ctx.stroke();
    };

    IWB.drawSpeechBubble = function(ctx, x, y, w, h, filled) {
        const bubbleH = h * 0.75;
        const cornerRadius = Math.min(w, h) * 0.1;

        ctx.beginPath();
        ctx.roundRect(x, y, w, bubbleH, cornerRadius);
        if (filled) ctx.fill();
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(x + w * 0.2, y + bubbleH);
        ctx.lineTo(x + w * 0.15, y + h);
        ctx.lineTo(x + w * 0.35, y + bubbleH);
        ctx.closePath();
        if (filled) ctx.fill();
        ctx.stroke();
    };

    IWB.drawCallout = function(ctx, x, y, w, h, filled) {
        const cornerRadius = Math.min(w, h) * 0.05;
        const pointerW = w * 0.15;

        ctx.beginPath();
        ctx.moveTo(x + cornerRadius, y);
        ctx.lineTo(x + w - cornerRadius, y);
        ctx.arcTo(x + w, y, x + w, y + cornerRadius, cornerRadius);
        ctx.lineTo(x + w, y + h - pointerW);
        ctx.lineTo(x + w + pointerW, y + h);
        ctx.lineTo(x + w, y + h);
        ctx.lineTo(x + cornerRadius, y + h);
        ctx.arcTo(x, y + h, x, y + h - cornerRadius, cornerRadius);
        ctx.lineTo(x, y + cornerRadius);
        ctx.arcTo(x, y, x + cornerRadius, y, cornerRadius);
        ctx.closePath();
        if (filled) ctx.fill();
        ctx.stroke();
    };

    IWB.drawStickyNote = function(ctx, x, y, w, h, filled) {
        const foldSize = Math.min(w, h) * 0.15;

        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x + w - foldSize, y);
        ctx.lineTo(x + w, y + foldSize);
        ctx.lineTo(x + w, y + h);
        ctx.lineTo(x, y + h);
        ctx.closePath();
        if (filled) ctx.fill();
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(x + w - foldSize, y);
        ctx.lineTo(x + w - foldSize, y + foldSize);
        ctx.lineTo(x + w, y + foldSize);
        ctx.stroke();
    };

    /**
     * Draw current shape being drawn (preview)
     */
    IWB.drawCurrentShape = function(ctx, color, strokeWidth) {
        if (!IWB.currentShape || !IWB.currentShapeType) return;

        const tempObj = {
            type: 'shape',
            shapeType: IWB.currentShapeType,
            x: IWB.currentShape.x,
            y: IWB.currentShape.y,
            w: IWB.currentShape.w,
            h: IWB.currentShape.h,
            color: color,
            strokeWidth: strokeWidth,
            filled: false,
            // Include start/end for connectors preview
            startX: IWB.shapeStart ? IWB.shapeStart.x : IWB.currentShape.x,
            startY: IWB.shapeStart ? IWB.shapeStart.y : IWB.currentShape.y,
            endX: IWB.currentShape.endX,
            endY: IWB.currentShape.endY
        };

        ctx.save();
        ctx.globalAlpha = 0.7;
        IWB.drawShape(ctx, tempObj);
        ctx.restore();
    };

    /**
     * Check if current tool is a shape tool
     */
    IWB.isShapeTool = function() {
        if (!IWB.currentTool) return false;
        
        for (const category in IWB.SHAPE_CATEGORIES) {
            if (IWB.SHAPE_CATEGORIES[category].shapes[IWB.currentTool]) {
                return true;
            }
        }
        return false;
    };

    console.log('Infinite Whiteboard Shapes module loaded');

})(window);
