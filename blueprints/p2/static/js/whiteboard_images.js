/**
 * Whiteboard Image Handling Module
 * Handles image upload, compression, cropping, and clipboard paste
 */

/**
 * Compress image to target size
 * @param {Image} img - Image to compress
 * @param {number} quality - JPEG quality (0-1)
 * @returns {Object} - {dataUrl, width, height}
 */
function compressImage(img, quality = 0.7) {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  
  // Calculate size for 1.2MP equivalent (approximately 1200x1000 max)
  const targetPixels = 1.2 * 1000000; // 1.2 megapixels
  const currentPixels = img.width * img.height;
  
  let w = img.width;
  let h = img.height;
  
  // If image is larger than 1.2MP, scale it down
  if (currentPixels > targetPixels) {
    const scale = Math.sqrt(targetPixels / currentPixels);
    w = Math.round(img.width * scale);
    h = Math.round(img.height * scale);
  }
  
  // Set canvas size
  canvas.width = w;
  canvas.height = h;
  
  // Draw and compress image
  ctx.drawImage(img, 0, 0, w, h);
  
  // Convert to JPEG with specified quality
  const compressedDataUrl = canvas.toDataURL('image/jpeg', quality);
  
  console.log(`[IMAGE] Original: ${img.width}x${img.height} (${Math.round(currentPixels/1000000*100)/100}MP), Resized: ${w}x${h} (${Math.round((w*h)/1000000*100)/100}MP)`);
  
  return {
    dataUrl: compressedDataUrl,
    width: w,
    height: h,
    originalSize: img.width * img.height,
    compressedSize: w * h
  };
}

/**
 * Handle image file upload
 * @param {File} file - Image file
 * @param {Function} callback - Callback(imageObject)
 */
function handleImageUpload(file, callback) {
  if (!file) return;
  
  const reader = new FileReader();
  reader.onload = (ev) => {
    const img = new Image();
    img.src = ev.target.result;
    img.onload = () => {
      const compressed = compressImage(img);
      
      // Warn if still too large
      if (compressed.dataUrl.length > 500000) {
        console.warn('[IMAGE] Large image detected (>500KB), may cause save issues');
      }
      
      if (callback) {
        callback({
          src: compressed.dataUrl,
          x: 50,
          y: 160,
          w: compressed.width,
          h: compressed.height
        });
      }
    };
  };
  reader.readAsDataURL(file);
}

/**
 * Handle clipboard image paste
 * @param {ClipboardItem} item - Clipboard item
 * @param {Function} callback - Callback(imageObject)
 */
async function handleClipboardImage(item, callback) {
  const imageTypes = item.types.filter(type => type.startsWith('image/'));
  if (imageTypes.length === 0) return false;
  
  console.log('Found image types:', imageTypes);
  
  // Get the first image type (usually image/png or image/jpeg)
  const imageType = imageTypes[0];
  const blob = await item.getType(imageType);
  console.log('Image blob size:', blob.size, 'bytes');
  
  // Process the image using compression
  const reader = new FileReader();
  reader.onload = (ev) => {
    const img = new Image();
    img.src = ev.target.result;
    img.onload = () => {
      const compressed = compressImage(img);
      
      console.log(`[CLIPBOARD IMAGE] Size - Original: ${ev.target.result.length} bytes, Compressed: ${compressed.dataUrl.length} bytes, Reduction: ${Math.round((1 - compressed.dataUrl.length/ev.target.result.length) * 100)}%`);
      
      // Warn if still too large
      if (compressed.dataUrl.length > 500000) {
        console.warn('[CLIPBOARD IMAGE] Large image detected (>500KB), may cause save issues');
      }
      
      if (callback) {
        callback({
          src: compressed.dataUrl,
          x: 50,
          y: 160,
          w: compressed.width,
          h: compressed.height
        });
      }
    };
  };
  reader.readAsDataURL(blob);
  
  return true;
}

/**
 * Crop Modal State
 */
let croppingImageId = null;
let cropSelection = { x: 0, y: 0, w: 100, h: 100 };
let isDraggingCrop = false;
let isResizingCrop = false;
let cropDragStart = { x: 0, y: 0 };
let resizeHandle = null;

/**
 * Update crop selection display
 */
