/**
 * Atrament Whiteboard Block Handler
 * Uses Atrament.js for lightweight freehand drawing
 */

class AtramentHandler {
    constructor() {
        console.log('[AtramentHandler] Constructor called');
        this.instances = new Map(); // blockId -> { atrament, canvas, isEditing, debounceTimer }
        this.atramentLoaded = false;
        this.loadPromise = null;
        this.atramentModule = null;
        this.AtramentCtor = null;
        this.currentEditingBlockId = null;
        this.MODES = {
            draw: null,
            erase: null,
            fill: null,
            disabled: null,
        };
        this.DEBOUNCE_DELAY = 1000; // 1 second debounce for auto-save
    }

    lockOtherCanvases(activeBlockId) {
        this.instances.forEach((instance, id) => {
            if (id === activeBlockId) return;
            if (!instance?.isEditing) return;

            const otherBlockEl = instance.canvas?.closest('.block-item');
            if (otherBlockEl) {
                this.lockCanvas(otherBlockEl);
            }
        });
    }

    #sizeCanvas(canvas) {
        const container = canvas.parentElement;
        const rect = container?.getBoundingClientRect();
        const targetWidth = Math.max(480, Math.floor(rect?.width || canvas.width || 800));
        const targetHeight = Math.max(320, Math.floor(rect?.height || canvas.height || 500));

        canvas.style.width = `${targetWidth}px`;
        canvas.style.height = `${targetHeight}px`;
        canvas.width = targetWidth;
        canvas.height = targetHeight;

        return { width: targetWidth, height: targetHeight };
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

