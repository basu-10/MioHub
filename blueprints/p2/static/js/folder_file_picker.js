/**
 * Folder/File Picker Module
 * Provides a reusable modal for selecting folders or files from user's account
 */

window.FolderFilePicker = (function() {
  let foldersData = [];
  let rootFiles = [];
    let dataLoaded = false;
  let currentFolderId = 'root';
  let selectedItems = [];
  let allowedTypes = ['folder', 'file'];
  let onSelectCallback = null;
  let multiSelectEnabled = true;

  const FILE_TYPE_ICONS = {
    // Legacy types
    note: 'description',
    whiteboard: 'dashboard',
    
    // Proprietary products
    proprietary_note: 'description',
    proprietary_whiteboard: 'dashboard',
    proprietary_blocks: 'menu_book',
    proprietary_infinite_whiteboard: 'wallpaper',
    proprietary_graph: 'device_hub',
    
    // Third-party integrations
    markdown: 'description',
    code: 'code',
    todo: 'checklist',
    diagram: 'account_tree',
    table: 'table_chart',
    blocks: 'view_agenda',
    
    // Binary types
    pdf: 'picture_as_pdf',
    
    // Legacy aliases
    book: 'menu_book',
    
    default: 'insert_drive_file'
  };

  async function init() {
    await loadData();

    setupEventListeners();
  }

  async function loadData(forceReload = false) {
    if (dataLoaded && !forceReload) return;
    try {
      const response = await fetch('/folders/api/picker/folders_and_files');
      const data = await response.json();
      if (data.success) {
        foldersData = data.folders || [];
        rootFiles = data.root_files || [];
        dataLoaded = true;
        console.log('[FolderFilePicker] Loaded', {
          roots: foldersData.length,
          rootFiles: rootFiles.length
        });
      } else {
        console.error('[FolderFilePicker] Failed to load picker data');
      }
    } catch (err) {
      console.error('[FolderFilePicker] Error loading picker data:', err);
    }
  }

  function setupEventListeners() {
    document.getElementById('picker-confirm-btn').addEventListener('click', handleConfirm);
    document.getElementById('picker-select-all-btn').addEventListener('click', selectAllInView);

    const modal = document.getElementById('folderFilePickerModal');
    modal.addEventListener('hidden.bs.modal', () => {
      resetPicker();

      const attachmentModalEl = document.getElementById('attachmentModal');
      if (attachmentModalEl?.classList.contains('show')) {
        document.body.classList.add('modal-open');
      }
    });
  }

  function open(types, callback, options = {}) {
    allowedTypes = types || ['folder', 'file'];
    onSelectCallback = callback;
    multiSelectEnabled = options.multiSelect !== undefined
      ? options.multiSelect
      : !(allowedTypes.length === 1 && allowedTypes[0] === 'folder');

    let typeDisplay = 'Item';
    if (allowedTypes.length === 1) {
      typeDisplay = allowedTypes[0].charAt(0).toUpperCase() + allowedTypes[0].slice(1);
    } else {
      typeDisplay = 'Folder or File';
    }
    document.getElementById('picker-item-type-display').textContent = typeDisplay;

    resetPicker();
    renderCurrentView();

    const pickerModalEl = document.getElementById('folderFilePickerModal');
    const pickerModal = bootstrap.Modal.getOrCreateInstance(pickerModalEl, {
      backdrop: false,
      focus: true
    });
    pickerModal.show();

    // Ensure fresh data when opening (useful if initial load happened before user had files)
    loadData(true).then(() => {
      renderCurrentView();
    });
  }

  function resetPicker() {
    currentFolderId = 'root';
    selectedItems = [];
    document.getElementById('picker-confirm-btn').disabled = true;
    document.getElementById('picker-selection').style.display = 'none';
    document.getElementById('picker-select-all-btn').disabled = true;
  }

  function renderCurrentView() {
    const content = document.getElementById('picker-content');

    const currentFolder = getCurrentFolder();
    const folders = currentFolderId === 'root' ? foldersData : currentFolder?.children || [];

    renderBreadcrumb(currentFolderId === 'root' ? null : currentFolder);

    let html = '';

    if (currentFolderId !== 'root' && currentFolder && currentFolder.parent_id !== null) {
      html += `
        <div class="picker-item picker-folder-item" data-action="navigate-parent">
          <div class="picker-item-icon">
            <span class="material-icons">arrow_upward</span>
          </div>
          <div class="picker-item-info">
            <div class="picker-item-title">.. (Parent Folder)</div>
          </div>
        </div>
      `;
    }

    // Always render folders for navigation, even in file-only mode
    folders.forEach(folder => {
      const isSelected = selectedItems.some(item => item.type === 'folder' && item.id === folder.id);
      html += `
        <div class="picker-item picker-folder-item ${isSelected ? 'selected' : ''}" 
             data-type="folder" 
             data-id="${folder.id}"
             data-name="${escapeHtml(folder.name)}">
          <div class="picker-item-icon">
            <span class="material-icons">folder</span>
          </div>
          <div class="picker-item-info">
            <div class="picker-item-title">${escapeHtml(folder.name)}</div>
            <div class="picker-item-meta">
              ${folder.children.length} subfolders, ${folder.files.length} files
            </div>
          </div>
          <div class="picker-item-actions">
            <button class="btn btn-sm btn-outline-accent" onclick="event.stopPropagation(); window.FolderFilePicker.navigateToFolder(${folder.id})">
              <span class="material-icons" style="font-size: 16px;">arrow_forward</span>
            </button>
          </div>
        </div>
      `;
    });

    if (allowedTypes.includes('file') && currentFolder) {
      currentFolder.files.forEach(file => {
        const isSelected = selectedItems.some(item => item.type === 'file' && item.id === file.id);
        const iconName = FILE_TYPE_ICONS[file.type] || FILE_TYPE_ICONS.default;
        const checkbox = multiSelectEnabled ? `
          <div class="form-check me-2">
            <input class="form-check-input picker-check" type="checkbox" ${isSelected ? 'checked' : ''} tabindex="0">
          </div>
        ` : '';
        html += `
          <div class="picker-item picker-file-item ${isSelected ? 'selected' : ''}" 
               data-type="file" 
               data-id="${file.id}"
               data-title="${escapeHtml(file.title)}"
               data-file-type="${file.type}">
            ${checkbox}
            <div class="picker-item-icon">
              <span class="material-icons">${iconName}</span>
            </div>
            <div class="picker-item-info">
              <div class="picker-item-title">${escapeHtml(file.title)}</div>
              <div class="picker-item-meta">
                Type: ${file.type} ${file.created_at ? '• Created: ' + new Date(file.created_at).toLocaleDateString() : ''}
              </div>
            </div>
          </div>
        `;
      });
    }

    if (html === '' && currentFolderId !== 'root') {
      html = '<div class="text-center text-muted py-4">This folder is empty</div>';
    } else if (html === '') {
      html = '<div class="text-center text-muted py-4">No folders found. Create some folders first!</div>';
    }

    content.innerHTML = html;
    attachItemClickHandlers();
    updateSelectionUI();
  }

  function renderBreadcrumb(currentFolder) {
    const breadcrumb = document.getElementById('picker-breadcrumb');
    let html = '<li class="breadcrumb-item"><a href="#" data-folder-id="root">Home</a></li>';

    if (currentFolder) {
      const path = buildFolderPath(currentFolder.id, foldersData) || [];
      path.forEach(folder => {
        html += `<li class="breadcrumb-item"><a href="#" data-folder-id="${folder.id}">${escapeHtml(folder.name)}</a></li>`;
      });
    }

    breadcrumb.innerHTML = html;

    breadcrumb.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const folderId = e.target.dataset.folderId;
        navigateToFolder(folderId === 'root' ? 'root' : parseInt(folderId, 10));
      });
    });
  }

  function navigateToFolder(folderId) {
    currentFolderId = folderId;
    renderCurrentView();
  }

  function attachItemClickHandlers() {
    document.querySelectorAll('.picker-item').forEach(item => {
      item.addEventListener('click', () => {
        if (item.dataset.action === 'navigate-parent') {
          const currentFolder = findFolderById(currentFolderId, foldersData);
          if (currentFolder && currentFolder.parent_id !== null) {
            navigateToFolder(currentFolder.parent_id);
          } else {
            navigateToFolder('root');
          }
          return;
        }

        const type = item.dataset.type;
        const id = parseInt(item.dataset.id, 10);

        // For folder items when folders are not selectable, treat click as navigation
        if (type === 'folder' && !allowedTypes.includes('folder')) {
          navigateToFolder(id);
          return;
        }

        if (!allowedTypes.includes(type)) return;

        const name = type === 'folder' ? item.dataset.name : item.dataset.title;
        const fileType = type === 'file' ? item.dataset.fileType : null;
        const itemData = { type, id, name, fileType };
        const singleSelectMode = !multiSelectEnabled || (allowedTypes.length === 1 && allowedTypes[0] === 'folder');

        if (singleSelectMode) {
          selectedItems = [itemData];
        } else {
          const existingIndex = selectedItems.findIndex(sel => sel.type === type && sel.id === id);
          if (existingIndex >= 0) {
            selectedItems.splice(existingIndex, 1);
          } else {
            selectedItems.push(itemData);
          }
        }

        updateSelectionUI();
      });
    });
  }

  function handleConfirm() {
    if (!selectedItems.length || !onSelectCallback) return;

    const payload = multiSelectEnabled ? [...selectedItems] : selectedItems[0];
    onSelectCallback(payload);

    const modal = bootstrap.Modal.getInstance(document.getElementById('folderFilePickerModal'));
    modal.hide();
  }

  function selectAllInView() {
    if (!multiSelectEnabled || !allowedTypes.includes('file')) return;

    const currentFolder = getCurrentFolder();
    const filesHere = currentFolder?.files || [];
    if (!filesHere.length) return;

    const currentFileIds = new Set(filesHere.map(f => f.id));
    const selectedHere = selectedItems.filter(item => item.type === 'file' && currentFileIds.has(item.id));

    if (selectedHere.length === filesHere.length) {
      selectedItems = selectedItems.filter(item => !(item.type === 'file' && currentFileIds.has(item.id)));
    } else {
      filesHere.forEach(file => {
        const exists = selectedItems.some(item => item.type === 'file' && item.id === file.id);
        if (!exists) {
          selectedItems.push({ type: 'file', id: file.id, name: file.title, fileType: file.type });
        }
      });
    }

    updateSelectionUI();
  }

  function updateSelectionUI() {
    const selectionEl = document.getElementById('picker-selection');
    const infoEl = document.getElementById('picker-selected-info');
    const confirmBtn = document.getElementById('picker-confirm-btn');
    const selectAllBtn = document.getElementById('picker-select-all-btn');

    if (selectedItems.length === 0) {
      selectionEl.style.display = 'none';
      confirmBtn.disabled = true;
      infoEl.innerHTML = '';
    } else {
      selectionEl.style.display = 'block';
      confirmBtn.disabled = false;
      infoEl.innerHTML = selectedItems.map(item => {
        const iconName = item.type === 'folder' ? 'folder' : (FILE_TYPE_ICONS[item.fileType] || FILE_TYPE_ICONS.default);
        const label = `${escapeHtml(item.name)}${item.fileType ? ' (' + item.fileType + ')' : ''}`;
        return `<div class="d-flex align-items-center gap-2 mb-1"><span class="material-icons" style="font-size: 18px; color: var(--accent);">${iconName}</span><span>${label}</span></div>`;
      }).join('');
    }

    const currentFolder = getCurrentFolder();
    const currentFileIds = new Set((currentFolder?.files || []).map(f => f.id));
    const selectedHere = selectedItems.filter(item => item.type === 'file' && currentFileIds.has(item.id));
    const hasFilesInView = currentFileIds.size > 0;

    if (multiSelectEnabled && allowedTypes.includes('file') && hasFilesInView) {
      selectAllBtn.disabled = false;
      const allSelectedHere = selectedHere.length === currentFileIds.size && currentFileIds.size > 0;
      selectAllBtn.textContent = allSelectedHere ? 'Clear Selection' : 'Select All In This Folder';
    } else {
      selectAllBtn.disabled = true;
      selectAllBtn.textContent = 'Select All In This Folder';
    }

    document.querySelectorAll('.picker-item').forEach(el => {
      const type = el.dataset.type;
      const id = parseInt(el.dataset.id, 10);
      const isSelected = selectedItems.some(item => item.type === type && item.id === id);
      el.classList.toggle('selected', isSelected);
      const checkbox = el.querySelector('.picker-check');
      if (checkbox) {
        checkbox.checked = isSelected;
      }
    });
  }

  function getCurrentFolder() {
    if (currentFolderId === 'root') {
      return { id: 'root', name: 'Home', parent_id: null, children: foldersData, files: rootFiles };
    }
    return findFolderById(currentFolderId, foldersData);
  }

  function findFolderById(id, folders) {
    for (const folder of folders) {
      if (folder.id === id) {
        return folder;
      }
      if (folder.children && folder.children.length > 0) {
        const found = findFolderById(id, folder.children);
        if (found) return found;
      }
    }
    return null;
  }

  function buildFolderPath(folderId, folders, path = []) {
    for (const folder of folders) {
      if (folder.id === folderId) {
        return [...path, folder];
      }
      if (folder.children && folder.children.length > 0) {
        const found = buildFolderPath(folderId, folder.children, [...path, folder]);
        if (found) return found;
      }
    }
    return null;
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  return {
    init,
    open,
    navigateToFolder
  };
})();

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => window.FolderFilePicker.init());
} else {
  window.FolderFilePicker.init();
}
