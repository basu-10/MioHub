/**
 * Whiteboard Rendering Module
 * Handles canvas rendering, drawing objects, and visual feedback
 */

const MAX_CACHED_IMAGES = 50;
const imageCache = new Map();

/**
 * Clear the canvas
 */
function clearCanvas() {
  const canvas = document.getElementById('board-canvas');
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
}

/**
 * Manage image cache size
 */
function manageImageCache() {
  if (imageCache.size > MAX_CACHED_IMAGES) {
    const entries = Array.from(imageCache.entries());
    const toRemove = entries.slice(0, imageCache.size - MAX_CACHED_IMAGES);
    toRemove.forEach(([key]) => imageCache.delete(key));
  }
}

/**
 * Draw a single object on the canvas
 * @param {Object} obj - Object to draw
 */
function drawObject(obj) {
  const canvas = document.getElementById('board-canvas');
  const ctx = canvas.getContext('2d');
  
  if (obj.type === 'stroke') {
    ctx.save();
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    const objColor = obj.props?.color || obj.color;
    const objSize = obj.props?.size || obj.size;
    const strokeType = obj.props?.strokeType || obj.strokeType;
    const objTransparency = obj.props?.transparency ?? obj.transparency;
    
    ctx.strokeStyle = objColor;
    ctx.lineWidth = objSize;
    
    // Apply transparency for marker and highlighter strokes
    if (strokeType === 'marker') {
      ctx.globalAlpha = objTransparency || 0.6;
    } else if (strokeType === 'highlighter') {
      ctx.globalAlpha = objTransparency || 0.4;
    }
    
    ctx.beginPath();
    // Use shapes module for unified shape drawing
    if (window.drawShapeStroke) {
      window.drawShapeStroke(ctx, obj);
    }
    ctx.stroke();
    ctx.restore();
    
  } else if (obj.type === 'image') {
    ctx.save();
    const objSrc = obj.props?.src || obj.src;
    const objX = obj.props?.x || obj.x || 0;
    const objY = obj.props?.y || obj.y || 0;
    const objW = obj.props?.w || obj.w || 0;
    const objH = obj.props?.h || obj.h || 0;
    const objRotation = obj.props?.rotation || obj.rotation;
    
    let img = imageCache.get(objSrc);
    if (!img) {
      img = new Image();
      img.src = objSrc;
      img.onload = () => {
        if (window.redraw) window.redraw();
      };
      imageCache.set(objSrc, img);
      manageImageCache();
    }
    
    if (img.complete && img.width > 0) {
      try {
        if (objRotation) {
          const centerX = objX + objW / 2;
          const centerY = objY + objH / 2;
          ctx.translate(centerX, centerY);
          ctx.rotate(objRotation);
          ctx.drawImage(img, -objW / 2, -objH / 2, objW, objH);
        } else {
          ctx.drawImage(img, objX, objY, objW, objH);
        }
      } catch(e) {
        console.error('Image draw error:', e);
      }
    }
    ctx.restore();
    
  } else if (obj.type === 'text') {
    ctx.save();
    const objFontSize = obj.props?.fontSize || obj.fontSize || 24;
    const objColor = obj.props?.color || obj.color || '#000';
    const objText = obj.props?.text || obj.text || '';
    const objX = obj.props?.x || obj.x || 0;
    const objY = obj.props?.y || obj.y || 0;
    const objRotation = obj.props?.rotation || obj.rotation;
    const objMaxWordsPerLine = obj.props?.maxWordsPerLine || obj.maxWordsPerLine || 
                                (window.userPrefs?.maxWordsPerLine || 10);
    
    ctx.font = objFontSize + 'px sans-serif';
    ctx.fillStyle = objColor;
    ctx.textBaseline = 'alphabetic';

    // Use text wrapping function
    const wrappedText = window.autoWrapTextByWords ? 
                        window.autoWrapTextByWords(objText, objMaxWordsPerLine) : 
                        objText;
    const lines = wrappedText.split('\n');
    const lineHeight = objFontSize * 1.2;

    if (objRotation) {
      ctx.translate(objX, objY);
      ctx.rotate(objRotation);
      lines.forEach((line, i) => ctx.fillText(line, 0, i * lineHeight));
    } else {
      lines.forEach((line, i) => ctx.fillText(line, objX, objY + i * lineHeight));
    }
    ctx.restore();
  }
}

/**
 * Draw the current stroke being drawn
 */
