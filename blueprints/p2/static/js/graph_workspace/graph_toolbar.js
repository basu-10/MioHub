/**
 * Graph Toolbar Module - Handles toolbar controls and modals
 */

window.GraphToolbar = (function() {
  let graphId = null;
  let selectedNode = null;
  let selectedEdge = null;

  // Modal references
  let createNodeModal = null;
  let attachmentModal = null;
  let editArrowModal = null;

  // Debounce utility
  let debounceTimers = {};
  function debounce(key, fn, delay = 500) {
    return function(...args) {
      clearTimeout(debounceTimers[key]);
      debounceTimers[key] = setTimeout(() => fn.apply(this, args), delay);
    };
  }

  function normalizeLineStyleForSelect(lineStyle) {
    if (!lineStyle) return 'straight';
    if (lineStyle === 'elbow') return 'elbow_hvh'; // backward compatibility
    return lineStyle;
  }

  function setActiveInGroup(attrName, value) {
    const buttons = document.querySelectorAll(`[${attrName}]`);
    buttons.forEach(btn => {
      if (btn.getAttribute(attrName) === value) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });
  }

  function getActiveValue(attrName, fallback) {
    const active = document.querySelector(`[${attrName}].active`);
    return active ? active.getAttribute(attrName) : fallback;
  }

  async function applyArrowStyleUpdate(partialStyle) {
    if (!selectedEdge) return;
    const defaultStyle = window.GraphEdges.DEFAULT_EDGE_STYLE;
    const style = selectedEdge.metadata?.style || {};
    const mergedStyle = {
      color: document.getElementById('arrow-color').value || style.color || defaultStyle.color,
      thickness: parseInt(document.getElementById('arrow-thickness').value) || style.thickness || defaultStyle.thickness,
      direction: getActiveValue('data-arrow-direction', style.direction || selectedEdge.edgeType || defaultStyle.direction),
      dashPattern: getActiveValue('data-arrow-dash', style.dashPattern || defaultStyle.dashPattern),
      lineStyle: getActiveValue('data-arrow-line-style', normalizeLineStyleForSelect(style.lineStyle || defaultStyle.lineStyle)),
      ...partialStyle
    };

    await window.GraphEdges.updateEdge(selectedEdge.id, {
      metadata: { style: mergedStyle }
    });
  }

  function init(fileId) {
    graphId = fileId;

    // Initialize modals with explicit backdrop and keyboard options
    const modalOptions = {
      backdrop: true,
      keyboard: true,
      focus: true
    };
    createNodeModal = new bootstrap.Modal(document.getElementById('createNodeModal'), modalOptions);
    attachmentModal = new bootstrap.Modal(document.getElementById('attachmentModal'), modalOptions);
    editArrowModal = new bootstrap.Modal(document.getElementById('editArrowModal'), modalOptions);

    // Bind toolbar buttons
    document.getElementById('btn-add-node')?.addEventListener('click', openCreateNodeModal);
    document.getElementById('btn-connect-nodes')?.addEventListener('click', startConnectMode);
    document.getElementById('btn-edit-arrow')?.addEventListener('click', openEditArrowModal);
    document.getElementById('btn-delete-arrow')?.addEventListener('click', deleteSelectedEdge);
    document.getElementById('btn-snap-to-grid')?.addEventListener('click', toggleSnapToGrid);
    document.getElementById('btn-refresh-names')?.addEventListener('click', refreshAttachmentNames);
    document.getElementById('btn-fit-all')?.addEventListener('click', () => window.GraphCanvas.fitAllItems());
    document.getElementById('btn-reset-view')?.addEventListener('click', () => window.GraphCanvas.resetView());

    // Bind panel buttons (manage and delete are now only in the panel)
    document.getElementById('btn-panel-manage')?.addEventListener('click', openAttachmentModal);
    document.getElementById('btn-panel-delete')?.addEventListener('click', deleteSelectedNode);
    
    // Bind arrow panel toggle
    document.getElementById('arrow-panel-toggle-btn')?.addEventListener('click', toggleArrowPanel);

    // Bind modal submit buttons
    document.getElementById('create-node-submit')?.addEventListener('click', handleCreateNode);
    document.getElementById('add-attachment-submit')?.addEventListener('click', handleAddAttachment);
    document.getElementById('save-arrow-submit')?.addEventListener('click', handleSaveArrow);
    document.getElementById('save-node-details-btn')?.addEventListener('click', handleSaveNodeDetails);

    // Bind picker buttons
    document.getElementById('btn-pick-file')?.addEventListener('click', openFilePicker);
    
    // Bind arrow thickness slider with debounce to prevent excessive DB calls
    const debouncedThicknessUpdate = debounce('arrow-thickness', async (value) => {
      await applyArrowStyleUpdate({ thickness: parseInt(value) });
    }, 300);
    
    document.getElementById('arrow-thickness')?.addEventListener('input', function(e) {
      document.getElementById('thickness-value').textContent = e.target.value;
      // Update the visual immediately for responsiveness
      if (selectedEdge) {
        selectedEdge.metadata = selectedEdge.metadata || {};
        selectedEdge.metadata.style = selectedEdge.metadata.style || {};
        selectedEdge.metadata.style.thickness = parseInt(e.target.value);
        window.GraphCanvas.render(); // Immediate visual feedback
      }
      // Debounced server update
      debouncedThicknessUpdate(e.target.value);
    });

    // Bind arrow style button groups for instant apply
    document.querySelectorAll('.arrow-direction-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        setActiveInGroup('data-arrow-direction', btn.getAttribute('data-arrow-direction'));
        await applyArrowStyleUpdate({ direction: btn.getAttribute('data-arrow-direction') });
      });
    });

    document.querySelectorAll('.arrow-dash-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        setActiveInGroup('data-arrow-dash', btn.getAttribute('data-arrow-dash'));
        await applyArrowStyleUpdate({ dashPattern: btn.getAttribute('data-arrow-dash') });
      });
    });

    document.querySelectorAll('.arrow-line-style-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        setActiveInGroup('data-arrow-line-style', btn.getAttribute('data-arrow-line-style'));
        await applyArrowStyleUpdate({ lineStyle: btn.getAttribute('data-arrow-line-style') });
      });
    });

    // Live apply color changes with debounce to prevent excessive DB calls
    const debouncedColorUpdate = debounce('arrow-color', async (value) => {
      await applyArrowStyleUpdate({ color: value });
    }, 300);
    
    document.getElementById('arrow-color')?.addEventListener('input', (e) => {
      // Update the visual immediately for responsiveness
      if (selectedEdge) {
        selectedEdge.metadata = selectedEdge.metadata || {};
        selectedEdge.metadata.style = selectedEdge.metadata.style || {};
        selectedEdge.metadata.style.color = e.target.value;
        window.GraphCanvas.render(); // Immediate visual feedback
      }
      // Debounced server update
      debouncedColorUpdate(e.target.value);
    });

    // Show/hide orientation group based on direction
    function updateOrientationGroup() {
      const dir = getActiveValue('data-arrow-direction', 'directed');
      const group = document.getElementById('arrow-oneway-orientation-group');
      if (group) group.style.display = (dir === 'directed') ? '' : 'none';
    }
    document.querySelectorAll('.arrow-direction-btn').forEach(btn => {
      btn.addEventListener('click', updateOrientationGroup);
    });
    updateOrientationGroup();

    // Orientation button group
    document.querySelectorAll('.arrow-orientation-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        setActiveInGroup('data-arrow-orientation', btn.getAttribute('data-arrow-orientation'));
        await applyArrowStyleUpdate({ orientation: btn.getAttribute('data-arrow-orientation') });
      });
    });

    updateToolbarState();
  }

  function updateNodeSelection(node) {
    selectedNode = node;
    // Only clear edge selection if we're selecting a node (not when node is null)
    if (node) {
      selectedEdge = null;
    }
    updateToolbarState();

    if (node) {
      // Update node info panel
      document.getElementById('selected-node-title').textContent = node.title;
      document.getElementById('selected-node-summary').textContent = node.summary || 'No description';
      
      // Render attachments
      const attachmentsContainer = document.getElementById('node-attachments-list');
      window.GraphAttachments.renderAttachmentsList(node, attachmentsContainer);
      document.getElementById('node-attachments-count').textContent = (node.attachments || []).length;

      document.getElementById('node-info-panel').style.display = 'block';
    } else {
      document.getElementById('node-info-panel').style.display = 'none';
      document.getElementById('node-attachments-count').textContent = '0';
    }
  }

  function updateEdgeSelection(edge) {
    selectedEdge = edge;
    selectedNode = null;
    updateToolbarState();
    const arrowPanel = document.getElementById('arrow-ops-panel');
    const nodePanel = document.getElementById('node-info-panel');
    if (edge) {
      // Hide node panel, show arrow panel
      nodePanel.style.display = 'none';
      arrowPanel.style.display = 'block';
      arrowPanel.classList.remove('collapsed');
    } else {
      // Hide arrow panel when no edge selected
      arrowPanel.style.display = 'none';
    }
  }

  function updateToolbarState() {
    const hasNodeSelection = selectedNode !== null;
    const hasEdgeSelection = selectedEdge !== null;
    // Connect button is always enabled - users can enter connection mode anytime
    // Manage and delete buttons are now only in the panel
    const panelManageBtn = document.getElementById('btn-panel-manage');
    const panelDeleteBtn = document.getElementById('btn-panel-delete');
    if (panelManageBtn) panelManageBtn.disabled = !hasNodeSelection;
    if (panelDeleteBtn) panelDeleteBtn.disabled = !hasNodeSelection;
    // Arrow ops buttons are now in the arrow panel, no need to enable/disable here
  }

  function openCreateNodeModal() {
    document.getElementById('create-node-title').value = '';
    document.getElementById('create-node-summary').value = '';
    createNodeModal.show();
  }

  function openAttachmentModal() {
    if (!selectedNode) {
      alert('Please select a node first');
      return;
    }
    document.getElementById('attachment-node-id').value = selectedNode.id;
    document.getElementById('attachment-node-name').textContent = selectedNode.title;
    
    // Populate node title and description fields
    document.getElementById('attachment-node-title').value = selectedNode.title;
    document.getElementById('attachment-node-description').value = selectedNode.summary || '';
    
    const attachmentTypeSelect = document.getElementById('attachment-type');
    attachmentTypeSelect.value = 'file_folder';
    attachmentTypeSelect.dispatchEvent(new Event('change'));
    
    // Reset picker displays
    document.getElementById('attachment-file-id').value = '';
    document.getElementById('attachment-file-id').dataset.selectedItems = '[]';
    document.getElementById('attachment-file-display').value = '';
    document.getElementById('attachment-url').value = '';
    
    attachmentModal.show();
  }

  function openFilePicker() {
    window.FolderFilePicker.open(['file', 'folder'], (selected) => {
      const pickedItems = Array.isArray(selected) ? selected : (selected ? [selected] : []);
      if (!pickedItems.length) return;

      const fileInput = document.getElementById('attachment-file-id');
      fileInput.dataset.selectedItems = JSON.stringify(pickedItems);
      fileInput.value = pickedItems.map(item => item.id).join(',');

      const displayText = pickedItems.length === 1
        ? `${pickedItems[0].name}${pickedItems[0].fileType ? ' (' + pickedItems[0].fileType + ')' : ''}`
        : `${pickedItems.length} items selected`;
      document.getElementById('attachment-file-display').value = displayText;
    }, { multiSelect: true });
  }

  function openEditArrowModal() {
    if (!selectedEdge) {
      alert('Please select an arrow first');
      return;
    }
    
    const style = selectedEdge.metadata?.style || {};
    const defaultStyle = window.GraphEdges.DEFAULT_EDGE_STYLE;
    
    document.getElementById('edit-arrow-id').value = selectedEdge.id;
    document.getElementById('arrow-label').value = selectedEdge.label || '';
    document.getElementById('arrow-color').value = style.color || defaultStyle.color;
    document.getElementById('arrow-thickness').value = style.thickness || defaultStyle.thickness;
    document.getElementById('thickness-value').textContent = style.thickness || defaultStyle.thickness;
    setActiveInGroup('data-arrow-direction', style.direction || selectedEdge.edgeType || defaultStyle.direction);
    setActiveInGroup('data-arrow-dash', style.dashPattern || defaultStyle.dashPattern);
    setActiveInGroup('data-arrow-line-style', normalizeLineStyleForSelect(style.lineStyle || defaultStyle.lineStyle));
    
    // Set orientation group visibility and active state
    const orientation = style.orientation || 'forward';
    setActiveInGroup('data-arrow-orientation', orientation);
    const dir = style.direction || selectedEdge.edgeType || defaultStyle.direction;
    const group = document.getElementById('arrow-oneway-orientation-group');
    if (group) group.style.display = (dir === 'directed') ? '' : 'none';
    editArrowModal.show();
  }

  async function handleSaveArrow() {
    // Check if we're in defaults mode (set by graph_workspace.html)
    const mode = document.getElementById('edit-arrow-mode')?.value;
    if (mode === 'defaults') {
      // Let the main template handler handle defaults mode
      return;
    }
    
    const edgeId = parseInt(document.getElementById('edit-arrow-id').value);
    const label = document.getElementById('arrow-label').value.trim();
    const color = document.getElementById('arrow-color').value;
    const thickness = parseInt(document.getElementById('arrow-thickness').value);
    const defaultStyle = window.GraphEdges.DEFAULT_EDGE_STYLE;
    const direction = getActiveValue('data-arrow-direction', defaultStyle.direction);
    const dashPattern = getActiveValue('data-arrow-dash', defaultStyle.dashPattern);
    const lineStyle = getActiveValue('data-arrow-line-style', defaultStyle.lineStyle);
    
    const updates = {
      label: label,
      metadata: {
        style: {
          color: color,
          thickness: thickness,
          direction: direction,
          dashPattern: dashPattern,
          lineStyle: lineStyle
        }
      }
    };
    
    await window.GraphEdges.updateEdge(edgeId, updates);
    editArrowModal.hide();
  }

  async function deleteSelectedEdge() {
    if (!selectedEdge) return;
    
    if (confirm('Delete this arrow?')) {
      await window.GraphEdges.deleteEdge(selectedEdge.id);
      selectedEdge = null;
      updateToolbarState();
    }
  }

  function toggleSnapToGrid() {
    const btn = document.getElementById('btn-snap-to-grid');
    if (!btn) return;
    
    const isEnabled = window.GraphCanvas.toggleSnapToGrid();
    btn.setAttribute('data-snap-enabled', isEnabled ? 'true' : 'false');
    btn.title = isEnabled ? 'Snap to Grid: ON' : 'Snap to Grid: OFF';
    
    // Update icon
    const icon = btn.querySelector('.material-icons');
    if (icon) {
      icon.textContent = isEnabled ? 'grid_on' : 'grid_off';
    }
  }

  async function handleCreateNode() {
    const title = document.getElementById('create-node-title').value.trim();
    const summary = document.getElementById('create-node-summary').value.trim();

    if (!title) {
      alert('Please enter a title');
      return;
    }

    // Create node at canvas center
    const viewport = window.GraphCanvas.getViewport();
    const canvas = window.GraphCanvas.getCanvas();
    const centerWorld = window.GraphCanvas.screenToWorld(canvas.width / 2, canvas.height / 2);

    await window.GraphNodes.createNode(title, summary, centerWorld.x - 110, centerWorld.y - 60);
    createNodeModal.hide();
  }

  async function handleSaveNodeDetails() {
    const nodeId = parseInt(document.getElementById('attachment-node-id').value);
    const title = document.getElementById('attachment-node-title').value.trim();
    const summary = document.getElementById('attachment-node-description').value.trim();

    if (!title) {
      alert('Please enter a title');
      return;
    }

    await window.GraphNodes.updateNode(nodeId, { title, summary });
    
    // Update the displayed node name in modal
    document.getElementById('attachment-node-name').textContent = title;
    
    // Keep modal open so user can continue adding attachments
    alert('Node details saved successfully!');
  }

  async function handleAddAttachment() {
    const nodeId = parseInt(document.getElementById('attachment-node-id').value);
    const attachmentType = document.getElementById('attachment-type').value;

    if (attachmentType === 'file_folder') {
      const fileInputEl = document.getElementById('attachment-file-id');
      let selectedItems = [];
      try {
        selectedItems = JSON.parse(fileInputEl.dataset.selectedItems || '[]');
      } catch (e) {
        selectedItems = [];
      }

      if (!selectedItems.length) {
        alert('Please select at least one file or folder');
        return;
      }

      let successCount = 0;
      let skipCount = 0;
      for (const item of selectedItems) {
        const targetType = item.type === 'folder' ? 'folder' : 'file';
        const displayName = item.name || 'Untitled';
        const typeSuffix = item.fileType ? ` (${item.fileType})` : '';
        const perItemMetadata = { title: `${displayName}${typeSuffix}` };
        const result = await window.GraphAttachments.addAttachment(nodeId, targetType, item.id, null, perItemMetadata);
        if (result) {
          successCount++;
        } else {
          skipCount++;
        }
      }

      // Only close modal if at least one attachment was added successfully
      if (successCount > 0) {
        attachmentModal.hide();
        clearAttachmentForm();
        if (skipCount > 0) {
          alert(`✓ Added ${successCount} attachment(s). Skipped ${skipCount} duplicate(s).`);
        }
      }
      return;
    }

    if (attachmentType === 'url') {
      const url = document.getElementById('attachment-url').value.trim();
      if (!url) {
        alert('Please enter a URL');
        return;
      }

      const result = await window.GraphAttachments.addAttachment(nodeId, attachmentType, null, url, {});
      if (result) {
        attachmentModal.hide();
        clearAttachmentForm();
      }
      return;
    }

    alert('Unsupported attachment type selected.');
  }

  function clearAttachmentForm() {
    document.getElementById('attachment-file-id').value = '';
    document.getElementById('attachment-file-id').dataset.selectedItems = '[]';
    document.getElementById('attachment-file-display').value = '';
    document.getElementById('attachment-url').value = '';
  }

  function startConnectMode() {
    // This function is now obsolete - connection mode is handled in main workspace script
    // Left here for backward compatibility
  }

  async function deleteSelectedNode() {
    if (!selectedNode) return;
    
    const success = await window.GraphNodes.deleteNode(selectedNode.id);
    if (success) {
      selectedNode = null;
      updateNodeSelection(null);
    }
  }

  async function refreshAttachmentNames() {
    try {
      const response = await fetch(`/graph/${graphId}/refresh-attachments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      const data = await response.json();
      if (data.ok) {
        // Reload the graph to show updated names
        await window.GraphStorage.loadGraph();
        alert(`Successfully refreshed ${data.updated_count} attachment name(s)`);
        
        // Update the info panel if a node is selected
        if (selectedNode) {
          const updatedNode = window.GraphNodes.getNodeById(selectedNode.id);
          if (updatedNode) {
            updateNodeSelection(updatedNode);
          }
        }
      } else {
        alert('Failed to refresh attachment names: ' + (data.error || 'Unknown error'));
      }
    } catch (err) {
      console.error('Error refreshing attachment names:', err);
      alert('Error refreshing attachment names');
    }
  }

  // Handle attachment type change to show/hide relevant inputs
  document.getElementById('attachment-type')?.addEventListener('change', function() {
    const type = this.value;
    document.getElementById('attachment-file-group').style.display = type === 'file_folder' ? 'block' : 'none';
    document.getElementById('attachment-url-group').style.display = type === 'url' ? 'block' : 'none';
  });

  // Toggle arrow panel collapsed state
  function toggleArrowPanel() {
    const panel = document.getElementById('arrow-ops-panel');
    panel.classList.toggle('collapsed');
  }

  return {
    init,
    updateNodeSelection,
    updateEdgeSelection,
    openEditArrowModal,
    openAttachmentModal,
    toggleArrowPanel
  };
})();
