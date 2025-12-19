/**
 * Whiteboard Shapes Module
 * Handles drawing and interaction for flowchart and geometric shapes
 * 
 * Categories:
 * - Drawing Tools: line, arrow, doubleArrow
 * - Flowchart: process, decision, inputOutput, document, manualInput, storedData, display, merge, connector
 * - Basic Shapes: rectangle, roundedRectangle, circle, ellipse, triangle, pentagon, hexagon, star
 * - Tech/Cloud Icons: cloud, ai, robot, iot, user, server, database, envelope, tower
 */

// Shape drawing functions
function drawArrow(ctx, startX, startY, endX, endY, size) {
  // Draw the line
  ctx.beginPath();
  ctx.moveTo(startX, startY);
  ctx.lineTo(endX, endY);
  ctx.stroke();
  
  // Calculate arrowhead
  const angle = Math.atan2(endY - startY, endX - startX);
  const arrowLength = size * 3; // Arrowhead length based on stroke size
  const arrowAngle = Math.PI / 6; // 30 degrees
  
  // Draw arrowhead
  ctx.beginPath();
  ctx.moveTo(endX, endY);
  ctx.lineTo(
    endX - arrowLength * Math.cos(angle - arrowAngle),
    endY - arrowLength * Math.sin(angle - arrowAngle)
  );
  ctx.moveTo(endX, endY);
  ctx.lineTo(
    endX - arrowLength * Math.cos(angle + arrowAngle),
    endY - arrowLength * Math.sin(angle + arrowAngle)
  );
  ctx.stroke();
}

function drawRoundedRectangle(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  // Corner radius based on stroke size, with a reasonable maximum
  const radius = Math.min(size * 2, Math.min(w, h) / 4);
  
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + w - radius, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
  ctx.lineTo(x + w, y + h - radius);
  ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
  ctx.lineTo(x + radius, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
  ctx.closePath();
}

function drawDecision(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  // Calculate diamond points
  const centerX = x + w / 2;
  const centerY = y + h / 2;
  
  ctx.beginPath();
  ctx.moveTo(centerX, y); // Top point
  ctx.lineTo(x + w, centerY); // Right point
  ctx.lineTo(centerX, y + h); // Bottom point
  ctx.lineTo(x, centerY); // Left point
  ctx.closePath();
}

function drawInputOutput(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  // Parallelogram with 20% skew
  const skew = w * 0.2;
  
  ctx.beginPath();
  ctx.moveTo(x + skew, y);
  ctx.lineTo(x + w, y);
  ctx.lineTo(x + w - skew, y + h);
  ctx.lineTo(x, y + h);
  ctx.closePath();
}

function drawConnector(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  // Draw circle with diameter equal to the smaller dimension
  const diameter = Math.min(w, h);
  const centerX = x + w / 2;
  const centerY = y + h / 2;
  const radius = diameter / 2;
  
  ctx.beginPath();
  ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
  ctx.closePath();
}

// New shape drawing functions

function drawDoubleArrow(ctx, startX, startY, endX, endY, size) {
  // Draw the line
  ctx.beginPath();
  ctx.moveTo(startX, startY);
  ctx.lineTo(endX, endY);
  ctx.stroke();
  
  const angle = Math.atan2(endY - startY, endX - startX);
  const arrowLength = size * 3;
  const arrowAngle = Math.PI / 6;
  
  // Draw arrowhead at end
  ctx.beginPath();
  ctx.moveTo(endX, endY);
  ctx.lineTo(
    endX - arrowLength * Math.cos(angle - arrowAngle),
    endY - arrowLength * Math.sin(angle - arrowAngle)
  );
  ctx.moveTo(endX, endY);
  ctx.lineTo(
    endX - arrowLength * Math.cos(angle + arrowAngle),
    endY - arrowLength * Math.sin(angle + arrowAngle)
  );
  ctx.stroke();
  
  // Draw arrowhead at start
  ctx.beginPath();
  ctx.moveTo(startX, startY);
  ctx.lineTo(
    startX + arrowLength * Math.cos(angle - arrowAngle),
    startY + arrowLength * Math.sin(angle - arrowAngle)
  );
  ctx.moveTo(startX, startY);
  ctx.lineTo(
    startX + arrowLength * Math.cos(angle + arrowAngle),
    startY + arrowLength * Math.sin(angle + arrowAngle)
  );
  ctx.stroke();
}

function drawProcess(ctx, startX, startY, endX, endY, size) {
  // Process is just a rectangle (same as rectangle)
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  ctx.rect(x, y, w, h);
}

function drawDocument(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  // Rectangle with wavy bottom
  const waveHeight = h * 0.1;
  
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x + w, y);
  ctx.lineTo(x + w, y + h - waveHeight);
  
  // Wavy bottom line
  ctx.quadraticCurveTo(x + w * 0.75, y + h - waveHeight * 2, x + w * 0.5, y + h - waveHeight);
  ctx.quadraticCurveTo(x + w * 0.25, y + h, x, y + h - waveHeight);
  
  ctx.lineTo(x, y);
  ctx.closePath();
}

