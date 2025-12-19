/**
 * Whiteboard Objects & Layers Module
 * Handles object listing, layer management, and object selection from UI
 */

/**
 * Populate layer dropdown with available layers
 */
function populateLayers() {
  const layerSelect = document.getElementById("layer-select");
  const objects = window.objects || [];
  
  const layers = new Set();
  objects.forEach(obj => layers.add(obj.layer));
  
  // Clear existing options except "All Layers"
  while (layerSelect.options.length > 1) {
    layerSelect.remove(1);
  }
  
  // Add layer options
  Array.from(layers).sort((a, b) => a - b).forEach(layer => {
    const option = document.createElement("option");
    option.value = layer;
    option.textContent = `Layer ${layer}`;
    layerSelect.appendChild(option);
  });
}

/**
 * Get icon and label for object type
 * @param {Object} obj - Whiteboard object
 * @returns {Object} - {icon: string, typeLabel: string}
 */
function getObjectIconAndLabel(obj) {
  let icon = "";
  let typeLabel = "";
  const strokeType = obj.props?.strokeType || obj.strokeType;
  
  switch (obj.type) {
    case "stroke":
      // Show specific stroke type instead of generic "Stroke"
      switch (strokeType) {
        case "pen":
          icon = "fas fa-pen";
          typeLabel = "Pen";
          break;
        case "highlighter":
          icon = "fas fa-highlighter";
          typeLabel = "Highlighter";
          break;
        case "marker":
          icon = "fas fa-marker";
          typeLabel = "Marker";
          break;
        case "line":
          icon = "fas fa-minus";
          typeLabel = "Line";
          break;
        case "rectangle":
          icon = "fas fa-square";
          typeLabel = "Rectangle";
          break;
        case "arrow":
          icon = "fas fa-arrow-right";
          typeLabel = "Arrow";
          break;
        case "roundedRectangle":
          icon = "fas fa-square";
          typeLabel = "Rounded Rectangle";
          break;
        case "decision":
          icon = "fas fa-diamond";
          typeLabel = "Decision";
          break;
        case "inputOutput":
          icon = "fas fa-exchange-alt";
          typeLabel = "Input/Output";
          break;
        case "connector":
          icon = "fas fa-link";
          typeLabel = "Connector";
          break;
        default:
          icon = "fas fa-pen";
          typeLabel = "Stroke";
      }
      break;
    case "text":
      icon = "fas fa-font";
      typeLabel = "Text";
      break;
    case "image":
      icon = "fas fa-image";
      typeLabel = "Image";
      break;
    default:
      icon = "fas fa-square";
      typeLabel = obj.type;
  }
  
  return { icon, typeLabel };
}

/**
 * Get object properties summary
 * @param {Object} obj - Whiteboard object
 * @returns {Array} - Array of property strings
 */
function getObjectProperties(obj) {
  const properties = [];
  
  if (obj.type === "text") {
    const text = obj.props?.text || obj.text || "";
    properties.push(`"${text.substring(0, 30)}${text.length > 30 ? '...' : ''}"`);
    properties.push(`Size: ${obj.props?.fontSize || obj.fontSize || 24}px`);
  } else if (obj.type === "stroke") {
    const color = obj.props?.color || obj.color || "#000000";
    const size = obj.props?.size || obj.size || 2;
    properties.push(`Color: ${color}`);
    properties.push(`Size: ${size}px`);
  } else if (obj.type === "image") {
    const w = obj.props?.w || obj.w || 0;
    const h = obj.props?.h || obj.h || 0;
    properties.push(`${Math.round(w)} × ${Math.round(h)}px`);
  }
  
  return properties;
}

/**
 * Populate objects list based on selected layer
 */
