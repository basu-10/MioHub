/**
 * Graph Canvas Module - Handles canvas setup, pan, zoom, and viewport transforms
 */

window.GraphCanvas = (function() {
  let canvas, ctx;
  let viewportX = 0, viewportY = 0;
  let scale = 1.0;
  let isPanning = false;
  let panStartX = 0, panStartY = 0;
  let panOffsetX = 0, panOffsetY = 0;
  let graphId = null;
  let saveViewportTimer = null;
  let snapToGridEnabled = true; // Snap to grid enabled by default

  // Grid settings
  const GRID_SIZE = 50;
  const MIN_SCALE = 0.2;
  const MAX_SCALE = 3.0;
  const ZOOM_SPEED = 0.1;
  const VIEWPORT_SAVE_DELAY = 500; // ms debounce

  function init(canvasElement, fileId) {
    canvas = canvasElement;
    ctx = canvas.getContext('2d');
    graphId = fileId;
    
    // Set canvas size to fill container
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    // Pan controls
    canvas.addEventListener('mousedown', handlePanStart);
    canvas.addEventListener('mousemove', handlePanMove);
    canvas.addEventListener('mouseup', handlePanEnd);
    canvas.addEventListener('mouseleave', handlePanEnd);
    
    // Dynamic cursor based on hover position
    canvas.addEventListener('mousemove', updateCursorForPosition);

    // Zoom controls
    canvas.addEventListener('wheel', handleZoom, { passive: false });

    // Touch support for mobile
    canvas.addEventListener('touchstart', handleTouchStart, { passive: false });
    canvas.addEventListener('touchmove', handleTouchMove, { passive: false });
    canvas.addEventListener('touchend', handleTouchEnd);
  }

  function resizeCanvas() {
    const container = canvas.parentElement;
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
    render();
  }

  function handlePanStart(e) {
    // Allow panning with left click (button 0) or middle mouse
    // But only if not clicking on a node or edge
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    const worldPos = screenToWorld(mouseX, mouseY);
    
    // Check if clicking on a node or edge (let those modules handle it)
    const overNode = window.GraphNodes?.getNodeAt?.(worldPos.x, worldPos.y);
    const overEdge = window.GraphEdges?.getEdgeAt?.(worldPos.x, worldPos.y);
    
    // Allow pan mode for left click ONLY if not over interactive elements, or middle mouse always
    const canPan = (e.button === 0 && !overNode && !overEdge) || e.button === 1;
    
    if (!canPan) return;
    
    isPanning = true;
    panStartX = e.clientX - panOffsetX;
    panStartY = e.clientY - panOffsetY;
    canvas.style.cursor = 'grabbing';
    e.preventDefault();
  }

  function handlePanMove(e) {
    if (!isPanning) return;
    e.preventDefault();
    panOffsetX = e.clientX - panStartX;
    panOffsetY = e.clientY - panStartY;
    viewportX = panOffsetX;
    viewportY = panOffsetY;
    render();
  }

  function handlePanEnd(e) {
    if (isPanning) {
      isPanning = false;
      // Return to pan cursor (move) after panning
      updateCursorForPosition(e);
      saveViewportState(); // Save viewport after panning
    }
  }

  function handleZoom(e) {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -ZOOM_SPEED : ZOOM_SPEED;
    const newScale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, scale + delta));
    
    // Zoom towards mouse position
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    
    // Adjust viewport to zoom towards mouse
    const scaleRatio = newScale / scale;
    viewportX = mouseX - (mouseX - viewportX) * scaleRatio;
    viewportY = mouseY - (mouseY - viewportY) * scaleRatio;
    
    scale = newScale;
    panOffsetX = viewportX;
    panOffsetY = viewportY;
    render();
    saveViewportState(); // Save viewport after zooming
  }

  // Touch support
  let lastTouchDistance = 0;
  function handleTouchStart(e) {
    if (e.touches.length === 1) {
      isPanning = true;
      panStartX = e.touches[0].clientX - panOffsetX;
      panStartY = e.touches[0].clientY - panOffsetY;
    } else if (e.touches.length === 2) {
      const dx = e.touches[0].clientX - e.touches[1].clientX;
      const dy = e.touches[0].clientY - e.touches[1].clientY;
      lastTouchDistance = Math.sqrt(dx * dx + dy * dy);
    }
  }

  function handleTouchMove(e) {
    e.preventDefault();
    if (e.touches.length === 1 && isPanning) {
      panOffsetX = e.touches[0].clientX - panStartX;
      panOffsetY = e.touches[0].clientY - panStartY;
      viewportX = panOffsetX;
      viewportY = panOffsetY;
      render();
    } else if (e.touches.length === 2) {
      const dx = e.touches[0].clientX - e.touches[1].clientX;
      const dy = e.touches[0].clientY - e.touches[1].clientY;
      const distance = Math.sqrt(dx * dx + dy * dy);
      const delta = (distance - lastTouchDistance) * 0.01;
      scale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, scale + delta));
      lastTouchDistance = distance;
      render();
    }
  }

  function handleTouchEnd() {
    isPanning = false;
  }

  /**
   * Update cursor based on current mouse position
   * Shows pointer over nodes/edges, grab cursor otherwise
   */
  function updateCursorForPosition(e) {
    if (isPanning) {
      canvas.style.cursor = 'grabbing';
      canvas.title = '';
      return;
    }
    
    if (!e) {
      canvas.style.cursor = 'grab';
      canvas.title = '';
      return;
    }
    
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    const worldPos = screenToWorld(mouseX, mouseY);
    
    const overNode = window.GraphNodes?.getNodeAt?.(worldPos.x, worldPos.y);
    const overEdge = window.GraphEdges?.getEdgeAt?.(worldPos.x, worldPos.y);
    
    if (overNode || overEdge) {
      canvas.style.cursor = 'pointer';
      // Show full label as tooltip for edges
      if (overEdge && overEdge.label) {
        canvas.title = overEdge.label;
      } else {
        canvas.title = '';
      }
    } else {
      canvas.style.cursor = 'grab';
      canvas.title = '';
    }
  }

  function clear() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }

  function drawGrid() {
    ctx.save();
    ctx.strokeStyle = 'rgba(100, 100, 100, 0.15)';
    ctx.lineWidth = 1;

    const startX = Math.floor((-viewportX / scale) / GRID_SIZE) * GRID_SIZE;
    const startY = Math.floor((-viewportY / scale) / GRID_SIZE) * GRID_SIZE;
    const endX = startX + (canvas.width / scale) + GRID_SIZE;
    const endY = startY + (canvas.height / scale) + GRID_SIZE;

    // Vertical lines
    for (let x = startX; x < endX; x += GRID_SIZE) {
      const screenX = x * scale + viewportX;
      ctx.beginPath();
      ctx.moveTo(screenX, 0);
      ctx.lineTo(screenX, canvas.height);
      ctx.stroke();
    }

    // Horizontal lines
    for (let y = startY; y < endY; y += GRID_SIZE) {
      const screenY = y * scale + viewportY;
      ctx.beginPath();
      ctx.moveTo(0, screenY);
      ctx.lineTo(canvas.width, screenY);
      ctx.stroke();
    }

    ctx.restore();
  }

  function render() {
    clear();
    drawGrid();
    
    // Render edges first, then nodes (so arrows appear behind cards)
    if (window.GraphEdges) {
      window.GraphEdges.render(ctx, viewportX, viewportY, scale);
    }
    if (window.GraphNodes) {
      window.GraphNodes.render(ctx, viewportX, viewportY, scale);
    }
    
    // Update rendered content overlays after canvas render
    if (window.GraphContentRenderer) {
      window.GraphContentRenderer.updateRenderedOverlays();
    }
  }

  function screenToWorld(screenX, screenY) {
    return {
      x: (screenX - viewportX) / scale,
      y: (screenY - viewportY) / scale
    };
  }

  function worldToScreen(worldX, worldY) {
    return {
      x: worldX * scale + viewportX,
      y: worldY * scale + viewportY
    };
  }

  function resetView() {
    scale = 1.0; // Reset zoom level
    
    // Get all nodes and find the first one (earliest created)
    const nodes = window.GraphNodes?.getAllNodes() || [];
    
    if (nodes.length > 0) {
      // Sort by ID to get the first created node (assuming IDs are sequential)
      const firstNode = nodes.reduce((earliest, node) => 
        (node.id < earliest.id) ? node : earliest
      );
      
      // Center view on the first node (use x and y properties directly)
      const nodeWorldX = firstNode.x;
      const nodeWorldY = firstNode.y;
      const nodeWidth = firstNode.width || 220;
      const nodeHeight = firstNode.height || 120;
      
      // Calculate viewport offset to center the first node (center of the node)
      viewportX = canvas.width / 2 - (nodeWorldX + nodeWidth / 2) * scale;
      viewportY = canvas.height / 2 - (nodeWorldY + nodeHeight / 2) * scale;
    } else {
      // No nodes - just center at origin
      viewportX = canvas.width / 2;
      viewportY = canvas.height / 2;
    }
    
    panOffsetX = viewportX;
    panOffsetY = viewportY;
    render();
    saveViewportState(); // Save viewport after reset
  }

  function fitAllItems() {
    // Get all nodes from GraphNodes module
    const nodes = window.GraphNodes?.getAllNodes() || [];
    if (nodes.length === 0) {
      resetView();
      return;
    }

    // Calculate bounding box of all nodes
    let minX = Infinity, minY = Infinity;
    let maxX = -Infinity, maxY = -Infinity;

    nodes.forEach(node => {
      const x1 = node.x;
      const y1 = node.y;
      const x2 = node.x + (node.width || 220);
      const y2 = node.y + (node.height || 120);
      minX = Math.min(minX, x1);
      minY = Math.min(minY, y1);
      maxX = Math.max(maxX, x2);
      maxY = Math.max(maxY, y2);
    });

    // Calculate center and size
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;
    const width = maxX - minX;
    const height = maxY - minY;

    // Calculate scale to fit all items with padding
    const padding = 100;
    const scaleX = (canvas.width - padding * 2) / width;
    const scaleY = (canvas.height - padding * 2) / height;
    const newScale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, Math.min(scaleX, scaleY)));

    // Center the view on all items
    scale = newScale;
    viewportX = canvas.width / 2 - centerX * scale;
    viewportY = canvas.height / 2 - centerY * scale;
    panOffsetX = viewportX;
    panOffsetY = viewportY;
    render();
    saveViewportState(); // Save viewport after fit all
  }

  function getCanvas() {
    return canvas;
  }

  function getScale() {
    return scale;
  }

  function getViewport() {
    return { x: viewportX, y: viewportY };
  }

  /**
   * Save viewport state (zoom, pan) to server with debouncing
   */
  function saveViewportState() {
    if (!graphId) return;
    
    // Clear existing timer
    if (saveViewportTimer) {
      clearTimeout(saveViewportTimer);
    }
    
    // Debounce: only save after user stops interacting for VIEWPORT_SAVE_DELAY
    saveViewportTimer = setTimeout(async () => {
      try {
        const response = await fetch(`/graph/${graphId}/settings`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            canvas: {
              zoom: scale,
              panX: viewportX,
              panY: viewportY
            }
          })
        });
        const data = await response.json();
        if (!data.ok) {
          console.error('Failed to save viewport state:', data.error);
        }
      } catch (err) {
        console.error('Error saving viewport state:', err);
      }
    }, VIEWPORT_SAVE_DELAY);
  }

  /**
   * Load viewport state from workspace settings
   */
  function loadViewportState(settings) {
    if (!settings || !settings.canvas) return;
    
    const canvas = settings.canvas;
    if (typeof canvas.zoom === 'number') {
      scale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, canvas.zoom));
    }
    if (typeof canvas.panX === 'number') {
      viewportX = canvas.panX;
      panOffsetX = canvas.panX;
    }
    if (typeof canvas.panY === 'number') {
      viewportY = canvas.panY;
      panOffsetY = canvas.panY;
    }
    
    render();
  }

  /**
   * Toggle snap to grid on/off
   */
  function toggleSnapToGrid() {
    snapToGridEnabled = !snapToGridEnabled;
    return snapToGridEnabled;
  }

  /**
   * Check if snap to grid is enabled
   */
  function isSnapToGridEnabled() {
    return snapToGridEnabled;
  }

  /**
   * Get individual viewport values for convenience
   */
  function getViewportX() {
    return viewportX;
  }

  function getViewportY() {
    return viewportY;
  }

  return {
    init,
    render,
    clear,
    screenToWorld,
    worldToScreen,
    resetView,
    fitAllItems,
    getCanvas,
    getScale,
    getViewport,
    getViewportX,
    getViewportY,
    loadViewportState,
    saveViewportState,
    toggleSnapToGrid,
    isSnapToGridEnabled
  };
})();
