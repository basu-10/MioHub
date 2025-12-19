/**
 * Infinite Whiteboard Layers Module
 * Handles z-order management, bring to front, send to back, layer visualization
 */

(function(window) {
    'use strict';

    window.InfiniteWhiteboard = window.InfiniteWhiteboard || {};
    const IWB = window.InfiniteWhiteboard;

    const getLayerValue = (obj) => Number.isFinite(obj?.layer) ? obj.layer : 0;

    const layerSort = (a, b) => {
        const layerDiff = getLayerValue(a) - getLayerValue(b);
        if (layerDiff !== 0) return layerDiff;
        // If same layer, sort by ID (creation order)
        return (a.id || 0) - (b.id || 0);
    };

    IWB.initializeLayerMetadata = function(objects) {
        if (!objects || objects.length === 0) {
            return;
        }

        objects.forEach((obj) => {
            if (!Number.isFinite(obj.layer)) {
                obj.layer = 0;
            }
        });
    };

    IWB.assignLayerMetadata = function(obj, layerValue = 0) {
        if (!obj) return;
        obj.layer = Number.isFinite(layerValue) ? layerValue : 0;
    };

    IWB.captureLayerSnapshot = function(obj) {
        if (!obj) return { layer: 0 };
        return {
            layer: getLayerValue(obj)
        };
    };

    IWB.sortObjectsByLayerInPlace = function(objects) {
        if (!Array.isArray(objects)) return objects;
        objects.sort(layerSort);
        return objects;
    };

    IWB.getObjectsInLayerOrder = function(objects) {
        if (!Array.isArray(objects)) return [];
        return [...objects].sort(layerSort);
    };

    /**
     * Bring selected object to front (highest z-index)
     * @param {Object} selectedObject - The currently selected object
     * @param {Array} objects - Array of all canvas objects
     * @returns {boolean} - True if operation was performed
     */
    IWB.bringToFront = function(selectedObject, objects) {
        if (!selectedObject) return false;
        
        const maxLayer = Math.max(...objects.map(getLayerValue), getLayerValue(selectedObject));
        selectedObject.layer = maxLayer + 1;
        IWB.sortObjectsByLayerInPlace(objects);
        console.log(`[LAYERS] Brought object ${selectedObject.id} to front (layer ${selectedObject.layer})`);
        return true;
    };

    /**
     * Send selected object to back (lowest z-index)
     * @param {Object} selectedObject - The currently selected object
     * @param {Array} objects - Array of all canvas objects
     * @returns {boolean} - True if operation was performed
     */
    IWB.sendToBack = function(selectedObject, objects) {
        if (!selectedObject) return false;
        
        const minLayer = Math.min(...objects.map(getLayerValue), getLayerValue(selectedObject));
        selectedObject.layer = minLayer - 1;
        IWB.sortObjectsByLayerInPlace(objects);
        console.log(`[LAYERS] Sent object ${selectedObject.id} to back (layer ${selectedObject.layer})`);
        return true;
    };

    /**
     * Move selected object one layer up (toward front)
     * @param {Object} selectedObject - The currently selected object
     * @param {Array} objects - Array of all canvas objects
     * @returns {boolean} - True if operation was performed
     */
    IWB.moveUp = function(selectedObject, objects) {
        if (!selectedObject) return false;
        
        selectedObject.layer += 1;
        IWB.sortObjectsByLayerInPlace(objects);
        console.log(`[LAYERS] Moved object ${selectedObject.id} up to layer ${selectedObject.layer}`);
        return true;
    };

    /**
     * Move selected object one layer down (toward back)
     * @param {Object} selectedObject - The currently selected object
     * @param {Array} objects - Array of all canvas objects
     * @returns {boolean} - True if operation was performed
     */
    IWB.moveDown = function(selectedObject, objects) {
        if (!selectedObject) return false;
        
        selectedObject.layer -= 1;
        IWB.sortObjectsByLayerInPlace(objects);
        console.log(`[LAYERS] Moved object ${selectedObject.id} down to layer ${selectedObject.layer}`);
        return true;
    };

    /**
     * Get the layer position of an object (0 = back, highest = front)
     * @param {Object} obj - The object to check
     * @param {Array} objects - Array of all canvas objects
     * @returns {number} - Layer index (-1 if not found)
     */
    IWB.getLayerPosition = function(obj, objects) {
        if (!obj) return -1;
        const ordered = IWB.getObjectsInLayerOrder(objects);
        return ordered.findIndex(o => o.id === obj.id);
    };

    /**
     * Get total number of layers
     * @param {Array} objects - Array of all canvas objects
     * @returns {number} - Total layer count
     */
    IWB.getTotalLayers = function(objects) {
        return objects.length;
    };

    /**
     * Draw layer indicator on canvas (shows position in z-order)
     * @param {Object} ctx - Canvas context
     * @param {Object} selectedObject - Currently selected object
     * @param {Array} objects - Array of all canvas objects
     * NOTE: This function expects to be called in screen space (after resetTransform)
     */
    IWB.drawLayerIndicator = function(ctx, selectedObject, objects) {
        if (!selectedObject) return;

        const layerLabel = getLayerValue(selectedObject);
        const layerText = `Layer ${layerLabel}`;
        
        // Draw indicator in top-right corner (already in screen space)
        ctx.save();
        ctx.font = '14px -apple-system, BlinkMacSystemFont, SF Pro Display, Segoe UI, sans-serif';
        ctx.fillStyle = 'rgba(20, 184, 166, 0.9)';
        ctx.strokeStyle = 'rgba(10, 10, 11, 0.8)';
        ctx.lineWidth = 3;
        
        const metrics = ctx.measureText(layerText);
        const textWidth = metrics.width;
        const textHeight = 14;
        const padding = 8;
        const x = window.innerWidth - textWidth - padding * 2 - 10;
        const y = 10;
        
        // Background
        ctx.fillStyle = 'rgba(18, 21, 22, 0.95)';
        ctx.fillRect(x - padding, y - padding, textWidth + padding * 2, textHeight + padding * 2);
        
        // Border
        ctx.strokeStyle = 'rgba(20, 184, 166, 0.5)';
        ctx.lineWidth = 1;
        ctx.strokeRect(x - padding, y - padding, textWidth + padding * 2, textHeight + padding * 2);
        
        // Text
        ctx.fillStyle = '#14b8a6';
        ctx.fillText(layerText, x, y + textHeight - 2);
        
        ctx.restore();
    };

    /**
     * Create undo action for layer operations
     * @param {string} operation - Type of operation (bringToFront, sendToBack, moveUp, moveDown)
     * @param {Object} obj - The object that was moved
     * @param {number} oldIndex - Original index
     * @param {number} newIndex - New index
     * @returns {Object} - Undo action object
     */
    IWB.createLayerUndoAction = function(operation, obj, beforeState, afterState) {
        return {
            type: 'layer',
            operation: operation,
            objectId: obj.id,
            fromLayer: beforeState?.layer ?? getLayerValue(obj),
            toLayer: afterState?.layer ?? getLayerValue(obj)
        };
    };

    /**
     * Apply layer undo action
     * @param {Object} action - The undo action to apply
     * @param {Array} objects - Array of all canvas objects
     * @returns {boolean} - True if action was applied
     */
    IWB.applyLayerUndo = function(action, objects) {
        if (action.type !== 'layer') return false;
        
        const obj = objects.find(o => o.id === action.objectId);
        if (!obj) return false;

        obj.layer = action.fromLayer;
        IWB.sortObjectsByLayerInPlace(objects);
        console.log(`[LAYERS] Undo: Restored object ${obj.id} to layer ${obj.layer}`);
        return true;
    };

    /**
     * Apply layer redo action
     * @param {Object} action - The redo action to apply
     * @param {Array} objects - Array of all canvas objects
     * @returns {boolean} - True if action was applied
     */
    IWB.applyLayerRedo = function(action, objects) {
        if (action.type !== 'layer') return false;
        
        const obj = objects.find(o => o.id === action.objectId);
        if (!obj) return false;

        obj.layer = action.toLayer;
        IWB.sortObjectsByLayerInPlace(objects);
        console.log(`[LAYERS] Redo: Set object ${obj.id} to layer ${obj.layer}`);
        return true;
    };

    /**
     * Draw mini layer stack visualization (shows all objects and their order)
     * @param {Object} ctx - Canvas context
     * @param {Array} objects - Array of all canvas objects
     * @param {Object} selectedObject - Currently selected object
     * NOTE: This function expects to be called in screen space (after resetTransform)
     */
    IWB.drawLayerStack = function(ctx, objects, selectedObject) {
        if (objects.length === 0) return;
        
        const maxVisible = 10;
        const itemHeight = 20;
        const itemWidth = 180;
        const padding = 10;
        const startX = 10;
        const startY = window.innerHeight - 200;
        
        // Already in screen space - no transform needed
        
        ctx.save();
        
        // Background panel
        const panelHeight = Math.min(objects.length, maxVisible) * itemHeight + padding * 2;
        ctx.fillStyle = 'rgba(18, 21, 22, 0.95)';
        ctx.fillRect(startX, startY, itemWidth + padding * 2, panelHeight);
        
        // Border
        ctx.strokeStyle = 'rgba(20, 184, 166, 0.5)';
        ctx.lineWidth = 1;
        ctx.strokeRect(startX, startY, itemWidth + padding * 2, panelHeight);
        
        // Title
        ctx.font = 'bold 12px -apple-system, BlinkMacSystemFont, SF Pro Display, Segoe UI, sans-serif';
        ctx.fillStyle = '#14b8a6';
        ctx.fillText('Layers', startX + padding, startY - 5);
        
        // Draw layers (reverse order - top of list is front of canvas)
        const ordered = IWB.getObjectsInLayerOrder(objects);
        const startIndex = Math.max(0, ordered.length - maxVisible);
        ctx.font = '11px -apple-system, BlinkMacSystemFont, SF Pro Display, Segoe UI, sans-serif';
        
        for (let i = ordered.length - 1; i >= startIndex; i--) {
            const obj = ordered[i];
            const displayIndex = ordered.length - i - 1;
            const y = startY + padding + displayIndex * itemHeight;
            
            const isSelected = selectedObject && selectedObject.id === obj.id;
            
            // Highlight selected
            if (isSelected) {
                ctx.fillStyle = 'rgba(20, 184, 166, 0.2)';
                ctx.fillRect(startX + padding, y, itemWidth, itemHeight - 2);
            }
            
            // Layer icon and text
            ctx.fillStyle = isSelected ? '#14b8a6' : '#9aa8ad';
            
            const icon = obj.type === 'image' ? '🖼️' : obj.type === 'stroke' ? '✏️' : '📄';
            const label = `${icon} Layer ${getLayerValue(obj)} - ${obj.type} #${obj.id}`;
            
            ctx.fillText(label, startX + padding + 5, y + 14);
        }
        
        // Show scroll indicator if more than maxVisible
        if (ordered.length > maxVisible) {
            ctx.fillStyle = '#9aa8ad';
            ctx.font = '10px -apple-system, BlinkMacSystemFont, SF Pro Display, Segoe UI, sans-serif';
            ctx.fillText(`+${ordered.length - maxVisible} more...`, startX + padding + 5, startY + panelHeight - 5);
        }
        
        ctx.restore();
    };

    /**
     * Get display information for a shape type
     * @param {string} shapeType - The shape type identifier
     * @returns {Object} - {icon: string, name: string}
     */
    IWB.getShapeDisplayInfo = function(shapeType) {
        const shapeMap = {
            // Flowchart shapes
            'process': { icon: '▭', name: 'Process' },
            'decision': { icon: '◇', name: 'Decision' },
            'terminator': { icon: '⬭', name: 'Start/End' },
            'data': { icon: '▱', name: 'Data' },
            'document': { icon: '📄', name: 'Document' },
            'predefinedProcess': { icon: '▯', name: 'Predefined' },
            'manualInput': { icon: '⏢', name: 'Manual Input' },
            'preparation': { icon: '⬠', name: 'Preparation' },
            
            // Connectors
            'arrow': { icon: '→', name: 'Arrow' },
            'doubleArrow': { icon: '↔', name: 'Double Arrow' },
            'line': { icon: '─', name: 'Line' },
            'curvedArrow': { icon: '↝', name: 'Squiggly Arrow' },
            'elbowArrowHV': { icon: '⌐→', name: 'Elbow Arrow H→V' },
            'elbowArrowVH': { icon: '└→', name: 'Elbow Arrow V→H' },
            'dashedArrow': { icon: '⇢', name: 'Dashed Arrow' },
            'thickArrow': { icon: '⯈', name: 'Thick Arrow' },
            'circleArrow': { icon: '⊙→', name: 'Circle Arrow' },
            'diamondArrow': { icon: '◇→', name: 'Diamond Arrow' },
            'squareArrow': { icon: '□→', name: 'Square Arrow' },
            'ballHead': { icon: '○→', name: 'Ball Head' },
            'doubleBallHead': { icon: '○↔○', name: 'Double Ball' },
            
            // Industry icons
            'database': { icon: '🗄️', name: 'Database' },
            'server': { icon: '🖥️', name: 'Server' },
            'cloud': { icon: '☁️', name: 'Cloud' },
            'user': { icon: '👤', name: 'User' },
            'building': { icon: '🏢', name: 'Building' },
            'factory': { icon: '🏭', name: 'Factory' },
            'mobile': { icon: '📱', name: 'Mobile' },
            'laptop': { icon: '💻', name: 'Laptop' },
            
            // Callouts
            'thought': { icon: '💭', name: 'Thought Bubble' },
            'speech': { icon: '💬', name: 'Speech Bubble' },
            'callout': { icon: '📢', name: 'Callout' },
            'note': { icon: '📝', name: 'Sticky Note' }
        };
        
        return shapeMap[shapeType] || { icon: '⬜', name: 'Shape' };
    };

    /**
     * Update the layer panel UI with current objects
     * @param {Array} objects - Array of all canvas objects
     * @param {Object} selectedObject - Currently selected object
     * @param {Set} selectedIds - Set of selected object IDs (for multi-select)
     */
    IWB.updateLayerPanel = function(objects, selectedObject, selectedIds) {
        const panelContent = document.getElementById('layer-panel-content');
        if (!panelContent) return;
        
        if (objects.length === 0) {
            panelContent.innerHTML = '<div class="layer-panel-empty">No objects yet</div>';
            return;
        }
        
        // Save scroll positions for all layer groups before updating
        const scrollPositions = new Map();
        const layerGroups = panelContent.querySelectorAll('.layer-group-content');
        layerGroups.forEach(group => {
            const layerValue = group.getAttribute('data-layer');
            if (layerValue) {
                scrollPositions.set(layerValue, group.scrollTop);
            }
        });
        
        // Create global object numbering sorted by ID (creation order)
        const sortedByIdDesc = [...objects].sort((a, b) => (b.id || 0) - (a.id || 0));
        const objectNumberMap = new Map();
        sortedByIdDesc.forEach((obj, index) => {
            objectNumberMap.set(obj.id, sortedByIdDesc.length - index);
        });
        
        // Group objects by layer value
        const layerGroupsMap = new Map();
        objects.forEach(obj => {
            const layerValue = getLayerValue(obj);
            if (!layerGroupsMap.has(layerValue)) {
                layerGroupsMap.set(layerValue, []);
            }
            layerGroupsMap.get(layerValue).push(obj);
        });
        
        // Sort layer values descending (front to back)
        const sortedLayerValues = Array.from(layerGroupsMap.keys()).sort((a, b) => b - a);
        
        const html = [];
        
        // Build HTML for each layer group
        sortedLayerValues.forEach(layerValue => {
            const layerObjects = layerGroupsMap.get(layerValue);
            const isVisible = !window.hiddenLayers || !window.hiddenLayers.has(layerValue);
            const objectCount = layerObjects.length;
            
            // Layer group header
            html.push(`
                <div class=\"layer-group\">
                    <div class=\"layer-group-header\" onclick=\"toggleLayerGroup(${layerValue})\">
                        <span class=\"layer-group-icon\" onclick=\"event.stopPropagation(); toggleLayerVisibility(${layerValue})\" data-layer=\"${layerValue}\">
                            <i class=\"fas ${isVisible ? 'fa-eye' : 'fa-eye-slash'}\"></i>
                        </span>
                        <span class=\"layer-group-title\">Layer ${layerValue}</span>
                        <span class=\"layer-group-count\">${objectCount} object${objectCount !== 1 ? 's' : ''}</span>
                        <span class=\"layer-group-toggle\" data-layer=\"${layerValue}\">
                            <i class=\"fas fa-chevron-down\"></i>
                        </span>
                    </div>
                    <div class=\"layer-group-content\" data-layer=\"${layerValue}\">
            `);
            
            // Sort objects within layer by ID (creation order)
            const sortedObjects = [...layerObjects].sort((a, b) => (b.id || 0) - (a.id || 0));
            
            // Build HTML for each object in this layer
            sortedObjects.forEach(obj => {
                const isSelected = (selectedObject && selectedObject.id === obj.id) || 
                                   (selectedIds && selectedIds.has(Number(obj.id)));
                
                // Get global object number
                const objNumber = objectNumberMap.get(obj.id) || obj.id;
                
                // Choose icon and name based on type and shapeType
                let icon = '📄';
                let typeName = obj.type;
                let displayDetails = '';
                
                if (obj.type === 'image') {
                    icon = '🖼️';
                    typeName = 'Image';
                    // Show integer coordinates and dimensions
                    const x = Math.floor(obj.x || 0);
                    const y = Math.floor(obj.y || 0);
                    const w = Math.floor(obj.w || 0);
                    const h = Math.floor(obj.h || 0);
                    displayDetails = `(${x}, ${y}) ${w}×${h}`;
                } else if (obj.type === 'stroke') {
                    icon = '✏️';
                    typeName = 'Stroke';
                    displayDetails = `${obj.path?.length || 0} points`;
                } else if (obj.type === 'text') {
                    icon = '📝';
                    typeName = 'Text';
                    // Show first 10 characters of text
                    const textPreview = obj.text ? obj.text.substring(0, 10) : '';
                    const x = Math.floor(obj.x || 0);
                    const y = Math.floor(obj.y || 0);
                    displayDetails = `(${x}, ${y}) "${textPreview}${obj.text && obj.text.length > 10 ? '...' : ''}"`;
                } else if (obj.type === 'shape' && obj.shapeType) {
                    // Get shape-specific icon and name
                    const shapeInfo = IWB.getShapeDisplayInfo(obj.shapeType);
                    icon = shapeInfo.icon;
                    typeName = shapeInfo.name;
                    const x = Math.floor(obj.x || 0);
                    const y = Math.floor(obj.y || 0);
                    const w = Math.floor(obj.w || 0);
                    const h = Math.floor(obj.h || 0);
                    displayDetails = `(${x}, ${y}) ${w}×${h}`;
                }
                
                // Display name format: obj<number> - <type>
                const displayName = `obj${objNumber} - ${typeName}`;
                
                html.push(`
                    <div class="layer-item ${isSelected ? 'selected' : ''} ${isVisible ? '' : 'hidden-layer'}" 
                         onclick="handleLayerItemClick(${obj.id})"
                         data-object-id="${obj.id}"
                         data-layer="${layerValue}">
                        <div class="layer-item-icon">${icon}</div>
                        <div class="layer-item-info">
                            <div class="layer-item-primary">${displayName}</div>
                            <div class="layer-item-secondary">${displayDetails}</div>
                        </div>
                    </div>
                `);
            });
            
            html.push(`
                    </div>
                </div>
            `);
        });
        
        panelContent.innerHTML = html.join('');
        
        // Restore scroll positions for all layer groups
        scrollPositions.forEach((scrollTop, layerValue) => {
            const group = panelContent.querySelector(`.layer-group-content[data-layer="${layerValue}"]`);
            if (group) {
                group.scrollTop = scrollTop;
            }
        });
    };

    /**
     * Initialize layer keyboard shortcuts
     * @param {Function} bringToFrontCallback - Callback for Ctrl+]
     * @param {Function} sendToBackCallback - Callback for Ctrl+[
     * @param {Function} moveUpCallback - Callback for ]
     * @param {Function} moveDownCallback - Callback for [
     */
    IWB.initLayerShortcuts = function(bringToFrontCallback, sendToBackCallback, moveUpCallback, moveDownCallback) {
        document.addEventListener('keydown', (e) => {
            if (IWB.shouldIgnoreHotkeys && IWB.shouldIgnoreHotkeys(e)) return;

            // Ctrl+] - Bring to front
            if (e.ctrlKey && e.key === ']') {
                e.preventDefault();
                bringToFrontCallback();
            }
            
            // Ctrl+[ - Send to back
            if (e.ctrlKey && e.key === '[') {
                e.preventDefault();
                sendToBackCallback();
            }
            
            // ] - Move up one layer
            if (!e.ctrlKey && e.key === ']') {
                e.preventDefault();
                moveUpCallback();
            }
            
            // [ - Move down one layer
            if (!e.ctrlKey && e.key === '[') {
                e.preventDefault();
                moveDownCallback();
            }
        });
        
        console.log('[LAYERS] Keyboard shortcuts initialized: Ctrl+] (front), Ctrl+[ (back), ] (up), [ (down)');
    };

    /**
     * Toggle visibility of a layer group
     * @param {number} layerValue - The layer value to toggle
     * @returns {boolean} - New visibility state
     */
    IWB.toggleLayerVisibility = function(layerValue) {
        if (!window.hiddenLayers) {
            window.hiddenLayers = new Set();
        }
        
        if (window.hiddenLayers.has(layerValue)) {
            window.hiddenLayers.delete(layerValue);
            console.log(`[LAYERS] Layer ${layerValue} is now visible`);
            return true;
        } else {
            window.hiddenLayers.add(layerValue);
            console.log(`[LAYERS] Layer ${layerValue} is now hidden`);
            return false;
        }
    };
    
    /**
     * Check if a layer is visible
     * @param {number} layerValue - The layer value to check
     * @returns {boolean} - True if visible
     */
    IWB.isLayerVisible = function(layerValue) {
        return !window.hiddenLayers || !window.hiddenLayers.has(layerValue);
    };
    
    /**
     * Check if an object should be rendered based on its layer visibility
     * @param {Object} obj - The object to check
     * @returns {boolean} - True if object should be rendered
     */
    IWB.shouldRenderObject = function(obj) {
        if (!obj) return false;
        const layerValue = getLayerValue(obj);
        return IWB.isLayerVisible(layerValue);
    };
    
    /**
     * Toggle collapse/expand state of a layer group
     * @param {number} layerValue - The layer value to toggle
     */
    IWB.toggleLayerGroupCollapse = function(layerValue) {
        if (!window.collapsedLayers) {
            window.collapsedLayers = new Set();
        }
        
        if (window.collapsedLayers.has(layerValue)) {
            window.collapsedLayers.delete(layerValue);
        } else {
            window.collapsedLayers.add(layerValue);
        }
    };
    
    /**
     * Check if a layer group is collapsed
     * @param {number} layerValue - The layer value to check
     * @returns {boolean} - True if collapsed
     */
    IWB.isLayerGroupCollapsed = function(layerValue) {
        return window.collapsedLayers && window.collapsedLayers.has(layerValue);
    };

    console.log('[LAYERS] Infinite Whiteboard Layers module loaded');

})(window);