function drawManualInput(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  // Trapezoid slanted at top
  const slant = w * 0.15;
  
  ctx.beginPath();
  ctx.moveTo(x, y + slant);
  ctx.lineTo(x + w, y);
  ctx.lineTo(x + w, y + h);
  ctx.lineTo(x, y + h);
  ctx.closePath();
}

function drawStoredData(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  // Cylinder shape
  const curveWidth = w * 0.15;
  
  ctx.beginPath();
  // Top curve
  ctx.moveTo(x, y + h * 0.1);
  ctx.quadraticCurveTo(x + curveWidth, y, x + curveWidth, y + h * 0.1);
  ctx.lineTo(x + curveWidth, y + h * 0.9);
  // Bottom curve
  ctx.quadraticCurveTo(x + curveWidth, y + h, x, y + h * 0.9);
  ctx.closePath();
  
  // Right side
  ctx.beginPath();
  ctx.moveTo(x + curveWidth, y + h * 0.1);
  ctx.lineTo(x + w, y + h * 0.1);
  ctx.lineTo(x + w, y + h * 0.9);
  ctx.lineTo(x + curveWidth, y + h * 0.9);
  ctx.stroke();
}

function drawDisplay(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  // Curved monitor shape
  const curve = w * 0.1;
  
  ctx.beginPath();
  ctx.moveTo(x + curve, y);
  ctx.lineTo(x + w - curve, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + curve);
  ctx.lineTo(x + w, y + h - curve);
  ctx.quadraticCurveTo(x + w, y + h, x + w - curve, y + h);
  ctx.lineTo(x + curve, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - curve);
  ctx.lineTo(x, y + curve);
  ctx.quadraticCurveTo(x, y, x + curve, y);
  ctx.closePath();
}

function drawMerge(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  // Triangle pointing down
  const centerX = x + w / 2;
  
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x + w, y);
  ctx.lineTo(centerX, y + h);
  ctx.closePath();
}

function drawCircle(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  // Perfect circle using smaller dimension
  const diameter = Math.min(w, h);
  const radius = diameter / 2;
  const centerX = x + w / 2;
  const centerY = y + h / 2;
  
  ctx.beginPath();
  ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
  ctx.closePath();
}

function drawEllipse(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  const centerX = x + w / 2;
  const centerY = y + h / 2;
  const radiusX = w / 2;
  const radiusY = h / 2;
  
  ctx.beginPath();
  ctx.ellipse(centerX, centerY, radiusX, radiusY, 0, 0, 2 * Math.PI);
  ctx.closePath();
}

function drawTriangle(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  const centerX = x + w / 2;
  
  ctx.beginPath();
  ctx.moveTo(centerX, y);
  ctx.lineTo(x + w, y + h);
  ctx.lineTo(x, y + h);
  ctx.closePath();
}

