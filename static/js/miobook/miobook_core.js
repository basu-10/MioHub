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
        this.lastActiveBlockRow = null;
        this.activeAnnotationMenu = null;
        this.activeAnnotationMenuRow = null;
        this.menuOutsideHandler = null;
        this.menuKeydownHandler = null;

        this.heightMultipliers = [1, 2, 2.5, 3];
        this.baseBlockHeight = 500;
        
        this.init();
    }
    
    init() {
        console.log('[MioBook] Initializing core...');
        
        // Initialize Sortable for drag-and-drop
        this.initializeSortable();

        // Track active block focus
        this.setupActiveBlockTracking();
        
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
                return;
            }

            // Ctrl+Shift+A to add annotation to active block
            if (e.ctrlKey && e.shiftKey && (e.key === 'A' || e.key === 'a')) {
                e.preventDefault();
                this.handleAddAnnotationShortcut();
                return;
            }

            // Ctrl+Shift+H to toggle annotations visibility for active block
            if (e.ctrlKey && e.shiftKey && (e.key === 'H' || e.key === 'h')) {
                e.preventDefault();
                this.handleToggleAnnotationShortcut();
                return;
            }

            // Escape closes annotation menu
            if (e.key === 'Escape' && this.activeAnnotationMenu) {
                this.closeAnnotationMenu();
            }
        });
    }

    setupActiveBlockTracking() {
        const container = document.getElementById('contentBlocks');
        if (!container) return;

        const trackRow = (el) => {
            const row = el?.closest?.('.block-row');
            if (row) {
                this.lastActiveBlockRow = row;
            }
        };

        container.addEventListener('focusin', (e) => trackRow(e.target));
        container.addEventListener('mousedown', (e) => trackRow(e.target));
    }

    getActiveBlockRow() {
        if (this.lastActiveBlockRow?.isConnected) return this.lastActiveBlockRow;
        return document.querySelector('.block-row');
    }

    handleAddAnnotationShortcut() {
        const row = this.getActiveBlockRow();
        if (!row) return;
        const button = row.querySelector('.annotation-add-btn') || row.querySelector('.block-controls .control-btn');

        if (button?.classList.contains('annotation-add-btn')) {
            button.focus();
            this.openAnnotationMenu(button);
        } else {
            this.addAnnotationForRow(row);
        }
    }

    handleToggleAnnotationShortcut() {
        const row = this.getActiveBlockRow();
        if (!row) return;
        const toggleBtn = row.querySelector('.block-controls .control-btn[onclick*="Annotation"]');
        if (toggleBtn && toggleBtn.getAttribute('onclick')?.includes('toggle')) {
            this.toggleAnnotation(toggleBtn);
        } else if (row.querySelector('.annotation-card')) {
            const fallbackBtn = toggleBtn || row.querySelector('.annotation-add-btn');
            if (fallbackBtn) {
                this.toggleAnnotation(fallbackBtn);
            }
        } else {
            this.showToast('No annotations to toggle on this block.', 'warn');
        }
    }
    
    markDirty() {
        this.isDirty = true;
    }
    
    async collectBlocksData() {
        const blocks = [];
        const blockRows = document.querySelectorAll('#contentBlocks .block-row');

        for (let i = 0; i < blockRows.length; i++) {
            const blockRow = blockRows[i];
            const blockEl = blockRow.querySelector('.main-block-column .block-item');
            if (!blockEl) continue;

            const mainBlock = await this.extractBlockData(blockEl);
            if (!mainBlock) continue;

            mainBlock.order = i;
            mainBlock.splitRatio = parseInt(blockRow.dataset.splitRatio, 10) || 50;
            mainBlock.heightMode = blockRow.dataset.heightMode || 'fixed';
            mainBlock.heightMultiplier = parseFloat(blockRow.dataset.heightMultiplier || '1');
            const baseHeight = parseFloat(blockRow.dataset.baseHeight || '');
            if (!Number.isNaN(baseHeight)) {
                mainBlock.baseHeight = baseHeight;
            }
            const heightIndex = parseInt(blockRow.dataset.heightIndex || '', 10);
            if (!Number.isNaN(heightIndex)) {
                mainBlock.heightIndex = heightIndex;
            }
            mainBlock.collapsed = blockEl.dataset.collapsed === 'true';

            const annotations = [];
            const annotationItems = blockRow.querySelectorAll('.annotation-column .block-item');
            annotationItems.forEach((annotationEl, idx) => {
                annotations.push({
                    ...this.extractBlockShell(annotationEl),
                    order: idx,
                    collapsed: annotationEl.dataset.collapsed === 'true'
                });
            });

            // Resolve annotation content asynchronously where needed
            for (let j = 0; j < annotations.length; j++) {
                const annotationEl = annotationItems[j];
                annotations[j] = await this.extractBlockData(annotationEl, annotations[j]);
                annotations[j].parentId = mainBlock.id;
            }

            if (annotations.length) {
                mainBlock.annotations = annotations;
                mainBlock.annotationShow = blockRow.dataset.annotationShow !== 'false';
            }

            blocks.push(mainBlock);
        }

        return blocks;
    }
    
    async saveDocument(silent = false) {
        console.log('[MioBook] ==================== SAVE STARTED ====================');
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
        console.log('[MioBook] Block details:', blocks.map(b => ({ id: b.id, type: b.type, contentLength: JSON.stringify(b.content).length })));
        
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

    extractBlockShell(blockEl) {
        if (!blockEl) return null;
        return {
            id: blockEl.dataset.blockId || `block-${Date.now()}`,
            type: blockEl.dataset.type || 'markdown',
            title: blockEl.querySelector('.block-title-input')?.value || '',
            metadata: {}
        };
    }

    async extractBlockData(blockEl, baseData = null) {
        if (!blockEl) return null;
        const data = baseData ? { ...baseData } : this.extractBlockShell(blockEl);

        let content = null;
        let metadata = data.metadata || {};

        switch (data.type) {
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
                content = await window.KonvaHandler?.getContent(blockEl);
                break;
            case 'annotation':
                content = await window.AnnotationHandler?.getContent(blockEl.closest('.annotation-card') || blockEl);
                break;
            default:
                content = null;
        }

        return {
            ...data,
            content,
            metadata
        };
    }

    escapeAttribute(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;');
    }

    serializeContent(content) {
        try {
            return this.escapeAttribute(JSON.stringify(content ?? ''));
        } catch (e) {
            console.warn('[MioBook] Failed to serialize content', e);
            return '';
        }
    }

    createDefaultBlockData(type, id = null) {
        const blockId = id || `${type}-${Date.now()}`;
        const metadata = type === 'code' ? { language: 'python' } : {};
        const defaultContent = {
            markdown: '',
            todo: [],
            code: '',
            blocks: { blocks: [] },
            whiteboard: { version: 'konva-v1', stageJSON: null },
            annotation: { blocks: [] }
        };

        return {
            id: blockId,
            type,
            title: '',
            content: defaultContent[type] ?? '',
            metadata,
            annotations: [],
            splitRatio: 50,
            annotationShow: true,
            heightMode: 'fixed',
            heightMultiplier: 1
        };
    }

    getBlockIcon(type) {
        const map = {
            markdown: { icon: 'fa-markdown', color: 'text-teal-400', label: 'Markdown' },
            todo: { icon: 'fa-tasks', color: 'text-dirty-yellow-400', label: 'Todo List' },
            code: { icon: 'fa-code', color: 'text-teal-400', label: 'Code' },
            blocks: { icon: 'fa-th-large', color: 'text-dirty-yellow-400', label: 'Rich Blocks' },
            whiteboard: { icon: 'fa-draw-polygon', color: 'text-dirty-yellow-400', label: 'Whiteboard' },
            annotation: { icon: 'fa-comment-alt', color: 'text-teal-400', label: 'Annotation' }
        };
        return map[type] || { icon: 'fa-sticky-note', color: 'text-graphite-400', label: 'Block' };
    }

    renderBlock(blockData, { containerType = 'main', hasAnnotations = false, parentId = null } = {}) {
        const { icon, color, label } = this.getBlockIcon(blockData.type);
        const blockId = blockData.id;
        const title = blockData.title || '';
        const contentAttr = this.serializeContent(blockData.content);
        const language = blockData.metadata?.language || 'python';
        const isCollapsed = blockData.collapsed === true;
        const collapsedClass = isCollapsed ? ' collapsed' : '';
        const collapsedAttr = isCollapsed ? ' data-collapsed="true"' : ' data-collapsed="false"';
        const annotationCount = Array.isArray(blockData.annotations) ? blockData.annotations.length : 0;

        const renderControls = () => {
            if (containerType === 'main') {
                const heightMultiplier = parseFloat(blockData.heightMultiplier || 1) || 1;
                const heightToggle = blockData.type !== 'whiteboard'
                    ? `<button type="button" class="control-btn hover-reveal height-toggle-btn" onclick="window.MioBook.toggleBlockHeight(this)" title="Cycle height (current: ${heightMultiplier}x)">
                            <i class="fas fa-ruler-vertical"></i>
                       </button>`
                    : '';

                const visibilityChip = `<button type="button" class="annotation-visibility-chip${hasAnnotations ? '' : ' hidden'}" onclick="window.MioBook.toggleAnnotation(this)" title="${blockData.annotationShow === false ? 'Show Annotations' : 'Hide Annotations'}">
                            <i class="fas ${blockData.annotationShow === false ? 'fa-eye-slash' : 'fa-eye'}"></i>
                            <span class="annotation-count" aria-label="Annotation count" data-annotation-count="${annotationCount}">${annotationCount}</span>
                        </button>`;

                const addAnnotationBtn = `<button type="button" class="control-btn add-annotation-btn${hasAnnotations ? ' hidden' : ''}" onclick="window.MioBook.addAnnotation(this)" title="Add Annotation">
                            <i class="fas fa-comment-alt"></i>
                       </button>`;

                const whiteboardEdit = containerType === 'main' && blockData.type === 'whiteboard'
                    ? `<button type="button" class="konva-edit-btn control-btn" title="Edit (enable drawing)">
                            <i class="fas fa-pen"></i>
                       </button>`
                    : '';

                return `${heightToggle}${visibilityChip}${addAnnotationBtn}${whiteboardEdit}
                        <button type="button" class="control-btn" onclick="window.MioBook.moveBlockUp(this)" title="Move Up">
                            <i class="fas fa-chevron-up"></i>
                        </button>
                        <button type="button" class="control-btn" onclick="window.MioBook.moveBlockDown(this)" title="Move Down">
                            <i class="fas fa-chevron-down"></i>
                        </button>
                        <button type="button" class="control-btn" onclick="window.MioBook.deleteBlock(this)" title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>`;
            }

            return `<button type="button" class="control-btn" onclick="window.MioBook.deleteAnnotationBlock(this)" title="Delete Annotation">
                        <i class="fas fa-trash"></i>
                    </button>`;
        };

        let contentHTML = '';
        switch (blockData.type) {
            case 'markdown':
                contentHTML = `<div class="markdown-editor-wrapper"><div class="markdown-editor" data-content="${contentAttr}"></div></div>`;
                break;
            case 'todo':
                contentHTML = `<div class="todo-list-wrapper">
                        <div class="todo-list" data-content="${contentAttr}"></div>
                        <button type="button" class="add-todo-btn" onclick="window.TodoHandler.addItem(this)">
                            <i class="fas fa-plus"></i> Add Task
                        </button>
                    </div>`;
                break;
            case 'code':
                contentHTML = `<div class="code-editor-wrapper">
                        <div class="monaco-editor" data-language="${this.escapeAttribute(language)}" data-content="${contentAttr}"></div>
                    </div>`;
                break;
            case 'blocks':
                contentHTML = `<div class="editorjs-wrapper"><div class="editorjs-editor" data-content="${contentAttr}"></div></div>`;
                break;
            case 'whiteboard':
                contentHTML = `<div class="konva-toolbar" style="display: none; gap: 12px; align-items: center; padding: 12px; background: #0d0e10; border: 1px solid #2a2c31; border-radius: 6px 6px 0 0; border-bottom: none;">
                        <button type="button" class="konva-tool-btn konva-draw active">
                            <i class="fas fa-pen"></i> Draw
                        </button>
                        <button type="button" class="konva-tool-btn konva-erase">
                            <i class="fas fa-eraser"></i> Erase
                        </button>
                        <button type="button" class="konva-tool-btn konva-drag" title="Drag / move objects">
                            <i class="fas fa-hand-paper"></i> Drag
                        </button>
                        <div style="border-left: 1px solid #3d4047; height: 24px;"></div>
                        <label style="display: flex; align-items: center; gap: 6px; color: #c3c6cb; font-size: 12px;">
                            Color:
                            <input type="color" class="konva-color" value="#14b8a6" style="width: 32px; height: 24px; border: 1px solid #3d4047; border-radius: 4px; cursor: pointer;">
                        </label>
                        <label style="display: flex; align-items: center; gap: 6px; color: #c3c6cb; font-size: 12px;">
                            Size:
                            <input type="range" class="konva-size" min="1" max="30" value="4" style="width: 120px;">
                        </label>
                        <button type="button" class="konva-undo" title="Undo" style="padding: 6px 10px; border: 1px solid #3d4047; background: transparent; color: #c3c6cb; border-radius: 4px; font-size: 12px;">
                            <i class="fas fa-undo"></i>
                        </button>
                        <button type="button" class="konva-redo" title="Redo" style="padding: 6px 10px; border: 1px solid #3d4047; background: transparent; color: #c3c6cb; border-radius: 4px; font-size: 12px;">
                            <i class="fas fa-redo"></i>
                        </button>
                        <button type="button" class="konva-image-btn" title="Insert image" style="padding: 6px 10px; border: 1px solid #3d4047; background: transparent; color: #c3c6cb; border-radius: 4px; font-size: 12px; display:flex; gap:6px; align-items:center;">
                            <i class="fas fa-paperclip"></i> Image
                        </button>
                        <input type="file" class="konva-image-input" accept="image/*" style="display:none">
                        <div style="flex: 1;"></div>
                        <button type="button" class="konva-clear" style="padding: 6px 12px; background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); color: #ef4444; border-radius: 4px; cursor: pointer; font-size: 12px;">
                            <i class="fas fa-trash"></i> Clear
                        </button>
                    </div>
                    <div class="konva-stage-shell" style="border: 1px solid #2a2c31; border-radius: 6px; overflow: hidden; background: #0d0e10; min-height: 360px;">
                        <div class="konva-stage" style="width: 100%; height: 480px;" data-content="${contentAttr}"></div>
                    </div>`;
                break;
            case 'annotation':
                contentHTML = `<div class="annotation-editor" data-content="${contentAttr}"></div>`;
                break;
            default:
                contentHTML = '<div class="p-4 text-graphite-400">Unsupported block type</div>';
        }

        return `
            <div class="block-item${collapsedClass}" data-type="${blockData.type}" data-block-id="${blockId}" data-container="${containerType}"${collapsedAttr}${parentId ? ` data-parent-id="${parentId}"` : ''}>
                <div class="block-header">
                    <div class="drag-handle" title="Drag to reorder">
                        <i class="fas fa-grip-vertical"></i>
                    </div>
                    <button type="button" class="control-btn collapse-btn" onclick="toggleBlockCollapse(this)" title="${isCollapsed ? 'Expand block' : 'Collapse block'}">
                        <i class="fas fa-chevron-down"></i>
                    </button>
                    <div class="flex items-center gap-2">
                        <i class="fas ${icon} ${color}"></i>
                        <span class="block-type-label">${label}</span>
                        ${blockData.type === 'code' ? `<select class="language-selector" onchange="window.CodeHandler.changeLanguage(this)">
                                <option value="python" ${language === 'python' ? 'selected' : ''}>Python</option>
                                <option value="javascript" ${language === 'javascript' ? 'selected' : ''}>JavaScript</option>
                                <option value="typescript" ${language === 'typescript' ? 'selected' : ''}>TypeScript</option>
                                <option value="html" ${language === 'html' ? 'selected' : ''}>HTML</option>
                                <option value="css" ${language === 'css' ? 'selected' : ''}>CSS</option>
                                <option value="json" ${language === 'json' ? 'selected' : ''}>JSON</option>
                                <option value="sql" ${language === 'sql' ? 'selected' : ''}>SQL</option>
                                <option value="markdown" ${language === 'markdown' ? 'selected' : ''}>Markdown</option>
                                <option value="yaml" ${language === 'yaml' ? 'selected' : ''}>YAML</option>
                                <option value="bash" ${language === 'bash' ? 'selected' : ''}>Bash</option>
                            </select>` : ''}
                    </div>
                    <input type="text" class="block-title-input" placeholder="Block Title" value="${this.escapeAttribute(title)}">
                    <div class="block-controls">
                        ${renderControls()}
                    </div>
                </div>
                <div class="block-content">${contentHTML}</div>
            </div>
        `;
    }

    renderAnnotationCard(annotationData, parentId) {
        return `
            <div class="annotation-card" data-annotation-id="${annotationData.id}" data-parent-id="${parentId}">
                ${this.renderBlock(annotationData, { containerType: 'annotation', parentId })}
            </div>
        `;
    }

    renderBlockRow(blockData) {
        const hasAnnotations = Array.isArray(blockData.annotations) && blockData.annotations.length > 0;
        const splitRatioRaw = blockData.splitRatio || 50;
        const splitRatio = Math.min(70, Math.max(30, splitRatioRaw));
        const annotationVisible = blockData.annotationShow !== false;
        const heightMode = blockData.heightMode === 'dynamic' ? 'dynamic' : 'fixed';
        const baseHeight = Math.max(1, parseFloat(blockData.baseHeight || this.baseBlockHeight || 500));
        const requestedMultiplier = parseFloat(blockData.heightMultiplier || 1);
        const requestedIndex = this.heightMultipliers.indexOf(requestedMultiplier);
        const heightIndex = requestedIndex >= 0 ? requestedIndex : 0;
        const heightMultiplier = this.heightMultipliers[heightIndex] || 1;
        const rowHeight = Math.round(baseHeight * heightMultiplier);
        const mainWidth = hasAnnotations ? ` style="width: ${splitRatio}%"` : '';
        const annotationWidth = hasAnnotations ? ` style="width: ${100 - splitRatio}%"` : '';
        const dynamicHeightClass = heightMode === 'dynamic' ? ' dynamic-height' : '';
        const heightStyle = heightMode === 'dynamic' ? '' : ` style="min-height: ${rowHeight}px; max-height: ${rowHeight}px;"`;
        const heightDataAttrs = ` data-height-mode="${heightMode}" data-height-multiplier="${heightMultiplier}" data-height-index="${heightIndex}" data-base-height="${baseHeight}"`;

        const annotationsHTML = hasAnnotations ? blockData.annotations.map((ann) => this.renderAnnotationCard(ann, blockData.id)).join('') : '';

        return `
            <div class="block-row${dynamicHeightClass}" data-block-id="${blockData.id}" data-split-ratio="${splitRatio}"${heightDataAttrs}${hasAnnotations ? ` data-annotation-show="${annotationVisible ? 'true' : 'false'}"` : ''}${heightStyle}>
                <div class="main-block-column"${mainWidth}>
                    ${this.renderBlock(blockData, { containerType: 'main', hasAnnotations, parentId: null })}
                </div>
                ${hasAnnotations ? `
                    <div class="resize-handle" onmousedown="window.MioBook.startResize(event, this)"></div>
                    <div class="annotation-column${annotationVisible ? '' : ' hidden'}"${annotationWidth} data-parent-id="${blockData.id}">
                        <div class="annotation-toolbar">
                            <div class="annotation-toolbar-title">
                                <i class="fas fa-comment-alt text-teal-400"></i>
                                <span>Annotations</span>
                            </div>
                            <button type="button" class="annotation-add-btn" onclick="window.MioBook.openAnnotationMenu(this)">
                                <i class="fas fa-plus"></i> Add
                            </button>
                        </div>
                        <div class="annotation-scroll-wrapper" data-parent-id="${blockData.id}">
                            ${annotationsHTML}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
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

        const blockData = this.createDefaultBlockData(type);
        const blockHTML = this.renderBlockRow(blockData);

        if (position && referenceBlockId) {
            const referenceRow = document.querySelector(`.block-row[data-block-id="${referenceBlockId}"]`);
            if (referenceRow) {
                if (position === 'before') {
                    referenceRow.insertAdjacentHTML('beforebegin', blockHTML);
                } else if (position === 'after') {
                    referenceRow.insertAdjacentHTML('afterend', blockHTML);
                }
            } else {
                container.insertAdjacentHTML('beforeend', blockHTML);
            }
        } else {
            const separators = container.querySelectorAll('.insert-separator');
            const lastSeparator = separators[separators.length - 1];
            if (lastSeparator) {
                lastSeparator.insertAdjacentHTML('beforebegin', blockHTML);
            } else {
                container.insertAdjacentHTML('beforeend', blockHTML);
            }
        }

        const newRow = document.querySelector(`.block-row[data-block-id="${blockData.id}"]`);
        const newBlock = newRow?.querySelector('.block-item');
        if (newRow && newBlock) {
            const separatorIndex = this.getBlockIndex(newBlock) + 1;
            const separatorHTML = this.createSeparatorHTML(separatorIndex);
            newRow.insertAdjacentHTML('afterend', separatorHTML);

            await this.initializeBlock(newBlock, type);
            this.initializeAnnotationSortable(newRow);
            this.updateSeparatorIndices();
        }

        this.markDirty();
    }
    
    async addBlockAtIndex(type, index) {
        const container = document.getElementById('contentBlocks');
        if (!container) return;

        const blockData = this.createDefaultBlockData(type);
        const blockHTML = this.renderBlockRow(blockData);

        const separators = container.querySelectorAll('.insert-separator');
        const targetSeparator = separators[index];

        if (targetSeparator) {
            targetSeparator.insertAdjacentHTML('afterend', blockHTML);

            const newRow = document.querySelector(`.block-row[data-block-id="${blockData.id}"]`);
            const newBlock = newRow?.querySelector('.block-item');
            if (newRow && newBlock) {
                const separatorHTML = this.createSeparatorHTML(index + 1);
                newRow.insertAdjacentHTML('afterend', separatorHTML);

                await this.initializeBlock(newBlock, type);
                this.initializeAnnotationSortable(newRow);
                this.updateSeparatorIndices();
            }
        }

        this.markDirty();
    }
    
    createSeparatorHTML(index) {
        return `
            <div class="insert-separator" onclick="showInsertMenuAtSeparator(event, ${index})">
                <div class="insert-separator-trigger">
                    <i class="fas fa-plus"></i>
                    <span>Insert Main Block</span>
                </div>
                <div class="insert-separator-line"></div>
            </div>
        `;
    }
    
    getBlockIndex(blockEl) {
        const blockRow = blockEl.closest('.block-row');
        const rows = document.querySelectorAll('#contentBlocks .block-row');
        return Array.from(rows).indexOf(blockRow);
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
                console.log('[MioBook] About to call KonvaHandler.initialize, handler exists:', !!window.KonvaHandler);
                await window.KonvaHandler?.initialize(blockEl);
                console.log('[MioBook] KonvaHandler.initialize returned');
                break;
            case 'annotation':
                await window.AnnotationHandler?.initialize(blockEl.closest('.annotation-card') || blockEl);
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
                                <button type="button" class="konva-edit-btn control-btn" title="Edit (enable drawing)">
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
                            <div class="konva-toolbar" style="display: none; gap: 12px; align-items: center; padding: 12px; background: #0d0e10; border: 1px solid #2a2c31; border-radius: 6px 6px 0 0; border-bottom: none;">
                                <button type="button" class="konva-tool-btn konva-draw active">
                                    <i class="fas fa-pen"></i> Draw
                                </button>
                                <button type="button" class="konva-tool-btn konva-erase">
                                    <i class="fas fa-eraser"></i> Erase
                                </button>
                                <button type="button" class="konva-tool-btn konva-drag" title="Drag / move objects">
                                    <i class="fas fa-hand-paper"></i> Drag
                                </button>
                                <div style="border-left: 1px solid #3d4047; height: 24px;"></div>
                                <label style="display: flex; align-items: center; gap: 6px; color: #c3c6cb; font-size: 12px;">
                                    Color:
                                    <input type="color" class="konva-color" value="#14b8a6" style="width: 32px; height: 24px; border: 1px solid #3d4047; border-radius: 4px; cursor: pointer;">
                                </label>
                                <label style="display: flex; align-items: center; gap: 6px; color: #c3c6cb; font-size: 12px;">
                                    Size:
                                    <input type="range" class="konva-size" min="1" max="30" value="4" style="width: 120px;">
                                </label>
                                <button type="button" class="konva-undo" title="Undo" style="padding: 6px 10px; border: 1px solid #3d4047; background: transparent; color: #c3c6cb; border-radius: 4px; font-size: 12px;">
                                    <i class="fas fa-undo"></i>
                                </button>
                                <button type="button" class="konva-redo" title="Redo" style="padding: 6px 10px; border: 1px solid #3d4047; background: transparent; color: #c3c6cb; border-radius: 4px; font-size: 12px;">
                                    <i class="fas fa-redo"></i>
                                </button>
                                <button type="button" class="konva-image-btn" title="Insert image" style="padding: 6px 10px; border: 1px solid #3d4047; background: transparent; color: #c3c6cb; border-radius: 4px; font-size: 12px; display:flex; gap:6px; align-items:center;">
                                    <i class="fas fa-paperclip"></i> Image
                                </button>
                                <input type="file" class="konva-image-input" accept="image/*" style="display:none">
                                <div style="flex: 1;"></div>
                                <button type="button" class="konva-clear" style="padding: 6px 12px; background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); color: #ef4444; border-radius: 4px; cursor: pointer; font-size: 12px;">
                                    <i class="fas fa-trash"></i> Clear
                                </button>
                            </div>
                            <div class="konva-stage-shell" style="border: 1px solid #2a2c31; border-radius: 6px; overflow: hidden; background: #0d0e10; min-height: 360px;">
                                <div class="konva-stage" 
                                        style="width: 100%; height: 480px;"
                                        data-content=""></div>
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
            const blockItems = blockRow?.querySelectorAll('.block-item') || [];
            blockItems.forEach((item) => this.destroyBlockInstance(item));

            blockRow.remove();

            this.rebuildSeparators();
            this.markDirty();
        }
    }

    destroyBlockInstance(blockEl) {
        if (!blockEl) return;
        const type = blockEl.dataset.type;

        switch (type) {
            case 'code':
                window.CodeHandler?.destroy(blockEl);
                break;
            case 'blocks':
                window.EditorJSHandler?.destroy(blockEl);
                break;
            case 'whiteboard':
                window.KonvaHandler?.destroy(blockEl);
                break;
            case 'annotation':
                window.AnnotationHandler?.destroy(blockEl.closest('.annotation-card') || blockEl);
                break;
            default:
                break;
        }
    }
    
    goBack() {
        if (this.folderId) {
            window.location.href = `/folders/${this.folderId}`;
        } else {
            window.location.href = '/p2/';
        }
    }
    
    async addAnnotation(button, type = 'annotation') {
        const blockRow = button.closest('.block-row');
        if (!blockRow) return;
        this.addAnnotationForRow(blockRow, type);
    }

    async addAnnotationForRow(blockRow, type = 'annotation') {
        if (!blockRow) return;

        this.closeAnnotationMenu();

        const { annotationColumn, wrapper } = this.ensureAnnotationContainer(blockRow);
        if (!wrapper) return;

        const annotationData = this.createDefaultBlockData(type, `annotation-${Date.now()}`);
        annotationData.parentId = blockRow.dataset.blockId;

        wrapper.insertAdjacentHTML('beforeend', this.renderAnnotationCard(annotationData, annotationData.parentId));

        const newBlockEl = wrapper.querySelector(`.annotation-card[data-annotation-id="${annotationData.id}"] .block-item`);
        if (newBlockEl) {
            await this.initializeBlock(newBlockEl, annotationData.type);
        }

        this.initializeAnnotationSortable(blockRow);
        this.updateMainAnnotationButton(blockRow, true);
        this.updateAnnotationCount(blockRow);
        blockRow.dataset.annotationShow = 'true';

        const annotationCol = blockRow.querySelector('.annotation-column');
        if (annotationCol) {
            annotationCol.classList.remove('hidden');
        }

        this.positionResizeHandle(blockRow);
        this.markDirty();
        this.lastActiveBlockRow = blockRow;

        // Scroll to the newly added annotation card
        const newCard = wrapper.querySelector(`.annotation-card[data-annotation-id="${annotationData.id}"]`);
        if (newCard) {
            this.scrollToAnnotationCard(wrapper, newCard);
        }

        const count = wrapper.querySelectorAll('.annotation-card').length;
        this.checkAnnotationSoftLimit(count);
        this.showToast('Annotation added.', 'success');
    }

    toggleAnnotation(button) {
        const blockRow = button.closest('.block-row');
        if (!blockRow) return;

        const annotationColumn = blockRow.querySelector('.annotation-column');
        if (!annotationColumn) return;

        const isHidden = annotationColumn.classList.toggle('hidden');
        blockRow.dataset.annotationShow = isHidden ? 'false' : 'true';

        const icon = button.querySelector('i');
        if (icon) {
            icon.className = `fas ${isHidden ? 'fa-eye-slash' : 'fa-eye'}`;
        }
        button.setAttribute('title', isHidden ? 'Show Annotations' : 'Hide Annotations');

        this.markDirty();
    }

    toggleBlockHeight(button) {
        const blockRow = button.closest('.block-row');
        if (!blockRow) return;

        const computedMinHeight = parseFloat(getComputedStyle(blockRow).minHeight) || this.baseBlockHeight;
        const baseHeight = Math.max(1, parseFloat(blockRow.dataset.baseHeight || this.baseBlockHeight || computedMinHeight || 500));
        const currentIndex = parseInt(blockRow.dataset.heightIndex || '0', 10);
        const nextIndex = Number.isNaN(currentIndex) ? 1 : (currentIndex + 1) % this.heightMultipliers.length;
        const multiplier = this.heightMultipliers[nextIndex] || 1;
        const newHeight = Math.round(baseHeight * multiplier);

        blockRow.dataset.heightMode = 'fixed';
        blockRow.dataset.heightIndex = String(nextIndex);
        blockRow.dataset.heightMultiplier = String(multiplier);
        blockRow.dataset.baseHeight = baseHeight;
        blockRow.classList.remove('dynamic-height');

        blockRow.style.minHeight = `${newHeight}px`;
        blockRow.style.maxHeight = `${newHeight}px`;
        blockRow.style.height = `${newHeight}px`;

        const mainBlock = blockRow.querySelector('.block-item[data-container="main"]');
        const blockType = mainBlock?.dataset?.type;

        if (blockType === 'code') {
            const codeWrapper = mainBlock.querySelector('.code-editor-wrapper');
            if (codeWrapper) {
                codeWrapper.style.height = '';
                codeWrapper.style.minHeight = '';
                codeWrapper.style.maxHeight = '';
                setTimeout(() => codeWrapper._monacoEditor?.layout(), 50);
            } else {
                window.CodeHandler?.resetEditorHeight?.(mainBlock);
            }
        } else if (blockType === 'markdown') {
            const markdownWrapper = mainBlock.querySelector('.markdown-editor-wrapper');
            if (markdownWrapper) {
                markdownWrapper.style.height = '';
                markdownWrapper.style.minHeight = '';
                markdownWrapper.style.maxHeight = '';

                const editorUI = markdownWrapper.querySelector('.toastui-editor-defaultUI');
                if (editorUI) {
                    editorUI.style.height = '';
                    editorUI.style.minHeight = '';
                    editorUI.style.maxHeight = '';

                    const mainContainer = editorUI.querySelector('.toastui-editor-main-container');
                    if (mainContainer) {
                        mainContainer.style.height = '';
                        mainContainer.style.minHeight = '';
                        mainContainer.style.maxHeight = '';
                    }

                    const wwContainer = editorUI.querySelector('.toastui-editor-ww-container');
                    if (wwContainer) {
                        wwContainer.style.height = '';
                        wwContainer.style.minHeight = '';
                        wwContainer.style.maxHeight = '';
                    }

                    const proseMirror = editorUI.querySelector('.ProseMirror');
                    if (proseMirror) {
                        proseMirror.style.height = '';
                        proseMirror.style.minHeight = '';
                        proseMirror.style.maxHeight = '';
                        proseMirror.style.overflowY = '';
                    }
                }
            }
        } else if (blockType === 'editorjs') {
            const editorjsWrapper = mainBlock.querySelector('.editorjs-wrapper');
            if (editorjsWrapper) {
                editorjsWrapper.style.height = '';
                editorjsWrapper.style.minHeight = '';
            }
        }

        const icon = button.querySelector('i');
        if (icon) {
            icon.className = 'fas fa-ruler-vertical';
        }
        button.title = `Cycle height (current: ${multiplier}x)`;

        this.markDirty();
        console.log(`[MioBook] Block height set to ${multiplier}x (~${newHeight}px)`);
    }

    deleteAnnotationBlock(button) {
        const card = button.closest('.annotation-card');
        const blockRow = button.closest('.block-row');
        if (!card || !blockRow) return;

        if (!confirm('Delete annotation? This cannot be undone.')) return;

        const blockEl = card.querySelector('.block-item');
        this.destroyBlockInstance(blockEl);
        card.remove();

        const wrapper = blockRow.querySelector('.annotation-scroll-wrapper');
        const remaining = wrapper ? wrapper.querySelectorAll('.annotation-card').length : 0;

        if (remaining === 0) {
            this.removeAnnotationContainer(blockRow);
        } else {
            this.initializeAnnotationSortable(blockRow, true);
            blockRow.dataset.annotationShow = 'true';
        }

        this.updateAnnotationCount(blockRow);
        this.updateMainAnnotationButton(blockRow, remaining > 0);
        this.positionResizeHandle(blockRow);
        this.markDirty();
    }

    openAnnotationMenu(button) {
        const blockRow = button?.closest?.('.block-row') || this.getActiveBlockRow();
        if (!blockRow) return;

        this.closeAnnotationMenu();
        this.activeAnnotationMenuRow = blockRow;

        const menu = document.createElement('div');
        menu.className = 'annotation-menu';
        menu.innerHTML = `
            <h4>Add Annotation</h4>
            <div class="annotation-option" data-type="annotation">
                <i class="fas fa-comment-dots"></i>
                <div>
                    <div style="font-weight: 600; font-size: 13px; color: #e5e7eb;">Rich Note</div>
                    <div style="font-size: 12px; color: #9aa8ad;">Add a Rich Text annotation beside this block.</div>
                </div>
            </div>
        `;

        document.body.appendChild(menu);
        this.activeAnnotationMenu = menu;

        const rect = button.getBoundingClientRect();
        const top = rect.bottom + 6;
        const left = Math.min(rect.left, window.innerWidth - menu.offsetWidth - 12);
        menu.style.top = `${top}px`;
        menu.style.left = `${Math.max(8, left)}px`;

        const onOutside = (e) => {
            if (!menu.contains(e.target) && e.target !== button) {
                this.closeAnnotationMenu();
            }
        };
        const onKeydown = (e) => {
            if (e.key === 'Escape') {
                this.closeAnnotationMenu();
            }
        };

        this.menuOutsideHandler = onOutside;
        this.menuKeydownHandler = onKeydown;
        document.addEventListener('mousedown', onOutside);
        document.addEventListener('keydown', onKeydown);

        menu.querySelectorAll('.annotation-option').forEach((option) => {
            option.addEventListener('click', () => {
                const type = option.dataset.type || 'annotation';
                this.addAnnotationForRow(blockRow, type);
            });
        });
    }

    closeAnnotationMenu() {
        if (this.activeAnnotationMenu) {
            this.activeAnnotationMenu.remove();
            this.activeAnnotationMenu = null;
        }

        if (this.menuOutsideHandler) {
            document.removeEventListener('mousedown', this.menuOutsideHandler);
            this.menuOutsideHandler = null;
        }

        if (this.menuKeydownHandler) {
            document.removeEventListener('keydown', this.menuKeydownHandler);
            this.menuKeydownHandler = null;
        }

        this.activeAnnotationMenuRow = null;
    }

    ensureAnnotationContainer(blockRow) {
        const blockId = blockRow.dataset.blockId;
        let annotationColumn = blockRow.querySelector('.annotation-column');
        let wrapper = blockRow.querySelector('.annotation-scroll-wrapper');

        if (!annotationColumn) {
            const splitRatio = parseInt(blockRow.dataset.splitRatio, 10) || 50;
            const mainColumn = blockRow.querySelector('.main-block-column');
            const mainRatio = Math.min(70, Math.max(30, splitRatio));
            const annotationRatio = 100 - mainRatio;

            if (mainColumn) {
                mainColumn.style.width = `${mainRatio}%`;
            }

            blockRow.dataset.splitRatio = Math.round(mainRatio);

            const handleHTML = '<div class="resize-handle" onmousedown="window.MioBook.startResize(event, this)"></div>';
            const columnHTML = `
                <div class="annotation-column" style="width: ${annotationRatio}%" data-parent-id="${blockId}">
                    <div class="annotation-toolbar">
                        <div class="annotation-toolbar-title">
                            <i class="fas fa-comment-alt text-teal-400"></i>
                            <span>Annotations</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <div class="annotation-nav-controls">
                                <button type="button" class="annotation-nav-btn" onclick="window.MioBook.navigateAnnotation(this, 'prev')" title="Previous Annotation">
                                    <i class="fas fa-angle-double-left"></i>
                                </button>
                                <button type="button" class="annotation-nav-btn" onclick="window.MioBook.navigateAnnotation(this, 'next')" title="Next Annotation">
                                    <i class="fas fa-angle-double-right"></i>
                                </button>
                            </div>
                            <button type="button" class="annotation-add-btn" onclick="window.MioBook.openAnnotationMenu(this)">
                                <i class="fas fa-plus"></i> Add
                            </button>
                        </div>
                    </div>
                    <div class="annotation-scroll-wrapper" data-parent-id="${blockId}"></div>
                </div>
            `;

            if (mainColumn) {
                mainColumn.insertAdjacentHTML('afterend', handleHTML + columnHTML);
            }

            annotationColumn = blockRow.querySelector('.annotation-column');
            wrapper = blockRow.querySelector('.annotation-scroll-wrapper');
            blockRow.dataset.annotationShow = 'true';
        }

        return { annotationColumn, wrapper };
    }

    removeAnnotationContainer(blockRow) {
        const annotationColumn = blockRow.querySelector('.annotation-column');
        const resizeHandle = blockRow.querySelector('.resize-handle');
        const mainColumn = blockRow.querySelector('.main-block-column');

        if (annotationColumn) {
            const nestedBlocks = annotationColumn.querySelectorAll('.block-item');
            nestedBlocks.forEach((b) => this.destroyBlockInstance(b));
            annotationColumn.remove();
        }

        if (resizeHandle) {
            resizeHandle.remove();
        }

        if (mainColumn) {
            mainColumn.style.width = '';
        }

        delete blockRow.dataset.annotationShow;
    }

    updateMainAnnotationButton(blockRow, hasAnnotations) {
        const addBtn = blockRow.querySelector('.add-annotation-btn');
        const chip = blockRow.querySelector('.annotation-visibility-chip');
        const icon = chip?.querySelector('i');

        if (hasAnnotations) {
            chip?.classList.remove('hidden');
            addBtn?.classList.add('hidden');

            const isHidden = blockRow.dataset.annotationShow === 'false';
            if (icon) {
                icon.className = `fas ${isHidden ? 'fa-eye-slash' : 'fa-eye'}`;
            }
            if (chip) {
                chip.setAttribute('title', isHidden ? 'Show Annotations' : 'Hide Annotations');
            }
        } else {
            chip?.classList.add('hidden');
            addBtn?.classList.remove('hidden');

            if (icon) {
                icon.className = 'fas fa-eye';
            }
            if (chip) {
                chip.setAttribute('title', 'Show Annotations');
            }
        }
    }

    checkAnnotationSoftLimit(count) {
        const thresholds = [5, 10, 15, 20];
        if (thresholds.includes(count)) {
            this.showToast(`You now have ${count} annotations on this block. Consider condensing if it feels cluttered.`, 'warn');
        }
    }

    ensureToastContainer() {
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        return container;
    }

    showToast(message, variant = 'info') {
        const container = this.ensureToastContainer();
        const toast = document.createElement('div');
        toast.className = `toast ${variant === 'warn' ? 'warn' : variant}`;

        const icon = variant === 'success' ? 'fa-check-circle' : variant === 'warn' ? 'fa-exclamation-triangle' : 'fa-info-circle';
        toast.innerHTML = `<i class="fas ${icon}"></i><span>${message}</span>`;

        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(-4px)';
            setTimeout(() => toast.remove(), 200);
        }, 2800);
    }

    initializeAnnotationSortable(blockRow, force = false) {
        const wrapper = blockRow?.querySelector('.annotation-scroll-wrapper');
        if (!wrapper) return;
        if (wrapper.dataset.sortableInit === '1' && !force) return;
        if (wrapper.dataset.sortableInit === '1' && force && wrapper._sortable) {
            wrapper._sortable.destroy();
            wrapper.dataset.sortableInit = '0';
        }

        wrapper._sortable = Sortable.create(wrapper, {
            handle: '.drag-handle',
            animation: 150,
            draggable: '.annotation-card',
            direction: 'horizontal',
            onEnd: () => {
                this.markDirty();
            }
        });

        wrapper.dataset.sortableInit = '1';
    }

    initializeAllAnnotationContainers() {
        const rows = document.querySelectorAll('.block-row');
        rows.forEach((row) => {
            const hasAnnotations = !!row.querySelector('.annotation-card');
            if (hasAnnotations) {
                this.initializeAnnotationSortable(row);
                this.positionResizeHandle(row);
                row.dataset.annotationShow = row.dataset.annotationShow === 'false' ? 'false' : 'true';
            }
            this.updateAnnotationCount(row);
            this.updateMainAnnotationButton(row, hasAnnotations);
        });
    }

    updateAnnotationCount(blockRow) {
        if (!blockRow) return;
        const countEl = blockRow.querySelector('.annotation-count');
        if (!countEl) return;

        const wrapper = blockRow.querySelector('.annotation-scroll-wrapper');
        const count = wrapper ? wrapper.querySelectorAll('.annotation-card').length : 0;
        countEl.textContent = count;
        countEl.dataset.annotationCount = String(count);
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

        handle.style.left = `${(startMainWidth / containerWidth) * 100}%`;

        const onMouseMove = (e) => {
            const deltaX = e.clientX - startX;
            const rawPercentage = ((startMainWidth + deltaX) / containerWidth) * 100;
            const mainPercentage = Math.min(70, Math.max(30, rawPercentage));
            const annotationPercentage = 100 - mainPercentage;

            mainColumn.style.width = `${mainPercentage}%`;
            annotationColumn.style.width = `${annotationPercentage}%`;

            handle.style.left = `${mainPercentage}%`;

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

    /**
     * Navigate to the next or previous annotation within the scroll wrapper
     * @param {HTMLElement} button - The navigation button element
     * @param {string} direction - 'next' or 'prev'
     */
    navigateAnnotation(button, direction) {
        const blockRow = button.closest('.block-row');
        if (!blockRow) return;

        const wrapper = blockRow.querySelector('.annotation-scroll-wrapper');
        if (!wrapper) return;

        const cards = Array.from(wrapper.querySelectorAll('.annotation-card'));
        if (cards.length === 0) return;

        // Find the currently visible card (or closest to being centered in view)
        const wrapperRect = wrapper.getBoundingClientRect();
        const wrapperCenter = wrapperRect.left + wrapperRect.width / 2;

        // Find card closest to center of wrapper viewport
        let closestIndex = 0;
        let closestDistance = Infinity;

        cards.forEach((card, index) => {
            const cardRect = card.getBoundingClientRect();
            const cardCenter = cardRect.left + cardRect.width / 2;
            const distance = Math.abs(cardCenter - wrapperCenter);

            if (distance < closestDistance) {
                closestDistance = distance;
                closestIndex = index;
            }
        });

        // Navigate to next/prev card
        let targetIndex;
        if (direction === 'next') {
            targetIndex = Math.min(closestIndex + 1, cards.length - 1);
        } else {
            targetIndex = Math.max(closestIndex - 1, 0);
        }

        // Only scroll if we're actually moving to a different card
        if (targetIndex !== closestIndex) {
            const targetCard = cards[targetIndex];
            this.scrollToAnnotationCard(wrapper, targetCard);
        }
    }

    /**
     * Scroll the annotation wrapper to center a specific card
     * @param {HTMLElement} wrapper - The annotation scroll wrapper
     * @param {HTMLElement} card - The annotation card to scroll to
     */
    scrollToAnnotationCard(wrapper, card) {
        if (!wrapper || !card) return;

        const wrapperRect = wrapper.getBoundingClientRect();
        const cardRect = card.getBoundingClientRect();

        // Calculate scroll position to center the card in the wrapper
        const wrapperCenter = wrapperRect.width / 2;
        const cardCenter = card.offsetLeft + cardRect.width / 2;
        const scrollTarget = cardCenter - wrapperCenter;

        // Smooth scroll to the target position
        wrapper.scrollTo({
            left: Math.max(0, scrollTarget),
            behavior: 'smooth'
        });
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
