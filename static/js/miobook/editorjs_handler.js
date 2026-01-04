/**
 * Editor.js Block Handler
 * Uses Editor.js for rich block-based editing
 */

class EditorJSHandler {
    constructor() {
        this.editors = new Map(); // blockId -> editor instance
        this.editorJSLoaded = false;
    }
    
    async ensureEditorJS() {
        if (this.editorJSLoaded) return;
        
        // EditorJS is loaded via CDN in the main template
        let attempts = 0;
        while (!window.EditorJS && attempts < 50) {
            await new Promise(resolve => setTimeout(resolve, 100));
            attempts++;
        }
        
        if (window.EditorJS) {
            this.editorJSLoaded = true;
        } else {
            console.error('[EditorJS] Editor.js not loaded');
        }
    }
    
    async initialize(blockEl) {
        await this.ensureEditorJS();
        
        const editorDiv = blockEl.querySelector('.editorjs-editor');
        if (!editorDiv || !window.EditorJS) return;
        
        const blockId = blockEl.dataset.blockId;
        
        // Check if already initialized - prevent duplicate instances
        if (this.editors.has(blockId)) {
            console.log(`[EditorJS] Block ${blockId} already initialized, skipping`);
            return;
        }
        
        // Get existing content
        let data = null;
        try {
            const dataContent = editorDiv.dataset.content;
            if (dataContent && dataContent !== '""' && dataContent !== 'null') {
                data = JSON.parse(dataContent);
            }
        } catch (e) {
            console.warn('[EditorJS] Could not parse content:', e);
        }
        
        // Initialize Editor.js
        const editor = new EditorJS({
            holder: editorDiv,
            minHeight: 200,
            placeholder: 'Start writing your content...',
            data: data,
            tools: {
                header: {
                    class: window.Header,
                    inlineToolbar: true,
                    config: {
                        placeholder: 'Enter a heading',
                        levels: [1, 2, 3, 4, 5, 6],
                        defaultLevel: 2
                    },
                    // Explicit conversion config to keep "Convert to → Heading" working across versions
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
                table: {
                    class: window.Table,
                    inlineToolbar: true
                },
                code: window.CodeTool,
                inlineCode: {
                    class: window.InlineCode
                },
                marker: window.Marker,
                underline: window.Underline
            },
            onChange: async () => {
                if (window.MioBook) {
                    window.MioBook.markDirty();
                }
            }
        });
        
        this.editors.set(blockId, editor);
    }
    
    async getContent(blockEl) {
        const blockId = blockEl.dataset.blockId;
        const editor = this.editors.get(blockId);
        
        if (editor) {
            try {
                const outputData = await editor.save();
                return outputData;
            } catch (e) {
                console.error('[EditorJS] Save error:', e);
                return null;
            }
        }

        // If not initialized yet (lazy init), preserve existing content.
        const editorDiv = blockEl.querySelector('.editorjs-editor');
        if (editorDiv) {
            try {
                const dataContent = editorDiv.dataset.content;
                if (dataContent && dataContent !== '""' && dataContent !== 'null') {
                    const parsed = JSON.parse(dataContent);
                    return parsed;
                }
            } catch (e) {
                console.warn('[EditorJS] Fallback parse failed:', e);
            }
        }

        return null;
    }
    
    async destroy(blockEl) {
        const blockId = blockEl.dataset.blockId;
        const editor = this.editors.get(blockId);
        
        if (editor) {
            try {
                await editor.destroy();
            } catch (e) {
                console.warn('[EditorJS] Destroy error:', e);
            }
            this.editors.delete(blockId);
        }
    }
}

// Export to window
window.EditorJSHandler = new EditorJSHandler();
