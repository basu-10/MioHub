/**
 * Graph Attachments Module - Handles file/folder attachments to nodes
 */

window.GraphAttachments = (function() {
  let graphId = null;

  function init(fileId) {
    graphId = fileId;
  }

  async function addAttachment(nodeId, attachmentType, targetId, url, metadata) {
    try {
      const payload = {
        node_id: nodeId,
        attachment_type: attachmentType,
        metadata: metadata || {}
      };

      if (attachmentType === 'file') {
        payload.file_id = targetId;
      } else if (attachmentType === 'folder') {
        payload.folder_id = targetId;
      } else if (attachmentType === 'url') {
        payload.url = url;
      }

      const response = await fetch(`/graph/${graphId}/attachments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await response.json();
      if (data.ok) {
        await window.GraphStorage.loadGraph();
        return data.attachment;
      } else {
        console.error('Failed to add attachment:', data.error);
        // Show user-friendly error message
        const errorMsg = data.error || 'Unknown error';
        if (errorMsg.includes('already attached')) {
          alert('⚠️ This file/folder is already attached to this node. Each file can only be attached once.');
        } else {
          alert('Failed to add attachment: ' + errorMsg);
        }
        return null;
      }
    } catch (err) {
      console.error('Error adding attachment:', err);
      alert('Error adding attachment');
      return null;
    }
  }

  async function removeAttachment(attachmentId) {
    if (!confirm('Remove this attachment?')) return false;

    try {
      const response = await fetch(`/graph/${graphId}/attachments/${attachmentId}`, {
        method: 'DELETE'
      });

      const data = await response.json();
      if (data.ok) {
        await window.GraphStorage.loadGraph();
        return true;
      } else {
        console.error('Failed to remove attachment:', data.error);
        alert('Failed to remove attachment: ' + (data.error || 'Unknown error'));
      }
    } catch (err) {
      console.error('Error removing attachment:', err);
      alert('Error removing attachment');
    }
    return false;
  }

  function renderAttachmentsList(node, container) {
    container.innerHTML = '';

    if (!node.attachments || node.attachments.length === 0) {
      container.innerHTML = '<p class="text-muted">No attachments</p>';
      return;
    }

    node.attachments.forEach(att => {
      const itemDiv = document.createElement('div');
      itemDiv.className = 'attachment-item';

      const icon = getAttachmentIcon(att.attachment_type, att.metadata?.file_type);
      const label = getAttachmentLabel(att);

      // Build action buttons based on attachment type
      let actionButtons = '';
      
      if (att.attachment_type === 'file') {
        const attData = JSON.stringify({ file_id: att.file_id, file_type: att.metadata?.file_type }).replace(/"/g, '&quot;');
        actionButtons += `<button class="btn-icon" onclick="window.GraphAttachments.openAttachment('${attData}')" title="Open file">
          <i class="material-icons">open_in_new</i>
        </button>`;
      } else if (att.attachment_type === 'folder') {
        actionButtons += `<button class="btn-icon" onclick="window.location.href='/folders/${att.folder_id}'" title="View folder">
          <i class="material-icons">folder_open</i>
        </button>`;
      } else if (att.attachment_type === 'url') {
        actionButtons += `<a href="${att.url}" target="_blank" class="btn-icon" title="Open link">
          <i class="material-icons">open_in_new</i>
        </a>`;
      }
      
      actionButtons += `<button class="btn-icon btn-danger" onclick="window.GraphAttachments.removeAttachment(${att.id})" title="Remove attachment">
        <i class="material-icons">delete_outline</i>
      </button>`;

      itemDiv.innerHTML = `
        <div class="attachment-info">
          <i class="material-icons">${icon}</i>
          <span class="attachment-label">${label}</span>
        </div>
        <div class="attachment-actions">
          ${actionButtons}
        </div>
      `;

      container.appendChild(itemDiv);
    });
  }

  function getAttachmentIcon(type, fileType = null) {
    // If it's a file attachment, use file-type-specific icon
    if (type === 'file' && fileType) {
      const fileTypeIcons = {
        // Legacy types
        'note': 'description',
        'whiteboard': 'dashboard',
        
        // Proprietary products
        'proprietary_note': 'description',
        'proprietary_whiteboard': 'dashboard',
        'proprietary_blocks': 'menu_book',
        'proprietary_infinite_whiteboard': 'wallpaper',
        'proprietary_graph': 'device_hub',
        
        // Third-party integrations
        'markdown': 'description',
        'code': 'code',
        'todo': 'checklist',
        'diagram': 'account_tree',
        'table': 'table_chart',
        'blocks': 'view_agenda',
        
        // Binary types
        'pdf': 'picture_as_pdf',
        
        // Legacy aliases
        'book': 'menu_book'
      };
      return fileTypeIcons[fileType] || 'insert_drive_file';
    }
    
    // Generic attachment type icons
    const icons = {
      'file': 'insert_drive_file',
      'folder': 'folder',
      'url': 'link',
      'task': 'check_box'
    };
    return icons[type] || 'attachment';
  }

  function getAttachmentLabel(att) {
    if (att.attachment_type === 'url') {
      return att.url || 'URL';
    }
    return att.metadata?.title || `${att.attachment_type} #${att.file_id || att.folder_id}`;
  }

  function openAttachment(attDataStr) {
    // Parse attachment data
    const attData = JSON.parse(attDataStr);
    const fileId = attData.file_id;
    const fileType = attData.file_type;
    
    // Route based on file type
    if (fileType === 'whiteboard' || fileType === 'proprietary_whiteboard') {
      // MioDraw
      window.location.href = `/boards/edit/${fileId}`;
    } else if (fileType === 'note' || fileType === 'proprietary_note') {
      // MioNote
      window.location.href = `/edit_note/${fileId}`;
    } else if (fileType === 'book' || fileType === 'proprietary_blocks') {
      // MioBook
      window.location.href = `/combined/edit/${fileId}`;
    } else if (fileType === 'proprietary_infinite_whiteboard') {
      // Infinite Whiteboard
      window.location.href = `/infinite_boards/edit/${fileId}`;
    } else if (fileType === 'proprietary_graph') {
      // Graph Workspace
      window.location.href = `/graph/${fileId}`;
    } else {
      // All other file types (markdown, code, todo, diagram, table, blocks, pdf)
      window.location.href = `/p2/files/${fileId}/edit`;
    }
  }

  return {
    init,
    addAttachment,
    removeAttachment,
    renderAttachmentsList,
    openAttachment,
    getAttachmentLabel,
    getAttachmentIcon
  };
})();
