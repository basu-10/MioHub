/**
 * Markdown Block Handler
 * Uses Toast UI Editor for markdown editing
 */

class MarkdownHandler {
    constructor() {
        this.editors = new Map(); // blockId -> editor instance
    }
    
    initialize(blockEl) {
        const editorDiv = blockEl.querySelector('.markdown-editor');
        if (!editorDiv) return;
        
        const blockId = blockEl.dataset.blockId;
        
        // Get existing content
        let content = '';
        try {
            const dataContent = editorDiv.dataset.content;
            if (dataContent && dataContent !== '""' && dataContent !== 'null') {
                content = JSON.parse(dataContent);
            }
        } catch (e) {
            console.warn('[Markdown] Could not parse content:', e);
        }
        
        // Initialize Toast UI Editor
        const editor = new toastui.Editor({
            el: editorDiv,
            height: '300px',
            initialEditType: 'wysiwyg',
            previewStyle: 'vertical',
            initialValue: content,
            theme: 'dark',
            usageStatistics: false,
            toolbarItems: [
                ['heading', 'bold', 'italic', 'strike'],
                ['hr', 'quote'],
                ['ul', 'ol', 'task'],
                ['table', 'link', 'image'],
                ['code', 'codeblock']
            ],
            events: {
                change: () => {
                    if (window.MioBook) {
                        window.MioBook.markDirty();
                    }
                }
            }
        });
        
        this.editors.set(blockId, editor);
    }
    
    getContent(blockEl) {
        const blockId = blockEl.dataset.blockId;
        const editor = this.editors.get(blockId);
        
        if (editor) {
            return editor.getMarkdown();
        }

        // If the editor was not initialized yet (lazy init), preserve existing content.
        const editorDiv = blockEl.querySelector('.markdown-editor');
        if (editorDiv) {
            try {
                const dataContent = editorDiv.dataset.content;
                if (dataContent && dataContent !== '""' && dataContent !== 'null') {
                    const parsed = JSON.parse(dataContent);
                    return typeof parsed === 'string' ? parsed : '';
                }
            } catch (e) {
                console.warn('[Markdown] Fallback parse failed:', e);
            }
        }

        return '';
    }
    
    destroy(blockEl) {
        const blockId = blockEl.dataset.blockId;
        const editor = this.editors.get(blockId);
        
        if (editor) {
            editor.destroy();
            this.editors.delete(blockId);
        }
    }
}

// Export to window
window.MarkdownHandler = new MarkdownHandler();
