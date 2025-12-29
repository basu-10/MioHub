/**
 * MioBook Core Module
 * Handles document state, saving, and block management
 */

class MioBookCore {
    constructor(documentId, folderId) {
        this.documentId = documentId;
        this.folderId = folderId;
        this.autoSaveInterval = null;
        this.isDirty = false;
        
        this.init();
    }
    
    init() {
        console.log('[MioBook] Initializing core...');
        
        // Initialize Sortable for drag-and-drop
        this.initializeSortable();
        
        // Setup auto-save
        this.setupAutoSave();
        
        // Setup keyboard shortcuts
        this.setupKeyboardShortcuts();
        
        // Mark as initialized
        window.MioBookInitialized = true;
    }
    
    initializeSortable() {
        const contentBlocks = document.getElementById('contentBlocks');
        if (contentBlocks) {
            this.sortable = Sortable.create(contentBlocks, {
                handle: '.drag-handle',
                animation: 150,
                ghostClass: 'sortable-ghost',
                filter: '.insert-separator',  // Don't allow dragging separators
                draggable: '.block-row',       // Drag entire row (block + annotation)
                forceFallback: false,           // Use native drag for better performance
                scroll: true,                   // Enable auto-scrolling
                scrollSensitivity: 80,          // Distance from edge (in px) to trigger scroll
                scrollSpeed: 15,                // Scrolling speed
                bubbleScroll: true,             // Allow scrolling in all scrollable ancestors
                onStart: (evt) => {
                    evt.item.classList.add('dragging');
                },
                onEnd: (evt) => {
                    evt.item.classList.remove('dragging');
                    this.rebuildSeparators();
                    this.markDirty();
                }
            });
        }
    }
    
