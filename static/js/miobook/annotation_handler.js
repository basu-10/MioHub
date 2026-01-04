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
        
        const editorContainer = annotationEl.querySelector('.annotation-editor');
        if (!editorContainer) {
            console.error('[Annotation] Editor container not found');
            return;
        }
        
        // Check if Editor.js is already attached to this DOM element
        if (editorContainer.dataset.editorjsInitialized === 'true') {
            console.log('[Annotation] Editor.js already attached:', annotationId);
            return;
        }
        
        // Check if already initialized in the Map
        if (this.instances.has(annotationId)) {
            console.log('[Annotation] Already has instance in Map:', annotationId);
            return;
        }
        
        // Mark immediately to prevent race conditions
        editorContainer.dataset.editorjsInitialized = 'true';
        
        console.log(`[Annotation] Initializing ${annotationId}`);
        
        // Wait for Editor.js to be loaded
        if (typeof EditorJS === 'undefined') {
            console.log('[Annotation] Waiting for Editor.js...');
            await this.waitForEditorJS();
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

        // Collapse multiple empty paragraphs into a single placeholder block to avoid duplicate prompts
        if (Array.isArray(initialData.blocks) && initialData.blocks.length > 1) {
            const emptyParagraph = (b) => b?.type === 'paragraph' && (!b.data?.text || b.data.text.trim() === '');
            const allEmpty = initialData.blocks.every(emptyParagraph);
            if (allEmpty) {
                initialData = { blocks: [initialData.blocks[0] || { type: 'paragraph', data: { text: '' } }] };
            }
        }
        
        try {
            const editor = new EditorJS({
                holder: editorContainer,
                data: initialData,
                placeholder: 'Add annotation notes...',
                minHeight: 100,
                tools: {
                    header: {
                        class: window.Header,
                        inlineToolbar: true,
                        config: {
                            placeholder: 'Header',
                            levels: [2, 3, 4],
                            defaultLevel: 3
                        },
                        // Keep Convert to → Heading working consistently
                        conversion: {
                            export: 'text',
                            import: 'text'
                        }
                    },
                    list: {
                        class: window.NestedList,
                        inlineToolbar: true,
                        config: {
                            defaultStyle: 'unordered'
                        }
                    },
                    checklist: {
                        class: window.Checklist,
                        inlineToolbar: true
                    },
                    quote: {
                        class: window.Quote,
                        inlineToolbar: true,
                        config: {
                            quotePlaceholder: 'Enter a quote',
                            captionPlaceholder: 'Quote\'s author'
                        }
                    },
                    delimiter: window.Delimiter,
                    table: window.Table,
                    code: window.CodeTool,
                    inlineCode: {
                        class: window.InlineCode,
                        shortcut: 'CMD+SHIFT+M'
                    },
                    marker: {
                        class: window.Marker,
                        shortcut: 'CMD+SHIFT+H'
                    },
                    underline: window.Underline
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
            editorContainer.dataset.editorjsInitialized = 'false';
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
        // Get annotation ID from the card or the element itself
        const card = annotationEl.closest('.annotation-card') || annotationEl;
        const annotationId = card.dataset.annotationId || annotationEl.dataset.annotationId;
        
        console.log('[Annotation] getContent called for:', annotationId);
        
        const editor = this.instances.get(annotationId);
        
        if (!editor) {
            console.warn('[Annotation] No editor instance found for', annotationId);
            console.log('[Annotation] Available instances:', Array.from(this.instances.keys()));
            
            // Try to get content from data attribute as fallback
            const editorContainer = card.querySelector('.annotation-editor');
            if (editorContainer && editorContainer.dataset.content) {
                try {
                    let parsed = JSON.parse(editorContainer.dataset.content);
                    if (typeof parsed === 'string') parsed = JSON.parse(parsed);
                    console.log('[Annotation] Returning fallback content from data attribute');
                    return parsed;
                } catch (e) {
                    console.warn('[Annotation] Failed to parse fallback content:', e);
                }
            }
            
            return { blocks: [] };
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