function populateObjects() {
  const layerSelect = document.getElementById("layer-select");
  const objectsList = document.getElementById("objects-list");
  const objects = window.objects || [];
  
  const selectedLayer = layerSelect.value;
  const filteredObjects = selectedLayer === "all" 
    ? objects 
    : objects.filter(obj => obj.layer == selectedLayer);
  
  objectsList.innerHTML = "";
  
  if (filteredObjects.length === 0) {
    objectsList.innerHTML = '<div style="padding: 20px; text-align: center; color: #666;">No objects found in this layer</div>';
    return;
  }
  
  filteredObjects.forEach(obj => {
    const objDiv = document.createElement("div");
    objDiv.style.cssText = `
      padding: 10px;
      border-bottom: 1px solid #e5e7eb;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 10px;
    `;
    
    objDiv.addEventListener("click", () => {
      if (window.selectObject) {
        window.selectObject(obj.id);
      }
      document.getElementById("objects-overlay").style.display = "none";
    });
    
    objDiv.addEventListener("mouseenter", () => {
      objDiv.style.backgroundColor = "#f3f4f6";
    });
    
    objDiv.addEventListener("mouseleave", () => {
      objDiv.style.backgroundColor = "";
    });
    
    // Get object icon and type label
    const { icon, typeLabel } = getObjectIconAndLabel(obj);
    
    // Get object properties
    const properties = getObjectProperties(obj);
    
    // Build object HTML
    objDiv.innerHTML = `
      <i class="${icon}" style="color: #6b7280; width: 20px; text-align: center;"></i>
      <div style="flex: 1;">
        <div style="font-weight: 600; font-size: 14px; color: #111827;">
          ${typeLabel} #${obj.id}
        </div>
        <div style="font-size: 12px; color: #6b7280; margin-top: 2px;">
          ${properties.join(' • ')}
        </div>
      </div>
      <div style="font-size: 11px; color: #9ca3af; background: #f3f4f6; padding: 2px 6px; border-radius: 4px;">
        Layer ${obj.layer}
      </div>
    `;
    
    objectsList.appendChild(objDiv);
  });
}

/**
 * Initialize objects and layers modal
 */
function initializeObjectsModal() {
  const objectsBtn = document.getElementById("objects-btn");
  const objectsOverlay = document.getElementById("objects-overlay");
  const objectsClose = document.getElementById("objects-close");
  const layerSelect = document.getElementById("layer-select");

  objectsBtn.addEventListener("click", () => {
    populateLayers();
    populateObjects();
    objectsOverlay.style.display = "flex";
  });

  objectsClose.addEventListener("click", () => {
    objectsOverlay.style.display = "none";
  });

  // Close objects overlay when clicking outside
  objectsOverlay.addEventListener("click", (e) => {
    if (e.target === objectsOverlay) {
      objectsOverlay.style.display = "none";
    }
  });

  layerSelect.addEventListener("change", () => {
    populateObjects();
  });
}

/**
 * Move object to different layer
 * @param {number} objectId - Object ID
 * @param {number} newLayer - New layer number
 */
function moveObjectToLayer(objectId, newLayer) {
  if (window.executeCommand && window.findById) {
    const obj = window.findById(objectId);
    if (obj) {
      const prev = { layer: obj.layer };
      const next = { layer: newLayer };
      window.executeCommand({ type: "updateRoot", id: objectId, prev, next });
    }
  }
}

/**
 * Perform layer operations on object(s)
 * @param {number|Array} objectIds - Single object ID or array of IDs
 * @param {string} operation - 'up', 'down', 'front', 'back'
 */
function performLayerOperation(objectIds, operation) {
  const ids = Array.isArray(objectIds) ? objectIds : [objectIds];
  const objects = window.objects || [];
  
  if (!window.executeCommand || !window.findById) {
    console.error('Command system not available');
    return;
  }
  
  const layerCmds = ids.map(id => {
    const obj = window.findById(id);
    if (!obj) return null;
    
    const prev = { layer: obj.layer };
    let newLayer = obj.layer;
    
    if (operation === 'up') newLayer = obj.layer + 1;
    else if (operation === 'down') newLayer = obj.layer - 1;
    else if (operation === 'front') newLayer = (objects.length ? Math.max(...objects.map(x => x.layer)) : 0) + 1;
    else if (operation === 'back') newLayer = (objects.length ? Math.min(...objects.map(x => x.layer)) : 0) - 1;
    
    return { type: "updateRoot", id: obj.id, prev, next: { layer: newLayer } };
  }).filter(Boolean);
  
  if (layerCmds.length > 0) {
    window.executeCommand({ type: "batch", commands: layerCmds });
  }
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeObjectsModal);
} else {
  initializeObjectsModal();
}

// Export for use in main whiteboard
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    populateLayers,
    populateObjects,
    getObjectIconAndLabel,
    getObjectProperties,
    initializeObjectsModal,
    moveObjectToLayer,
    performLayerOperation
  };
}
