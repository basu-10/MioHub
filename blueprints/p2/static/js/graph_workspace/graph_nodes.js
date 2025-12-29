/**
 * Graph Nodes Module - Handles node creation, dragging, selection, and rendering
 */

window.GraphNodes = (function() {
  let nodes = [];
  let selectedNode = null;
  let isDragging = false;
  let dragOffsetX = 0;
  let dragOffsetY = 0;
  let canvas = null;
  let graphId = null;

  // Node defaults
  const NODE_WIDTH = 220;
  const NODE_HEIGHT = 120;
  const NODE_PADDING = 12;
  const NODE_BORDER_RADIUS = 8;
  const GRID_SIZE = 50; // Match canvas grid size

  // Snap to grid utility
  function snapToGrid(value) {
    const snapEnabled = window.GraphCanvas?.isSnapToGridEnabled?.() ?? true;
    if (!snapEnabled) return value;
    return Math.round(value / GRID_SIZE) * GRID_SIZE;
  }

  // Check if connection mode is active (set by main workspace script)
  function isConnectionModeActive() {
    return window.graphConnectionModeActive === true;
  }

  function init(canvasElement, fileId) {
    canvas = canvasElement;
    graphId = fileId;

    canvas.addEventListener('mousedown', handleMouseDown);
    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('mouseup', handleMouseUp);
    canvas.addEventListener('dblclick', handleDoubleClick);

    // Cursor handling is now managed by GraphCanvas module
  }

  function loadNodes(nodesData) {
    const prevSelectedId = selectedNode ? selectedNode.id : null;

    nodes = nodesData.map(n => ({
      id: n.id,
      graphId: n.graph_id,
      title: n.title || 'Untitled',
      summary: n.summary || '',
      x: (n.position && n.position.x) || 0,
      y: (n.position && n.position.y) || 0,
      width: (n.size && n.size.w) || NODE_WIDTH,
      height: (n.size && n.size.h) || NODE_HEIGHT,
      style: n.style || {},
      metadata: n.metadata || {},
      attachments: n.attachments || []
    }));

    console.log('Loaded nodes:', nodes.length, nodes);

    // Restore selection after reload so highlighting persists
    if (prevSelectedId) {
      selectedNode = nodes.find(n => n.id === prevSelectedId) || null;
    }

    window.GraphCanvas.render();
    console.log('Initial render called after loading', nodes.length, 'nodes');
  }

  function handleMouseDown(e) {
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    const worldPos = window.GraphCanvas.screenToWorld(mouseX, mouseY);

    // Check if clicking on a node
    const clickedNode = getNodeAt(worldPos.x, worldPos.y);
    if (clickedNode) {
      selectedNode = clickedNode;
      
      // In connection mode, only select nodes - don't enable dragging
      if (!isConnectionModeActive()) {
        isDragging = true;
        dragOffsetX = worldPos.x - clickedNode.x;
        dragOffsetY = worldPos.y - clickedNode.y;
      }
      
      // Deselect edge when node is selected
      if (window.GraphEdges) {
        window.GraphEdges.deselectEdge();
      }
      window.GraphCanvas.render();
      if (window.GraphToolbar) {
        window.GraphToolbar.updateNodeSelection(clickedNode);
      }
      
      // Dispatch custom event for connection mode
      const nodeSelectedEvent = new CustomEvent('graph:nodeSelected', {
        detail: { nodeId: clickedNode.id, node: clickedNode }
      });
      window.dispatchEvent(nodeSelectedEvent);
    } else {
      // Check if clicking on an edge
      const clickedEdge = window.GraphEdges?.getEdgeAt(worldPos.x, worldPos.y);
      if (clickedEdge) {
        const previouslySelectedEdge = window.GraphEdges?.getSelectedEdge ? window.GraphEdges.getSelectedEdge() : null;
        selectedNode = null;
        if (window.GraphEdges) {
          window.GraphEdges.selectEdge(clickedEdge);
        }
        if (previouslySelectedEdge && previouslySelectedEdge.id === clickedEdge.id && window.GraphToolbar) {
          window.GraphToolbar.openEditArrowModal();
        }
        // Don't call updateNodeSelection here - selectEdge already updates toolbar
      } else {
        selectedNode = null;
        if (window.GraphEdges) {
          window.GraphEdges.deselectEdge();
        }
        if (window.GraphToolbar) {
          window.GraphToolbar.updateNodeSelection(null);
        }
        window.GraphCanvas.render();
      }
    }
  }

  function handleMouseMove(e) {
    if (!isDragging || !selectedNode) return;
    
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    const worldPos = window.GraphCanvas.screenToWorld(mouseX, mouseY);

    // Apply snap to grid
    selectedNode.x = snapToGrid(worldPos.x - dragOffsetX);
    selectedNode.y = snapToGrid(worldPos.y - dragOffsetY);
    
    window.GraphCanvas.render();
  }

  function handleMouseUp() {
    if (isDragging && selectedNode) {
      isDragging = false;
      // Save node position to server
      saveNodePosition(selectedNode);
    }
  }

  function handleDoubleClick(e) {
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    const worldPos = window.GraphCanvas.screenToWorld(mouseX, mouseY);

    const clickedNode = getNodeAt(worldPos.x, worldPos.y);
    if (clickedNode && window.GraphToolbar) {
      // Select the node first
      selectedNode = clickedNode;
      if (window.GraphEdges) {
        window.GraphEdges.deselectEdge();
      }
      window.GraphCanvas.render();
      window.GraphToolbar.updateNodeSelection(clickedNode);
      // Open Manage Node Modal (attachment modal)
      window.GraphToolbar.openAttachmentModal();
      return;
    }
    
    // Check if double-clicking on an edge
    const clickedEdge = window.GraphEdges?.getEdgeAt(worldPos.x, worldPos.y);
    if (clickedEdge && window.GraphToolbar) {
      window.GraphEdges.selectEdge(clickedEdge);
      window.GraphToolbar.openEditArrowModal();
    }
  }

  function getNodeAt(worldX, worldY) {
    // Check in reverse order (top nodes first)
    for (let i = nodes.length - 1; i >= 0; i--) {
      const node = nodes[i];
      if (worldX >= node.x && worldX <= node.x + node.width &&
          worldY >= node.y && worldY <= node.y + node.height) {
        return node;
      }
    }
    return null;
  }
  
  function getNodes() {
    return nodes;
  }

  function render(ctx, viewportX, viewportY, scale) {
    if (!ctx || !nodes || nodes.length === 0) {
      return; // Nothing to render
    }

    nodes.forEach(node => {
      try {
        const screenPos = window.GraphCanvas.worldToScreen(node.x, node.y);
        const screenWidth = node.width * scale;
        const screenHeight = node.height * scale;

        // Get style properties with defaults - ensure style object exists
        const style = node.style || {};
        const shape = style.shape || 'rounded';
        const bgColor = style.backgroundColor || 'rgba(18, 21, 22, 0.95)';
        const borderColor = style.borderColor || 'rgba(100, 100, 100, 0.5)';
        const borderWidth = (style.borderWidth !== undefined && style.borderWidth !== null) ? style.borderWidth : 1;
        const borderStyle = style.borderStyle || 'solid';
        const borderDashPattern = Array.isArray(style.borderDashPattern) ? style.borderDashPattern : [];
        const opacity = (style.opacity !== undefined && style.opacity !== null) ? style.opacity : 0.95;
        const cornerRadius = ((style.cornerRadius !== undefined && style.cornerRadius !== null) ? style.cornerRadius : NODE_BORDER_RADIUS) * scale;

      // Node background
      ctx.save();
      
      // Apply opacity
      ctx.globalAlpha = opacity;
      
      // Highlight selected node with glow effect
      if (selectedNode === node) {
        ctx.shadowColor = '#14b8a6';
        ctx.shadowBlur = 15 * scale;
      }
      
      // Set fill and stroke styles
      ctx.fillStyle = selectedNode === node ? 'rgba(20, 184, 166, 0.1)' : bgColor;
      ctx.strokeStyle = selectedNode === node ? '#14b8a6' : borderColor;
      ctx.lineWidth = selectedNode === node ? 3 * scale : (borderWidth * scale);
      
      // Apply border dash pattern
      if (borderStyle !== 'none' && borderDashPattern.length > 0) {
        ctx.setLineDash(borderDashPattern.map(d => d * scale));
      } else {
        ctx.setLineDash([]);
      }

      // Draw shape based on node.style.shape
      ctx.beginPath();
      
      switch(shape) {
        case 'rectangle':
          // Sharp rectangle
          ctx.rect(screenPos.x, screenPos.y, screenWidth, screenHeight);
          break;
          
        case 'circle':
          // Perfect circle (uses smaller dimension)
          const circleRadius = Math.min(screenWidth, screenHeight) / 2;
          const circleCenterX = screenPos.x + screenWidth / 2;
          const circleCenterY = screenPos.y + screenHeight / 2;
          ctx.arc(circleCenterX, circleCenterY, circleRadius, 0, Math.PI * 2);
          break;
          
        case 'ellipse':
          // Ellipse
          const ellipseCenterX = screenPos.x + screenWidth / 2;
          const ellipseCenterY = screenPos.y + screenHeight / 2;
          const radiusX = screenWidth / 2;
          const radiusY = screenHeight / 2;
          ctx.ellipse(ellipseCenterX, ellipseCenterY, radiusX, radiusY, 0, 0, Math.PI * 2);
          break;
          
        case 'rounded':
        default:
          // Rounded rectangle (default)
          ctx.moveTo(screenPos.x + cornerRadius, screenPos.y);
          ctx.lineTo(screenPos.x + screenWidth - cornerRadius, screenPos.y);
          ctx.quadraticCurveTo(screenPos.x + screenWidth, screenPos.y, screenPos.x + screenWidth, screenPos.y + cornerRadius);
          ctx.lineTo(screenPos.x + screenWidth, screenPos.y + screenHeight - cornerRadius);
          ctx.quadraticCurveTo(screenPos.x + screenWidth, screenPos.y + screenHeight, screenPos.x + screenWidth - cornerRadius, screenPos.y + screenHeight);
          ctx.lineTo(screenPos.x + cornerRadius, screenPos.y + screenHeight);
          ctx.quadraticCurveTo(screenPos.x, screenPos.y + screenHeight, screenPos.x, screenPos.y + screenHeight - cornerRadius);
          ctx.lineTo(screenPos.x, screenPos.y + cornerRadius);
          ctx.quadraticCurveTo(screenPos.x, screenPos.y, screenPos.x + cornerRadius, screenPos.y);
          break;
      }
      
      ctx.closePath();
      ctx.fill();
      
      // Only draw border if style is not 'none'
      if (borderStyle !== 'none') {
        ctx.stroke();
      }

      // Reset global alpha for text rendering
      ctx.globalAlpha = 1.0;

      // Calculate text width constraint based on shape
      // For circles/ellipses, constrain text to fit within the inscribed rectangle
      let textMaxWidth = screenWidth - 2 * NODE_PADDING * scale;
      if (shape === 'circle') {
        // For circles, use ~70% of diameter to ensure text fits within circle
        textMaxWidth = (Math.min(screenWidth, screenHeight) * 0.7) - 2 * NODE_PADDING * scale;
      } else if (shape === 'ellipse') {
        // For ellipses, use ~75% of width to account for curved boundaries
        textMaxWidth = (screenWidth * 0.75) - 2 * NODE_PADDING * scale;
      }

      // Center text horizontally for circles/ellipses
      let titleX = screenPos.x + NODE_PADDING * scale;
      if (shape === 'circle' || shape === 'ellipse') {
        titleX = screenPos.x + screenWidth / 2;
        ctx.textAlign = 'center';
      } else {
        ctx.textAlign = 'left';
      }

      // Node title
      ctx.fillStyle = '#ECFFFF';
      ctx.font = `bold ${14 * scale}px system-ui, -apple-system, sans-serif`;
      ctx.textBaseline = 'top';
      const titleY = screenPos.y + NODE_PADDING * scale;
      ctx.fillText(truncateText(ctx, node.title, textMaxWidth), titleX, titleY);

      // Node summary
      const summaryLines = node.summary ? wrapText(ctx, node.summary, textMaxWidth) : [];
      const summaryLinesToRender = summaryLines.slice(0, 2);
      if (summaryLinesToRender.length) {
        ctx.fillStyle = '#9aa8ad';
        ctx.font = `${11 * scale}px system-ui, -apple-system, sans-serif`;
        const summaryY = titleY + 20 * scale;
        summaryLinesToRender.forEach((line, idx) => {
          ctx.fillText(line, titleX, summaryY + idx * 14 * scale);
        });
      }

      // Reset text alignment for attachment chips
      if (shape === 'circle' || shape === 'ellipse') {
        ctx.textAlign = 'center';
      } else {
        ctx.textAlign = 'left';
      }

      // Attachment preview chips (limited for at-a-glance context)
      const attachmentsPreview = (node.attachments || []).slice(0, 3);
      if (attachmentsPreview.length > 0) {
        const summaryBlockHeight = summaryLinesToRender.length * 14 * scale;
        const attachmentsStartY = (summaryLinesToRender.length > 0 ? titleY + 20 * scale + summaryBlockHeight : titleY + 20 * scale) + 8 * scale;
        const maxLabelWidth = textMaxWidth;

        ctx.fillStyle = '#14b8a6';
        ctx.font = `${10 * scale}px system-ui, -apple-system, sans-serif`;
        attachmentsPreview.forEach((att, idx) => {
          const text = buildAttachmentPreview(att, ctx, maxLabelWidth);
          ctx.fillText(text, titleX, attachmentsStartY + idx * 14 * scale);
        });

        const remaining = node.attachments.length - attachmentsPreview.length;
        if (remaining > 0) {
          ctx.fillStyle = '#9aa8ad';
          ctx.fillText(`+${remaining} more`, titleX, attachmentsStartY + attachmentsPreview.length * 14 * scale);
        }
      }

      // Attachment count badge
      if (node.attachments && node.attachments.length > 0) {
        const badgeX = screenPos.x + screenWidth - 35 * scale;
        const badgeY = screenPos.y + screenHeight - 25 * scale;
        ctx.fillStyle = '#14b8a6';
        ctx.beginPath();
        ctx.arc(badgeX + 12 * scale, badgeY + 8 * scale, 12 * scale, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#0a0a0b';
        ctx.font = `bold ${10 * scale}px system-ui`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(node.attachments.length.toString(), badgeX + 12 * scale, badgeY + 8 * scale);
      }

      ctx.restore();
      } catch (error) {
        console.error('Error rendering node:', node.id, error);
        // Continue rendering other nodes even if one fails
      }
    });
  }

  function truncateText(ctx, text, maxWidth) {
    if (ctx.measureText(text).width <= maxWidth) return text;
    let truncated = text;
    while (ctx.measureText(truncated + '...').width > maxWidth && truncated.length > 0) {
      truncated = truncated.slice(0, -1);
    }
    return truncated + '...';
  }

  function wrapText(ctx, text, maxWidth) {
    const words = text.split(' ');
    const lines = [];
    let currentLine = '';

    words.forEach(word => {
      const testLine = currentLine ? currentLine + ' ' + word : word;
      if (ctx.measureText(testLine).width > maxWidth && currentLine) {
        lines.push(currentLine);
        currentLine = word;
      } else {
        currentLine = testLine;
      }
    });
    if (currentLine) lines.push(currentLine);
    return lines;
  }

  function buildAttachmentPreview(att, ctx, maxWidth) {
    const labelSource = window.GraphAttachments?.getAttachmentLabel(att) || getFallbackAttachmentLabel(att);
    const prefix = formatAttachmentType(att.attachment_type);
    return truncateText(ctx, `${prefix} ${labelSource}`, maxWidth);
  }

  function formatAttachmentType(type) {
    const prefixes = {
      file: '[File]',
      folder: '[Folder]',
      url: '[URL]'
    };
    return prefixes[type] || '[Attachment]';
  }

  function getFallbackAttachmentLabel(att) {
    if (att.attachment_type === 'url') {
      return att.url || 'URL';
    }
    if (att.metadata && att.metadata.title) {
      return att.metadata.title;
    }
    return `${att.attachment_type} #${att.file_id || att.folder_id || ''}`.trim();
  }

  async function createNode(title, summary, x, y) {
    try {
      // Apply snap to grid for new node placement
      const snappedX = snapToGrid(x);
      const snappedY = snapToGrid(y);
      
      const response = await fetch(`/graph/${graphId}/nodes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: title || 'Untitled Node',
          summary: summary || '',
          position: { x: snappedX, y: snappedY },
          size: { w: NODE_WIDTH, h: NODE_HEIGHT }
        })
      });
      const data = await response.json();
      if (data.ok) {
        // Reload graph data
        await window.GraphStorage.loadGraph();
        return data.node;
      } else {
        console.error('Failed to create node:', data.error);
        alert('Failed to create node: ' + (data.error || 'Unknown error'));
      }
    } catch (err) {
      console.error('Error creating node:', err);
      alert('Error creating node');
    }
  }

  async function updateNode(nodeId, updates) {
    try {
      const response = await fetch(`/graph/${graphId}/nodes/${nodeId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      });
      const data = await response.json();
      if (data.ok) {
        await window.GraphStorage.loadGraph();
        return true;
      } else {
        console.error('Failed to update node:', data.error);
        alert('Failed to update node: ' + (data.error || 'Unknown error'));
      }
    } catch (err) {
      console.error('Error updating node:', err);
      alert('Error updating node');
    }
    return false;
  }

  async function deleteNode(nodeId) {
    if (!confirm('Delete this node? All connections and attachments will be removed.')) return false;
    
    try {
      const response = await fetch(`/graph/${graphId}/nodes/${nodeId}`, {
        method: 'DELETE'
      });
      const data = await response.json();
      if (data.ok) {
        await window.GraphStorage.loadGraph();
        return true;
      } else {
        console.error('Failed to delete node:', data.error);
        alert('Failed to delete node: ' + (data.error || 'Unknown error'));
      }
    } catch (err) {
      console.error('Error deleting node:', err);
      alert('Error deleting node');
    }
    return false;
  }

  function saveNodePosition(node) {
    updateNode(node.id, {
      position: { x: node.x, y: node.y }
    });
  }

  function getNodes() {
    return nodes;
  }

  function getSelectedNode() {
    return selectedNode;
  }

  function getNodeById(nodeId) {
    return nodes.find(n => n.id === nodeId);
  }

  function selectNode(node) {
    selectedNode = node;
    window.GraphCanvas.render();
  }

  function getAllNodes() {
    return nodes;
  }

  return {
    init,
    loadNodes,
    render,
    createNode,
    updateNode,
    deleteNode,
    saveNodePosition,
    getNodes,
    getNodeAt,
    getSelectedNode,
    getNodeById,
    selectNode,
    getAllNodes
  };
})();
