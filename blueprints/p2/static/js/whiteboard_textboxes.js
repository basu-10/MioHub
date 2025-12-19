/**
 * Whiteboard Text Boxes Module
 * Handles creation of text boxes with various shape backgrounds
 * Uses the same shapes as the shapes module for consistency
 * 
 * Categories:
 * - Drawing Tools: line, arrow, doubleArrow
 * - Flowchart: process, decision, inputOutput, document, manualInput, storedData, display, merge, connector
 * - Basic Shapes: rectangle, roundedRectangle, circle, ellipse, triangle, pentagon, hexagon, star
 * - Tech/Cloud Icons: cloud, ai, robot, iot, user, server, database, envelope, tower
 */

/**
 * Creates a text box with a shape background
 * @param {string} shapeType - The shape type (process, decision, etc.)
 * @param {number} x - X coordinate
 * @param {number} y - Y coordinate
 * @param {string} text - Text content
 * @param {object} options - Additional options (color, fontSize, etc.)
 * @returns {object} Text box object with shape and text
 */
function createTextBox(shapeType, x, y, text = 'Text', options = {}) {
  const {
    color = '#000000',
    fontSize = 16,
    backgroundColor = '#ffffff',
    strokeColor = '#000000',
    strokeSize = 2,
    width = 150,
    height = 80,
    padding = 10
  } = options;

  // Generate unique IDs for the shape and text
  const shapeId = nextObjectId++;
  const textId = nextObjectId++;

  // Create the shape object (background)
  const shapeObj = {
    id: shapeId,
    type: 'stroke',
    layer: objects.length,
    props: {
      strokeType: shapeType,
      path: createTextBoxShapePath(shapeType, x, y, width, height),
      color: strokeColor,
      size: strokeSize,
      transparency: 1.0
    }
  };

  // Calculate text position (centered in shape)
  const textX = x + padding;
  const textY = y + height / 2;

  // Create the text object
  const textObj = {
    id: textId,
    type: 'text',
    layer: objects.length + 1,
    props: {
      text: text,
      x: textX,
      y: textY,
      fontSize: fontSize,
      color: color,
      maxWordsPerLine: Math.floor((width - padding * 2) / (fontSize * 0.6))
    }
  };

  return { shape: shapeObj, text: textObj };
}

/**
 * Creates a path for a text box shape
 * @param {string} shapeType - The shape type
 * @param {number} x - X coordinate
 * @param {number} y - Y coordinate
 * @param {number} width - Width
 * @param {number} height - Height
 * @returns {Array} Path array for the shape
 */
function createTextBoxShapePath(shapeType, x, y, width, height) {
  const endX = x + width;
  const endY = y + height;
  
  // For most shapes, we just need start and end points
  // The actual drawing is handled by the shapes module
  return [
    { x: x, y: y },
    { x: endX, y: endY }
  ];
}

/**
 * Checks if a shape type is valid for text boxes
 * @param {string} shapeType - The shape type to check
 * @returns {boolean} True if valid
 */
function isValidTextBoxShape(shapeType) {
  const validShapes = [
    // Drawing Tools
    'line', 'arrow', 'doubleArrow',
    // Flowchart
    'process', 'decision', 'inputOutput', 'document', 'manualInput', 
    'storedData', 'display', 'merge', 'connector',
    // Basic Shapes
    'rectangle', 'roundedRectangle', 'circle', 'ellipse', 'triangle', 
    'pentagon', 'hexagon', 'star',
    // Tech/Cloud Icons
    'cloud', 'ai', 'robot', 'iot', 'user', 'server', 'database', 
    'envelope', 'tower'
  ];
  return validShapes.includes(shapeType);
}

/**
 * Initiates text box placement mode
 * @param {string} shapeType - The shape type
 */
function promptCreateTextBox(shapeType) {
  if (!isValidTextBoxShape(shapeType)) {
    console.error('Invalid text box shape type:', shapeType);
    return;
  }

  // Close the text boxes dropdown
  const textboxesDropdown = document.getElementById('textboxes-dropdown');
  if (textboxesDropdown) {
    textboxesDropdown.classList.add('hidden');
  }

  // Set pending text box mode with the selected shape type
  window.pendingTextBoxShape = shapeType;
  
  // Change cursor to indicate placement mode
  if (window.canvas) {
    window.canvas.style.cursor = 'crosshair';
  }
  
  console.log('Text box placement mode activated. Click on canvas to place.');
}

/**
 * Places a text box at the specified location
 * @param {number} x - X coordinate
 * @param {number} y - Y coordinate
 * @param {string} shapeType - The shape type
 */
function placeTextBox(x, y, shapeType) {
  if (!isValidTextBoxShape(shapeType)) {
    console.error('Invalid text box shape type:', shapeType);
    return;
  }

  // Adjust position so shape is centered on click point
  const adjustedX = x - 75; // Half of default width (150)
  const adjustedY = y - 40; // Half of default height (80)

  // Create the text box with default "Sample Text"
  const textBox = createTextBox(shapeType, adjustedX, adjustedY, 'Sample Text', {
    color: window.color || '#000000',
    fontSize: parseInt(document.getElementById('text-size')?.value) || 16,
    strokeColor: window.color || '#000000',
    strokeSize: window.size || 2
  });

  // Add both objects to the canvas
  if (typeof window.addObject === 'function') {
    window.addObject(textBox.shape);
    window.addObject(textBox.text);
  }

  // Refresh the canvas
  if (typeof window.redraw === 'function') {
    window.redraw();
  }

  // Add to undo stack
  if (typeof window.addCommand === 'function') {
    window.addCommand({
      undo: () => {
        removeObject(textBox.text.id);
        removeObject(textBox.shape.id);
        if (typeof window.redraw === 'function') {
          window.redraw();
        }
      },
      redo: () => {
        if (typeof window.addObject === 'function') {
          window.addObject(textBox.shape);
          window.addObject(textBox.text);
        }
        if (typeof window.redraw === 'function') {
          window.redraw();
        }
      }
    });
  }

  // Clear pending state
  window.pendingTextBoxShape = null;
  if (window.canvas) {
    window.canvas.style.cursor = 'default';
  }
}

/**
 * Helper function to remove an object by ID
 * @param {number} id - Object ID to remove
 */
function removeObject(id) {
  const index = objects.findIndex(o => o.id === id);
  if (index !== -1) {
    objects.splice(index, 1);
  }
}

// Expose functions to window for global access
if (typeof window !== 'undefined') {
  window.createTextBox = createTextBox;
  window.createTextBoxShapePath = createTextBoxShapePath;
  window.isValidTextBoxShape = isValidTextBoxShape;
  window.promptCreateTextBox = promptCreateTextBox;
  window.placeTextBox = placeTextBox;
}
