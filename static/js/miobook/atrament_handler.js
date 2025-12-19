/**
 * Atrament Whiteboard Block Handler
 * Uses Atrament.js for lightweight freehand drawing
 */

class AtramentHandler {
    constructor() {
        console.log('[AtramentHandler] Constructor called');
        this.instances = new Map(); // blockId -> { atrament, canvas, isEditing }
        this.atramentLoaded = false;
        this.loadPromise = null;
        this.atramentModule = null;
        this.AtramentCtor = null;
        this.MODES = {
            draw: null,
            erase: null,
            fill: null,
            disabled: null,
        };
    }
    
    async ensureAtramentLoaded() {
        if (this.atramentLoaded && this.AtramentCtor) {
            return this.atramentModule;
        }

        if (this.loadPromise) {
            return this.loadPromise;
        }

        // Atrament v4+ ships ESM/CJS builds (no UMD global). Use dynamic import for lazy loading.
        const atramentEsmUrl = 'https://cdn.jsdelivr.net/npm/atrament@4.3.0/dist/esm/index.js';

        this.loadPromise = import(atramentEsmUrl)
            .then((mod) => {
                if (!mod || !mod.default) {
                    throw new Error('Atrament module loaded but default export missing');
                }
                this.atramentModule = mod;
                this.AtramentCtor = mod.default;
                this.MODES = {
                    draw: mod.MODE_DRAW,
                    erase: mod.MODE_ERASE,
                    fill: mod.MODE_FILL,
                    disabled: mod.MODE_DISABLED,
                };
                this.atramentLoaded = true;
                console.log('[Atrament] ESM library loaded successfully');
                return mod;
            })
            .catch((err) => {
                console.error('[Atrament] Failed to load ESM module', err);
                // Allow retry on next click
                this.loadPromise = null;
                throw err;
            });

        return this.loadPromise;
    }

