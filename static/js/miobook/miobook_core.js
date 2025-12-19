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
                draggable: '.block-item',      // Only allow dragging block items
                forceFallback: false,           // Use native drag for better performance
                scroll: true,                   // Enable auto-scrolling
                scrollSensitivity: 80,          // Distance from edge (in px) to trigger scroll
                scrollSpeed: 15,                // Scrolling speed
                bubbleScroll: true,             // Allow scrolling in all scrollable ancestors
                onEnd: () => {
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
        const blockElements = document.querySelectorAll('#contentBlocks .block-item');
        
        for (let i = 0; i < blockElements.length; i++) {
            const blockEl = blockElements[i];
            const type = blockEl.dataset.type;
            const blockId = blockEl.dataset.blockId || `block-${Date.now()}-${i}`;
            const title = blockEl.querySelector('.block-title-input')?.value || '';
            
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
            
            blocks.push({
                id: blockId,
                type: type,
                title: title,
                content: content,
                metadata: metadata
            });
        }
        
        return blocks;
    }
    
    async saveDocument(silent = false) {
        const title = document.getElementById('documentTitle')?.value?.trim();
        
        if (!title) {
            if (!silent) {
                alert('Please enter a document title');
            }
            return false;
        }
        
        const blocks = await this.collectBlocksData();
        
        const data = {
            title: title,
            content_json: JSON.stringify({
                version: '1.0',
                blocks: blocks
            })
        };
        
        const url = this.documentId ? 
            `/combined/edit/${this.documentId}` : 
            '/combined/new';
        
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            
            if (result.success) {
                if (!this.documentId && result.document_id) {
                    this.documentId = result.document_id;
                    // Update URL without reload
                    window.history.replaceState({}, '', `/combined/edit/${this.documentId}`);
                }
                
                this.isDirty = false;
                
                if (!silent) {
                    this.showSaveSuccess();
                }
                
                return true;
            } else {
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
        
        // Get all blocks
        const blocks = container.querySelectorAll('.block-item');
        
        // Add separator before first block
        if (blocks.length > 0) {
            blocks[0].insertAdjacentHTML('beforebegin', this.createSeparatorHTML(0));
        } else {
            // No blocks, add single separator
            container.innerHTML = this.createSeparatorHTML(0);
            return;
        }
        
        // Add separator after each block
        blocks.forEach((block, index) => {
            block.insertAdjacentHTML('afterend', this.createSeparatorHTML(index + 1));
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
            <div class="block-item" data-type="markdown" data-block-id="${blockId}">
                <div class="block-header">
                    <div class="flex items-center gap-2">
                        <i class="fas fa-markdown text-teal-400"></i>
                        <span class="block-type-label">Markdown</span>
                    </div>
                    <div class="block-controls">
                        <button type="button" class="control-btn" onclick="window.MioBook.moveBlockUp(this)" title="Move Up">
                            <i class="fas fa-chevron-up"></i>
                        </button>
                        <button type="button" class="control-btn" onclick="window.MioBook.moveBlockDown(this)" title="Move Down">
                            <i class="fas fa-chevron-down"></i>
                        </button>
                        <button type="button" class="control-btn" onclick="window.MioBook.deleteBlock(this)" title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>
                        <div class="drag-handle" title="Drag to reorder">
                            <i class="fas fa-grip-vertical"></i>
                        </div>
                    </div>
                </div>
                <div class="block-content">
                    <input type="text" class="block-title-input" placeholder="Block Title" value="">
                    <div class="markdown-editor-wrapper">
                        <div class="markdown-editor" data-content=""></div>
                    </div>
                </div>
            </div>
        `;
    }
    
    createTodoBlockHTML(blockId) {
        return `
            <div class="block-item" data-type="todo" data-block-id="${blockId}">
                <div class="block-header">
                    <div class="flex items-center gap-2">
                        <i class="fas fa-tasks text-yellow-400"></i>
                        <span class="block-type-label">Todo List</span>
                    </div>
                    <div class="block-controls">
                        <button type="button" class="control-btn" onclick="window.MioBook.moveBlockUp(this)" title="Move Up">
                            <i class="fas fa-chevron-up"></i>
                        </button>
                        <button type="button" class="control-btn" onclick="window.MioBook.moveBlockDown(this)" title="Move Down">
                            <i class="fas fa-chevron-down"></i>
                        </button>
                        <button type="button" class="control-btn" onclick="window.MioBook.deleteBlock(this)" title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>
                        <div class="drag-handle" title="Drag to reorder">
                            <i class="fas fa-grip-vertical"></i>
                        </div>
                    </div>
                </div>
                <div class="block-content">
                    <input type="text" class="block-title-input" placeholder="Block Title" value="">
                    <div class="todo-list-wrapper">
                        <div class="todo-list" data-content="[]"></div>
                        <button type="button" class="add-todo-btn" onclick="window.TodoHandler.addItem(this)">
                            <i class="fas fa-plus"></i> Add Task
                        </button>
                    </div>
                </div>
            </div>
        `;
    }
    
    createCodeBlockHTML(blockId) {
        return `
            <div class="block-item" data-type="code" data-block-id="${blockId}">
                <div class="block-header">
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
                    <div class="block-controls">
                        <button type="button" class="control-btn" onclick="window.MioBook.moveBlockUp(this)" title="Move Up">
                            <i class="fas fa-chevron-up"></i>
                        </button>
                        <button type="button" class="control-btn" onclick="window.MioBook.moveBlockDown(this)" title="Move Down">
                            <i class="fas fa-chevron-down"></i>
                        </button>
                        <button type="button" class="control-btn" onclick="window.MioBook.deleteBlock(this)" title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>
                        <div class="drag-handle" title="Drag to reorder">
                            <i class="fas fa-grip-vertical"></i>
                        </div>
                    </div>
                </div>
                <div class="block-content">
                    <input type="text" class="block-title-input" placeholder="Block Title" value="">
                    <div class="code-editor-wrapper">
                        <div class="monaco-editor" data-language="python" data-content=""></div>
                    </div>
                </div>
            </div>
        `;
    }
    
    createEditorJSBlockHTML(blockId) {
        return `
            <div class="block-item" data-type="blocks" data-block-id="${blockId}">
                <div class="block-header">
                    <div class="flex items-center gap-2">
                        <i class="fas fa-th-large text-yellow-400"></i>
                        <span class="block-type-label">Rich Blocks</span>
                    </div>
                    <div class="block-controls">
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
        `;
    }
    
    createAtramentBlockHTML(blockId) {
        return `
            <div class="block-item" data-type="whiteboard" data-block-id="${blockId}">
                <div class="block-header">
                    <div class="drag-handle" title="Drag to reorder">
                        <i class="fas fa-grip-vertical"></i>
                    </div>
                    <button type="button" class="collapse-toggle-btn" onclick="toggleBlockCollapse(this)" title="Collapse/Expand">
                        <i class="fas fa-chevron-down"></i>
                    </button>
                    <div class="flex items-center gap-2">
                        <i class="fas fa-draw-polygon text-dirty-yellow-400"></i>
                        <span class="block-type-label">Whiteboard</span>
                    </div>
                    <input type="text" class="block-title-input" placeholder="Block Title" value="">
                    <div class="block-controls">
                        <button type="button" class="atrament-edit-btn control-btn" title="Edit (enable drawing)">
                            <i class="fas fa-pen"></i>
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
                        <button type="button" class="atrament-draw active" style="padding: 6px 12px; background: rgba(20, 184, 166, 0.2); border: 1px solid #14b8a6; color: #14b8a6; border-radius: 4px; cursor: pointer; font-size: 12px;">
                            <i class="fas fa-pen"></i> Draw
                        </button>
                        <button type="button" class="atrament-erase" style="padding: 6px 12px; background: transparent; border: 1px solid #3d4047; color: #7a7f8a; border-radius: 4px; cursor: pointer; font-size: 12px;">
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
        `;
    }
    
    moveBlockUp(button) {
        const block = button.closest('.block-item');
        const blocks = Array.from(document.querySelectorAll('#contentBlocks .block-item'));
        const currentIndex = blocks.indexOf(block);
        
        if (currentIndex > 0) {
            const prevBlock = blocks[currentIndex - 1];
            
            // Move current block before the previous block
            prevBlock.insertAdjacentElement('beforebegin', block);
            
            this.rebuildSeparators();
            this.markDirty();
            
            // Scroll to keep block in view
            block.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }
    
    moveBlockDown(button) {
        const block = button.closest('.block-item');
        const blocks = Array.from(document.querySelectorAll('#contentBlocks .block-item'));
        const currentIndex = blocks.indexOf(block);
        
        if (currentIndex < blocks.length - 1) {
            const nextBlock = blocks[currentIndex + 1];
            
            // Move current block after the next block
            nextBlock.insertAdjacentElement('afterend', block);
            
            this.rebuildSeparators();
            this.markDirty();
            
            // Scroll to keep block in view
            block.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }
    
    deleteBlock(button) {
        if (confirm('Are you sure you want to delete this block?')) {
            const block = button.closest('.block-item');
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
            
            // Remove the block
            block.remove();
            
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