    setupAutoSave() {
        // Auto-save every 30 seconds if dirty
        this.autoSaveInterval = setInterval(() => {
            if (this.documentId && this.isDirty) {
                this.saveDocument(true); // silent save
            }
        }, 30000);
    }
    
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl+S to save
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                this.saveDocument();
            }
        });
    }
    
    markDirty() {
        this.isDirty = true;
    }
    
    async collectBlocksData() {
        const blocks = [];
        const blockRows = document.querySelectorAll('#contentBlocks .block-row');
        
        for (let i = 0; i < blockRows.length; i++) {
            const blockRow = blockRows[i];
            const blockEl = blockRow.querySelector('.block-item');
            if (!blockEl) continue;
            
            const type = blockEl.dataset.type;
            const blockId = blockEl.dataset.blockId || `block-${Date.now()}-${i}`;
            const title = blockEl.querySelector('.block-title-input')?.value || '';
            const splitRatio = parseInt(blockRow.dataset.splitRatio) || 50;
            
            let content = null;
            let metadata = {};
            
            switch (type) {
                case 'markdown':
                    content = window.MarkdownHandler?.getContent(blockEl);
                    break;
                    
                case 'todo':
                    content = window.TodoHandler?.getContent(blockEl);
                    break;
                    
                case 'code':
                    const codeData = window.CodeHandler?.getContent(blockEl);
                    content = codeData?.content;
                    metadata = codeData?.metadata || {};
                    break;
                    
                case 'blocks':
                    content = await window.EditorJSHandler?.getContent(blockEl);
                    break;
                    
                case 'whiteboard':
                    content = window.AtramentHandler?.getContent(blockEl);
                    break;
            }
            
            // Check for annotation block
            const annotationEl = blockRow.querySelector('.annotation-block');
            let annotationId = null;
            
            if (annotationEl) {
                annotationId = annotationEl.dataset.annotationId || `annotation-${Date.now()}-${i}`;
                const annotationContent = await window.AnnotationHandler?.getContent(annotationEl);
                
                // Add annotation as separate block
                blocks.push({
                    id: annotationId,
                    type: 'annotation',
                    parentId: blockId,
                    content: annotationContent
                });
            }
            
            // Default to true (visible) if not explicitly set
            const annotationShow = blockRow.dataset.annotationShow !== 'false';
            
            blocks.push({
                id: blockId,
                type: type,
                title: title,
                content: content,
                metadata: metadata,
                annotationId: annotationId,
                splitRatio: splitRatio,
                annotationShow: annotationShow
            });
        }
        
        return blocks;
    }
    
    async saveDocument(silent = false) {
        console.log('[MioBook] saveDocument called, silent:', silent, 'isDirty:', this.isDirty, 'documentId:', this.documentId);
        
        const title = document.getElementById('documentTitle')?.value?.trim();
        
        if (!title) {
            console.warn('[MioBook] No title provided');
            if (!silent) {
                alert('Please enter a document title');
            }
            return false;
        }
        
        console.log('[MioBook] Collecting blocks data...');
        const blocks = await this.collectBlocksData();
        console.log('[MioBook] Collected', blocks.length, 'blocks');
        
        const data = {
            title: title,
            content_json: JSON.stringify({
                version: '2.0',
                blocks: blocks
            })
        };
        
        const url = this.documentId ? 
            `/combined/edit/${this.documentId}` : 
            '/combined/new';
        
        console.log('[MioBook] Saving to URL:', url);
        
        try {
            console.log('[MioBook] Sending fetch request...');
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(data)
            });
            
            console.log('[MioBook] Response status:', response.status);
            const result = await response.json();
            console.log('[MioBook] Response result:', result);
            
            if (result.success) {
                console.log('[MioBook] Save successful');
                if (!this.documentId && result.document_id) {
                    this.documentId = result.document_id;
                    // Update URL without reload
                    window.history.replaceState({}, '', `/combined/edit/${this.documentId}`);
                }
                
                this.isDirty = false;
                console.log('[MioBook] isDirty set to false');
                
                if (!silent) {
                    this.showSaveSuccess();
                }
                
                return true;
            } else {
                console.error('[MioBook] Save failed:', result.error);
                if (!silent) {
                    alert('Failed to save: ' + (result.error || 'Unknown error'));
                }
                return false;
            }
        } catch (error) {
            console.error('[MioBook] Save error:', error);
            if (!silent) {
                alert('Failed to save document. Please try again.');
            }
            return false;
        }
    }
    
    showSaveSuccess() {
        const saveBtn = document.querySelector('.save-document-btn');
        if (saveBtn) {
            const originalHTML = saveBtn.innerHTML;
            saveBtn.innerHTML = '<i class="fas fa-check"></i> Saved!';
            saveBtn.classList.add('bg-teal-600');
            
            setTimeout(() => {
                saveBtn.innerHTML = originalHTML;
                saveBtn.classList.remove('bg-teal-600');
            }, 2000);
        }
    }
    
    async addBlock(type, position = null, referenceBlockId = null) {
        const container = document.getElementById('contentBlocks');
        if (!container) return;
        
        const blockId = `block-${Date.now()}`;
        let blockHTML = '';
        
        switch (type) {
            case 'markdown':
                blockHTML = this.createMarkdownBlockHTML(blockId);
                break;
            case 'todo':
                blockHTML = this.createTodoBlockHTML(blockId);
                break;
            case 'code':
                blockHTML = this.createCodeBlockHTML(blockId);
                break;
            case 'blocks':
                blockHTML = this.createEditorJSBlockHTML(blockId);
                break;
            case 'whiteboard':
                blockHTML = this.createAtramentBlockHTML(blockId);
                break;
        }
        
        // Insert based on position
        if (position && referenceBlockId) {
            const referenceBlock = document.querySelector(`[data-block-id="${referenceBlockId}"]`);
            if (referenceBlock) {
                if (position === 'before') {
                    referenceBlock.insertAdjacentHTML('beforebegin', blockHTML);
                } else if (position === 'after') {
                    referenceBlock.insertAdjacentHTML('afterend', blockHTML);
                }
            } else {
                container.insertAdjacentHTML('beforeend', blockHTML);
            }
        } else {
            // Find last separator and insert before it
            const separators = container.querySelectorAll('.insert-separator');
            const lastSeparator = separators[separators.length - 1];
            if (lastSeparator) {
                lastSeparator.insertAdjacentHTML('beforebegin', blockHTML);
            } else {
                container.insertAdjacentHTML('beforeend', blockHTML);
            }
        }
        
        // Initialize the new block - find it by blockId
        const newBlock = document.querySelector(`[data-block-id="${blockId}"]`);
        if (newBlock) {
            // Add separator after the new block
            const separatorIndex = this.getBlockIndex(newBlock) + 1;
            const separatorHTML = this.createSeparatorHTML(separatorIndex);
            newBlock.insertAdjacentHTML('afterend', separatorHTML);
            
            await this.initializeBlock(newBlock, type);
            this.updateSeparatorIndices();
        }
        
        this.markDirty();
    }
    
    async addBlockAtIndex(type, index) {
        const container = document.getElementById('contentBlocks');
        if (!container) return;
        
        const blockId = `block-${Date.now()}`;
        let blockHTML = '';
        
        switch (type) {
            case 'markdown':
                blockHTML = this.createMarkdownBlockHTML(blockId);
                break;
            case 'todo':
                blockHTML = this.createTodoBlockHTML(blockId);
                break;
            case 'code':
                blockHTML = this.createCodeBlockHTML(blockId);
                break;
            case 'blocks':
                blockHTML = this.createEditorJSBlockHTML(blockId);
                break;
            case 'whiteboard':
                blockHTML = this.createAtramentBlockHTML(blockId);
                break;
        }
        
        const separators = container.querySelectorAll('.insert-separator');
        const targetSeparator = separators[index];
        
        if (targetSeparator) {
            // Insert after the separator
            targetSeparator.insertAdjacentHTML('afterend', blockHTML);
            
            // Find the newly added block
            const newBlock = document.querySelector(`[data-block-id="${blockId}"]`);
            if (newBlock) {
                // Add separator after the new block
                const separatorHTML = this.createSeparatorHTML(index + 1);
                newBlock.insertAdjacentHTML('afterend', separatorHTML);
                
                await this.initializeBlock(newBlock, type);
                this.updateSeparatorIndices();
            }
        }
        
        this.markDirty();
    }
    
    createSeparatorHTML(index) {
        return `
            <div class="insert-separator" onclick="showInsertMenuAtSeparator(event, ${index})">
                <div class="insert-separator-line"></div>
                <div class="insert-separator-trigger">
                    <i class="fas fa-plus"></i>
                    <span>Insert Block</span>
                </div>
            </div>
        `;
    }
    
    getBlockIndex(blockEl) {
        const blocks = document.querySelectorAll('#contentBlocks .block-item');
        return Array.from(blocks).indexOf(blockEl);
    }
    
    updateSeparatorIndices() {
        const separators = document.querySelectorAll('#contentBlocks .insert-separator');
        separators.forEach((sep, idx) => {
            sep.setAttribute('onclick', `showInsertMenuAtSeparator(event, ${idx})`);
        });
    }
    
    rebuildSeparators() {
        const container = document.getElementById('contentBlocks');
        if (!container) return;
        
        // Remove all existing separators
        const oldSeparators = container.querySelectorAll('.insert-separator');
        oldSeparators.forEach(sep => sep.remove());
        
        // Get all block rows
        const blockRows = container.querySelectorAll('.block-row');
        
        // Add separator before first block row
        if (blockRows.length > 0) {
            blockRows[0].insertAdjacentHTML('beforebegin', this.createSeparatorHTML(0));
        } else {
            // No blocks, add single separator
            container.innerHTML = this.createSeparatorHTML(0);
            return;
        }
        
        // Add separator after each block row
        blockRows.forEach((blockRow, index) => {
            blockRow.insertAdjacentHTML('afterend', this.createSeparatorHTML(index + 1));
        });
    }
    
    async initializeBlock(blockEl, type) {
        console.log(`[MioBook] Initializing ${type} block ${blockEl.dataset.blockId}`);
        switch (type) {
            case 'markdown':
                await window.MarkdownHandler?.initialize(blockEl);
                break;
            case 'todo':
                await window.TodoHandler?.initialize(blockEl);
                break;
            case 'code':
                await window.CodeHandler?.initialize(blockEl);
                break;
            case 'blocks':
                await window.EditorJSHandler?.initialize(blockEl);
                break;
            case 'whiteboard':
                console.log('[MioBook] About to call AtramentHandler.initialize, handler exists:', !!window.AtramentHandler);
                await window.AtramentHandler?.initialize(blockEl);
                console.log('[MioBook] AtramentHandler.initialize returned');
                break;
        }
    }
    
    createMarkdownBlockHTML(blockId) {
        return `
            <div class="block-row" data-block-id="${blockId}" data-split-ratio="50">
                <div class="main-block-column">
                    <div class="block-item" data-type="markdown" data-block-id="${blockId}">
                        <div class="block-header">
                            <div class="drag-handle" title="Drag to reorder">
                                <i class="fas fa-grip-vertical"></i>
                            </div>
                            <div class="flex items-center gap-2">
                                <i class="fas fa-markdown text-teal-400"></i>
                                <span class="block-type-label">Markdown</span>
                            </div>
                            <input type="text" class="block-title-input" placeholder="Block Title" value="">
                            <div class="block-controls">
                                <button type="button" class="control-btn" onclick="window.MioBook.addAnnotation(this)" title="Add Annotation">
                                    <i class="fas fa-comment-alt"></i>
                                </button>
                                <button type="button" class="control-btn" onclick="window.MioBook.moveBlockUp(this)" title="Move Up">
                                    <i class="fas fa-chevron-up"></i>
                                </button>
                                <button type="button" class="control-btn" onclick="window.MioBook.moveBlockDown(this)" title="Move Down">
                                    <i class="fas fa-chevron-down"></i>
                                </button>
                                <button type="button" class="control-btn" onclick="window.MioBook.deleteBlock(this)" title="Delete">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </div>
                        <div class="block-content">
                            <div class="markdown-editor-wrapper">
                                <div class="markdown-editor" data-content=""></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    createTodoBlockHTML(blockId) {
        return `
            <div class="block-row" data-block-id="${blockId}" data-split-ratio="50">
                <div class="main-block-column">
                    <div class="block-item" data-type="todo" data-block-id="${blockId}">
                        <div class="block-header">
                            <div class="drag-handle" title="Drag to reorder">
                                <i class="fas fa-grip-vertical"></i>
                            </div>
                            <div class="flex items-center gap-2">
                                <i class="fas fa-tasks text-dirty-yellow-400"></i>
                                <span class="block-type-label">Todo List</span>
                            </div>
                            <input type="text" class="block-title-input" placeholder="Block Title" value="">
                            <div class="block-controls">
                                <button type="button" class="control-btn" onclick="window.MioBook.addAnnotation(this)" title="Add Annotation">
                                    <i class="fas fa-comment-alt"></i>
                                </button>
                                <button type="button" class="control-btn" onclick="window.MioBook.moveBlockUp(this)" title="Move Up">
                                    <i class="fas fa-chevron-up"></i>
                                </button>
                                <button type="button" class="control-btn" onclick="window.MioBook.moveBlockDown(this)" title="Move Down">
                                    <i class="fas fa-chevron-down"></i>
                                </button>
                                <button type="button" class="control-btn" onclick="window.MioBook.deleteBlock(this)" title="Delete">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </div>
                        <div class="block-content">
                            <div class="todo-list-wrapper">
                                <div class="todo-list" data-content="[]"></div>
                                <button type="button" class="add-todo-btn" onclick="window.TodoHandler.addItem(this)">
                                    <i class="fas fa-plus"></i> Add Task
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    createCodeBlockHTML(blockId) {
        return `
            <div class="block-row" data-block-id="${blockId}" data-split-ratio="50">
                <div class="main-block-column">
                    <div class="block-item" data-type="code" data-block-id="${blockId}">
                        <div class="block-header">
                            <div class="drag-handle" title="Drag to reorder">
                                <i class="fas fa-grip-vertical"></i>
                            </div>
                            <div class="flex items-center gap-2">
                                <i class="fas fa-code text-teal-400"></i>
                                <span class="block-type-label">Code</span>
                                <select class="language-selector" onchange="window.CodeHandler.changeLanguage(this)">
                                    <option value="python">Python</option>
                                    <option value="javascript">JavaScript</option>
                                    <option value="typescript">TypeScript</option>
                                    <option value="html">HTML</option>
                                    <option value="css">CSS</option>
                                    <option value="json">JSON</option>
                                    <option value="sql">SQL</option>
                                    <option value="markdown">Markdown</option>
                                    <option value="yaml">YAML</option>
                                    <option value="bash">Bash</option>
                                </select>
                            </div>
                            <input type="text" class="block-title-input" placeholder="Block Title" value="">
                            <div class="block-controls">
                                <button type="button" class="control-btn" onclick="window.MioBook.addAnnotation(this)" title="Add Annotation">
                                    <i class="fas fa-comment-alt"></i>
                                </button>
                                <button type="button" class="control-btn" onclick="window.MioBook.moveBlockUp(this)" title="Move Up">
                                    <i class="fas fa-chevron-up"></i>
                                </button>
                                <button type="button" class="control-btn" onclick="window.MioBook.moveBlockDown(this)" title="Move Down">
                                    <i class="fas fa-chevron-down"></i>
                                </button>
                                <button type="button" class="control-btn" onclick="window.MioBook.deleteBlock(this)" title="Delete">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </div>
                        <div class="block-content">
                            <div class="code-editor-wrapper">
                                <div class="monaco-editor" data-language="python" data-content=""></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    createEditorJSBlockHTML(blockId) {
        return `
            <div class="block-row" data-block-id="${blockId}" data-split-ratio="50">
                <div class="main-block-column">
                    <div class="block-item" data-type="blocks" data-block-id="${blockId}">
                        <div class="block-header">
                            <div class="drag-handle" title="Drag to reorder">
                                <i class="fas fa-grip-vertical"></i>
                            </div>
                            <div class="flex items-center gap-2">
                                <i class="fas fa-th-large text-dirty-yellow-400"></i>
                                <span class="block-type-label">Rich Blocks</span>
                            </div>
                            <input type="text" class="block-title-input" placeholder="Block Title" value="">
                            <div class="block-controls">
                                <button type="button" class="control-btn" onclick="window.MioBook.addAnnotation(this)" title="Add Annotation">
                                    <i class="fas fa-comment-alt"></i>
                                </button>
                                <button type="button" class="control-btn" onclick="window.MioBook.moveBlockUp(this)" title="Move Up">
                                    <i class="fas fa-chevron-up"></i>
                                </button>
                                <button type="button" class="control-btn" onclick="window.MioBook.moveBlockDown(this)" title="Move Down">
                                    <i class="fas fa-chevron-down"></i>
                                </button>
                                <button type="button" class="control-btn" onclick="window.MioBook.deleteBlock(this)" title="Delete">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </div>
                        <div class="block-content">
                            <div class="editorjs-wrapper">
                                <div class="editorjs-editor" data-content=""></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    createAtramentBlockHTML(blockId) {
        return `
            <div class="block-row" data-block-id="${blockId}" data-split-ratio="50">
                <div class="main-block-column">
                    <div class="block-item" data-type="whiteboard" data-block-id="${blockId}">
                        <div class="block-header">
                            <div class="drag-handle" title="Drag to reorder">
                                <i class="fas fa-grip-vertical"></i>
                            </div>
                            <div class="flex items-center gap-2">
                                <i class="fas fa-draw-polygon text-dirty-yellow-400"></i>
                                <span class="block-type-label">Whiteboard</span>
                            </div>
                            <input type="text" class="block-title-input" placeholder="Block Title" value="">
                            <div class="block-controls">
                                <button type="button" class="atrament-edit-btn control-btn" title="Edit (enable drawing)">
                                    <i class="fas fa-pen"></i>
                                </button>
                                <button type="button" class="control-btn" onclick="window.MioBook.addAnnotation(this)" title="Add Annotation">
                                    <i class="fas fa-comment-alt"></i>
                                </button>
                                <button type="button" class="control-btn" onclick="window.MioBook.moveBlockUp(this)" title="Move Up">
                                    <i class="fas fa-chevron-up"></i>
                                </button>
                                <button type="button" class="control-btn" onclick="window.MioBook.moveBlockDown(this)" title="Move Down">
                                    <i class="fas fa-chevron-down"></i>
                                </button>
                                <button type="button" class="control-btn" onclick="window.MioBook.deleteBlock(this)" title="Delete">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </div>
                        <div class="block-content">
                            <div class="atrament-toolbar" style="display: none; gap: 12px; align-items: center; padding: 12px; background: #0d0e10; border: 1px solid #2a2c31; border-radius: 6px 6px 0 0; border-bottom: none;">
                                <button type="button" class="atrament-mode-btn atrament-draw active">
                                    <i class="fas fa-pen"></i> Draw
                                </button>
                                <button type="button" class="atrament-mode-btn atrament-erase">
                                    <i class="fas fa-eraser"></i> Erase
                                </button>
                                <div style="border-left: 1px solid #3d4047; height: 24px;"></div>
                                <label style="display: flex; align-items: center; gap: 6px; color: #c3c6cb; font-size: 12px;">
                                    Color:
                                    <input type="color" class="atrament-color" value="#14b8a6" style="width: 32px; height: 24px; border: 1px solid #3d4047; border-radius: 4px; cursor: pointer;">
                                </label>
                                <label style="display: flex; align-items: center; gap: 6px; color: #c3c6cb; font-size: 12px;">
                                    Size:
                                    <input type="range" class="atrament-size" min="1" max="20" value="2" style="width: 100px;">
                                </label>
                                <button type="button" class="atrament-action-btn atrament-attach" title="Attach image">
                                    <i class="fas fa-paperclip"></i> Image
                                </button>
                                <input type="file" class="atrament-image-input" accept="image/*" style="display:none">
                                <div style="flex: 1;"></div>
                                <button type="button" class="atrament-clear" style="padding: 6px 12px; background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); color: #ef4444; border-radius: 4px; cursor: pointer; font-size: 12px;">
                                    <i class="fas fa-trash"></i> Clear
                                </button>
                            </div>
                            <div style="border: 1px solid #2a2c31; border-radius: 6px; overflow: hidden; background: #0d0e10;">
                                <canvas class="atrament-canvas" 
                                        style="display: block; cursor: default; touch-action: none;"
                                        data-content=""></canvas>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    moveBlockUp(button) {
        const blockRow = button.closest('.block-row');
        const blockRows = Array.from(document.querySelectorAll('#contentBlocks .block-row'));
        const currentIndex = blockRows.indexOf(blockRow);
        
        if (currentIndex > 0) {
            const prevBlockRow = blockRows[currentIndex - 1];
            
            // Move current row before the previous row
            prevBlockRow.insertAdjacentElement('beforebegin', blockRow);
            
            this.rebuildSeparators();
            this.markDirty();
            
            // Scroll to keep block in view
            blockRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }
    
    moveBlockDown(button) {
        const blockRow = button.closest('.block-row');
        const blockRows = Array.from(document.querySelectorAll('#contentBlocks .block-row'));
        const currentIndex = blockRows.indexOf(blockRow);
        
        if (currentIndex < blockRows.length - 1) {
            const nextBlockRow = blockRows[currentIndex + 1];
            
            // Move current row after the next row
            nextBlockRow.insertAdjacentElement('afterend', blockRow);
            
            this.rebuildSeparators();
            this.markDirty();
            
            // Scroll to keep block in view
            blockRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }
    
    deleteBlock(button) {
        if (confirm('Are you sure you want to delete this block?')) {
            const blockRow = button.closest('.block-row');
            const block = blockRow?.querySelector('.block-item');
            if (!block) return;
            
            const type = block.dataset.type;
            
            // Cleanup before removal
            switch (type) {
                case 'code':
                    window.CodeHandler?.destroy(block);
                    break;
                case 'blocks':
                    window.EditorJSHandler?.destroy(block);
                    break;
                case 'whiteboard':
                    window.AtramentHandler?.destroy(block);
                    break;
            }
            
            // Cleanup annotation if exists
            const annotationEl = blockRow.querySelector('.annotation-block');
            if (annotationEl) {
                window.AnnotationHandler?.destroy(annotationEl);
            }
            
            // Remove the entire row
            blockRow.remove();
            
            // Rebuild all separators to maintain proper structure
            this.rebuildSeparators();
            this.markDirty();
        }
    }
    
    goBack() {
        if (this.folderId) {
            window.location.href = `/folders/${this.folderId}`;
        } else {
            window.location.href = '/p2/';
        }
    }
    
    addAnnotation(button) {
        const blockRow = button.closest('.block-row');
        if (!blockRow) return;
        
        // Check if annotation already exists
        if (blockRow.querySelector('.annotation-column')) {
            return;
        }
        
        const blockId = blockRow.dataset.blockId;
        const annotationId = `annotation-${Date.now()}`;
        const splitRatio = parseInt(blockRow.dataset.splitRatio) || 50;
        
        // Calculate widths based on split ratio
        const mainWidth = `${splitRatio}%`;
        const annotationWidth = `${100 - splitRatio}%`;
        
        const annotationHTML = `
            <div class="resize-handle" onmousedown="window.MioBook.startResize(event, this)"></div>
            <div class="annotation-column" style="width: ${annotationWidth}">
                <div class="annotation-block" data-annotation-id="${annotationId}" data-parent-id="${blockId}">
                    <div class="annotation-header">
                        <div class="flex items-center gap-2 flex-1">
                            <i class="fas fa-comment-alt text-teal-400"></i>
                            <span class="block-type-label">Annotation</span>
                        </div>
                        <button type="button" class="annotation-control-btn remove" onclick="window.MioBook.deleteAnnotation(this)" title="Delete Annotation">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                    <div class="annotation-content">
                        <div class="annotation-editor" data-content=""></div>
                    </div>
                </div>
            </div>
        `;
        
        // Set main column width
        const mainColumn = blockRow.querySelector('.main-block-column');
        if (mainColumn) {
            mainColumn.style.width = mainWidth;
        }
        
        // Set annotation show state
        blockRow.dataset.annotationShow = 'true';
        
        blockRow.insertAdjacentHTML('beforeend', annotationHTML);
        
        // Initialize the annotation
        const annotationEl = blockRow.querySelector('.annotation-block');
        if (annotationEl) {
            window.AnnotationHandler?.initialize(annotationEl);
        }
        
        // Change button to toggle annotation visibility
        button.innerHTML = '<i class="fas fa-eye"></i>';
        button.setAttribute('title', 'Hide Annotation');
        button.setAttribute('onclick', 'window.MioBook.toggleAnnotation(this)');
        
        this.markDirty();
    }
    
    toggleAnnotation(button) {
        const blockRow = button.closest('.block-row');
        if (!blockRow) return;
        
        const annotationColumn = blockRow.querySelector('.annotation-column');
        if (!annotationColumn) return;
        
        const isHidden = annotationColumn.classList.contains('hidden');
        
        if (isHidden) {
            // Show annotation
            annotationColumn.classList.remove('hidden');
            blockRow.dataset.annotationShow = 'true';
            button.innerHTML = '<i class="fas fa-eye"></i>';
            button.setAttribute('title', 'Hide Annotation');
        } else {
            // Hide annotation
            annotationColumn.classList.add('hidden');
            blockRow.dataset.annotationShow = 'false';
            button.innerHTML = '<i class="fas fa-eye-slash"></i>';
            button.setAttribute('title', 'Show Annotation');
        }
        
        this.markDirty();
    }
    
    deleteAnnotation(button) {
        const blockRow = button.closest('.block-row');
        if (!blockRow) return;
        
        if (confirm('Delete annotation? This cannot be undone.')) {
            const annotationColumn = blockRow.querySelector('.annotation-column');
            const resizeHandle = blockRow.querySelector('.resize-handle');
            const mainColumn = blockRow.querySelector('.main-block-column');
            
            if (annotationColumn) {
                const annotationEl = annotationColumn.querySelector('.annotation-block');
                if (annotationEl) {
                    window.AnnotationHandler?.destroy(annotationEl);
                }
                annotationColumn.remove();
            }
            
            if (resizeHandle) {
                resizeHandle.remove();
            }
            
            // Reset main column width
            if (mainColumn) {
                mainColumn.style.width = '';
            }
            
            // Remove annotation show state
            delete blockRow.dataset.annotationShow;
            
            // Change button back to add annotation
            const addBtn = blockRow.querySelector('.block-controls .control-btn[onclick*="Annotation"]');
            if (addBtn) {
                addBtn.innerHTML = '<i class="fas fa-comment-alt"></i>';
                addBtn.setAttribute('title', 'Add Annotation');
                addBtn.setAttribute('onclick', 'window.MioBook.addAnnotation(this)');
            }
            
            this.markDirty();
        }
    }

    updateAllResizeHandles() {
        const blockRows = document.querySelectorAll('.block-row');
        blockRows.forEach((row) => this.positionResizeHandle(row));
    }

    positionResizeHandle(blockRow) {
        if (!blockRow) return;
        const handle = blockRow.querySelector('.resize-handle');
        const mainColumn = blockRow.querySelector('.main-block-column');
        const containerWidth = blockRow.offsetWidth;
        if (!handle || !mainColumn || !containerWidth) return;

        const mainPercentage = (mainColumn.offsetWidth / containerWidth) * 100;
        handle.style.left = `${mainPercentage}%`;
    }
    
    startResize(event, handle) {
        event.preventDefault();
        const blockRow = handle.closest('.block-row');
        if (!blockRow) return;
        
        const mainColumn = blockRow.querySelector('.main-block-column');
        const annotationColumn = blockRow.querySelector('.annotation-column');
        if (!mainColumn || !annotationColumn) return;
        
        const startX = event.clientX;
        const containerWidth = blockRow.offsetWidth;
        const startMainWidth = mainColumn.offsetWidth;
        const startAnnotationWidth = annotationColumn.offsetWidth;

        // Position the handle at the current split before dragging
        handle.style.left = `${(startMainWidth / containerWidth) * 100}%`;
        
        const onMouseMove = (e) => {
            const deltaX = e.clientX - startX;
            const newMainWidth = Math.max(200, Math.min(containerWidth - 200, startMainWidth + deltaX));
            const newAnnotationWidth = containerWidth - newMainWidth - 16; // 16px gap
            
            const mainPercentage = (newMainWidth / containerWidth) * 100;
            const annotationPercentage = (newAnnotationWidth / containerWidth) * 100;
            
            mainColumn.style.width = `${mainPercentage}%`;
            annotationColumn.style.width = `${annotationPercentage}%`;

            handle.style.left = `${mainPercentage}%`;
            
            // Store the split ratio
            blockRow.dataset.splitRatio = Math.round(mainPercentage);
        };
        
        const onMouseUp = () => {
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            this.markDirty();
        };
        
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    }
    
    destroy() {
        if (this.autoSaveInterval) {
            clearInterval(this.autoSaveInterval);
        }
        if (this.sortable) {
            this.sortable.destroy();
        }
    }
}

// Export to window
window.MioBookCore = MioBookCore;