    async #drawDataUrlToCanvas(canvas, dataUrl) {
        if (!dataUrl) return;
        await new Promise((resolve) => {
            const img = new Image();
            img.onload = () => {
                try {
                    const ctx = canvas.getContext('2d');
                    // Draw into the unscaled coordinate space (Atrament scales context internally)
                    ctx.drawImage(img, 0, 0, 800, 500);
                } catch (e) {
                    console.warn('[Atrament] Failed to draw existing image onto canvas', e);
                }
                resolve();
            };
            img.onerror = () => resolve();
            img.src = dataUrl;
        });
    }

    #showLoadError(blockEl, message) {
        let el = blockEl.querySelector('.atrament-load-error');
        if (!el) {
            el = document.createElement('div');
            el.className = 'atrament-load-error';
            el.style.cssText = 'margin-top:8px;padding:10px;border:1px solid rgba(239,68,68,0.35);background:rgba(239,68,68,0.08);color:#ef4444;border-radius:6px;font-size:12px;';
            const content = blockEl.querySelector('.block-content');
            content?.appendChild(el);
        }
        el.textContent = message;
    }
    
    async initialize(blockEl) {
        console.log('[Atrament] initialize() called for block', blockEl?.dataset?.blockId);
        try {
            const canvas = blockEl.querySelector('.atrament-canvas');
            const toolbar = blockEl.querySelector('.atrament-toolbar');
            const editBtn = blockEl.querySelector('.atrament-edit-btn');
            
            console.log('[Atrament] Elements found:', { canvas: !!canvas, toolbar: !!toolbar, editBtn: !!editBtn });
            
            if (!canvas) {
                console.error('[Atrament] Canvas not found in block', blockEl);
                return;
            }
            
            const blockId = blockEl.dataset.blockId;
            
            // Set canvas size
            const container = canvas.parentElement;
            canvas.width = 800;
            canvas.height = 500;
            canvas.style.pointerEvents = 'none';
            canvas.style.cursor = 'default';
            
            // Load existing content into canvas (view-only initially)
            try {
                const dataContent = canvas.dataset.content;
                if (dataContent && dataContent !== '""' && dataContent !== 'null') {
                    const parsedData = JSON.parse(dataContent);
                    if (parsedData && parsedData.imageData) {
                        await this.#drawDataUrlToCanvas(canvas, parsedData.imageData);
                    }
                }
            } catch (e) {
                console.warn('[Atrament] Could not parse content:', e);
            }
            
            // Store initial state (not editing)
            this.instances.set(blockId, { 
                atrament: null, 
                canvas, 
                isEditing: false,
                toolbar,
                editBtn
            });
            
            // Setup edit button - IMPORTANT: bind the event listener
            if (editBtn) {
                const handler = () => this.toggleEdit(blockEl);
                editBtn.addEventListener('click', handler);
                // Store handler for cleanup
                this.instances.get(blockId).editHandler = handler;
                console.log('[Atrament] Edit button listener attached for block', blockId);
            } else {
                console.warn('[Atrament] Edit button not found for block', blockId);
            }
            
            console.log(`[Atrament] Initialized block ${blockId} (view-only)`);
        } catch (error) {
            console.error('[Atrament] Initialization error:', error);
        }
    }
    
    async toggleEdit(blockEl) {
        const blockId = blockEl.dataset.blockId;
        const instance = this.instances.get(blockId);
        
        console.log('[Atrament] Toggle edit called for block', blockId, 'current state:', instance?.isEditing);
        
        if (!instance) {
            console.error('[Atrament] No instance found for block', blockId);
            return;
        }
        
        if (instance.isEditing) {
            // Lock (disable editing)
            this.lockCanvas(blockEl);
        } else {
            // Unlock (enable editing)
            await this.unlockCanvas(blockEl);
        }
    }
    
    async unlockCanvas(blockEl) {
        console.log('[Atrament] Unlocking canvas...');
        
        const blockId = blockEl.dataset.blockId;
        const instance = this.instances.get(blockId);
        
        if (!instance || !instance.canvas) {
            console.error('[Atrament] Cannot unlock - no instance or canvas');
            return;
        }
        
        // If we already created Atrament once, just re-enable interaction
        if (instance.atrament) {
            instance.isEditing = true;
            instance.canvas.style.pointerEvents = 'auto';
            instance.canvas.style.cursor = 'crosshair';
            if (instance.toolbar) instance.toolbar.style.display = 'flex';
            if (instance.editBtn) {
                instance.editBtn.innerHTML = '<i class="fas fa-lock"></i>';
                instance.editBtn.title = 'Lock (disable editing)';
                instance.editBtn.style.background = 'rgba(20, 184, 166, 0.2)';
                instance.editBtn.style.borderColor = '#14b8a6';
                instance.editBtn.style.color = '#14b8a6';
            }
            console.log(`[Atrament] Editing re-enabled for block ${blockId}`);
            return;
        }

        let module;
        try {
            module = await this.ensureAtramentLoaded();
        } catch (e) {
            this.#showLoadError(blockEl, 'Failed to load whiteboard engine. Please refresh and try again.');
            return;
        }

        console.log('[Atrament] Creating Atrament instance...');

        // Preserve existing pixels before Atrament resizes the canvas
        let existingImage = null;
        try {
            existingImage = instance.canvas.toDataURL('image/png');
        } catch {
            existingImage = null;
        }

        const AtramentCtor = this.AtramentCtor;

        // Create Atrament instance
        const atrament = new AtramentCtor(instance.canvas, {
            width: 800,
            height: 500,
            color: '#14b8a6',
            weight: 2,
            mode: this.MODES.draw,
            smoothing: 0.85,
            adaptiveStroke: true,
        });

        // Restore existing pixels after Atrament resize
        if (existingImage) {
            await this.#drawDataUrlToCanvas(instance.canvas, existingImage);
        }

        console.log('[Atrament] Atrament instance created');

        // Mark dirty on stroke
        atrament.addEventListener('strokerecorded', () => {
            if (window.MioBook) {
                window.MioBook.markDirty();
            }
        });

        // Update instance
        instance.atrament = atrament;
        instance.isEditing = true;
        
        // Show toolbar and update button
        if (instance.toolbar) {
            instance.toolbar.style.display = 'flex';
        }
        if (instance.editBtn) {
            instance.editBtn.innerHTML = '<i class="fas fa-lock"></i>';
            instance.editBtn.title = 'Lock (disable editing)';
            instance.editBtn.style.background = 'rgba(20, 184, 166, 0.2)';
            instance.editBtn.style.borderColor = '#14b8a6';
            instance.editBtn.style.color = '#14b8a6';
        }
        
        // Update canvas cursor
        instance.canvas.style.pointerEvents = 'auto';
        instance.canvas.style.cursor = 'crosshair';
        
        // Setup toolbar
        if (!instance.toolbarBound) {
            this.setupToolbar(blockEl, atrament);
            instance.toolbarBound = true;
        }
        
        console.log(`[Atrament] Editing enabled for block ${blockId}`);
    }
    
    lockCanvas(blockEl) {
        const blockId = blockEl.dataset.blockId;
        const instance = this.instances.get(blockId);
        
        if (!instance) return;

        instance.isEditing = false;
        if (instance.canvas) {
            instance.canvas.style.pointerEvents = 'none';
            instance.canvas.style.cursor = 'default';
        }
        
        // Hide toolbar and update button
        if (instance.toolbar) {
            instance.toolbar.style.display = 'none';
        }
        if (instance.editBtn) {
            instance.editBtn.innerHTML = '<i class="fas fa-pen"></i>';
            instance.editBtn.title = 'Edit (enable drawing)';
            instance.editBtn.style.background = 'transparent';
            instance.editBtn.style.borderColor = '#3d4047';
            instance.editBtn.style.color = '#7a7f8a';
        }
        
        console.log(`[Atrament] Editing disabled for block ${blockId}`);
    }
    
    setupToolbar(blockEl, atrament) {
        // Color picker
        const colorPicker = blockEl.querySelector('.atrament-color');
        if (colorPicker) {
            colorPicker.addEventListener('change', (e) => {
                atrament.color = e.target.value;
            });
        }
        
        // Brush size
        const sizeSlider = blockEl.querySelector('.atrament-size');
        if (sizeSlider) {
            sizeSlider.addEventListener('input', (e) => {
                atrament.weight = parseInt(e.target.value);
            });
        }
        
        // Mode buttons
        const drawBtn = blockEl.querySelector('.atrament-draw');
        const eraseBtn = blockEl.querySelector('.atrament-erase');
        const fillBtn = blockEl.querySelector('.atrament-fill');
        
        if (drawBtn) {
            drawBtn.addEventListener('click', () => {
                atrament.mode = this.MODES.draw;
                drawBtn.classList.add('active');
                eraseBtn?.classList.remove('active');
                fillBtn?.classList.remove('active');
            });
        }
        
        if (eraseBtn) {
            eraseBtn.addEventListener('click', () => {
                atrament.mode = this.MODES.erase;
                eraseBtn.classList.add('active');
                drawBtn?.classList.remove('active');
                fillBtn?.classList.remove('active');
            });
        }
        
        if (fillBtn) {
            fillBtn.addEventListener('click', () => {
                atrament.mode = this.MODES.fill;
                fillBtn.classList.add('active');
                drawBtn?.classList.remove('active');
                eraseBtn?.classList.remove('active');
            });
        }
        
        // Clear button
        const clearBtn = blockEl.querySelector('.atrament-clear');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                if (confirm('Clear the entire canvas?')) {
                    atrament.clear();
                }
            });
        }
    }
    
    getContent(blockEl) {
        const blockId = blockEl.dataset.blockId;
        const instance = this.instances.get(blockId);
        
        if (!instance || !instance.canvas) {
            return { imageData: null };
        }
        
        try {
            // Export canvas as data URL
            const imageData = instance.canvas.toDataURL('image/png');
            return { imageData };
        } catch (error) {
            console.error('[Atrament] Error getting content:', error);
            return { imageData: null };
        }
    }
    
    destroy(blockEl) {
        const blockId = blockEl.dataset.blockId;
        const instance = this.instances.get(blockId);
        
        if (instance) {
            // Remove event listener
            if (instance.editBtn && instance.editHandler) {
                instance.editBtn.removeEventListener('click', instance.editHandler);
            }
            
            // Destroy Atrament instance
            if (instance.atrament) {
                try {
                    instance.atrament.destroy();
                } catch (error) {
                    console.error('[Atrament] Error destroying instance:', error);
                }
            }
            
            this.instances.delete(blockId);
            console.log('[Atrament] Destroyed block', blockId);
        }
    }
}

// Export to window
console.log('[AtramentHandler] Creating singleton instance');
window.AtramentHandler = new AtramentHandler();
console.log('[AtramentHandler] Singleton exported to window.AtramentHandler', window.AtramentHandler);
