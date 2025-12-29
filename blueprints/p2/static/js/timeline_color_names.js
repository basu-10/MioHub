/**
 * Timeline Color Names Module
 * Maps hex color codes to human-readable names for timeline event cards
 */

const TimelineColorNames = {
  // Row 1: Vibrant colors
  '#14b8a6': 'Teal',
  '#3b82f6': 'Blue',
  '#8b5cf6': 'Purple',
  '#ec4899': 'Pink',
  '#ef4444': 'Red',
  '#f97316': 'Orange',
  '#f59e0b': 'Amber',
  '#84cc16': 'Lime',
  
  // Row 2: Rich colors
  '#10b981': 'Emerald',
  '#06b6d4': 'Cyan',
  '#6366f1': 'Indigo',
  '#a855f7': 'Violet',
  '#e11d48': 'Rose',
  '#dc2626': 'Crimson',
  '#ea580c': 'Burnt Orange',
  '#d97706': 'Dark Amber',
  
  // Row 3: Dark pastel colors
  '#0891b2': 'Dark Cyan',
  '#0e7490': 'Ocean Blue',
  '#334155': 'Slate Gray',
  '#475569': 'Steel Blue',
  '#78716c': 'Stone Gray',
  '#57534e': 'Charcoal',
  '#a16207': 'Bronze',
  
  /**
   * Get the name of a color by its hex code
   * @param {string} hexColor - The hex color code (e.g., '#14b8a6')
   * @returns {string} The color name or 'Custom Color' if not found
   */
  getName: function(hexColor) {
    return this[hexColor] || 'Custom Color';
  }
};

// Export for use in other scripts
if (typeof window !== 'undefined') {
  window.TimelineColorNames = TimelineColorNames;
}
