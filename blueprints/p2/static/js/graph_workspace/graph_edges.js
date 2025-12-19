/**
 * Graph Edges Module - Handles edge creation, rendering, and management
 */

window.GraphEdges = (function() {
  let edges = [];
  let canvas = null;
  let graphId = null;
  let isDrawingEdge = false;
  let edgeSourceNode = null;
  let edgeEndX = 0;
  let edgeEndY = 0;
  let selectedEdge = null;

  // Default arrow settings
  const DEFAULT_EDGE_STYLE = {
    color: '#9aa8ad',
    thickness: 2,
    dashPattern: 'solid', // solid, dashed, dotted
    lineStyle: 'straight', // straight, wavy, elbow_hvh, elbow_vhv, elbow_hv, elbow_vh
    direction: 'directed', // directed, bidirectional, undirected
    label: ''
  };

  function init(canvasElement, fileId) {
    canvas = canvasElement;
    graphId = fileId;
  }

  function loadEdges(edgesData) {
    edges = edgesData.map(e => ({
      id: e.id,
      graphId: e.graph_id,
      sourceNodeId: e.source_node_id,
      targetNodeId: e.target_node_id,
      label: e.label || '',
      edgeType: e.edge_type || 'directed',
      metadata: e.metadata || {}
    }));
    window.GraphCanvas.render();
  }

  function startDrawingEdge(sourceNode) {
    isDrawingEdge = true;
    edgeSourceNode = sourceNode;
    
    canvas.addEventListener('mousemove', handleEdgeDrawing);
    canvas.addEventListener('mouseup', handleEdgeComplete);
  }

  function handleEdgeDrawing(e) {
    if (!isDrawingEdge) return;
    
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    const worldPos = window.GraphCanvas.screenToWorld(mouseX, mouseY);
    
    edgeEndX = worldPos.x;
    edgeEndY = worldPos.y;
    
    window.GraphCanvas.render();
    
    // Draw temporary edge
    if (edgeSourceNode) {
      const ctx = canvas.getContext('2d');
      const sourceCenter = getNodeCenter(edgeSourceNode);
      const startScreen = window.GraphCanvas.worldToScreen(sourceCenter.x, sourceCenter.y);
      const endScreen = window.GraphCanvas.worldToScreen(edgeEndX, edgeEndY);
      
      ctx.save();
      ctx.strokeStyle = '#14b8a6';
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 5]);
      ctx.beginPath();
      ctx.moveTo(startScreen.x, startScreen.y);
      ctx.lineTo(endScreen.x, endScreen.y);
      ctx.stroke();
      ctx.restore();
    }
  }

  function handleEdgeComplete(e) {
    if (!isDrawingEdge) return;
    
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    const worldPos = window.GraphCanvas.screenToWorld(mouseX, mouseY);
    
    // Check if mouse is over a node
    const nodes = window.GraphNodes.getNodes();
    const targetNode = nodes.find(n => 
      worldPos.x >= n.x && worldPos.x <= n.x + n.width &&
      worldPos.y >= n.y && worldPos.y <= n.y + n.height &&
      n !== edgeSourceNode
    );
    
    if (targetNode) {
      createEdge(edgeSourceNode.id, targetNode.id, '');
    }
    
    stopDrawingEdge();
  }

  function stopDrawingEdge() {
    isDrawingEdge = false;
    edgeSourceNode = null;
    canvas.removeEventListener('mousemove', handleEdgeDrawing);
    canvas.removeEventListener('mouseup', handleEdgeComplete);
    window.GraphCanvas.render();
  }

  function render(ctx, viewportX, viewportY, scale) {
    const nodes = window.GraphNodes.getNodes();
    
    edges.forEach(edge => {
      const sourceNode = nodes.find(n => n.id === edge.sourceNodeId);
      const targetNode = nodes.find(n => n.id === edge.targetNodeId);
      
      if (!sourceNode || !targetNode) return;
      
      const sourceCenter = getNodeCenter(sourceNode);
      const targetCenter = getNodeCenter(targetNode);
      
      const startScreen = window.GraphCanvas.worldToScreen(sourceCenter.x, sourceCenter.y);
      const endScreen = window.GraphCanvas.worldToScreen(targetCenter.x, targetCenter.y);
      
      // Get edge style (use custom or default)
      const style = edge.metadata?.style || {};
      const color = style.color || DEFAULT_EDGE_STYLE.color;
      const thickness = style.thickness || DEFAULT_EDGE_STYLE.thickness;
      const dashPattern = style.dashPattern || DEFAULT_EDGE_STYLE.dashPattern;
      const lineStyle = normalizeLineStyle(style.lineStyle || DEFAULT_EDGE_STYLE.lineStyle);
      const direction = style.direction || edge.edgeType || DEFAULT_EDGE_STYLE.direction;
      
      // Highlight if selected
      const isSelected = selectedEdge && selectedEdge.id === edge.id;
      const strokeColor = isSelected ? '#14b8a6' : color;
      const lineWidth = isSelected ? thickness + 2 : thickness;
      
      // Draw edge line
      ctx.save();
      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = lineWidth;
      
      // Apply dash pattern
      if (dashPattern === 'dashed') {
        ctx.setLineDash([10, 5]);
      } else if (dashPattern === 'dotted') {
        ctx.setLineDash([2, 4]);
      }
      
      // Draw line (straight, wavy, elbow variants)
      if (lineStyle === 'wavy') {
        drawWavyLine(ctx, startScreen.x, startScreen.y, endScreen.x, endScreen.y);
      } else if (isElbowStyle(lineStyle)) {
        const elbowPoints = getElbowPoints(startScreen.x, startScreen.y, endScreen.x, endScreen.y, lineStyle);
        drawElbowLine(ctx, elbowPoints);
      } else {
        ctx.beginPath();
        ctx.moveTo(startScreen.x, startScreen.y);
        ctx.lineTo(endScreen.x, endScreen.y);
        ctx.stroke();
      }
      
      // Reset dash pattern
      ctx.setLineDash([]);
      
      // Draw arrowheads based on direction and orientation
      const arrowSegments = getArrowSegments(lineStyle, startScreen, endScreen);
      const orientation = style.orientation || 'forward';
      if (direction === 'directed') {
        if (orientation === 'forward') {
          drawArrowhead(ctx, arrowSegments.forward.from, arrowSegments.forward.to, strokeColor);
        } else {
          drawArrowhead(ctx, arrowSegments.backward.from, arrowSegments.backward.to, strokeColor);
        }
      } else if (direction === 'bidirectional') {
        drawArrowhead(ctx, arrowSegments.forward.from, arrowSegments.forward.to, strokeColor);
        drawArrowhead(ctx, arrowSegments.backward.from, arrowSegments.backward.to, strokeColor);
      }
      
      // Draw label if exists
      if (edge.label) {
        const midX = (startScreen.x + endScreen.x) / 2;
        const midY = (startScreen.y + endScreen.y) / 2;
        
        ctx.fillStyle = 'rgba(18, 21, 22, 0.9)';
        ctx.strokeStyle = 'rgba(154, 168, 173, 0.8)';
        ctx.lineWidth = 1;
        
        const textMetrics = ctx.measureText(edge.label);
        const padding = 6;
        const labelWidth = textMetrics.width + padding * 2;
        const labelHeight = 20;
        
        ctx.fillRect(midX - labelWidth / 2, midY - labelHeight / 2, labelWidth, labelHeight);
        ctx.strokeRect(midX - labelWidth / 2, midY - labelHeight / 2, labelWidth, labelHeight);
        
        ctx.fillStyle = '#ECFFFF';
        ctx.font = '12px system-ui, -apple-system, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(edge.label, midX, midY);
      }
      
      ctx.restore();
    });
  }

  function drawWavyLine(ctx, fromX, fromY, toX, toY) {
    const dx = toX - fromX;
    const dy = toY - fromY;
    const length = Math.sqrt(dx * dx + dy * dy);
    const angle = Math.atan2(dy, dx);
    const amplitude = 8;
    const frequency = 0.05;
    
    ctx.beginPath();
    ctx.moveTo(fromX, fromY);
    
    for (let i = 0; i <= length; i += 2) {
      const progress = i / length;
      const waveOffset = Math.sin(i * frequency) * amplitude;
      const x = fromX + Math.cos(angle) * i - Math.sin(angle) * waveOffset;
      const y = fromY + Math.sin(angle) * i + Math.cos(angle) * waveOffset;
      ctx.lineTo(x, y);
    }
    
    ctx.stroke();
  }

  function drawArrowhead(ctx, fromPoint, toPoint, color) {
    // Get current zoom scale to properly size arrowhead
    const currentScale = window.GraphCanvas.getScale();
    
    // Scale arrowhead size and offset by zoom level
    const headlen = 12 * currentScale;
    const offsetDistance = 60 * currentScale; // Approximate node radius
    
    const fromX = fromPoint.x;
    const fromY = fromPoint.y;
    const toX = toPoint.x;
    const toY = toPoint.y;
    const angle = Math.atan2(toY - fromY, toX - fromX);
    
    // Offset arrow to end at node boundary, not center
    const endX = toX - offsetDistance * Math.cos(angle);
    const endY = toY - offsetDistance * Math.sin(angle);
    
    ctx.fillStyle = color || 'rgba(154, 168, 173, 0.8)';
    ctx.beginPath();
    ctx.moveTo(endX, endY);
    ctx.lineTo(
      endX - headlen * Math.cos(angle - Math.PI / 6),
      endY - headlen * Math.sin(angle - Math.PI / 6)
    );
    ctx.lineTo(
      endX - headlen * Math.cos(angle + Math.PI / 6),
      endY - headlen * Math.sin(angle + Math.PI / 6)
    );
    ctx.closePath();
    ctx.fill();
  }

  function drawElbowLine(ctx, points) {
    if (!points || points.length < 2) return;
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
      ctx.lineTo(points[i].x, points[i].y);
    }
    ctx.stroke();
  }

  function getElbowPoints(startX, startY, endX, endY, lineStyle) {
    // 3-segment elbow: V-H-V (vertical, horizontal, vertical)
    if (lineStyle === 'elbow_vhv') {
      const midY = (startY + endY) / 2;
      return [
        { x: startX, y: startY },
        { x: startX, y: midY },
        { x: endX, y: midY },
        { x: endX, y: endY }
      ];
    }

    // 2-segment elbow: V-H (vertical then horizontal)
    if (lineStyle === 'elbow_vh') {
      return [
        { x: startX, y: startY },
        { x: startX, y: endY },
        { x: endX, y: endY }
      ];
    }

    // 2-segment elbow: H-V (horizontal then vertical)
    if (lineStyle === 'elbow_hv') {
      return [
        { x: startX, y: startY },
        { x: endX, y: startY },
        { x: endX, y: endY }
      ];
    }

    // Default 3-segment elbow: H-V-H (horizontal, vertical, horizontal)
    const midX = (startX + endX) / 2;
    return [
      { x: startX, y: startY },
      { x: midX, y: startY },
      { x: midX, y: endY },
      { x: endX, y: endY }
    ];
  }

  function getArrowSegments(lineStyle, startPoint, endPoint) {
    if (isElbowStyle(lineStyle)) {
      const points = getElbowPoints(startPoint.x, startPoint.y, endPoint.x, endPoint.y, lineStyle);
      const forwardFrom = points[points.length - 2];
      const forwardTo = points[points.length - 1];
      const backwardFrom = points[1] || points[0];
      const backwardTo = points[0];
      return {
        forward: { from: forwardFrom, to: forwardTo },
        backward: { from: backwardFrom, to: backwardTo }
      };
    }

    return {
      forward: { from: startPoint, to: endPoint },
      backward: { from: endPoint, to: startPoint }
    };
  }

  function normalizeLineStyle(lineStyle) {
    if (!lineStyle) return DEFAULT_EDGE_STYLE.lineStyle;
    // Backward compatibility for previously saved generic elbow style
    if (lineStyle === 'elbow') return 'elbow_hvh';
    return lineStyle;
  }

  function isElbowStyle(lineStyle) {
    return lineStyle === 'elbow_hvh' || lineStyle === 'elbow_vhv' || 
           lineStyle === 'elbow_hv' || lineStyle === 'elbow_vh';
  }

  function getNodeCenter(node) {
    return {
      x: node.x + node.width / 2,
      y: node.y + node.height / 2
    };
  }

  function getEdgeAt(worldX, worldY) {
    const nodes = window.GraphNodes.getNodes();
    const threshold = 30 / window.GraphCanvas.getScale(); // Expanded hit detection for easier selection

    for (let i = edges.length - 1; i >= 0; i--) {
      const edge = edges[i];
      const sourceNode = nodes.find(n => n.id === edge.sourceNodeId);
      const targetNode = nodes.find(n => n.id === edge.targetNodeId);
      
      if (!sourceNode || !targetNode) continue;
      
      const sourceCenter = getNodeCenter(sourceNode);
      const targetCenter = getNodeCenter(targetNode);
      
      // Get edge style to determine if it's an elbow line
      const style = edge.metadata?.style || {};
      const lineStyle = normalizeLineStyle(style.lineStyle || DEFAULT_EDGE_STYLE.lineStyle);
      
      let minDist = Infinity;
      
      if (isElbowStyle(lineStyle)) {
        // For elbow lines, check distance to each segment
        const elbowPoints = getElbowPoints(sourceCenter.x, sourceCenter.y, targetCenter.x, targetCenter.y, lineStyle);
        
        for (let j = 0; j < elbowPoints.length - 1; j++) {
          const dist = distanceToLineSegment(
            worldX, worldY,
            elbowPoints[j].x, elbowPoints[j].y,
            elbowPoints[j + 1].x, elbowPoints[j + 1].y
          );
          minDist = Math.min(minDist, dist);
        }
      } else {
        // For straight/wavy lines, check distance to direct line segment
        minDist = distanceToLineSegment(
          worldX, worldY,
          sourceCenter.x, sourceCenter.y,
          targetCenter.x, targetCenter.y
        );
      }
      
      if (minDist < threshold) {
        return edge;
      }
    }
    return null;
  }

  function distanceToLineSegment(px, py, x1, y1, x2, y2) {
    const A = px - x1;
    const B = py - y1;
    const C = x2 - x1;
    const D = y2 - y1;
    
    const dot = A * C + B * D;
    const lenSq = C * C + D * D;
    let param = -1;
    
    if (lenSq !== 0) param = dot / lenSq;
    
    let xx, yy;
    
    if (param < 0) {
      xx = x1;
      yy = y1;
    } else if (param > 1) {
      xx = x2;
      yy = y2;
    } else {
      xx = x1 + param * C;
      yy = y1 + param * D;
    }
    
    const dx = px - xx;
    const dy = py - yy;
    return Math.sqrt(dx * dx + dy * dy);
  }

  async function createEdge(sourceNodeId, targetNodeId, styleOrLabel) {
    try {
      // Support both old signature (label string) and new signature (style object)
      let label = '';
      let edgeStyle = {};
      
      if (typeof styleOrLabel === 'string') {
        // Old signature: just a label
        label = styleOrLabel;
      } else if (typeof styleOrLabel === 'object' && styleOrLabel !== null) {
        // New signature: full style object
        label = styleOrLabel.label || '';
        edgeStyle = {
          color: styleOrLabel.color,
          thickness: styleOrLabel.thickness,
          direction: styleOrLabel.direction,
          orientation: styleOrLabel.orientation,
          dash: styleOrLabel.dash,
          lineStyle: styleOrLabel.lineStyle
        };
      }
      
      const response = await fetch(`/graph/${graphId}/edges`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_node_id: sourceNodeId,
          target_node_id: targetNodeId,
          label: label,
          edge_type: edgeStyle.direction || 'directed',
          metadata: {
            style: edgeStyle
          }
        })
      });
      const data = await response.json();
      if (data.ok) {
        await window.GraphStorage.loadGraph();
        return data.edge;
      } else {
        console.error('Failed to create edge:', data.error);
        alert('Failed to create edge: ' + (data.error || 'Unknown error'));
      }
    } catch (err) {
      console.error('Error creating edge:', err);
      alert('Error creating edge');
    }
  }

  async function updateEdge(edgeId, updates) {
    try {
      const response = await fetch(`/graph/${graphId}/edges/${edgeId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      });
      const data = await response.json();
      if (data.ok) {
        await window.GraphStorage.loadGraph();
        return data.edge;
      } else {
        console.error('Failed to update edge:', data.error);
        alert('Failed to update edge: ' + (data.error || 'Unknown error'));
      }
    } catch (err) {
      console.error('Error updating edge:', err);
      alert('Error updating edge');
    }
    return null;
  }

  async function deleteEdge(edgeId) {
    try {
      const response = await fetch(`/graph/${graphId}/edges/${edgeId}`, {
        method: 'DELETE'
      });
      const data = await response.json();
      if (data.ok) {
        await window.GraphStorage.loadGraph();
        return true;
      } else {
        console.error('Failed to delete edge:', data.error);
        alert('Failed to delete edge: ' + (data.error || 'Unknown error'));
      }
    } catch (err) {
      console.error('Error deleting edge:', err);
      alert('Error deleting edge');
    }
    return false;
  }

  function getEdges() {
    return edges;
  }

  function selectEdge(edge) {
    selectedEdge = edge;
    window.GraphCanvas.render();
    if (window.GraphToolbar) {
      window.GraphToolbar.updateEdgeSelection(edge);
    }
  }

  function getSelectedEdge() {
    return selectedEdge;
  }

  function deselectEdge() {
    selectedEdge = null;
    window.GraphCanvas.render();
    if (window.GraphToolbar) {
      window.GraphToolbar.updateEdgeSelection(null);
    }
  }

  return {
    init,
    loadEdges,
    render,
    startDrawingEdge,
    stopDrawingEdge,
    createEdge,
    updateEdge,
    deleteEdge,
    getEdges,
    getEdgeAt,
    selectEdge,
    getSelectedEdge,
    deselectEdge,
    DEFAULT_EDGE_STYLE
  };
})();