function drawCurrentStroke() {
  const canvas = document.getElementById('board-canvas');
  const ctx = canvas.getContext('2d');
  const currentStroke = window.currentStroke;
  const currentTool = window.currentTool;
  const color = window.color;
  const size = window.size;
  const currentTransparency = window.currentTransparency;
  
  if (!currentStroke || !currentStroke.length) return;
  
  ctx.save();
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  ctx.strokeStyle = color;
  ctx.lineWidth = size;
  
  // Apply transparency for marker and highlighter while drawing
  if (currentTool === 'marker') {
    ctx.globalAlpha = currentTransparency;
  } else if (currentTool === 'highlighter') {
    ctx.globalAlpha = currentTransparency;
  }
  
  ctx.beginPath();
  // Use shapes module for current stroke preview
  if (window.isShapeTool && window.isShapeTool(currentTool) && currentStroke.length >= 2) {
    const tempStroke = {
      props: {
        path: currentStroke,
        strokeType: currentTool,
        size: size
      }
    };
    if (window.drawShapeStroke) {
      window.drawShapeStroke(ctx, tempStroke);
    }
  } else {
    // Draw normal stroke path for pen/marker/highlighter/line
    ctx.moveTo(currentStroke[0].x, currentStroke[0].y);
    for (let i = 1; i < currentStroke.length; i++) {
      ctx.lineTo(currentStroke[i].x, currentStroke[i].y);
    }
  }
  ctx.stroke();
  ctx.restore();
}

/**
 * Draw selection handles for an object
 * @param {Object} obj - Selected object
 * @returns {Array} - Array of handle objects
 */