    async #drawDataUrlToCanvas(canvas, dataUrl, targetWidth, targetHeight) {
        if (!dataUrl) return;
        await new Promise((resolve) => {
            const img = new Image();
            img.onload = () => {
                try {
                    const ctx = canvas.getContext('2d');
                    // Draw into the unscaled coordinate space (Atrament scales context internally)
                    const drawW = targetWidth ?? canvas.width ?? 800;
                    const drawH = targetHeight ?? canvas.height ?? 500;
                    ctx.drawImage(img, 0, 0, drawW, drawH);
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

    async #uploadImageFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/upload_image', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`Upload failed with status ${response.status}`);
        }

        const data = await response.json();
        if (!data || !data.url) {
            throw new Error('Upload succeeded but no URL returned');
        }

        return data.url;
    }
    
    /**
     * Debounced auto-save for atrament strokes
     * Waits 1 second after last stroke before triggering save
     */
    #debouncedAutoSave(blockId) {
        const instance = this.instances.get(blockId);
        if (!instance) {
            console.warn(`[Atrament] debouncedAutoSave: No instance found for block ${blockId}`);
            return;
        }
        
        console.log(`[Atrament] Setting up debounced save for block ${blockId}`);
        
        // Clear existing timer
        if (instance.debounceTimer) {
            console.log(`[Atrament] Clearing existing debounce timer for block ${blockId}`);
            clearTimeout(instance.debounceTimer);
        }
        
        // Set new timer
        instance.debounceTimer = setTimeout(() => {
            console.log(`[Atrament] Debounced auto-save triggered for block ${blockId}`);
            console.log(`[Atrament] window.MioBook exists:`, !!window.MioBook);
            if (window.MioBook) {
                console.log(`[Atrament] Calling MioBook.saveDocument(true)`);
                window.MioBook.saveDocument(true); // silent save
            } else {
                console.error('[Atrament] window.MioBook not available for save');
            }
            instance.debounceTimer = null;
        }, this.DEBOUNCE_DELAY);
        
        console.log(`[Atrament] Debounce timer set for block ${blockId}, will fire in ${this.DEBOUNCE_DELAY}ms`);
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
            const size = this.#sizeCanvas(canvas);
            canvas.style.pointerEvents = 'none';
            canvas.style.cursor = 'default';
            
            // Load existing content into canvas (view-only initially)
            try {
                const dataContent = canvas.dataset.content;
                if (dataContent && dataContent !== '""' && dataContent !== 'null') {
                    const parsedData = JSON.parse(dataContent);
                    if (parsedData && parsedData.imageData) {
                        await this.#drawDataUrlToCanvas(canvas, parsedData.imageData, size.width, size.height);
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
        console.log('[Atrament] Instance details:', instance ? {
            hasAtrament: !!instance.atrament,
            hasCanvas: !!instance.canvas,
            hasToolbar: !!instance.toolbar,
            hasEditBtn: !!instance.editBtn
        } : 'NO INSTANCE');
        
        if (!instance) {
            console.error('[Atrament] No instance found for block', blockId);
            return;
        }
        
        if (instance.isEditing) {
            // Lock (disable editing)
            console.log('[Atrament] Locking canvas...');
            this.lockCanvas(blockEl);
        } else {
            // Unlock (enable editing)
            console.log('[Atrament] Unlocking canvas...');
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

        // Only one whiteboard should be editable at a time
        this.lockOtherCanvases(blockId);
        
        // If we already created Atrament once, just re-enable interaction
        if (instance.atrament) {
            instance.isEditing = true;
            instance.canvas.style.pointerEvents = 'auto';
            instance.canvas.style.cursor = 'crosshair';
            
            // Re-enable drawing mode
            if (this.MODES.draw) {
                instance.atrament.mode = this.MODES.draw;
                console.log('[Atrament] Set mode to DRAW');
            }
            
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

        const size = this.#sizeCanvas(instance.canvas);

        const AtramentCtor = this.AtramentCtor;

        // Create Atrament instance
        const atrament = new AtramentCtor(instance.canvas, {
            width: size.width,
            height: size.height,
            color: '#14b8a6',
            weight: 2,
            mode: this.MODES.draw,
            smoothing: 0.85,
            adaptiveStroke: true,
        });

        // Restore existing pixels after Atrament resize
        if (existingImage) {
            await this.#drawDataUrlToCanvas(instance.canvas, existingImage, size.width, size.height);
        }

        console.log('[Atrament] Atrament instance created');

        // Mark dirty on stroke and trigger debounced auto-save
        atrament.addEventListener('strokerecorded', () => {
            console.log(`[Atrament] Stroke recorded for block ${blockId}`);
            if (window.MioBook) {
                console.log('[Atrament] Marking document as dirty');
                window.MioBook.markDirty();
                // Trigger debounced auto-save (waits 1 second after last stroke)
                console.log('[Atrament] Triggering debounced auto-save');
                this.#debouncedAutoSave(blockId);
            } else {
                console.warn('[Atrament] window.MioBook not found - cannot save');
            }
        });

        // Update instance
        instance.atrament = atrament;
        instance.isEditing = true;
        instance.debounceTimer = null; // Initialize debounce timer
        
        // Ensure we're in draw mode
        if (this.MODES.draw) {
            atrament.mode = this.MODES.draw;
            console.log('[Atrament] Initial mode set to DRAW');
        }
        
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
        this.currentEditingBlockId = blockId;
    }
    
    lockCanvas(blockEl) {
        const blockId = blockEl.dataset.blockId;
        const instance = this.instances.get(blockId);
        
        if (!instance) return;

        // Clear any pending debounced save
        if (instance.debounceTimer) {
            clearTimeout(instance.debounceTimer);
            instance.debounceTimer = null;
        }
        
        // Trigger immediate save when locking
        if (instance.isEditing && window.MioBook && window.MioBook.isDirty) {
            console.log(`[Atrament] Locking canvas - triggering immediate save for block ${blockId}`);
            window.MioBook.saveDocument(true); // silent save
        }

        instance.isEditing = false;
        
        // CRITICAL: Disable Atrament drawing engine
        if (instance.atrament && this.MODES.disabled) {
            instance.atrament.mode = this.MODES.disabled;
            console.log('[Atrament] Set mode to DISABLED');
        }
        
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
        if (this.currentEditingBlockId === blockId) {
            this.currentEditingBlockId = null;
        }
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

        const attachBtn = blockEl.querySelector('.atrament-attach');
        const fileInput = blockEl.querySelector('.atrament-image-input');

        if (attachBtn && fileInput) {
            const originalHtml = attachBtn.innerHTML;

            const resetButton = () => {
                attachBtn.disabled = false;
                attachBtn.classList.remove('loading');
                attachBtn.innerHTML = originalHtml;
            };

            attachBtn.addEventListener('click', () => {
                fileInput.click();
            });

            fileInput.addEventListener('change', async (e) => {
                const file = e.target.files?.[0];
                fileInput.value = '';
                if (!file) return;

                attachBtn.disabled = true;
                attachBtn.classList.add('loading');
                attachBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Uploading';

                try {
                    await this.handleImageAttach(blockEl, file);
                } catch (err) {
                    console.error('[Atrament] Failed to attach image', err);
                    alert('Failed to attach image. Please try again.');
                } finally {
                    resetButton();
                }
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

    async handleImageAttach(blockEl, file) {
        if (!file || !file.type?.startsWith('image/')) {
            alert('Please choose an image file.');
            return;
        }

        const blockId = blockEl.dataset.blockId;
        let instance = this.instances.get(blockId);

        if (!instance) {
            console.error('[Atrament] No instance found for image attach', blockId);
            return;
        }

        if (!instance.isEditing) {
            await this.unlockCanvas(blockEl);
            instance = this.instances.get(blockId);
        }

        if (!instance || !instance.canvas) {
            console.error('[Atrament] Cannot attach image - missing canvas');
            return;
        }

        const imageUrl = await this.#uploadImageFile(file);
        const size = this.#sizeCanvas(instance.canvas);
        await this.#drawDataUrlToCanvas(instance.canvas, imageUrl, size.width, size.height);

        if (window.MioBook) {
            window.MioBook.markDirty();
            this.#debouncedAutoSave(blockId);
        }

        return imageUrl;
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
            // Clear debounce timer
            if (instance.debounceTimer) {
                clearTimeout(instance.debounceTimer);
                instance.debounceTimer = null;
            }
            
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

        if (this.currentEditingBlockId === blockId) {
            this.currentEditingBlockId = null;
        }
    }
}

// Export to window
console.log('[AtramentHandler] Creating singleton instance');
window.AtramentHandler = new AtramentHandler();
console.log('[AtramentHandler] Singleton exported to window.AtramentHandler', window.AtramentHandler);
