// Konva-based whiteboard handler for MioBlocks whiteboard blocks
class KonvaHandler {
    constructor() {
        this.instances = new Map();
        this.maxHistory = 10;
    }

    parseContent(raw) {
        if (!raw) return {};
        try {
            if (typeof raw === 'string') {
                return JSON.parse(raw);
            }
            return raw;
        } catch (err) {
            console.warn('[KonvaHandler] Failed to parse content payload', err);
            return {};
        }
    }

    computeSize(container) {
        const width = Math.max(480, Math.floor(container?.clientWidth || 800));
        const height = Math.max(360, Math.floor(container?.clientHeight || 500));
        return { width, height };
    }

    getState(blockEl) {
        const blockId = blockEl?.dataset?.blockId;
        if (!blockId) return null;
        return this.instances.get(blockId);
    }

    initialize(blockEl) {
        try {
            if (!window.Konva) {
                throw new Error('Konva not available on window');
            }

            const blockId = blockEl?.dataset?.blockId;
            const container = blockEl.querySelector('.konva-stage');
            if (!blockId || !container) {
                console.error('[KonvaHandler] Missing blockId or container');
                return;
            }

            const existing = this.instances.get(blockId);
            if (existing?.initialized) {
                return existing;
            }

            const contentRaw = container.dataset.content;
            const parsed = this.parseContent(contentRaw);
            const size = this.computeSize(container);

            let stage;
            try {
                if (parsed?.stageJSON) {
                    stage = Konva.Node.create(parsed.stageJSON, container);
                    stage.container(container);
                    stage.width(size.width);
                    stage.height(size.height);
                } else {
                    stage = new Konva.Stage({
                        container,
                        width: size.width,
                        height: size.height
                    });
                }
            } catch (err) {
                console.warn('[KonvaHandler] Failed to restore stage from JSON, creating fresh stage', err);
                stage = new Konva.Stage({ container, width: size.width, height: size.height });
            }

            let layer = stage.findOne('Layer');
            if (!layer) {
                layer = new Konva.Layer();
                stage.add(layer);
            }

            const state = {
                blockId,
                blockEl,
                container,
                stage,
                layer,
                mode: 'view',
                tool: 'draw',
                color: parsed?.color || '#14b8a6',
                size: parsed?.size || 4,
                history: [],
                future: [],
                toolbar: blockEl.querySelector('.konva-toolbar'),
                editBtn: blockEl.querySelector('.konva-edit-btn'),
                colorInput: blockEl.querySelector('.konva-color'),
                sizeInput: blockEl.querySelector('.konva-size'),
                drawBtn: blockEl.querySelector('.konva-draw'),
                eraseBtn: blockEl.querySelector('.konva-erase'),
                dragBtn: blockEl.querySelector('.konva-drag'),
                undoBtn: blockEl.querySelector('.konva-undo'),
                redoBtn: blockEl.querySelector('.konva-redo'),
                clearBtn: blockEl.querySelector('.konva-clear'),
                imageBtn: blockEl.querySelector('.konva-image-btn'),
                fileInput: blockEl.querySelector('.konva-image-input'),
                activeLine: null,
                isPointerDown: false,
                dragMode: false,
                hoveringDraggable: false,
                initialized: true
            };

            this.instances.set(blockId, state);
            this.bindUI(state);
            this.attachCursorTracking(state);
            this.pushHistory(state, false);
            this.setMode(state, 'view');
            this.updateUndoRedoUI(state);
            this.reloadImages(state);
            return state;
        } catch (err) {
            console.error('[KonvaHandler] initialize failed', err);
            this.showError(blockEl, 'Unable to load whiteboard. Please refresh.');
            return null;
        }
    }

    showError(blockEl, message) {
        if (!blockEl) return;
        let el = blockEl.querySelector('.konva-error');
        if (!el) {
            el = document.createElement('div');
            el.className = 'konva-error';
            el.style.cssText = 'margin-top:8px;padding:10px;border:1px solid rgba(239,68,68,0.35);background:rgba(239,68,68,0.08);color:#ef4444;border-radius:6px;font-size:12px;';
            const content = blockEl.querySelector('.block-content');
            content?.appendChild(el);
        }
        el.textContent = message;
    }

