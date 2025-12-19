/**
 * Whiteboard Selection & Transform Module
 * Handles object selection, resizing, rotation, hit-testing, and positioning
 */

/**
 * Get selection handle at point
 * @param {Array} handles - Array of handle objects
 * @param {Object} pt - Point {x, y}
 * @returns {Object|undefined} - Handle object or undefined
 */
function getHandleAt(handles, pt) {
  const handleSize = 8;
  return handles.find(h => pt.x >= h.x && pt.x <= h.x + handleSize &&
                           pt.y >= h.y && pt.y <= h.y + handleSize);
}

/**
 * Get multi-selection handle at point
 * @param {Array} handles - Array of handle objects with w/h
 * @param {Object} pt - Point {x, y}
 * @returns {Object|undefined} - Handle object or undefined
 */
function getMultiHandleAt(handles, pt) {
  return handles.find(h => pt.x >= h.x && pt.x <= h.x + h.w &&
                           pt.y >= h.y && pt.y <= h.y + h.h);
}

/**
 * Get cursor style for handle type
 * @param {string} handleType - Type of handle
 * @returns {string} - CSS cursor value
 */
function getCursorForHandle(handleType) {
  switch(handleType) {
    case 'resize-nw': case 'resize-se': return 'nw-resize';
    case 'resize-ne': case 'resize-sw': return 'ne-resize';
    case 'resize-n': case 'resize-s': return 'n-resize';
    case 'resize-e': case 'resize-w': return 'e-resize';
    case 'rotate': return 'grab';
    default: return 'default';
  }
}

/**
 * Get center point of object
 * @param {Object} o - Object
 * @returns {Object} - Center point {x, y}
 */
function getObjectCenter(o) {
  const b = window.getBounds ? window.getBounds(o) : {x: 0, y: 0, w: 0, h: 0};
  return { x: b.x + b.w/2, y: b.y + b.h/2 };
}

/**
 * Rotate a point around a center
 * @param {number} px - Point x
 * @param {number} py - Point y
 * @param {number} cx - Center x
 * @param {number} cy - Center y
 * @param {number} angle - Rotation angle in radians
 * @returns {Object} - Rotated point {x, y}
 */
function rotatePoint(px, py, cx, cy, angle) {
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  const dx = px - cx;
  const dy = py - cy;
  return {
    x: cx + dx * cos - dy * sin,
    y: cy + dx * sin + dy * cos
  };
}

/**
 * Perform rotation on object
 * @param {Object} o - Object to rotate
 * @param {number} currentAngle - Current rotation angle
 * @param {number} initialAngle - Initial rotation angle
 */
function performRotation(o, currentAngle, initialAngle) {
  const originalPositions = window.originalPositions || new Map();
  const center = originalPositions.get(o.id)?.center;
  if(!center) return;
  
  const deltaAngle = currentAngle - initialAngle;
  
  if(o.type === 'image' || o.type === 'text') {
    o.props.rotation = (o.props.rotation || 0) + deltaAngle;
  } else if(o.type === 'stroke') {
    const originalPath = originalPositions.get(o.id)?.path || [];
    o.props.path = originalPath.map(pt => 
      rotatePoint(pt.x, pt.y, center.x, center.y, deltaAngle)
    );
  }
}

/**
 * Get bounding box for object
 * @param {Object} o - Object
 * @returns {Object} - Bounds {x, y, w, h}
 */
function getBounds(o) {
  const canvas = document.getElementById('board-canvas');
  const ctx = canvas.getContext('2d');
  const userPrefs = window.userPrefs || {};
  const autoWrapTextByWords = window.autoWrapTextByWords || ((text) => text);
  
  if(o.type === 'image') return {x: o.props.x, y: o.props.y, w: o.props.w, h: o.props.h};

  if(o.type === 'text') {
    const fs = o.props.fontSize || 24;
    ctx.save();
    ctx.font = fs + 'px sans-serif';
    const maxWordsPerLine = o.props.maxWordsPerLine || userPrefs.maxWordsPerLine || 10;
    const wrappedText = autoWrapTextByWords(o.props.text || '', maxWordsPerLine);
    const lines = wrappedText.split('\n');
    let maxWidth = 0;
    lines.forEach(line => {
      const m = ctx.measureText(line);
      maxWidth = Math.max(maxWidth, m.width);
    });
    const lineHeight = fs * 1.2;
    const totalHeight = lines.length * lineHeight;
    ctx.restore();
    return { x: o.props.x, y: o.props.y - fs, w: maxWidth, h: totalHeight };
  }

  const pts = o.props.path || [];
  if(!pts.length) return {x: 0, y: 0, w: 0, h: 0};
  const xs = pts.map(p => p.x), ys = pts.map(p => p.y);
  const minx = Math.min(...xs) - o.props.size, maxx = Math.max(...xs) + o.props.size;
  const miny = Math.min(...ys) - o.props.size, maxy = Math.max(...ys) + o.props.size;
  return {x: minx, y: miny, w: maxx - minx, h: maxy - miny};
}