function updateCropSelection() {
  const img = document.getElementById('crop-image');
  const selection = document.getElementById('crop-selection');
  const handles = document.querySelectorAll('.crop-handle');
  
  if (!img || !img.complete || img.naturalWidth === 0) return;
  
  const scaleX = img.clientWidth / img.naturalWidth;
  const scaleY = img.clientHeight / img.naturalHeight;
  
  selection.style.left = (cropSelection.x * scaleX) + 'px';
  selection.style.top = (cropSelection.y * scaleY) + 'px';
  selection.style.width = (cropSelection.w * scaleX) + 'px';
  selection.style.height = (cropSelection.h * scaleY) + 'px';
  
  // Update handles
  const handlesPos = [
    { handle: 'nw', x: cropSelection.x, y: cropSelection.y },
    { handle: 'ne', x: cropSelection.x + cropSelection.w, y: cropSelection.y },
    { handle: 'sw', x: cropSelection.x, y: cropSelection.y + cropSelection.h },
    { handle: 'se', x: cropSelection.x + cropSelection.w, y: cropSelection.y + cropSelection.h }
  ];
  
  handlesPos.forEach(({ handle, x, y }) => {
    const handleEl = document.querySelector(`[data-handle="${handle}"]`);
    if (handleEl) {
      handleEl.style.left = (x * scaleX - 5) + 'px';
      handleEl.style.top = (y * scaleY - 5) + 'px';
    }
  });
}

/**
 * Open crop modal
 * @param {Object} imageObj - Image object to crop
 */
function openCropModal(imageObj) {
  croppingImageId = imageObj.id;
  const img = document.getElementById('crop-image');
  
  // Create a new image to load the source and get dimensions
  const tempImg = new Image();
  tempImg.onload = () => {
    img.src = imageObj.props.src;
    cropSelection = { x: 0, y: 0, w: tempImg.naturalWidth, h: tempImg.naturalHeight };
    updateCropSelection();
    document.getElementById('crop-overlay').style.display = 'flex';
  };
  tempImg.src = imageObj.props.src;
}

/**
 * Close crop modal
 * @param {boolean} save - Whether to save changes
 */
function closeCropModal(save = false) {
  if (save && croppingImageId && window.findById && window.commitAppliedChange) {
    const o = window.findById(croppingImageId);
    if (o) {
      const img = document.getElementById('crop-image');
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      
      canvas.width = cropSelection.w;
      canvas.height = cropSelection.h;
      
      ctx.drawImage(img, 
        cropSelection.x, cropSelection.y, cropSelection.w, cropSelection.h,
        0, 0, cropSelection.w, cropSelection.h
      );
      
      const croppedDataUrl = canvas.toDataURL('image/png');
      
      // Update the image object with cropped version
      const prev = { src: o.props.src, w: o.props.w, h: o.props.h };
      const next = { src: croppedDataUrl, w: cropSelection.w, h: cropSelection.h };
      o.props.src = croppedDataUrl;
      o.props.w = cropSelection.w;
      o.props.h = cropSelection.h;
      window.commitAppliedChange({ type: "updateProps", id: o.id, prev, next });
    }
  }
  document.getElementById('crop-overlay').style.display = 'none';
  croppingImageId = null;
}

/**
 * Initialize crop modal event listeners
 */
