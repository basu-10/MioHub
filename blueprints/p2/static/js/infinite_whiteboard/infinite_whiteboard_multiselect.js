/**
 * Infinite Whiteboard Multi-Select & Clipboard Module
 * Adds multi-selection tracking plus cut/copy/paste helpers for canvas objects.
 *
 * Exposed helpers:
 *  - Selection management: selectSingle, toggleSelection, clearSelection, getSelectionIds, etc.
 *  - Clipboard operations: copySelection, cutSelection, pasteClipboard, deleteSelection.
 *  - Rendering aid: drawMultiSelection (renders bounding boxes for multi-select state).
 */
(function(window) {
  'use strict';

  window.InfiniteWhiteboard = window.InfiniteWhiteboard || {};
  const IWB = window.InfiniteWhiteboard;

  const selectionState = {
    selectedIds: new Set(),
    primaryId: null,
    clipboard: null,
    pasteIterations: 0,
    boundsCache: null,
    handleCache: [],
    pointerPosition: { x: 0, y: 0 }
  };

  IWB.setPointerPosition = function(pos) {
    if (!pos || !Number.isFinite(pos.x) || !Number.isFinite(pos.y)) return;
    selectionState.pointerPosition = { x: pos.x, y: pos.y };
  };

  IWB.getPointerPosition = function() {
    return { ...selectionState.pointerPosition };
  };

  const normalizeId = (id) => {
    const num = Number(id);
    return Number.isFinite(num) ? num : null;
  };

  const ensurePrimaryConsistency = () => {
    if (selectionState.primaryId === null) return;
    if (!selectionState.selectedIds.has(selectionState.primaryId)) {
      const next = selectionState.selectedIds.values().next();
      selectionState.primaryId = next && !next.done ? next.value : null;
    }
  };

  const getObjectBounds = (obj) => {
    if (!obj || typeof IWB.getBounds !== 'function') return null;
    return IWB.getBounds(obj);
  };

  const expandBounds = (acc, bounds) => {
    if (!bounds) return acc;
    if (!acc) return { ...bounds };
    const minX = Math.min(acc.x, bounds.x);
    const minY = Math.min(acc.y, bounds.y);
    const maxX = Math.max(acc.x + acc.w, bounds.x + bounds.w);
    const maxY = Math.max(acc.y + acc.h, bounds.y + bounds.h);
    return { x: minX, y: minY, w: maxX - minX, h: maxY - minY };
  };

  const buildHandle = (type, cx, cy, shape, icon) => ({
    type,
    shape: shape || 'circle',
    icon: icon || '',
    cx,
    cy,
    x: cx - 16,
    y: cy - 16,
    w: 32,
    h: 32
  });

  const computeHandleLayout = (bounds) => {
    if (!bounds) return [];
    const handles = [];
    const centerX = bounds.x + bounds.w / 2;
    const centerY = bounds.y + bounds.h / 2;
    handles.push(buildHandle('move', centerX, bounds.y - 48, 'circle', '⇕'));
    handles.push(buildHandle('rotate', bounds.x + bounds.w + 48, centerY, 'circle', '⟳'));
    handles.push(buildHandle('mirror-h', bounds.x - 48, centerY, 'rect', '⇋'));
    handles.push(buildHandle('mirror-v', centerX, bounds.y + bounds.h + 48, 'rect', '⇵'));
    return handles;
  };

  const snapshotObject = (obj) => {
    if (!obj) return null;
    const safeCopy = { ...obj };
    delete safeCopy.imageElement;
    return {
      data: JSON.parse(JSON.stringify(safeCopy)),
      imageSrc: obj.type === 'image' ? (obj.imageElement?.src || obj.src || '') : null,
      bounds: getObjectBounds(obj)
    };
  };

  const instantiateSnapshot = (snapshot, nextIdFn, offsetVec, requestRender) => {
    if (!snapshot || typeof nextIdFn !== 'function') return null;
    const clone = JSON.parse(JSON.stringify(snapshot.data || {}));
    const newId = nextIdFn();
    clone.id = newId;
    const dx = offsetVec?.dx || 0;
    const dy = offsetVec?.dy || 0;

    if (clone.type === 'stroke' && Array.isArray(clone.path)) {
      clone.path = clone.path.map(pt => ({
        x: pt.x + dx,
        y: pt.y + dy
      }));
    } else if (clone.type === 'image') {
      clone.x = (clone.x || 0) + dx;
      clone.y = (clone.y || 0) + dy;
      const src = snapshot.imageSrc || clone.src;
      if (src) {
        const img = new Image();
        img.src = src;
        clone.src = src;
        clone.imageElement = img;
        img.onload = () => {
          clone.imageElement = img;
          if (typeof requestRender === 'function') {
            requestRender();
          }
        };
      }
    }

    const layerValue = Number.isFinite(clone.layer) ? clone.layer : 0;
    if (typeof IWB.assignLayerMetadata === 'function') {
      IWB.assignLayerMetadata(clone, layerValue);
    } else {
      clone.layer = layerValue;
    }

    return clone;
  };

  const findObjectById = (objects, id) => {
    if (!Array.isArray(objects)) return null;
    return objects.find(o => o && Number(o.id) === Number(id)) || null;
  };

  const removeIdsFromObjects = (objects, ids) => {
    if (!Array.isArray(objects) || !ids.length) return [];
    const removed = [];
    ids.forEach(id => {
      const idx = objects.findIndex(o => Number(o.id) === Number(id));
      if (idx !== -1) {
        const [obj] = objects.splice(idx, 1);
        removed.push(obj);
      }
    });
    return removed;
  };

  IWB.clearSelection = function() {
    selectionState.selectedIds.clear();
    selectionState.primaryId = null;
    selectionState.boundsCache = null;
    selectionState.handleCache = [];
  };

  IWB.selectSingle = function(id) {
    selectionState.selectedIds.clear();
    const normalized = normalizeId(id);
    if (normalized !== null) {
      selectionState.selectedIds.add(normalized);
      selectionState.primaryId = normalized;
    } else {
      selectionState.primaryId = null;
    }
    return selectionState.selectedIds.size;
  };

  IWB.toggleSelection = function(id) {
    const normalized = normalizeId(id);
    if (normalized === null) return selectionState.selectedIds.size;
    if (selectionState.selectedIds.has(normalized)) {
      selectionState.selectedIds.delete(normalized);
      ensurePrimaryConsistency();
    } else {
      selectionState.selectedIds.add(normalized);
      selectionState.primaryId = normalized;
    }
    return selectionState.selectedIds.size;
  };

  IWB.addToSelection = function(id) {
    const normalized = normalizeId(id);
    if (normalized === null) return selectionState.selectedIds.size;
    selectionState.selectedIds.add(normalized);
    selectionState.primaryId = normalized;
    return selectionState.selectedIds.size;
  };

  IWB.removeFromSelection = function(id) {
    const normalized = normalizeId(id);
    if (normalized === null) return selectionState.selectedIds.size;
    if (selectionState.selectedIds.delete(normalized)) {
      ensurePrimaryConsistency();
    }
    return selectionState.selectedIds.size;
  };

  IWB.getSelectionIds = function() {
    return new Set(selectionState.selectedIds);
  };

  IWB.getSelectionCount = function() {
    return selectionState.selectedIds.size;
  };

  IWB.getPrimarySelectionId = function() {
    ensurePrimaryConsistency();
    return selectionState.primaryId;
  };

  IWB.getSelectedObjects = function(objects) {
    if (!Array.isArray(objects)) return [];
    const ids = selectionState.selectedIds;
    if (!ids.size) return [];
    return objects.filter(o => ids.has(Number(o.id)));
  };

  IWB.selectAll = function(objects) {
    selectionState.selectedIds.clear();
    if (!Array.isArray(objects) || !objects.length) {
      selectionState.primaryId = null;
      return 0;
    }
    objects.forEach(obj => {
      if (obj && obj.id !== undefined) {
        selectionState.selectedIds.add(Number(obj.id));
      }
    });
    const last = objects[objects.length - 1];
    selectionState.primaryId = last ? Number(last.id) : null;
    return selectionState.selectedIds.size;
  };

  IWB.copySelection = function(objects) {
    const ids = Array.from(selectionState.selectedIds);
    if (!ids.length) {
      selectionState.clipboard = null;
      return 0;
    }
    const snapshots = ids
      .map(id => snapshotObject(findObjectById(objects, id)))
      .filter(Boolean);
    const combinedBounds = snapshots.reduce((acc, snap) => expandBounds(acc, snap.bounds), null);
    selectionState.clipboard = snapshots.length ? { items: snapshots, bounds: combinedBounds } : null;
    selectionState.pasteIterations = 0;
    return snapshots.length;
  };

  IWB.cutSelection = function(objects) {
    const copied = IWB.copySelection(objects);
    if (!copied) return { removed: 0 };
    const ids = Array.from(selectionState.selectedIds);
    const removed = removeIdsFromObjects(objects, ids);
    removed.forEach(obj => {
      if (typeof IWB.addToUndoStack === 'function') {
        IWB.addToUndoStack({ type: 'delete', object: obj });
      }
    });
    IWB.clearSelection();
    return { removed: removed.length };
  };

  IWB.deleteSelection = function(objects) {
    const ids = Array.from(selectionState.selectedIds);
    if (!ids.length) return 0;
    const removed = removeIdsFromObjects(objects, ids);
    removed.forEach(obj => {
      if (typeof IWB.addToUndoStack === 'function') {
        IWB.addToUndoStack({ type: 'delete', object: obj });
      }
    });
    IWB.clearSelection();
    return removed.length;
  };

  IWB.hasClipboardSelection = function() {
    return Array.isArray(selectionState.clipboard?.items) && selectionState.clipboard.items.length > 0;
  };

  IWB.pasteClipboard = function(objects, nextIdFn, options = {}) {
    if (!IWB.hasClipboardSelection() || typeof nextIdFn !== 'function' || !Array.isArray(objects)) {
      return { added: [] };
    }
    const clipboardPayload = selectionState.clipboard;
    const snapshots = clipboardPayload?.items || [];
    if (!snapshots.length) return { added: [] };

    const requestRender = typeof IWB.requestRender === 'function' ? IWB.requestRender : null;
    let offsetVec = { dx: 0, dy: 0 };

    const hasAnchor = options.anchor && Number.isFinite(options.anchor.x) && Number.isFinite(options.anchor.y);
    if (hasAnchor && clipboardPayload?.bounds) {
      const center = {
        x: clipboardPayload.bounds.x + clipboardPayload.bounds.w / 2,
        y: clipboardPayload.bounds.y + clipboardPayload.bounds.h / 2
      };
      offsetVec = {
        dx: options.anchor.x - center.x,
        dy: options.anchor.y - center.y
      };
      selectionState.pasteIterations = 0;
    } else {
      const nudge = Number.isFinite(options.nudge) ? options.nudge : 32;
      selectionState.pasteIterations = (selectionState.pasteIterations + 1) % 10;
      const offset = Math.max(selectionState.pasteIterations, 1) * nudge;
      offsetVec = { dx: offset, dy: offset };
    }

    const added = snapshots
      .map(snapshot => instantiateSnapshot(snapshot, nextIdFn, offsetVec, requestRender))
      .filter(Boolean);

    added.forEach(obj => {
      objects.push(obj);
      if (typeof IWB.addToUndoStack === 'function') {
        IWB.addToUndoStack({ type: 'add', object: obj });
      }
    });

    if (typeof IWB.sortObjectsByLayerInPlace === 'function') {
      IWB.sortObjectsByLayerInPlace(objects);
    }

    selectionState.selectedIds = new Set(added.map(obj => Number(obj.id)));
    selectionState.primaryId = added.length ? Number(added[added.length - 1].id) : null;

    return { added };
  };

  IWB.drawMultiSelection = function(ctx, objects) {
    if (!ctx || !Array.isArray(objects)) return;
    const ids = selectionState.selectedIds;
    if (ids.size <= 1 || typeof IWB.getBounds !== 'function') {
      selectionState.boundsCache = null;
      selectionState.handleCache = [];
      return;
    }

    const lookup = new Map(objects.map(obj => [Number(obj.id), obj]));
    let aggregateBounds = null;

    ctx.save();
    ctx.strokeStyle = 'rgba(20, 184, 166, 0.85)';
    ctx.lineWidth = 2;
    ctx.setLineDash([4, 4]);

    ids.forEach(id => {
      const obj = lookup.get(Number(id));
      if (!obj) return;
      const bounds = IWB.getBounds(obj);
      if (!bounds) return;
      ctx.strokeRect(bounds.x - 6, bounds.y - 6, bounds.w + 12, bounds.h + 12);
      aggregateBounds = expandBounds(aggregateBounds, {
        x: bounds.x - 8,
        y: bounds.y - 8,
        w: bounds.w + 16,
        h: bounds.h + 16
      });
    });

    ctx.restore();

    if (!aggregateBounds) {
      selectionState.boundsCache = null;
      selectionState.handleCache = [];
      return;
    }

    selectionState.boundsCache = aggregateBounds;

    ctx.save();
    ctx.fillStyle = 'rgba(20, 184, 166, 0.12)';
    ctx.strokeStyle = 'rgba(20, 184, 166, 0.5)';
    ctx.lineWidth = 1;
    ctx.setLineDash([8, 6]);
    ctx.fillRect(aggregateBounds.x, aggregateBounds.y, aggregateBounds.w, aggregateBounds.h);
    ctx.strokeRect(aggregateBounds.x, aggregateBounds.y, aggregateBounds.w, aggregateBounds.h);
    ctx.restore();

    const handles = computeHandleLayout(aggregateBounds);
    selectionState.handleCache = handles;

    handles.forEach(handle => {
      ctx.save();
      ctx.lineWidth = 2;
      ctx.strokeStyle = '#0f766e';
      ctx.fillStyle = handle.type === 'rotate' ? '#0a0a0b' : '#121516';
      if (handle.shape === 'circle') {
        ctx.beginPath();
        ctx.arc(handle.cx, handle.cy, 16, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
      } else {
        ctx.beginPath();
        ctx.rect(handle.x, handle.y, handle.w, handle.h);
        ctx.fill();
        ctx.stroke();
      }
      if (handle.icon) {
        ctx.fillStyle = '#14b8a6';
        ctx.font = 'bold 16px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(handle.icon, handle.cx, handle.cy);
      }
      ctx.restore();
    });
  };

  IWB.getMultiSelectionBounds = function() {
    return selectionState.boundsCache ? { ...selectionState.boundsCache } : null;
  };

  IWB.getMultiSelectionHandles = function() {
    return selectionState.handleCache ? [...selectionState.handleCache] : [];
  };

  console.log('Infinite Whiteboard Multi-Select module loaded');
})(window);