/**
 * Create path for stroke object
 * @param {Object} o - Stroke object
 */
function pathForStroke(o) {
  const canvas = document.getElementById('board-canvas');
  const ctx = canvas.getContext('2d');
  const p = o.props.path || [];
  if(p.length === 0) return;
  ctx.beginPath();
  if (window.createShapePath) {
    window.createShapePath(ctx, o);
  }
}

/**
 * Check if point is on object
 * @param {Object} o - Object
 * @param {Object} pt - Point {x, y}
 * @returns {boolean}
 */
function isPointOnObject(o, pt) {
  const canvas = document.getElementById('board-canvas');
  const ctx = canvas.getContext('2d');
  
  if(o.type === 'stroke') {
    const strokeType = o.props?.strokeType || o.strokeType;
    
    // Use shapes module for shape hit testing
    if(window.isShapeTool && window.isShapeTool(strokeType)) {
      if (window.isPointOnShape) {
        return window.isPointOnShape(o, pt);
      }
    } else {
      // For other strokes (pen, marker, highlighter, line), check if point is on the stroke path
      const p = o.props.path || [];
      if(p.length === 0) return false;
      ctx.save();
      pathForStroke(o);
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      ctx.lineWidth = o.props.size;
      const hit = ctx.isPointInStroke(pt.x, pt.y);
      ctx.restore();
      return hit;
    }
  } else if(o.type === 'image' || o.type === 'text') {
    const b = getBounds(o);
    return pt.x >= b.x && pt.x <= b.x + b.w && pt.y >= b.y && pt.y <= b.y + b.h;
  }
  return false;
}

/**
 * Pick topmost object at point
 * @param {Object} pt - Point {x, y}
 * @returns {Object|undefined} - Object or undefined
 */
function pickTopMost(pt) {
  const objects = window.objects || [];
  const sorted = [...objects].sort((a, b) => (b.layer - a.layer) || (b.id - a.id));
  return sorted.find(o => isPointOnObject(o, pt));
}

/**
 * Perform resize operation on object
 * @param {Object} o - Object to resize
 * @param {string} handleType - Handle type (resize-nw, resize-ne, etc.)
 * @param {Object} currentMouse - Current mouse position {x, y}
 * @param {Object} initialMouse - Initial mouse position {x, y}
 * @param {Object} initialBounds - Initial bounds {x, y, w, h, fontSize}
 * @param {boolean} shiftPressed - Whether Shift key is pressed (aspect ratio constraint)
 */
