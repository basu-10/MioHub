/**
 * Graph Node Customization Module - Handles comprehensive node styling and appearance
 * Provides UI controls for shape, color, borders, and visual properties
 */

window.GraphNodeCustomization = (function() {
  let selectedNode = null;
  let graphId = null;
  let pendingSave = null; // Timer for debounced saves
  const SAVE_DEBOUNCE_MS = 800; // Wait 800ms after last change before saving

  // Dark theme color palette - muted, professional tones without flashy/glassy effects
  const DARK_THEME_COLORS = [
    { name: 'Graphite', value: '#121516', category: 'neutral' },
    { name: 'Charcoal', value: '#1e2326', category: 'neutral' },
    { name: 'Slate', value: '#2a3439', category: 'neutral' },
    { name: 'Steel', value: '#3a4449', category: 'neutral' },
    
    { name: 'Deep Teal', value: '#0d4d4a', category: 'accent' },
    { name: 'Muted Teal', value: '#14625e', category: 'accent' },
    { name: 'Carbon Teal', value: '#14b8a6', category: 'accent' },
    
    { name: 'Deep Blue', value: '#1e3a5f', category: 'cool' },
    { name: 'Navy', value: '#2c4f7c', category: 'cool' },
    { name: 'Muted Indigo', value: '#3f4f7c', category: 'cool' },
    
    { name: 'Deep Purple', value: '#3d2f5f', category: 'cool' },
    { name: 'Plum', value: '#4a3f5f', category: 'cool' },
    
    { name: 'Deep Green', value: '#2d4a3e', category: 'natural' },
    { name: 'Forest', value: '#3d5a4e', category: 'natural' },
    { name: 'Sage', value: '#4a6858', category: 'natural' },
    
    { name: 'Burnt Sienna', value: '#5a3d2f', category: 'warm' },
    { name: 'Rust', value: '#6b4423', category: 'warm' },
    { name: 'Amber', value: '#7d5a3d', category: 'warm' },
    
    { name: 'Deep Red', value: '#5a2d2f', category: 'warm' },
    { name: 'Burgundy', value: '#6b3d3f', category: 'warm' },
    { name: 'Brick', value: '#7d4d4f', category: 'warm' }
  ];

  // Border color palette (slightly lighter for contrast)
  const BORDER_COLORS = [
    { name: 'Subtle Gray', value: '#646464' },
    { name: 'Medium Gray', value: '#808080' },
    { name: 'Light Gray', value: '#9a9a9a' },
    { name: 'Teal', value: '#14b8a6' },
    { name: 'Blue', value: '#3b82f6' },
    { name: 'Purple', value: '#8b5cf6' },
    { name: 'Green', value: '#10b981' },
    { name: 'Amber', value: '#f59e0b' },
    { name: 'Red', value: '#ef4444' }
  ];

  // Node shape options
  const NODE_SHAPES = [
    { name: 'Rectangle', value: 'rectangle', icon: 'crop_square' },
    { name: 'Rounded', value: 'rounded', icon: 'rounded_corner' },
    { name: 'Circle', value: 'circle', icon: 'circle' },
    { name: 'Ellipse', value: 'ellipse', icon: 'panorama_fish_eye' }
  ];

  // Border style options
  const BORDER_STYLES = [
    { name: 'Solid', value: 'solid', dashPattern: [] },
    { name: 'Dashed', value: 'dashed', dashPattern: [10, 5] },
    { name: 'Dotted', value: 'dotted', dashPattern: [2, 3] },
    { name: 'None', value: 'none', dashPattern: [] }
  ];

  // Border width options
  const BORDER_WIDTHS = [
    { name: 'Thin', value: 1 },
    { name: 'Medium', value: 2 },
    { name: 'Thick', value: 3 },
    { name: 'Bold', value: 4 }
  ];

  function init(fileId) {
    graphId = fileId;
    setupEventListeners();
  }

  function setupEventListeners() {
    // Background color swatches
    document.querySelectorAll('.node-bg-color-swatch').forEach(swatch => {
      swatch.addEventListener('click', (e) => {
        const color = e.currentTarget.dataset.color;
        applyNodeStyleImmediate({ backgroundColor: color });
        updateActiveState('.node-bg-color-swatch', e.currentTarget);
      });
    });

    // Border color swatches
    document.querySelectorAll('.node-border-color-swatch').forEach(swatch => {
      swatch.addEventListener('click', (e) => {
        const color = e.currentTarget.dataset.color;
        applyNodeStyleImmediate({ borderColor: color });
        updateActiveState('.node-border-color-swatch', e.currentTarget);
      });
    });

    // Shape buttons
    document.querySelectorAll('.node-shape-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const shape = e.currentTarget.dataset.shape;
        applyNodeStyleImmediate({ shape: shape });
        updateActiveState('.node-shape-btn', e.currentTarget);
      });
    });

    // Border style buttons
    document.querySelectorAll('.node-border-style-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const style = e.currentTarget.dataset.borderStyle;
        const dashPattern = JSON.parse(e.currentTarget.dataset.dashPattern || '[]');
        applyNodeStyleImmediate({ 
          borderStyle: style,
          borderDashPattern: dashPattern
        });
        updateActiveState('.node-border-style-btn', e.currentTarget);
      });
    });

    // Border width buttons
    document.querySelectorAll('.node-border-width-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const width = parseInt(e.currentTarget.dataset.width);
        applyNodeStyleImmediate({ borderWidth: width });
        updateActiveState('.node-border-width-btn', e.currentTarget);
      });
    });

    // Opacity slider - live preview with debounced save
    const opacitySlider = document.getElementById('node-opacity-slider');
    if (opacitySlider) {
      opacitySlider.addEventListener('input', (e) => {
        const opacity = parseFloat(e.target.value);
        document.getElementById('node-opacity-value').textContent = Math.round(opacity * 100) + '%';
        applyNodeStyleImmediate({ opacity: opacity });
      });
    }

    // Corner radius slider - live preview with debounced save
    const cornerRadiusSlider = document.getElementById('node-corner-radius-slider');
    if (cornerRadiusSlider) {
      cornerRadiusSlider.addEventListener('input', (e) => {
        const radius = parseInt(e.target.value);
        document.getElementById('node-corner-radius-value').textContent = radius + 'px';
        applyNodeStyleImmediate({ cornerRadius: radius });
      });
    }

    // Reset button
    const resetBtn = document.getElementById('btn-reset-node-style');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => resetNodeStyle());
    }
  }

  function updateActiveState(selector, activeElement) {
    document.querySelectorAll(selector).forEach(el => {
      el.classList.remove('active');
    });
    if (activeElement) {
      activeElement.classList.add('active');
    }
  }

  function applyNodeStyleImmediate(styleUpdates) {
    if (!selectedNode) return;

    // Get the actual node from the nodes array (not our local reference)
    const nodes = window.GraphNodes?.getNodes?.() || [];
    const actualNode = nodes.find(n => n.id === selectedNode.id);
    
    if (!actualNode) return;

    // Merge with existing style
    const currentStyle = actualNode.style || {};
    const newStyle = { ...currentStyle, ...styleUpdates };
    actualNode.style = newStyle;
    
    // Update our local reference too
    selectedNode.style = newStyle;

    // Immediate visual update (no lag!)
    window.GraphCanvas.render();

    // Debounce the database save (wait for user to finish tweaking)
    if (pendingSave) {
      clearTimeout(pendingSave);
    }
    
    pendingSave = setTimeout(() => {
      saveNodeStyleToServer(actualNode.id, newStyle);
      pendingSave = null;
    }, SAVE_DEBOUNCE_MS);
  }

  async function saveNodeStyleToServer(nodeId, style) {
    try {
      const response = await fetch(`/graph/${graphId}/nodes/${nodeId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ style: style })
      });

      if (!response.ok) {
        throw new Error('Failed to update node style');
      }
      
      // Optional: Show subtle success indicator
      console.log('Node style saved successfully');
    } catch (error) {
      console.error('Error updating node style:', error);
      alert('Failed to save node customization. Your changes are visible but may not persist.');
    }
  }

  async function resetNodeStyle() {
    if (!selectedNode) return;

    if (!confirm('Reset this node to default styling?')) return;

    const defaultStyle = {
      backgroundColor: '#121516',
      borderColor: '#646464',
      borderWidth: 1,
      borderStyle: 'solid',
      borderDashPattern: [],
      shape: 'rounded',
      opacity: 0.95,
      cornerRadius: 8
    };

    // Get the actual node from the nodes array
    const nodes = window.GraphNodes?.getNodes?.() || [];
    const actualNode = nodes.find(n => n.id === selectedNode.id);
    
    if (actualNode) {
      actualNode.style = defaultStyle;
    }
    selectedNode.style = defaultStyle;
    
    window.GraphCanvas.render();

    // Update UI controls to reflect defaults
    updateCustomizationPanel(selectedNode);

    // Save immediately (user explicitly clicked reset)
    await saveNodeStyleToServer(selectedNode.id, defaultStyle);
  }

  function updateCustomizationPanel(node) {
    selectedNode = node;

    if (!node) {
      document.getElementById('node-customization-section')?.classList.add('d-none');
      return;
    }

    // Show customization section
    document.getElementById('node-customization-section')?.classList.remove('d-none');

    const style = node.style || {};

    // Update background color active state
    const bgColor = style.backgroundColor || '#121516';
    document.querySelectorAll('.node-bg-color-swatch').forEach(swatch => {
      if (swatch.dataset.color === bgColor) {
        swatch.classList.add('active');
      } else {
        swatch.classList.remove('active');
      }
    });

    // Update border color active state
    const borderColor = style.borderColor || '#646464';
    document.querySelectorAll('.node-border-color-swatch').forEach(swatch => {
      if (swatch.dataset.color === borderColor) {
        swatch.classList.add('active');
      } else {
        swatch.classList.remove('active');
      }
    });

    // Update shape active state
    const shape = style.shape || 'rounded';
    document.querySelectorAll('.node-shape-btn').forEach(btn => {
      if (btn.dataset.shape === shape) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    // Update border style active state
    const borderStyle = style.borderStyle || 'solid';
    document.querySelectorAll('.node-border-style-btn').forEach(btn => {
      if (btn.dataset.borderStyle === borderStyle) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    // Update border width active state
    const borderWidth = style.borderWidth || 1;
    document.querySelectorAll('.node-border-width-btn').forEach(btn => {
      if (parseInt(btn.dataset.width) === borderWidth) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    // Update opacity slider
    const opacity = style.opacity !== undefined ? style.opacity : 0.95;
    const opacitySlider = document.getElementById('node-opacity-slider');
    if (opacitySlider) {
      opacitySlider.value = opacity;
      document.getElementById('node-opacity-value').textContent = Math.round(opacity * 100) + '%';
    }

    // Update corner radius slider
    const cornerRadius = style.cornerRadius !== undefined ? style.cornerRadius : 8;
    const cornerRadiusSlider = document.getElementById('node-corner-radius-slider');
    if (cornerRadiusSlider) {
      cornerRadiusSlider.value = cornerRadius;
      document.getElementById('node-corner-radius-value').textContent = cornerRadius + 'px';
    }
  }

  function getColors() {
    return DARK_THEME_COLORS;
  }

  function getBorderColors() {
    return BORDER_COLORS;
  }

  function getShapes() {
    return NODE_SHAPES;
  }

  function getBorderStyles() {
    return BORDER_STYLES;
  }

  function getBorderWidths() {
    return BORDER_WIDTHS;
  }

  function toggleCustomization() {
    const content = document.getElementById('node-customization-content');
    const icon = document.getElementById('customization-toggle-icon');
    
    if (!content || !icon) return;
    
    const isHidden = content.style.display === 'none';
    
    if (isHidden) {
      // Show content
      content.style.display = 'block';
      icon.textContent = 'expand_less';
    } else {
      // Hide content
      content.style.display = 'none';
      icon.textContent = 'expand_more';
    }
  }

  // Public API
  return {
    init,
    updateCustomizationPanel,
    applyNodeStyleImmediate,
    resetNodeStyle,
    toggleCustomization,
    getColors,
    getBorderColors,
    getShapes,
    getBorderStyles,
    getBorderWidths
  };
})();