    bindUI(state) {
        const { editBtn, colorInput, sizeInput, drawBtn, eraseBtn, undoBtn, redoBtn, clearBtn, imageBtn, fileInput } = state;

        if (colorInput) {
            colorInput.value = state.color;
            colorInput.addEventListener('change', (e) => {
                state.color = e.target.value;
            });
        }

        if (sizeInput) {
            sizeInput.value = state.size;
            sizeInput.addEventListener('input', (e) => {
                state.size = parseInt(e.target.value, 10) || 2;
            });
        }

        if (drawBtn) {
            drawBtn.addEventListener('click', () => this.setTool(state, 'draw'));
        }

        if (eraseBtn) {
            eraseBtn.addEventListener('click', () => this.setTool(state, 'erase'));
        }

        if (state.dragBtn) {
            state.dragBtn.addEventListener('click', () => {
                this.setDragMode(state, !state.dragMode);
            });
        }

        if (editBtn) {
            editBtn.addEventListener('click', () => {
                if (state.mode === 'view') {
                    this.setMode(state, 'edit');
                } else {
                    this.setMode(state, 'view');
                }
            });
        }

        if (undoBtn) {
            undoBtn.addEventListener('click', () => this.undo(state));
        }

        if (redoBtn) {
            redoBtn.addEventListener('click', () => this.redo(state));
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                if (!confirm('Clear the entire canvas?')) return;
                state.layer.removeChildren();
                state.layer.draw();
                this.pushHistory(state);
                this.markDirty();
            });
        }

        if (imageBtn && fileInput) {
            imageBtn.addEventListener('click', () => fileInput.click());
            fileInput.addEventListener('change', async (e) => {
                const file = e.target.files?.[0];
                fileInput.value = '';
                if (!file) return;
                try {
                    await this.handleImageInsert(state, file, imageBtn);
                } catch (err) {
                    console.error('[KonvaHandler] Image insert failed', err);
                    alert('Failed to insert image. Please try again.');
                }
            });
        }

        this.setTool(state, state.tool);
        this.attachResizeObserver(state);
    }

    setMode(state, mode) {
        if (!state?.stage) return;
        state.mode = mode;
        const isEditing = mode === 'edit';

        if (state.toolbar) {
            state.toolbar.style.display = isEditing ? 'flex' : 'none';
        }

        if (state.editBtn) {
            if (isEditing) {
                state.editBtn.innerHTML = '<i class="fas fa-lock"></i>';
                state.editBtn.title = 'Lock (disable editing)';
                state.editBtn.style.background = 'rgba(20, 184, 166, 0.2)';
                state.editBtn.style.borderColor = '#14b8a6';
                state.editBtn.style.color = '#14b8a6';
            } else {
                state.editBtn.innerHTML = '<i class="fas fa-pen"></i>';
                state.editBtn.title = 'Edit (enable drawing)';
                state.editBtn.style.background = 'transparent';
                state.editBtn.style.borderColor = '#3d4047';
                state.editBtn.style.color = '#7a7f8a';
            }
        }

        if (isEditing) {
            this.attachDrawing(state);
        } else {
            this.detachDrawing(state);
        }

        if (state.stage) {
            state.stage.listening(isEditing);
        }
        if (state.layer) {
            state.layer.listening(isEditing);
        }

        // Leave drag mode when exiting edit; refresh interactivity
        if (!isEditing && state.dragMode) {
            this.setDragMode(state, false);
        } else {
            this.updateInteractivity(state);
        }

        this.updateCursor(state);
    }

    setTool(state, tool) {
        state.tool = tool;
        if (state.drawBtn) {
            state.drawBtn.classList.toggle('active', tool === 'draw');
        }
        if (state.eraseBtn) {
            state.eraseBtn.classList.toggle('active', tool === 'erase');
        }

        // Drawing/erasing should disable drag mode
        if (state.dragMode && (tool === 'draw' || tool === 'erase')) {
            this.setDragMode(state, false);
        } else {
            this.updateInteractivity(state);
        }

        this.updateCursor(state);
    }

    attachDrawing(state) {
        const stage = state.stage;
        if (!stage) return;
        stage.off('.konva-draw');

        stage.on('pointerdown.konva-draw', (evt) => this.handlePointerDown(evt, state));
        stage.on('pointermove.konva-draw', (evt) => this.handlePointerMove(evt, state));
        stage.on('pointerup.konva-draw pointerleave.konva-draw', () => this.handlePointerUp(state));
    }

    detachDrawing(state) {
        state.stage?.off('.konva-draw');
        state.isPointerDown = false;
        state.activeLine = null;
    }

    handlePointerDown(evt, state) {
        if (state.mode !== 'edit') return;
        if (state.dragMode) return;
        const pos = state.stage.getPointerPosition();
        if (!pos) return;

        state.isPointerDown = true;
        state.activeLine = new Konva.Line({
            stroke: state.tool === 'erase' ? '#000' : state.color,
            strokeWidth: state.size,
            lineCap: 'round',
            lineJoin: 'round',
            globalCompositeOperation: state.tool === 'erase' ? 'destination-out' : 'source-over',
            points: [pos.x, pos.y]
        });
        state.layer.add(state.activeLine);
    }

    handlePointerMove(evt, state) {
        if (!state.isPointerDown || !state.activeLine) return;
        const pos = state.stage.getPointerPosition();
        if (!pos) return;
        const points = state.activeLine.points().concat([pos.x, pos.y]);
        state.activeLine.points(points);
        state.layer.batchDraw();
    }

    handlePointerUp(state) {
        if (!state.isPointerDown) return;
        state.isPointerDown = false;
        state.activeLine = null;
        this.pushHistory(state);
        this.markDirty();
    }

    async handleImageInsert(state, file, button) {
        if (!file || !file.type?.startsWith('image/')) {
            alert('Please choose an image file.');
            return;
        }

        const originalHtml = button?.innerHTML;
        if (button) {
            button.disabled = true;
            button.classList.add('loading');
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Uploading';
        }

        try {
            const imageUrl = await this.uploadImage(file);
            await this.addImageToStage(state, imageUrl);
            this.pushHistory(state);
            this.markDirty();
        } finally {
            if (button) {
                button.disabled = false;
                button.classList.remove('loading');
                button.innerHTML = originalHtml;
            }
        }
    }

    async uploadImage(file) {
        const formData = new FormData();
        formData.append('file', file);
        const response = await fetch('/upload_image', { method: 'POST', body: formData });
        if (!response.ok) {
            throw new Error(`Upload failed with status ${response.status}`);
        }
        const data = await response.json();
        if (!data?.url) {
            throw new Error('Upload succeeded but no URL returned');
        }
        return data.url;
    }

    async addImageToStage(state, imageUrl) {
        const { imageNode, size } = await this.loadImageNode(imageUrl, state.stage);
        imageNode.setAttrs({
            draggable: false,
            imageUrl
        });
        state.layer.add(imageNode);
        state.layer.draw();
    }

    async loadImageNode(imageUrl, stageRef) {
        return new Promise((resolve, reject) => {
            Konva.Image.fromURL(
                imageUrl,
                (node) => {
                    const stageWidth = stageRef?.width?.() || 800;
                    const stageHeight = stageRef?.height?.() || 600;
                    const maxW = stageWidth * 0.8;
                    const maxH = stageHeight * 0.8;
                    const naturalW = node.image()?.naturalWidth || node.width();
                    const naturalH = node.image()?.naturalHeight || node.height();
                    const scale = Math.min(1, maxW / naturalW, maxH / naturalH);
                    node.width(naturalW * scale);
                    node.height(naturalH * scale);
                    node.position({ x: 20, y: 20 });
                    resolve({ imageNode: node, size: { w: node.width(), h: node.height() } });
                },
                (err) => {
                    console.error('[KonvaHandler] Failed to load image from URL', err);
                    reject(new Error('Image load failed'));
                }
            );
        });
    }

    pushHistory(state, markDirty = true) {
        if (!state?.stage) return;
        const json = state.stage.toJSON();
        const history = state.history;
        const last = history[history.length - 1];
        if (last === json) return;

        history.push(json);
        while (history.length > this.maxHistory) {
            history.shift();
        }
        state.future = [];
        this.updateUndoRedoUI(state);
        if (markDirty) {
            this.markDirty();
        }
    }

    undo(state) {
        if (!state || state.history.length <= 1) return;
        const current = state.history.pop();
        state.future.push(current);
        const previous = state.history[state.history.length - 1];
        this.restoreFromJSON(state, previous);
        this.updateUndoRedoUI(state);
        this.markDirty();
    }

    redo(state) {
        if (!state || state.future.length === 0) return;
        const next = state.future.pop();
        state.history.push(next);
        this.restoreFromJSON(state, next);
        this.updateUndoRedoUI(state);
        this.markDirty();
    }

    restoreFromJSON(state, json) {
        if (!json) return;
        const { container } = state;
        const size = this.computeSize(container);
        try {
            state.stage.destroy();
        } catch (err) {
            console.warn('[KonvaHandler] Failed to destroy stage before restore', err);
        }

        try {
            state.stage = Konva.Node.create(json, container);
        } catch (err) {
            console.warn('[KonvaHandler] Failed to recreate stage, using empty stage', err);
            state.stage = new Konva.Stage({ container, width: size.width, height: size.height });
        }

        state.stage.container(container);
        state.stage.width(size.width);
        state.stage.height(size.height);

        state.layer = state.stage.findOne('Layer');
        if (!state.layer) {
            state.layer = new Konva.Layer();
            state.stage.add(state.layer);
        }

        if (state.mode === 'edit') {
            this.attachDrawing(state);
        }
        state.stage.listening(state.mode === 'edit');
        state.layer.listening(state.mode === 'edit');
        this.reloadImages(state);
        state.stage.draw();
    }

    updateUndoRedoUI(state) {
        if (state.undoBtn) {
            state.undoBtn.disabled = state.history.length <= 1;
        }
        if (state.redoBtn) {
            state.redoBtn.disabled = state.future.length === 0;
        }
    }

    setDragMode(state, enabled) {
        if (!state?.stage) return;
        state.dragMode = !!enabled;
        if (!state.dragMode) {
            state.hoveringDraggable = false;
        }
        if (state.dragBtn) {
            state.dragBtn.classList.toggle('active', state.dragMode);
        }

        if (state.dragMode) {
            // Turn off drawing while dragging
            this.detachDrawing(state);
        } else if (state.mode === 'edit') {
            this.attachDrawing(state);
        }

        this.updateInteractivity(state);
        this.updateCursor(state);
    }

    async reloadImages(state) {
        if (!state?.stage) return;
        const images = state.stage.find('Image');
        if (!images?.length) return;

        const promises = images.map(async (node) => {
            const url = node.getAttr('imageUrl');
            if (!url) return;
            try {
                const { imageNode } = await this.loadImageNode(url, state.stage);
                node.image(imageNode.image());
                node.width(imageNode.width());
                node.height(imageNode.height());
                node.setAttr('imageUrl', url);
            } catch (err) {
                console.warn('[KonvaHandler] Failed to reload image', url, err);
            }
        });

        try {
            await Promise.all(promises);
            state.layer?.batchDraw();
        } catch (err) {
            console.warn('[KonvaHandler] reloadImages batch error', err);
        }
    }

    updateInteractivity(state) {
        if (!state?.stage) return;
        const allowHit = state.dragMode || state.mode !== 'edit';
        const canDrag = state.dragMode;

        // Images
        const images = state.stage.find('Image');
        images.forEach((img) => {
            img.listening(allowHit);
            img.draggable(canDrag);
        });

        // Strokes and shapes
        const shapes = state.layer?.find('Line') || [];
        shapes.forEach((shape) => {
            shape.listening(allowHit);
            shape.draggable(canDrag);
        });
    }

    updateCursor(state) {
        if (!state?.stage) return;
        const container = state.stage.container();
        if (!container) return;

        if (state.dragMode) {
            container.style.cursor = state.hoveringDraggable ? 'grab' : 'default';
        } else if (state.mode === 'edit') {
            container.style.cursor = 'crosshair';
        } else {
            container.style.cursor = 'default';
        }
    }

    attachResizeObserver(state) {
        if (!state?.container || state.resizeObserver) return;
        if (typeof ResizeObserver === 'undefined') return;
        const observer = new ResizeObserver(() => {
            const size = this.computeSize(state.container);
            state.stage.width(size.width);
            state.stage.height(size.height);
            state.stage.draw();
        });
        observer.observe(state.container);
        state.resizeObserver = observer;
    }

    getContent(blockEl) {
        const state = this.getState(blockEl);
        if (!state?.stage) return { version: 'konva-v1', stageJSON: null };
        return {
            version: 'konva-v1',
            stageJSON: state.stage.toJSON(),
            color: state.color,
            size: state.size
        };
    }

    destroy(blockEl) {
        const state = this.getState(blockEl);
        if (!state) return;
        try {
            state.stage?.destroy();
            state.resizeObserver?.disconnect();
        } catch (err) {
            console.warn('[KonvaHandler] destroy error', err);
        }
        this.instances.delete(state.blockId);
    }

    attachCursorTracking(state) {
        const stage = state?.stage;
        if (!stage) return;
        stage.off('.konva-cursor');

        stage.on('pointermove.konva-cursor', (evt) => {
            const target = evt?.target;
            const cls = target?.getClassName?.();
            const isObject = cls && cls !== 'Stage' && cls !== 'Layer';
            state.hoveringDraggable = !!(state.dragMode && state.mode === 'edit' && isObject);
            this.updateCursor(state);
        });

        stage.on('pointerleave.konva-cursor', () => {
            state.hoveringDraggable = false;
            this.updateCursor(state);
        });
    }

    markDirty() {
        if (window.MioBook) {
            window.MioBook.markDirty();
        }
    }
}

window.KonvaHandler = new KonvaHandler();