function performResize(o, handleType, currentMouse, initialMouse, initialBounds, shiftPressed) {
  const originalPositions = window.originalPositions || new Map();
  const dx = currentMouse.x - initialMouse.x;
  const dy = currentMouse.y - initialMouse.y;
  
  if(o.type === 'image') {
    let newX = initialBounds.x;
    let newY = initialBounds.y;
    let newW = initialBounds.w;
    let newH = initialBounds.h;
    
    switch(handleType) {
      case 'resize-nw':
        newX = initialBounds.x + dx;
        newY = initialBounds.y + dy;
        newW = initialBounds.w - dx;
        newH = initialBounds.h - dy;
        break;
      case 'resize-ne':
        newY = initialBounds.y + dy;
        newW = initialBounds.w + dx;
        newH = initialBounds.h - dy;
        break;
      case 'resize-sw':
        newX = initialBounds.x + dx;
        newW = initialBounds.w - dx;
        newH = initialBounds.h + dy;
        break;
      case 'resize-se':
        newW = initialBounds.w + dx;
        newH = initialBounds.h + dy;
        break;
      case 'resize-n':
        newY = initialBounds.y + dy;
        newH = initialBounds.h - dy;
        break;
      case 'resize-s':
        newH = initialBounds.h + dy;
        break;
      case 'resize-e':
        newW = initialBounds.w + dx;
        break;
      case 'resize-w':
        newX = initialBounds.x + dx;
        newW = initialBounds.w - dx;
        break;
    }
    
    if(shiftPressed) {
      const originalRatio = initialBounds.w / initialBounds.h;
      
      if(handleType.includes('nw') || handleType.includes('ne') || handleType.includes('sw') || handleType.includes('se')) {
        const scaleX = newW / initialBounds.w;
        const scaleY = newH / initialBounds.h;
        const scale = Math.max(Math.abs(scaleX), Math.abs(scaleY));
        
        newW = initialBounds.w * scale * (scaleX >= 0 ? 1 : -1);
        newH = initialBounds.h * scale * (scaleY >= 0 ? 1 : -1);
        
        if(handleType === 'resize-nw') {
          newX = initialBounds.x + initialBounds.w - newW;
          newY = initialBounds.y + initialBounds.h - newH;
        } else if(handleType === 'resize-ne') {
          newY = initialBounds.y + initialBounds.h - newH;
        } else if(handleType === 'resize-sw') {
          newX = initialBounds.x + initialBounds.w - newW;
        }
      } else if(handleType === 'resize-n' || handleType === 'resize-s') {
        newW = newH * originalRatio;
        if(handleType === 'resize-n') {
          newY = initialBounds.y + initialBounds.h - newH;
        }
      } else if(handleType === 'resize-e' || handleType === 'resize-w') {
        newH = newW / originalRatio;
        if(handleType === 'resize-w') {
          newX = initialBounds.x + initialBounds.w - newW;
        }
      }
    }
    
    newW = Math.max(10, Math.abs(newW));
    newH = Math.max(10, Math.abs(newH));
    
    o.props.x = newX;
    o.props.y = newY;
    o.props.w = newW;
    o.props.h = newH;
    
  } else if(o.type === 'text') {
    const scale = 1 + dx/200;
    const newFontSize = Math.max(8, Math.min(160, (initialBounds.fontSize || 24) * scale));
    o.props.fontSize = newFontSize;
    
  } else if(o.type === 'stroke') {
    let scaleX = 1, scaleY = 1;
    let offsetX = 0, offsetY = 0;
    
    switch(handleType) {
      case 'resize-nw':
        scaleX = (initialBounds.w - dx) / initialBounds.w;
        scaleY = (initialBounds.h - dy) / initialBounds.h;
        offsetX = dx;
        offsetY = dy;
        break;
      case 'resize-ne':
        scaleX = (initialBounds.w + dx) / initialBounds.w;
        scaleY = (initialBounds.h - dy) / initialBounds.h;
        offsetY = dy;
        break;
      case 'resize-sw':
        scaleX = (initialBounds.w - dx) / initialBounds.w;
        scaleY = (initialBounds.h + dy) / initialBounds.h;
        offsetX = dx;
        break;
      case 'resize-se':
        scaleX = (initialBounds.w + dx) / initialBounds.w;
        scaleY = (initialBounds.h + dy) / initialBounds.h;
        break;
      case 'resize-n':
        scaleY = (initialBounds.h - dy) / initialBounds.h;
        offsetY = dy;
        break;
      case 'resize-s':
        scaleY = (initialBounds.h + dy) / initialBounds.h;
        break;
      case 'resize-e':
        scaleX = (initialBounds.w + dx) / initialBounds.w;
        break;
      case 'resize-w':
        scaleX = (initialBounds.w - dx) / initialBounds.w;
        offsetX = dx;
        break;
    }
    
    if(shiftPressed) {
      if(handleType.includes('nw') || handleType.includes('ne') || handleType.includes('sw') || handleType.includes('se')) {
        const scale = Math.max(Math.abs(scaleX), Math.abs(scaleY));
        scaleX = scale * (scaleX >= 0 ? 1 : -1);
        scaleY = scale * (scaleY >= 0 ? 1 : -1);
      } else if(handleType === 'resize-n' || handleType === 'resize-s') {
        scaleX = scaleY;
      } else if(handleType === 'resize-e' || handleType === 'resize-w') {
        scaleY = scaleX;
      }
    }
    
    const originalPath = originalPositions.get(o.id) || o.props.path;
    o.props.path = originalPath.map(pt => ({
      x: initialBounds.x + offsetX + (pt.x - initialBounds.x) * scaleX,
      y: initialBounds.y + offsetY + (pt.y - initialBounds.y) * scaleY
    }));
  }
}

// Export for use in main whiteboard
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    getHandleAt,
    getMultiHandleAt,
    getCursorForHandle,
    getObjectCenter,
    rotatePoint,
    performRotation,
    getBounds,
    pathForStroke,
    isPointOnObject,
    pickTopMost,
    performResize
  };
}