function drawPentagon(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  const centerX = x + w / 2;
  const centerY = y + h / 2;
  const radius = Math.min(w, h) / 2;
  
  ctx.beginPath();
  for (let i = 0; i < 5; i++) {
    const angle = (i * 2 * Math.PI / 5) - Math.PI / 2;
    const px = centerX + radius * Math.cos(angle);
    const py = centerY + radius * Math.sin(angle);
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.closePath();
}

function drawHexagon(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  const centerX = x + w / 2;
  const centerY = y + h / 2;
  const radius = Math.min(w, h) / 2;
  
  ctx.beginPath();
  for (let i = 0; i < 6; i++) {
    const angle = (i * 2 * Math.PI / 6);
    const px = centerX + radius * Math.cos(angle);
    const py = centerY + radius * Math.sin(angle);
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.closePath();
}

function drawStar(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  const centerX = x + w / 2;
  const centerY = y + h / 2;
  const outerRadius = Math.min(w, h) / 2;
  const innerRadius = outerRadius * 0.4;
  
  ctx.beginPath();
  for (let i = 0; i < 10; i++) {
    const angle = (i * Math.PI / 5) - Math.PI / 2;
    const radius = i % 2 === 0 ? outerRadius : innerRadius;
    const px = centerX + radius * Math.cos(angle);
    const py = centerY + radius * Math.sin(angle);
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.closePath();
}

// Tech/Cloud Icons
function drawCloud(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  const centerY = y + h / 2;
  
  ctx.beginPath();
  // Bottom flat line
  ctx.moveTo(x + w * 0.2, y + h * 0.75);
  ctx.lineTo(x + w * 0.8, y + h * 0.75);
  // Right small arc
  ctx.arc(x + w * 0.75, y + h * 0.6, w * 0.15, Math.PI / 3, -Math.PI / 2, false);
  // Top large arc
  ctx.arc(x + w * 0.5, y + h * 0.4, w * 0.25, -Math.PI / 2, Math.PI, false);
  // Left small arc
  ctx.arc(x + w * 0.25, y + h * 0.6, w * 0.15, Math.PI, Math.PI / 3, false);
  ctx.closePath();
}

function drawAI(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  const centerX = x + w / 2;
  const centerY = y + h / 2;
  const radius = Math.min(w, h) / 3;
  
  ctx.beginPath();
  // Central hexagon
  for (let i = 0; i < 6; i++) {
    const angle = (i * Math.PI / 3);
    const px = centerX + radius * Math.cos(angle);
    const py = centerY + radius * Math.sin(angle);
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.closePath();
  
  // Connection nodes at 4 corners
  const nodeRadius = size * 1.5;
  const corners = [
    [x + w * 0.15, y + h * 0.15],
    [x + w * 0.85, y + h * 0.15],
    [x + w * 0.85, y + h * 0.85],
    [x + w * 0.15, y + h * 0.85]
  ];
  
  corners.forEach(([cx, cy]) => {
    ctx.moveTo(cx + nodeRadius, cy);
    ctx.arc(cx, cy, nodeRadius, 0, 2 * Math.PI);
    // Line to center
    ctx.moveTo(cx, cy);
    ctx.lineTo(centerX, centerY);
  });
}

function drawRobot(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  // Head
  const headH = h * 0.3;
  ctx.rect(x + w * 0.25, y, w * 0.5, headH);
  
  // Antenna
  ctx.moveTo(x + w * 0.5, y);
  ctx.lineTo(x + w * 0.5, y - h * 0.1);
  ctx.moveTo(x + w * 0.5 - size, y - h * 0.1);
  ctx.arc(x + w * 0.5, y - h * 0.1, size, 0, 2 * Math.PI);
  
  // Body
  ctx.rect(x + w * 0.2, y + headH, w * 0.6, h * 0.5);
  
  // Arms
  ctx.rect(x, y + headH + h * 0.1, w * 0.2, h * 0.25);
  ctx.rect(x + w * 0.8, y + headH + h * 0.1, w * 0.2, h * 0.25);
  
  // Eyes
  const eyeY = y + headH * 0.4;
  ctx.moveTo(x + w * 0.35 + size * 0.5, eyeY);
  ctx.arc(x + w * 0.35, eyeY, size * 0.5, 0, 2 * Math.PI);
  ctx.moveTo(x + w * 0.65 + size * 0.5, eyeY);
  ctx.arc(x + w * 0.65, eyeY, size * 0.5, 0, 2 * Math.PI);
}

function drawIoT(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  const centerX = x + w / 2;
  const centerY = y + h / 2;
  
  // Central device (small rectangle)
  const deviceW = w * 0.2;
  const deviceH = h * 0.2;
  ctx.rect(centerX - deviceW / 2, centerY - deviceH / 2, deviceW, deviceH);
  
  // Connected nodes in a circle
  const nodeCount = 6;
  const radius = Math.min(w, h) * 0.35;
  const nodeRadius = size * 1.2;
  
  for (let i = 0; i < nodeCount; i++) {
    const angle = (i * 2 * Math.PI / nodeCount) - Math.PI / 2;
    const nx = centerX + radius * Math.cos(angle);
    const ny = centerY + radius * Math.sin(angle);
    
    // Node circle
    ctx.moveTo(nx + nodeRadius, ny);
    ctx.arc(nx, ny, nodeRadius, 0, 2 * Math.PI);
    
    // Connection line to center
    ctx.moveTo(nx, ny);
    ctx.lineTo(centerX, centerY);
  }
}

function drawUser(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  const centerX = x + w / 2;
  const headRadius = Math.min(w, h) * 0.2;
  
  // Head (circle)
  ctx.moveTo(centerX + headRadius, y + h * 0.2);
  ctx.arc(centerX, y + h * 0.2, headRadius, 0, 2 * Math.PI);
  
  // Body (trapezoid)
  ctx.moveTo(centerX - w * 0.15, y + h * 0.35);
  ctx.lineTo(centerX + w * 0.15, y + h * 0.35);
  ctx.lineTo(centerX + w * 0.35, y + h * 0.85);
  ctx.lineTo(centerX - w * 0.35, y + h * 0.85);
  ctx.closePath();
}

function drawServer(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  // Three stacked server units
  const unitH = h / 3;
  
  for (let i = 0; i < 3; i++) {
    const unitY = y + i * unitH;
    // Unit rectangle
    ctx.rect(x, unitY, w, unitH);
    
    // Two indicator lights
    const lightY = unitY + unitH * 0.5;
    const lightRadius = size * 0.6;
    ctx.moveTo(x + w * 0.15 + lightRadius, lightY);
    ctx.arc(x + w * 0.15, lightY, lightRadius, 0, 2 * Math.PI);
    ctx.moveTo(x + w * 0.3 + lightRadius, lightY);
    ctx.arc(x + w * 0.3, lightY, lightRadius, 0, 2 * Math.PI);
  }
}

function drawDatabase(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  const centerX = x + w / 2;
  const radiusX = w / 2;
  const radiusY = h * 0.15;
  
  ctx.beginPath();
  // Top ellipse
  ctx.ellipse(centerX, y + radiusY, radiusX, radiusY, 0, 0, 2 * Math.PI);
  
  // Left line
  ctx.moveTo(x, y + radiusY);
  ctx.lineTo(x, y + h - radiusY);
  
  // Right line
  ctx.moveTo(x + w, y + radiusY);
  ctx.lineTo(x + w, y + h - radiusY);
  
  // Bottom ellipse
  ctx.ellipse(centerX, y + h - radiusY, radiusX, radiusY, 0, 0, 2 * Math.PI);
  
  // Middle divider lines
  ctx.moveTo(x, y + h * 0.4);
  ctx.ellipse(centerX, y + h * 0.4, radiusX, radiusY, 0, Math.PI, 2 * Math.PI);
  ctx.moveTo(x, y + h * 0.65);
  ctx.ellipse(centerX, y + h * 0.65, radiusX, radiusY, 0, Math.PI, 2 * Math.PI);
}

function drawEnvelope(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  const centerX = x + w / 2;
  
  ctx.beginPath();
  // Envelope rectangle
  ctx.rect(x, y, w, h);
  
  // Flap lines
  ctx.moveTo(x, y);
  ctx.lineTo(centerX, y + h * 0.5);
  ctx.lineTo(x + w, y);
  ctx.moveTo(x, y + h);
  ctx.lineTo(centerX, y + h * 0.5);
  ctx.moveTo(x + w, y + h);
  ctx.lineTo(centerX, y + h * 0.5);
}

function drawTower(ctx, startX, startY, endX, endY, size) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  const w = Math.abs(endX - startX);
  const h = Math.abs(endY - startY);
  
  const centerX = x + w / 2;
  
  ctx.beginPath();
  // Tower body (trapezoid)
  ctx.moveTo(centerX - w * 0.15, y + h * 0.4);
  ctx.lineTo(centerX + w * 0.15, y + h * 0.4);
  ctx.lineTo(centerX + w * 0.25, y + h);
  ctx.lineTo(centerX - w * 0.25, y + h);
  ctx.closePath();
  
  // Antenna
  ctx.moveTo(centerX, y + h * 0.4);
  ctx.lineTo(centerX, y);
  
  // Signal waves (3 arcs on each side)
  const waveY = y + h * 0.15;
  for (let i = 1; i <= 3; i++) {
    const waveRadius = w * 0.15 * i;
    ctx.moveTo(centerX - waveRadius, waveY);
    ctx.arc(centerX, waveY, waveRadius, Math.PI, 0, true);
  }
}

// Shape rendering in draw context
function drawShapeStroke(ctx, strokeObj) {
  const objPath = strokeObj.props?.path || strokeObj.path || [];
  const strokeType = strokeObj.props?.strokeType || strokeObj.strokeType;
  const objSize = strokeObj.props?.size || strokeObj.size;
  
  if (objPath.length < 2) return;
  
  const start = objPath[0];
  const end = objPath[1];
  
  // Drawing Tools
  if (strokeType === 'arrow') {
    drawArrow(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'doubleArrow') {
    drawDoubleArrow(ctx, start.x, start.y, end.x, end.y, objSize);
  } 
  // Flowchart Shapes
  else if (strokeType === 'process') {
    drawProcess(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'decision') {
    drawDecision(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'inputOutput') {
    drawInputOutput(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'document') {
    drawDocument(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'manualInput') {
    drawManualInput(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'storedData') {
    drawStoredData(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'display') {
    drawDisplay(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'merge') {
    drawMerge(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'connector') {
    drawConnector(ctx, start.x, start.y, end.x, end.y, objSize);
  } 
  // Basic Shapes
  else if (strokeType === 'rectangle') {
    const x = Math.min(start.x, end.x);
    const y = Math.min(start.y, end.y);
    const w = Math.abs(end.x - start.x);
    const h = Math.abs(end.y - start.y);
    ctx.rect(x, y, w, h);
  } else if (strokeType === 'roundedRectangle') {
    drawRoundedRectangle(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'circle') {
    drawCircle(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'ellipse') {
    drawEllipse(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'triangle') {
    drawTriangle(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'pentagon') {
    drawPentagon(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'hexagon') {
    drawHexagon(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'star') {
    drawStar(ctx, start.x, start.y, end.x, end.y, objSize);
  } 
  // Tech/Cloud Icons
  else if (strokeType === 'cloud') {
    drawCloud(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'ai') {
    drawAI(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'robot') {
    drawRobot(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'iot') {
    drawIoT(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'user') {
    drawUser(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'server') {
    drawServer(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'database') {
    drawDatabase(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'envelope') {
    drawEnvelope(ctx, start.x, start.y, end.x, end.y, objSize);
  } else if (strokeType === 'tower') {
    drawTower(ctx, start.x, start.y, end.x, end.y, objSize);
  } else {
    // Draw normal stroke path (fallback for pen, marker, highlighter, line)
    if (objPath.length) {
      ctx.moveTo(objPath[0].x, objPath[0].y);
      for (let i = 1; i < objPath.length; i++) {
        ctx.lineTo(objPath[i].x, objPath[i].y);
      }
    }
  }
}

// Shape path creation for hit testing
function createShapePath(ctx, strokeObj) {
  const objPath = strokeObj.props?.path || strokeObj.path || [];
  const strokeType = strokeObj.props?.strokeType || strokeObj.strokeType;
  
  if (objPath.length < 2) {
    // Default path creation for lines and other strokes
    if (objPath.length) {
      ctx.moveTo(objPath[0].x, objPath[0].y);
      for (let i = 1; i < objPath.length; i++) {
        ctx.lineTo(objPath[i].x, objPath[i].y);
      }
    }
    return;
  }
  
  const start = objPath[0];
  const end = objPath[1];
  const x = Math.min(start.x, end.x);
  const y = Math.min(start.y, end.y);
  const w = Math.abs(end.x - start.x);
  const h = Math.abs(end.y - start.y);
  
  // For all shape types, use bounding box for hit testing (simplified)
  ctx.rect(x, y, w, h);
}

// Shape hit testing
function isPointOnShape(strokeObj, point) {
  const objPath = strokeObj.props?.path || strokeObj.path || [];
  const strokeType = strokeObj.props?.strokeType || strokeObj.strokeType;
  
  if (!objPath.length || objPath.length < 2) {
    return false;
  }
  
  const start = objPath[0];
  const end = objPath[1];
  const x = Math.min(start.x, end.x);
  const y = Math.min(start.y, end.y);
  const w = Math.abs(end.x - start.x);
  const h = Math.abs(end.y - start.y);
  
  // For all shape types, use bounding box hit testing
  return point.x >= x && point.x <= x + w && point.y >= y && point.y <= y + h;
}

// List of shape tool types
const SHAPE_TOOLS = [
  // Drawing Tools
  'arrow', 'doubleArrow',
  // Flowchart
  'process', 'decision', 'inputOutput', 'document', 'manualInput', 
  'storedData', 'display', 'merge', 'connector',
  // Basic Shapes
  'rectangle', 'roundedRectangle', 'circle', 'ellipse', 
  'triangle', 'pentagon', 'hexagon', 'star',
  // Tech/Cloud Icons
  'cloud', 'ai', 'robot', 'iot', 'user', 'server', 'database', 'envelope', 'tower'
];

// Check if current tool is a shape tool
function isShapeTool(toolName) {
  return SHAPE_TOOLS.includes(toolName);
}

// Export to browser window object
if (typeof window !== 'undefined') {
  window.drawArrow = drawArrow;
  window.drawRoundedRectangle = drawRoundedRectangle;
  window.drawDecision = drawDecision;
  window.drawInputOutput = drawInputOutput;
  window.drawConnector = drawConnector;
  window.drawDoubleArrow = drawDoubleArrow;
  window.drawProcess = drawProcess;
  window.drawDocument = drawDocument;
  window.drawManualInput = drawManualInput;
  window.drawStoredData = drawStoredData;
  window.drawDisplay = drawDisplay;
  window.drawMerge = drawMerge;
  window.drawCircle = drawCircle;
  window.drawEllipse = drawEllipse;
  window.drawTriangle = drawTriangle;
  window.drawPentagon = drawPentagon;
  window.drawHexagon = drawHexagon;
  window.drawStar = drawStar;
  window.drawCloud = drawCloud;
  window.drawAI = drawAI;
  window.drawRobot = drawRobot;
  window.drawIoT = drawIoT;
  window.drawUser = drawUser;
  window.drawServer = drawServer;
  window.drawDatabase = drawDatabase;
  window.drawEnvelope = drawEnvelope;
  window.drawTower = drawTower;
  window.drawShapeStroke = drawShapeStroke;
  window.createShapePath = createShapePath;
  window.isPointOnShape = isPointOnShape;
  window.isShapeTool = isShapeTool;
  window.SHAPE_TOOLS = SHAPE_TOOLS;
}

// Export functions for use in Node.js modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    // Original shapes
    drawArrow,
    drawRoundedRectangle,
    drawDecision,
    drawInputOutput,
    drawConnector,
    // New shapes
    drawDoubleArrow,
    drawProcess,
    drawDocument,
    drawManualInput,
    drawStoredData,
    drawDisplay,
    drawMerge,
    drawCircle,
    drawEllipse,
    drawTriangle,
    drawPentagon,
    drawHexagon,
    drawStar,
    // Tech/Cloud Icons
    drawCloud,
    drawAI,
    drawRobot,
    drawIoT,
    drawUser,
    drawServer,
    drawDatabase,
    drawEnvelope,
    drawTower,
    // Core functions
    drawShapeStroke,
    createShapePath,
    isPointOnShape,
    isShapeTool,
    SHAPE_TOOLS
  };
}
