/**
 * Graph Content Renderer Module - Handles rendering markdown and blocks content within nodes
 */

window.GraphContentRenderer = (function() {
  let graphId = null;
  let renderedContents = new Map(); // nodeId -> { fileId, type, content, isRendered }
  let isResizingOverlay = false; // Flag to prevent overlay recreation during resize

  function init(fileId) {
    graphId = fileId;
  }

  /**
   * Check if a file type can be rendered inline
   */
  function canRenderFileType(fileType) {
    const renderableTypes = ['markdown', 'blocks', 'proprietary_blocks'];
    return renderableTypes.includes(fileType);
  }

  /**
   * Toggle rendering of a file within a node
   */
  async function toggleRender(nodeId, attachment) {
    const key = `${nodeId}_${attachment.file_id}`;
    const currentState = renderedContents.get(key);

    if (currentState && currentState.isRendered) {
      // Turn off rendering
      renderedContents.delete(key);
      await updateNodeRenderedContent(nodeId);
      window.GraphCanvas.render();
      return { success: true, isRendered: false };
    } else {
      // Turn on rendering - fetch content first
      try {
        const content = await fetchFileContent(attachment.file_id);
        if (content) {
          renderedContents.set(key, {
            fileId: attachment.file_id,
            fileType: attachment.metadata?.file_type || 'markdown',
            title: attachment.metadata?.title || 'Untitled',
            content: content,
            isRendered: true
          });
          await updateNodeRenderedContent(nodeId);
          window.GraphCanvas.render();
          return { success: true, isRendered: true };
        }
      } catch (error) {
        console.error('Error fetching file content:', error);
        alert('Failed to load file content');
        return { success: false, error: error.message };
      }
    }
  }

  /**
   * Fetch file content from API
   */
  async function fetchFileContent(fileId) {
    const response = await fetch(`/p2/api/files/${fileId}/content`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const data = await response.json();
    return data;
  }

  /**
   * Update node with rendered content data and create overlay
   */
  async function updateNodeRenderedContent(nodeId) {
    const node = window.GraphNodes.getNodeById(nodeId);
    if (!node) return;

    // Collect all rendered content for this node
    const nodeRenderedContent = [];
    for (const [key, value] of renderedContents.entries()) {
      if (key.startsWith(`${nodeId}_`)) {
        nodeRenderedContent.push(value);
      }
    }

    // Store in node's metadata
    if (!node.metadata) {
      node.metadata = {};
    }
    node.metadata.renderedContent = nodeRenderedContent;

    // Auto-expand node height if content is rendered
    if (nodeRenderedContent.length > 0) {
      // Get saved content size or use defaults
      const contentSize = node.metadata.renderedContentSize || { width: 400, height: 300 };
      const titleHeight = 80;
      const padding = 20;
      const minHeightWithContent = titleHeight + contentSize.height + padding;
      
      // Also ensure width is adequate
      const minWidthWithContent = contentSize.width + 24; // 24px for padding
      
      let needsUpdate = false;
      if (node.height < minHeightWithContent) {
        node.height = minHeightWithContent;
        needsUpdate = true;
      }
      if (node.width < minWidthWithContent) {
        node.width = Math.max(220, minWidthWithContent); // Min 220px width
        needsUpdate = true;
      }
      
      if (needsUpdate) {
        // Save node size and metadata to server
        await window.GraphNodes.updateNode(nodeId, {
          size: { w: node.width, h: node.height },
          metadata: node.metadata
        });
      }
    } else {
      // Content was removed - restore default size
      const defaultHeight = 120;
      const defaultWidth = 220;
      let needsUpdate = false;
      
      if (node.height > defaultHeight) {
        node.height = defaultHeight;
        needsUpdate = true;
      }
      if (node.width > defaultWidth) {
        node.width = defaultWidth;
        needsUpdate = true;
      }
      
      if (needsUpdate) {
        await window.GraphNodes.updateNode(nodeId, {
          size: { w: node.width, h: node.height },
          metadata: node.metadata
        });
      }
    }

    // Update rendered overlays
    updateRenderedOverlays();
  }

  /**
   * Check if a specific file is currently rendered in a node
   */
  function isFileRendered(nodeId, fileId) {
    const key = `${nodeId}_${fileId}`;
    const state = renderedContents.get(key);
    return state && state.isRendered;
  }

  /**
   * Get all rendered content for a specific node
   */
  function getRenderedContentForNode(nodeId) {
    const content = [];
    for (const [key, value] of renderedContents.entries()) {
      if (key.startsWith(`${nodeId}_`)) {
        content.push(value);
      }
    }
    return content;
  }

  /**
   * Render markdown content to HTML
   */
  function renderMarkdownContent(markdownText) {
    if (!markdownText) return '<p class="text-muted">Empty content</p>';
    
    // Use marked.js if available, otherwise basic rendering
    if (window.marked) {
      return marked.parse(markdownText);
    }
    
    // Fallback: basic markdown-to-HTML conversion
    let html = markdownText
      .replace(/^### (.*$)/gim, '<h3>$1</h3>')
      .replace(/^## (.*$)/gim, '<h2>$1</h2>')
      .replace(/^# (.*$)/gim, '<h1>$1</h1>')
      .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
      .replace(/\*(.*)\*/gim, '<em>$1</em>')
      .replace(/\n\n/gim, '</p><p>')
      .replace(/\n/gim, '<br>');
    
    return `<p>${html}</p>`;
  }

  /**
   * Render blocks (Editor.js) content to HTML
   */
  function renderBlocksContent(blocksData) {
    if (!blocksData || !blocksData.blocks || blocksData.blocks.length === 0) {
      return '<p class="text-muted">Empty content</p>';
    }

    let html = '';
    
    blocksData.blocks.forEach(block => {
      switch (block.type) {
        case 'header':
          const level = block.data.level || 2;
          html += `<h${level}>${block.data.text || ''}</h${level}>`;
          break;
        
        case 'paragraph':
          html += `<p>${block.data.text || ''}</p>`;
          break;
        
        case 'list':
          const listTag = block.data.style === 'ordered' ? 'ol' : 'ul';
          const items = block.data.items || [];
          html += `<${listTag}>`;
          items.forEach(item => {
            html += `<li>${item}</li>`;
          });
          html += `</${listTag}>`;
          break;
        
        case 'quote':
          html += `<blockquote>${block.data.text || ''}</blockquote>`;
          break;
        
        case 'code':
          html += `<pre><code>${block.data.code || ''}</code></pre>`;
          break;
        
        case 'delimiter':
          html += '<hr>';
          break;
        
        case 'table':
          if (block.data.content && block.data.content.length > 0) {
            html += '<table class="table table-sm table-bordered">';
            block.data.content.forEach((row, idx) => {
              const tag = idx === 0 ? 'th' : 'td';
              html += '<tr>';
              row.forEach(cell => {
                html += `<${tag}>${cell}</${tag}>`;
              });
              html += '</tr>';
            });
            html += '</table>';
          }
          break;
        
        case 'checklist':
          html += '<ul class="checklist">';
          (block.data.items || []).forEach(item => {
            const checked = item.checked ? 'checked' : '';
            html += `<li><input type="checkbox" ${checked} disabled> ${item.text}</li>`;
          });
          html += '</ul>';
          break;
        
        default:
          // Unknown block type - display as paragraph
          if (block.data.text) {
            html += `<p>${block.data.text}</p>`;
          }
      }
    });

    return html;
  }

  /**
   * Generate HTML for rendered content display in node
   */
  function generateRenderedHTML(renderedContent) {
    if (!renderedContent || renderedContent.length === 0) {
      return '';
    }

    let html = '<div class="node-rendered-content">';
    
    renderedContent.forEach(item => {
      html += `<div class="rendered-content-item" data-file-id="${item.fileId}">`;
      html += `<div class="rendered-content-title">${item.title}</div>`;
      html += '<div class="rendered-content-body">';
      
      if (item.fileType === 'markdown') {
        const markdownSource = item.content.content_text || '';
        html += renderMarkdownContent(markdownSource);
      } else if (item.fileType === 'blocks' || item.fileType === 'proprietary_blocks') {
        const blocksData = item.content.content_json || {};
        html += renderBlocksContent(blocksData);
      }
      
      html += '</div></div>';
    });
    
    html += '</div>';
    return html;
  }

  /**
   * Clear all rendered content for a node
   */
  function clearRenderedContentForNode(nodeId) {
    const keysToDelete = [];
    for (const key of renderedContents.keys()) {
      if (key.startsWith(`${nodeId}_`)) {
        keysToDelete.push(key);
      }
    }
    keysToDelete.forEach(key => renderedContents.delete(key));
  }

  /**
   * Load renderer state from node metadata
   */
  function loadRendererState(nodes) {
    // When loading graph data, restore rendered content state from node metadata
    nodes.forEach(node => {
      if (node.metadata && node.metadata.renderedContent) {
        node.metadata.renderedContent.forEach(item => {
          const key = `${node.id}_${item.fileId}`;
          renderedContents.set(key, item);
        });
      }
    });
    // Update overlays after loading state
    updateRenderedOverlays();
  }

  /**
   * Update all rendered content overlays on the canvas
   */
  function updateRenderedOverlays() {
    // Skip update if actively resizing to prevent overlay recreation
    if (isResizingOverlay) {
      return;
    }
    
    const overlaysContainer = document.getElementById('graph-rendered-overlays');
    if (!overlaysContainer) {
      console.warn('Rendered overlays container not found');
      return;
    }

    // Clear existing overlays
    overlaysContainer.innerHTML = '';

    // Get all nodes with rendered content
    const nodes = window.GraphNodes?.getNodes() || [];
    nodes.forEach(node => {
      const renderedContent = getRenderedContentForNode(node.id);
      if (renderedContent.length > 0) {
        createOverlayForNode(node, renderedContent, overlaysContainer);
      }
    });
  }

  /**
   * Create an HTML overlay for a node's rendered content
   */
  function createOverlayForNode(node, renderedContent, container) {
    const canvas = document.getElementById('graph-canvas');
    if (!canvas) return;

    // Get screen position for the node
    const screenPos = window.GraphCanvas.worldToScreen(node.x, node.y);
    const scale = window.GraphCanvas.getScale ? window.GraphCanvas.getScale() : 1;

    const overlayDiv = document.createElement('div');
    overlayDiv.className = 'graph-rendered-content-overlay';
    overlayDiv.dataset.nodeId = node.id;
    
    // Get or create size from node metadata
    if (!node.metadata.renderedContentSize) {
      node.metadata.renderedContentSize = { width: 400, height: 300 };
    }
    const contentSize = node.metadata.renderedContentSize;
    
    // Position overlay below title/summary area, INSIDE the node
    const titleHeight = 80; // Title + summary + padding
    const padding = 12;
    const overlayX = screenPos.x + padding * scale;
    const overlayY = screenPos.y + titleHeight * scale;
    
    // Store unscaled dimensions; transform handles visual scale so the box tracks zoom without drifting
    overlayDiv.style.left = `${overlayX}px`;
    overlayDiv.style.top = `${overlayY}px`;
    overlayDiv.style.width = `${contentSize.width}px`;
    overlayDiv.style.height = `${contentSize.height}px`;
    
    // Apply scale transform so text/content size follows canvas zoom while anchor stays inside the node
    overlayDiv.style.transform = `scale(${scale})`;
    overlayDiv.style.transformOrigin = 'top left';

    // Build content HTML with resize handle
    let contentHTML = '';
    renderedContent.forEach(item => {
      contentHTML += `<div class="rendered-content-item" data-file-id="${item.fileId}">`;
      contentHTML += `<div class="rendered-content-header">`;
      contentHTML += `<div class="rendered-content-title">${escapeHTML(item.title)}</div>`;
      contentHTML += `<div class="rendered-content-actions">`;
      contentHTML += `<button class="btn-icon-small" onclick="window.GraphContentRenderer.openFileInEditMode(${item.fileId}, '${item.fileType}')" title="Edit file in new tab">`;
      contentHTML += `<i class="material-icons">edit</i>`;
      contentHTML += `</button>`;
      contentHTML += `<button class="btn-icon-small btn-danger" onclick="window.GraphContentRenderer.toggleRenderFromOverlay(${node.id}, ${item.fileId})" title="Hide rendered content">`;
      contentHTML += `<i class="material-icons">visibility_off</i>`;
      contentHTML += `</button>`;
      contentHTML += `</div>`;
      contentHTML += `</div>`;
      contentHTML += '<div class="rendered-content-body">';
      
      if (item.fileType === 'markdown') {
        const markdownSource = item.content.content_text || '';
        contentHTML += renderMarkdownContent(markdownSource);
      } else if (item.fileType === 'blocks' || item.fileType === 'proprietary_blocks') {
        const blocksData = item.content.content_json || {};
        contentHTML += renderBlocksContent(blocksData);
      }
      
      contentHTML += '</div></div>';
    });
    
    // Add resize handle
    contentHTML += '<div class="rendered-content-resize-handle" title="Drag to resize"></div>';

    overlayDiv.innerHTML = contentHTML;
    container.appendChild(overlayDiv);
    
    // Attach resize functionality
    attachResizeHandler(overlayDiv, node);
  }

  /**
   * Escape HTML to prevent XSS
   */
  function escapeHTML(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  /**
   * Toggle render from the overlay itself
   */
  async function toggleRenderFromOverlay(nodeId, fileId) {
    // Find the attachment with this fileId
    const node = window.GraphNodes.getNodeById(nodeId);
    if (!node) return;
    
    const attachment = node.attachments.find(att => att.file_id === fileId);
    if (!attachment) return;
    
    // Toggle off (we know it's currently rendered)
    const key = `${nodeId}_${fileId}`;
    renderedContents.delete(key);
    await updateNodeRenderedContent(nodeId);
    window.GraphCanvas.render();
    
    // Refresh attachment list to update button state
    if (window.GraphToolbar) {
      const container = document.getElementById('node-attachments-list');
      if (container) {
        window.GraphAttachments.renderAttachmentsList(node, container);
      }
    }
  }

  /**
   * Open file in edit mode in new tab
   */
  function openFileInEditMode(fileId, fileType) {
    let url = '';
    
    // Route based on file type
    if (fileType === 'proprietary_whiteboard') {
      url = `/boards/edit/${fileId}`;
    } else if (fileType === 'proprietary_note') {
      url = `/edit_note/${fileId}`;
    } else if (fileType === 'proprietary_blocks') {
      url = `/combined/edit/${fileId}`;
    } else if (fileType === 'proprietary_infinite_whiteboard') {
      url = `/infinite_boards/edit/${fileId}`;
    } else if (fileType === 'proprietary_graph') {
      url = `/graph/${fileId}`;
    } else {
      // All other file types (markdown, code, todo, diagram, table, blocks, pdf)
      url = `/p2/files/${fileId}/edit`;
    }
    
    window.open(url, '_blank');
  }

  /**
   * Attach resize handler to overlay
   */
  function attachResizeHandler(overlayDiv, node) {
    const resizeHandle = overlayDiv.querySelector('.rendered-content-resize-handle');
    if (!resizeHandle) return;

    let isResizing = false;
    let startX, startY, startWidth, startHeight;

    resizeHandle.addEventListener('mousedown', function(e) {
      e.preventDefault();
      e.stopPropagation();
      isResizing = true;
      isResizingOverlay = true; // Prevent overlay recreation
      
      // Get the actual rendered size (accounting for scale transform)
      const rect = overlayDiv.getBoundingClientRect();
      startX = e.clientX;
      startY = e.clientY;
      startWidth = rect.width;
      startHeight = rect.height;

      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    });

    function handleMouseMove(e) {
      if (!isResizing) return;
      e.preventDefault();

      const scale = window.GraphCanvas.getScale ? window.GraphCanvas.getScale() : 1;
      const deltaX = e.clientX - startX;
      const deltaY = e.clientY - startY;
      
      // Calculate new size in screen space
      const newScreenWidth = Math.max(200, startWidth + deltaX);
      const newScreenHeight = Math.max(150, startHeight + deltaY);
      
      // Convert to world space (unscaled dimensions)
      const contentWidth = newScreenWidth / scale;
      const contentHeight = newScreenHeight / scale;
      
      // Update metadata
      node.metadata.renderedContentSize = {
        width: contentWidth,
        height: contentHeight
      };
      
      // Apply the new unscaled size (scale transform will handle display)
      overlayDiv.style.width = `${contentWidth}px`;
      overlayDiv.style.height = `${contentHeight}px`;
      
      // Auto-adjust node size to match content (both expand AND shrink)
      const padding = 24;
      const titleHeight = 80;
      const minNodeWidth = 220; // Absolute minimum node width
      const requiredNodeWidth = Math.max(minNodeWidth, contentWidth + padding);
      const requiredNodeHeight = contentHeight + titleHeight + padding;
      
      let nodeChanged = false;
      
      // Update node dimensions to match content size
      if (Math.abs(node.width - requiredNodeWidth) > 1) {
        node.width = requiredNodeWidth;
        nodeChanged = true;
      }
      if (Math.abs(node.height - requiredNodeHeight) > 1) {
        node.height = requiredNodeHeight;
        nodeChanged = true;
      }
      
      // Re-render canvas if node size changed
      if (nodeChanged) {
        window.GraphCanvas.render();
      }
    }

    function handleMouseUp(e) {
      if (!isResizing) return;
      isResizing = false;
      
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      
      // Get final size from the overlay's unscaled dimensions
      const scale = window.GraphCanvas.getScale ? window.GraphCanvas.getScale() : 1;
      const contentWidth = parseFloat(overlayDiv.style.width);
      const contentHeight = parseFloat(overlayDiv.style.height);
      
      node.metadata.renderedContentSize = {
        width: contentWidth,
        height: contentHeight
      };
      
      // Ensure node dimensions accommodate the content
      const titleHeight = 80;
      const padding = 24;
      const minNodeHeight = titleHeight + contentHeight + padding;
      const minNodeWidth = Math.max(220, contentWidth + padding);
      
      let needsSizeUpdate = false;
      if (Math.abs(node.height - minNodeHeight) > 1) {
        node.height = minNodeHeight;
        needsSizeUpdate = true;
      }
      if (Math.abs(node.width - minNodeWidth) > 1) {
        node.width = minNodeWidth;
        needsSizeUpdate = true;
      }
      
      // Save both metadata and size to server
      const updates = { metadata: node.metadata };
      if (needsSizeUpdate) {
        updates.size = { w: node.width, h: node.height };
      }
      
      // Clear resize flag and update
      isResizingOverlay = false;
      
      window.GraphNodes.updateNode(node.id, updates).then(() => {
        // Force re-render to show updated node size
        window.GraphCanvas.render();
      });
    }
  }

  return {
    init,
    canRenderFileType,
    toggleRender,
    isFileRendered,
    getRenderedContentForNode,
    generateRenderedHTML,
    clearRenderedContentForNode,
    loadRendererState,
    updateRenderedOverlays,
    toggleRenderFromOverlay,
    openFileInEditMode
  };
})();