function drawSelectionHandles(obj) {
  const canvas = document.getElementById('board-canvas');
  const ctx = canvas.getContext('2d');
  const b = window.getBounds ? window.getBounds(obj) : {x: 0, y: 0, w: 0, h: 0};
  const handleSize = 8;
  const rotateDistance = 30;
  
  const handles = [
    {type: 'resize-nw', x: b.x - handleSize/2, y: b.y - handleSize/2},
    {type: 'resize-ne', x: b.x + b.w - handleSize/2, y: b.y - handleSize/2},
    {type: 'resize-sw', x: b.x - handleSize/2, y: b.y + b.h - handleSize/2},
    {type: 'resize-se', x: b.x + b.w - handleSize/2, y: b.y + b.h - handleSize/2},
    {type: 'resize-n', x: b.x + b.w/2 - handleSize/2, y: b.y - handleSize/2},
    {type: 'resize-s', x: b.x + b.w/2 - handleSize/2, y: b.y + b.h - handleSize/2},
    {type: 'resize-e', x: b.x + b.w - handleSize/2, y: b.y + b.h/2 - handleSize/2},
    {type: 'resize-w', x: b.x - handleSize/2, y: b.y + b.h/2 - handleSize/2},
    {type: 'rotate', x: b.x + b.w/2 - handleSize/2, y: b.y - rotateDistance - handleSize/2}
  ];

  ctx.save();
  ctx.fillStyle = '#0078d4';
  ctx.strokeStyle = '#fff';
  ctx.lineWidth = 1;
  
  for (let i = 0; i < 8; i++) {
    const h = handles[i];
    ctx.fillRect(h.x, h.y, handleSize, handleSize);
    ctx.strokeRect(h.x, h.y, handleSize, handleSize);
  }
  
  const rotHandle = handles[8];
  ctx.beginPath();
  ctx.arc(rotHandle.x + handleSize/2, rotHandle.y + handleSize/2, handleSize/2, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  
  ctx.strokeStyle = '#fff';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(rotHandle.x + handleSize/2, rotHandle.y + handleSize/2, 3, -Math.PI/3, Math.PI/3);
  ctx.stroke();

  ctx.strokeStyle = '#0078d4';
  ctx.lineWidth = 1;
  ctx.setLineDash([3, 3]);
  ctx.beginPath();
  ctx.moveTo(b.x + b.w/2, b.y);
  ctx.lineTo(rotHandle.x + handleSize/2, rotHandle.y + handleSize/2);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.restore();

  return handles;
}

/**
 * Get utility functions for rectangle selection
 */
function getRectFromPoints(a, b) {
  const x = Math.min(a.x, b.x);
  const y = Math.min(a.y, b.y);
  const w = Math.abs(a.x - b.x);
  const h = Math.abs(a.y - b.y);
  return {x, y, w, h};
}

/**
 * Main render function - draws entire canvas
 * @returns {Array} - Array of current handles
 */
function render() {
  console.log('=== RENDER CALLED ===');
  const objects = window.objects || [];
  console.log('Objects to render:', objects);
  console.log('Objects count:', objects.length);
  
  clearCanvas();
  
  const canvas = document.getElementById('board-canvas');
  const ctx = canvas.getContext('2d');
  const sorted = [...objects].sort((a, b) => (a.layer - b.layer) || (a.id - b.id));
  console.log('Sorted objects:', sorted);
  
  for (const o of sorted) {
    console.log('Drawing object:', o.id, o.type);
    drawObject(o);
  }

  if (window.drawing && window.currentStroke) {
    drawCurrentStroke();
  }

  let handles = [];
  const selectedId = window.selectedId;
  const currentTool = window.currentTool;
  const multiSelectedIds = window.multiSelectedIds;
  
  if (selectedId != null) {
    const s = window.findById ? window.findById(selectedId) : null;
    if (s) {
      const b = window.getBounds ? window.getBounds(s) : {x: 0, y: 0, w: 0, h: 0};
      ctx.save();
      ctx.strokeStyle = 'rgba(0,120,215,.9)';
      ctx.setLineDash([6, 4]);
      ctx.lineWidth = 2;
      ctx.strokeRect(b.x - 4, b.y - 4, b.w + 8, b.h + 8);
      ctx.restore();

      if (currentTool === 'select') {
        handles = drawSelectionHandles(s);
      }
    }
  }

  // Multi-selection visualization
  if (multiSelectedIds && multiSelectedIds.size > 0) {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const id of multiSelectedIds) {
      const o = window.findById ? window.findById(id) : null;
      if (o) {
        const b = window.getBounds ? window.getBounds(o) : {x: 0, y: 0, w: 0, h: 0};
        minX = Math.min(minX, b.x - 4);
        minY = Math.min(minY, b.y - 4);
        maxX = Math.max(maxX, b.x + b.w + 8);
        maxY = Math.max(maxY, b.y + b.h + 8);
      }
    }
    
    ctx.save();
    ctx.fillStyle = 'rgba(255,0,0,0.18)';
    if (isFinite(minX) && isFinite(minY) && isFinite(maxX) && isFinite(maxY)) {
      ctx.fillRect(minX, minY, maxX - minX, maxY - minY);

      // Draw move handle (center top)
      ctx.fillStyle = '#0078d4';
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      const moveX = (minX + maxX) / 2 - 12;
      const moveY = minY - 28;
      ctx.beginPath();
      ctx.arc(moveX + 12, moveY + 12, 12, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      ctx.font = "bold 16px sans-serif";
      ctx.fillStyle = "#fff";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("⇕", moveX + 12, moveY + 12);

      // Draw rotate handle (center right)
      ctx.fillStyle = '#0078d4';
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      const rotX = maxX + 24;
      const rotY = (minY + maxY) / 2 - 12;
      ctx.beginPath();
      ctx.arc(rotX, rotY + 12, 12, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = "#fff";
      ctx.font = "bold 16px sans-serif";
      ctx.fillText("⟳", rotX, rotY + 12);

      // Draw menu handle (center left)
      ctx.fillStyle = '#0078d4';
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      const menuX = minX - 36;
      const menuY = (minY + maxY) / 2 - 12;
      ctx.beginPath();
      ctx.arc(menuX + 12, menuY + 12, 12, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = "#fff";
      ctx.font = "bold 20px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("⋮", menuX + 12, menuY + 12);

      // Save handles for hit-testing
      handles = [
        {type: "multi-move", x: moveX, y: moveY, w: 24, h: 24},
        {type: "multi-rotate", x: rotX - 12, y: rotY, w: 24, h: 24},
        {type: "multi-menu", x: menuX, y: menuY, w: 24, h: 24}
      ];
    }
    ctx.restore();
  }

  // Draw highlight boxes for selection preview
  let highlightIds = new Set(multiSelectedIds || []);
  const rectSelecting = window.rectSelecting;
  const rectSelectStart = window.rectSelectStart;
  const rectSelectEnd = window.rectSelectEnd;
  
  if (currentTool === 'rect-select' && rectSelecting && rectSelectStart && rectSelectEnd) {
    const selRect = getRectFromPoints(rectSelectStart, rectSelectEnd);
    highlightIds = new Set();
    for (const o of objects) {
      if (window.isObjectFullyInRect && window.isObjectFullyInRect(o, selRect)) {
        highlightIds.add(o.id);
      }
    }
  }

  if (highlightIds.size > 0) {
    ctx.save();
    ctx.strokeStyle = 'rgba(0,120,215,0.7)';
    ctx.setLineDash([2, 2]);
    ctx.lineWidth = 2;
    for (const id of highlightIds) {
      const o = window.findById ? window.findById(id) : null;
      if (o) {
        const b = window.getBounds ? window.getBounds(o) : {x: 0, y: 0, w: 0, h: 0};
        ctx.strokeRect(b.x - 4, b.y - 4, b.w + 8, b.h + 8);
      }
    }
    ctx.restore();
  }

  // Draw rectangle selection
  if (currentTool === 'rect-select' && rectSelecting && rectSelectStart && rectSelectEnd) {
    const r = getRectFromPoints(rectSelectStart, rectSelectEnd);
    ctx.save();
    ctx.strokeStyle = '#0078d4';
    ctx.setLineDash([4, 4]);
    ctx.lineWidth = 2;
    ctx.strokeRect(r.x, r.y, r.w, r.h);
    ctx.restore();
  }

  if (window.updateStatus) {
    window.updateStatus();
  }
  
  return handles;
}

/**
 * Redraw wrapper function
 */
function redraw() {
  if (window.render) {
    window.currentHandles = render() || [];
  }
}

// Export for use in main whiteboard
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    clearCanvas,
    manageImageCache,
    drawObject,
    drawCurrentStroke,
    drawSelectionHandles,
    getRectFromPoints,
    render,
    redraw,
    imageCache
  };
}
