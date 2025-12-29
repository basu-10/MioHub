/**
 * Annotation Handler Module
 * Handles Editor.js-based annotation blocks
 */

class AnnotationHandler {
    constructor() {
        this.instances = new Map(); // Map<blockId, EditorJS>
    }
    
    async initialize(annotationEl) {
        const annotationId = annotationEl.dataset.annotationId;
        if (!annotationId) {
            console.error('[Annotation] No annotation ID found');
            return;
        }
        
        console.log(`[Annotation] Initializing ${annotationId}`);
        
        const editorContainer = annotationEl.querySelector('.annotation-editor');
        if (!editorContainer) {
            console.error('[Annotation] Editor container not found');
            return;
        }
        
        // Parse existing content
        let initialData = {
            blocks: []
        };
        
        const contentAttr = editorContainer.dataset.content;
        if (contentAttr && contentAttr !== '""' && contentAttr !== 'null' && contentAttr !== '') {
            try {
                // Try to parse as JSON
                let parsed = JSON.parse(contentAttr);
                
                // Handle double-encoded JSON
                if (typeof parsed === 'string') {
                    parsed = JSON.parse(parsed);
                }
                
                if (parsed && typeof parsed === 'object') {
                    // Check if it has the correct structure
                    if (parsed.blocks && Array.isArray(parsed.blocks)) {
                        initialData = parsed;
                    } else if (Array.isArray(parsed)) {
                        // If it's just an array, wrap it
                        initialData = { blocks: parsed };
                    }
                }
                console.log('[Annotation] Loaded content:', initialData);
            } catch (e) {
                console.warn('[Annotation] Failed to parse content:', e, contentAttr);
            }
        }
        
        // Wait for Editor.js to be loaded
        if (typeof EditorJS === 'undefined') {
            console.log('[Annotation] Waiting for Editor.js...');
            await this.waitForEditorJS();
        }
        
        try {
            const editor = new EditorJS({
                holder: editorContainer,
                data: initialData,
                placeholder: 'Add annotation notes...',
                minHeight: 100,
                tools: {
                    header: {
                        class: Header,
                        config: {
                            placeholder: 'Header',
                            levels: [2, 3, 4],
                            defaultLevel: 3
                        }
                    },
                    list: {
                        class: NestedList,
                        inlineToolbar: true
                    },
                    checklist: {
                        class: Checklist,
                        inlineToolbar: true
                    },
                    quote: Quote,
                    delimiter: Delimiter,
                    table: Table,
                    code: CodeTool,
                    inlineCode: {
                        class: InlineCode,
                        shortcut: 'CMD+SHIFT+M'
                    },
                    marker: {
                        class: Marker,
                        shortcut: 'CMD+SHIFT+H'
                    },
                    underline: Underline
                },
                onChange: () => {
                    if (window.MioBook) {
                        window.MioBook.markDirty();
                    }
                }
            });
            
            await editor.isReady;
            this.instances.set(annotationId, editor);
            console.log(`[Annotation] Initialized ${annotationId}`);
            
        } catch (error) {
            console.error('[Annotation] Failed to initialize:', error);
        }
    }
    
    async waitForEditorJS() {
        return new Promise((resolve) => {
            const checkInterval = setInterval(() => {
                if (typeof EditorJS !== 'undefined') {
                    clearInterval(checkInterval);
                    resolve();
                }
            }, 100);
        });
    }
    
    async getContent(annotationEl) {
        const annotationId = annotationEl.dataset.annotationId;
        const editor = this.instances.get(annotationId);
        
        if (!editor) {
            console.warn('[Annotation] No editor instance found for', annotationId);
            return null;
        }
        
        try {
            const data = await editor.save();
            return data;
        } catch (error) {
            console.error('[Annotation] Failed to get content:', error);
            return null;
        }
    }
    
    destroy(annotationEl) {
        const annotationId = annotationEl.dataset.annotationId;
        const editor = this.instances.get(annotationId);
        
        if (editor && typeof editor.destroy === 'function') {
            editor.destroy();
            this.instances.delete(annotationId);
            console.log(`[Annotation] Destroyed ${annotationId}`);
        }
    }
}

// Export to window
window.AnnotationHandler = new AnnotationHandler();