function initializeCropModal() {
  const cropSave = document.getElementById('crop-save');
  const cropCancel = document.getElementById('crop-cancel');
  const cropOverlay = document.getElementById('crop-overlay');
  const cropSelection = document.getElementById('crop-selection');
  
  if (cropSave) {
    cropSave.addEventListener('click', () => closeCropModal(true));
  }
  
  if (cropCancel) {
    cropCancel.addEventListener('click', () => closeCropModal(false));
  }
  
  if (cropOverlay) {
    cropOverlay.addEventListener('click', (e) => { 
      if (e.target === cropOverlay) closeCropModal(false); 
    });
  }
  
  // Add keyboard support for crop modal
  document.addEventListener('keydown', (e) => {
    if (document.getElementById('crop-overlay').style.display === 'flex') {
      if (e.key === 'Escape') {
        closeCropModal(false);
      } else if (e.key === 'Enter') {
        closeCropModal(true);
      }
    }
  });
  
  // Crop selection dragging
  if (cropSelection) {
    cropSelection.addEventListener('mousedown', (e) => {
      isDraggingCrop = true;
      cropDragStart = { x: e.clientX, y: e.clientY };
      e.preventDefault();
    });
  }
  
  // Crop handle resizing
  document.querySelectorAll('.crop-handle').forEach(handle => {
    handle.addEventListener('mousedown', (e) => {
      isResizingCrop = true;
      resizeHandle = e.target.dataset.handle;
      cropDragStart = { x: e.clientX, y: e.clientY };
      e.preventDefault();
      e.stopPropagation();
    });
  });
  
  // Global mouse move and up for crop
  document.addEventListener('mousemove', (e) => {
    if (!isDraggingCrop && !isResizingCrop) return;
    
    const img = document.getElementById('crop-image');
    if (!img) return;
    
    const scaleX = img.naturalWidth / img.clientWidth;
    const scaleY = img.naturalHeight / img.clientHeight;
    const deltaX = (e.clientX - cropDragStart.x) * scaleX;
    const deltaY = (e.clientY - cropDragStart.y) * scaleY;
    
    if (isDraggingCrop) {
      cropSelection.x = Math.max(0, Math.min(img.naturalWidth - cropSelection.w, cropSelection.x + deltaX));
      cropSelection.y = Math.max(0, Math.min(img.naturalHeight - cropSelection.h, cropSelection.y + deltaY));
    } else if (isResizingCrop && resizeHandle) {
      const minSize = 10;
      if (resizeHandle.includes('n')) {
        const newY = Math.max(0, cropSelection.y + deltaY);
        const newH = Math.max(minSize, cropSelection.h - (newY - cropSelection.y));
        cropSelection.y = newY;
        cropSelection.h = newH;
      }
      if (resizeHandle.includes('s')) {
        cropSelection.h = Math.max(minSize, cropSelection.h + deltaY);
      }
      if (resizeHandle.includes('w')) {
        const newX = Math.max(0, cropSelection.x + deltaX);
        const newW = Math.max(minSize, cropSelection.w - (newX - cropSelection.x));
        cropSelection.x = newX;
        cropSelection.w = newW;
      }
      if (resizeHandle.includes('e')) {
        cropSelection.w = Math.max(minSize, cropSelection.w + deltaX);
      }
      
      // Ensure selection stays within image bounds
      cropSelection.x = Math.max(0, Math.min(img.naturalWidth - cropSelection.w, cropSelection.x));
      cropSelection.y = Math.max(0, Math.min(img.naturalHeight - cropSelection.h, cropSelection.y));
      cropSelection.w = Math.min(cropSelection.w, img.naturalWidth - cropSelection.x);
      cropSelection.h = Math.min(cropSelection.h, img.naturalHeight - cropSelection.y);
    }
    
    cropDragStart = { x: e.clientX, y: e.clientY };
    updateCropSelection();
  });
  
  document.addEventListener('mouseup', () => {
    isDraggingCrop = false;
    isResizingCrop = false;
    resizeHandle = null;
  });
}

/**
 * Initialize image upload input
 */
function initializeImageUpload() {
  const imageUpload = document.getElementById('image-upload');
  if (imageUpload) {
    imageUpload.addEventListener('change', (e) => {
      const file = e.target.files?.[0];
      if (file && window.addObject) {
        handleImageUpload(file, (imageProps) => {
          const BASE_OBJECT_LAYER = window.BASE_OBJECT_LAYER || 0;
          const nextObjectId = window.nextObjectId || 1;
          
          window.addObject({
            id: nextObjectId,
            type: 'image',
            layer: BASE_OBJECT_LAYER,
            props: imageProps
          });
          
          if (window.nextObjectId !== undefined) {
            window.nextObjectId++;
          }
        });
      }
    });
  }
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    initializeCropModal();
    initializeImageUpload();
  });
} else {
  initializeCropModal();
  initializeImageUpload();
}

// Export for use in main whiteboard
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    compressImage,
    handleImageUpload,
    handleClipboardImage,
    openCropModal,
    closeCropModal,
    updateCropSelection,
    initializeCropModal,
    initializeImageUpload
  };
}
