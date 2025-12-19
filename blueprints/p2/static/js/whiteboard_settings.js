/**
 * Whiteboard Settings & Preferences Module
 * Handles user preferences, color palettes, and settings persistence
 */

// User preferences with defaults
let userPrefs = {
  maxLinesPerPage: 25,
  maxWordsPerLine: 10,
  activePalette: 'pastel'
};

// Color Palette Definitions
const colorPalettes = {
  pastel: {
    name: 'Pastel Colors',
    colors: ['#FFB3BA', '#FFDFBA', '#FFFFBA', '#BAFFC9', '#BAE1FF', '#D4BAFF', '#FFBAE8', '#F0F0F0']
  },
  primary: {
    name: 'Primary Colors',
    colors: ['#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', '#00FFFF', '#000000', '#FFFFFF']
  },
  secondary: {
    name: 'Secondary Colors',
    colors: ['#FF8000', '#8000FF', '#0080FF', '#80FF00', '#FF0080', '#00FF80', '#808080', '#400040']
  },
  warm: {
    name: 'Warm Colors',
    colors: ['#FF6B35', '#F7931E', '#FFD23F', '#EE4B2B', '#DC143C', '#B22222', '#A0522D', '#CD853F']
  },
  cool: {
    name: 'Cool Colors',
    colors: ['#00CED1', '#20B2AA', '#008B8B', '#4682B4', '#6495ED', '#7B68EE', '#9370DB', '#8A2BE2']
  }
};

// Current active palette
let activePalette = 'pastel';
let selectedPaletteColor = null;

/**
 * Load user preferences from localStorage
 */
function loadPrefs() {
  try {
    const stored = JSON.parse(localStorage.getItem("whiteboard-prefs"));
    if (stored) {
      userPrefs = { ...userPrefs, ...stored };
      activePalette = userPrefs.activePalette || 'pastel';
    }
  } catch(e) { 
    console.warn("Prefs load failed", e); 
  }
}

/**
 * Save user preferences to localStorage
 */
function savePrefs() {
  userPrefs.activePalette = activePalette;
  localStorage.setItem("whiteboard-prefs", JSON.stringify(userPrefs));
}

/**
 * Update palette preview in settings modal
 */
function updatePalettePreview() {
  const selectedPalette = document.getElementById("color-palette-select").value;
  const previewContainer = document.getElementById("palette-preview");
  const previewColors = document.getElementById("palette-preview-colors");
  
  if (selectedPalette === 'none') {
    previewContainer.style.display = 'none';
  } else {
    previewContainer.style.display = 'block';
    previewColors.innerHTML = '';
    
    const palette = colorPalettes[selectedPalette];
    if (palette) {
      palette.colors.forEach(color => {
        const colorDiv = document.createElement('div');
        colorDiv.className = 'palette-preview-color';
        colorDiv.style.backgroundColor = color;
        colorDiv.title = color;
        previewColors.appendChild(colorDiv);
      });
    }
  }
}

/**
 * Update toolbar color palette display
 */
function updateToolbarPalette() {
  const paletteContainer = document.getElementById("color-palette");
  const paletteColors = document.getElementById("palette-colors");
  
  if (activePalette === 'none' || !colorPalettes[activePalette]) {
    paletteContainer.classList.add('hidden');
    selectedPaletteColor = null;
  } else {
    paletteContainer.classList.remove('hidden');
    paletteColors.innerHTML = '';
    
    const palette = colorPalettes[activePalette];
    palette.colors.forEach((color, index) => {
      const colorDiv = document.createElement('div');
      colorDiv.className = 'palette-color';
      colorDiv.style.backgroundColor = color;
      colorDiv.title = color;
      colorDiv.dataset.color = color;
      
      colorDiv.addEventListener('click', () => {
        selectPaletteColor(color, colorDiv);
      });
      
      paletteColors.appendChild(colorDiv);
    });
  }
}

/**
 * Select a color from the palette
 * @param {string} colorValue - Hex color value
 * @param {HTMLElement} colorElement - The palette color element clicked
 */
function selectPaletteColor(colorValue, colorElement) {
  // Remove active class from all palette colors
  document.querySelectorAll('.palette-color').forEach(el => {
    el.classList.remove('active');
  });
  
  // Add active class to selected color
  colorElement.classList.add('active');
  selectedPaletteColor = colorValue;
  
  // Update the main color picker and current color
  if (window.updateColorFromPalette) {
    window.updateColorFromPalette(colorValue);
  } else {
    // Fallback for standalone usage
    document.getElementById('color-picker').value = colorValue;
    document.getElementById('current-tool-color').style.backgroundColor = colorValue;
  }
}

/**
 * Initialize settings modal event listeners
 */
function initializeSettingsModal() {
  const settingsBtn = document.getElementById("settings-btn");
  const settingsOverlay = document.getElementById("settings-overlay");
  const settingsSave = document.getElementById("settings-save");
  const settingsCancel = document.getElementById("settings-cancel");

  settingsBtn.addEventListener("click", () => {
    document.getElementById("max-lines-per-page").value = userPrefs.maxLinesPerPage;
    document.getElementById("max-words-per-line").value = userPrefs.maxWordsPerLine;
    document.getElementById("color-palette-select").value = activePalette;
    updatePalettePreview();
    settingsOverlay.style.display = "flex";
  });

  settingsCancel.addEventListener("click", () => {
    settingsOverlay.style.display = "none";
  });

  settingsSave.addEventListener("click", () => {
    userPrefs.maxLinesPerPage = parseInt(document.getElementById("max-lines-per-page").value, 10) || 25;
    userPrefs.maxWordsPerLine = parseInt(document.getElementById("max-words-per-line").value, 10) || 10;
    activePalette = document.getElementById("color-palette-select").value;
    
    savePrefs();
    updateToolbarPalette();
    settingsOverlay.style.display = "none";
  });

  // Close modal when clicking outside
  settingsOverlay.addEventListener("click", (e) => {
    if (e.target === settingsOverlay) {
      settingsOverlay.style.display = "none";
    }
  });

  // Add event listener for palette selection preview
  document.getElementById("color-palette-select").addEventListener("change", updatePalettePreview);
}

/**
 * Initialize keyboard shortcuts modal
 */
function initializeShortcutsModal() {
  const infoBtn = document.getElementById("info-btn");
  const shortcutsOverlay = document.getElementById("shortcuts-overlay");
  const shortcutsClose = document.getElementById("shortcuts-close");

  infoBtn.addEventListener("click", () => {
    shortcutsOverlay.style.display = "flex";
  });

  shortcutsClose.addEventListener("click", () => {
    shortcutsOverlay.style.display = "none";
  });

  // Close shortcuts modal when clicking outside
  shortcutsOverlay.addEventListener("click", (e) => {
    if (e.target === shortcutsOverlay) {
      shortcutsOverlay.style.display = "none";
    }
  });
}

/**
 * Initialize all settings and preferences
 */
function initializeSettings() {
  loadPrefs();
  initializeSettingsModal();
  initializeShortcutsModal();
  updateToolbarPalette();
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeSettings);
} else {
  initializeSettings();
}

// Export for use in main whiteboard
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    userPrefs,
    colorPalettes,
    activePalette,
    selectedPaletteColor,
    loadPrefs,
    savePrefs,
    updatePalettePreview,
    updateToolbarPalette,
    selectPaletteColor,
    initializeSettings
  };
}
