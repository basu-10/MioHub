# MioDraw Toolbar Architecture

## Overview
The MioDraw toolbar has been extracted into a separate partial template for better maintainability and reusability.

## File Structure

### Main Template
- **File**: `mioboard_v4.html`
- **Purpose**: Main MioDraw application template
- **Toolbar Integration**: Uses Jinja2 `{% include %}` to load the toolbar partial

### Toolbar Partial
- **File**: `board_toolbar_partial.html`
- **Purpose**: Contains the compact single-row toolbar with all controls
- **Sections**:
  - **Left**: Document info (title & description), tool selection (select, pen, marker, highlighter, shapes, text, image)
  - **Center**: Tool properties (font size, color picker, brush size, transparency)
  - **Right**: Actions (undo/redo, paste, clear), utilities (shortcuts, settings, layers), file menu

## Usage

### Including the Toolbar
```jinja2
{% include 'p2/board_toolbar_partial.html' %}
```

### Toolbar Height
The toolbar is approximately **60px tall** (single row design). Adjust the main content area's `margin-top` accordingly:

```html
<div class="board" style="margin-top: 60px; height: calc(100vh - 60px - 40px);">
```

## Design Features

### Compact Layout
- **Single-row design** saves ~100px vertical space compared to previous 3-row layout
- **Reduced padding**: `py-2`, `px-3`, button padding `px-2 py-1.5`
- **Tight gaps**: `gap-1.5` and `gap-2` between elements
- **Stacked title/description** in single compact box

### Visual Organization
- **Vertical dividers** (`w-px h-8 bg-gray-300`) separate major sections
- **Grouped tools** with clear visual boundaries
- **Icon-only buttons** with tooltips to save space
- **Dropdown menus** for shapes and file operations

### Categorization
1. **Document Info** - Title and description inputs
2. **Selection & Drawing Tools** - Primary tool buttons
3. **Tool Properties** - Dynamic controls for active tool
4. **Actions** - Undo/redo, clipboard operations
5. **Utilities** - Settings, shortcuts, layers panel
6. **File Menu** - Save, export, print options

## Customization

### Modifying the Toolbar
Edit `board_toolbar_partial.html` to:
- Add/remove tool buttons
- Adjust spacing and padding
- Change color schemes
- Modify dropdown menus

### Styling
The toolbar uses:
- **Tailwind CSS** for utility classes
- **Font Awesome** for icons
- **Custom transitions** for smooth interactions
- **Responsive design** with `hidden sm:inline` for mobile

## Dependencies
- Tailwind CSS (via CDN)
- Font Awesome 6.0.0 (via CDN)
- JavaScript functions: `s()` (tool selection), `exportJSON()`, `importJSON()`

## Element IDs Reference

### Critical IDs (referenced by JavaScript)
- `#board-title` - Whiteboard title input
- `#board-description` - Whiteboard description input
- `#shapes-btn` - Shapes dropdown trigger
- `#shapes-dropdown` - Shapes dropdown menu
- `#text-size` - Font size input
- `#color-picker` - Color picker input
- `#current-tool-color` - Color indicator span
- `#size-range` - Brush size slider
- `#transparency-control` - Transparency controls container
- `#transparency-range` - Transparency slider
- `#transparency-value` - Transparency percentage display
- `#color-palette` - Quick color palette container
- `#palette-colors` - Color palette buttons container
- `#undo-btn` - Undo button
- `#redo-btn` - Redo button
- `#paste-btn` - Paste button
- `#clear-btn` - Clear page button
- `#info-btn` - Keyboard shortcuts button
- `#settings-btn` - Settings button
- `#objects-btn` - Layers/objects panel button
- `#file-menu-btn` - File menu trigger
- `#file-menu` - File menu dropdown
- `#save-btn` - Save button
- `#export-png` - Export PNG button
- `#print-pdf` - Print PDF button
- `#image-upload` - Hidden file input for images
- `#tool-select` - Hidden input for current tool
- `#tool-buttons` - Hidden toolbar container

## Maintenance Notes
- Keep element IDs consistent with JavaScript event handlers
- Preserve the include statement in main template
- Test responsiveness on different screen sizes
- Ensure dropdown z-index (`z-[9999]`) prevents overlap issues
