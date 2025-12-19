/**
 * Code Block Handler
 * Uses Monaco Editor for code editing with syntax highlighting
 */

class CodeHandler {
    constructor() {
        this.editors = new Map(); // blockId -> editor instance
        this.monacoLoaded = false;
    }
    
    async ensureMonaco() {
        if (this.monacoLoaded) return;
        
        // Monaco is loaded via CDN in the main template
        // Just wait for it to be available
        let attempts = 0;
        while (!window.monaco && attempts < 50) {
            await new Promise(resolve => setTimeout(resolve, 100));
            attempts++;
        }
        
        if (window.monaco) {
            // Set Monaco theme to dark
            monaco.editor.setTheme('vs-dark');
            this.monacoLoaded = true;
        } else {
            console.error('[Code] Monaco Editor not loaded');
        }
    }
    
    async initialize(blockEl) {
        await this.ensureMonaco();
        
        const editorDiv = blockEl.querySelector('.monaco-editor');
        if (!editorDiv || !window.monaco) return;
        
        const blockId = blockEl.dataset.blockId;
        const language = editorDiv.dataset.language || 'python';
        
        // Get existing content
        let content = '';
        try {
            const dataContent = editorDiv.dataset.content;
            if (dataContent && dataContent !== '""' && dataContent !== 'null') {
                content = JSON.parse(dataContent);
            }
        } catch (e) {
            console.warn('[Code] Could not parse content:', e);
        }
        
        // Create Monaco editor
        const editor = monaco.editor.create(editorDiv, {
            value: content,
            language: language,
            theme: 'vs-dark',
            minimap: { enabled: false },
            fontSize: 14,
            lineNumbers: 'on',
            roundedSelection: true,
            scrollBeyondLastLine: false,
            automaticLayout: true,
            wordWrap: 'on'
        });
        
        // Listen for changes
        editor.onDidChangeModelContent(() => {
            if (window.MioBook) {
                window.MioBook.markDirty();
            }
        });
        
        this.editors.set(blockId, editor);
    }
    
    changeLanguage(selectEl) {
        const blockEl = selectEl.closest('.block-item');
        const blockId = blockEl.dataset.blockId;
        const editor = this.editors.get(blockId);
        
        if (editor) {
            const newLanguage = selectEl.value;
            const model = editor.getModel();
            if (model) {
                monaco.editor.setModelLanguage(model, newLanguage);
            }
            
            if (window.MioBook) {
                window.MioBook.markDirty();
            }
        }
    }
    
    getContent(blockEl) {
        const blockId = blockEl.dataset.blockId;
        const editor = this.editors.get(blockId);
        const languageSelect = blockEl.querySelector('.language-selector');
        
        if (editor) {
            return {
                content: editor.getValue(),
                metadata: {
                    language: languageSelect ? languageSelect.value : 'python'
                }
            };
        }

        // If not initialized yet (lazy init), preserve existing content from DOM.
        let content = '';
        let language = languageSelect ? languageSelect.value : 'python';
        const editorDiv = blockEl.querySelector('.monaco-editor');
        if (editorDiv) {
            if (editorDiv.dataset.language) {
                language = editorDiv.dataset.language;
            }
            try {
                const dataContent = editorDiv.dataset.content;
                if (dataContent && dataContent !== '""' && dataContent !== 'null') {
                    const parsed = JSON.parse(dataContent);
                    if (typeof parsed === 'string') {
                        content = parsed;
                    }
                }
            } catch (e) {
                console.warn('[Code] Fallback parse failed:', e);
            }
        }

        return {
            content,
            metadata: { language }
        };
    }
    
    destroy(blockEl) {
        const blockId = blockEl.dataset.blockId;
        const editor = this.editors.get(blockId);
        
        if (editor) {
            editor.dispose();
            this.editors.delete(blockId);
        }
    }
}

// Export to window
window.CodeHandler = new CodeHandler();
