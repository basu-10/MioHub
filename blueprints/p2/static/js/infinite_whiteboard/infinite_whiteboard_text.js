/**
 * Infinite Whiteboard Text Module
 * Handles direct canvas text input with inline editing
 */

(function(window) {
    'use strict';

    window.InfiniteWhiteboard = window.InfiniteWhiteboard || {};
    const IWB = window.InfiniteWhiteboard;

    // Text editing state
    let textEditingActive = false;
    let textEditingObject = null;
    let textEditingPosition = null;
    let textInputElement = null;
    let textCursor = 0;
    let textSelectionStart = null;
    let textSelectionEnd = null;

    // Cursor blink state and timer
    let cursorBlinkState = true;
    let cursorBlinkTimer = null;

    /**
     * Start cursor blink animation
     */
    function startCursorBlink() {
        stopCursorBlink();
        cursorBlinkState = true;
        
        cursorBlinkTimer = setInterval(() => {
            cursorBlinkState = !cursorBlinkState;
            if (typeof IWB.requestRender === 'function') {
                IWB.requestRender();
            }
        }, 500); // Blink every 500ms
    }

    /**
     * Stop cursor blink animation
     */
    function stopCursorBlink() {
        if (cursorBlinkTimer) {
            clearInterval(cursorBlinkTimer);
            cursorBlinkTimer = null;
        }
        cursorBlinkState = true;
    }

    /**
     * Get text editing object (for toolbar state updates)
     */
    IWB.getTextEditingObject = function() {
        return textEditingObject;
    };

    /**
     * Update text dimensions (exposed for external use)
     */
    IWB.updateTextDimensions = updateTextDimensions;

    // Store original text for undo tracking
    let originalTextContent = null;

    /**
     * Start text editing at world position
     */
    IWB.startTextEditing = function(worldX, worldY, existingTextObj = null) {
        console.log('[TEXT] Starting text editing at', worldX, worldY);
        
        if (textEditingActive) {
            IWB.finishTextEditing();
        }

        textEditingActive = true;
        textEditingPosition = { x: worldX, y: worldY };
        originalTextContent = null; // Reset for new editing session
        
        if (existingTextObj) {
            // Editing existing text object
            textEditingObject = existingTextObj;
            // Store original text for undo tracking
            originalTextContent = existingTextObj.text || '';
            textCursor = existingTextObj.text ? existingTextObj.text.length : 0;
        } else {
            // Creating new text object
            textEditingObject = {
                type: 'text',
                text: '',
                x: worldX,
                y: worldY,
                fontSize: IWB.size * 6 || 18, // Scale from brush size
                color: IWB.color || '#14b8a6', // Use current toolbar color (teal by default)
                fontFamily: 'sf, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif',
                width: null, // Auto-width initially
                height: null,
                align: 'left',
                bold: false,
                italic: false
            };
            textCursor = 0;
        }

        // Create invisible input element for keyboard handling
        createTextInputElement();
        
        // Start cursor blink animation
        startCursorBlink();
        
        return textEditingObject;
    };

    /**
     * Create invisible HTML input for keyboard events
     */
    function createTextInputElement() {
        if (textInputElement) {
            textInputElement.remove();
        }

        textInputElement = document.createElement('textarea');
        textInputElement.style.position = 'fixed';
        textInputElement.style.left = '-9999px';
        textInputElement.style.top = '-9999px';
        textInputElement.style.opacity = '0';
        textInputElement.style.pointerEvents = 'none';
        textInputElement.style.width = '1px';
        textInputElement.style.height = '1px';
        textInputElement.value = textEditingObject.text || '';
        
        // Handle text input
        textInputElement.addEventListener('input', (e) => {
            if (!textEditingActive || !textEditingObject) return;
            textEditingObject.text = e.target.value;
            textCursor = e.target.selectionStart || textEditingObject.text.length;
            
            // Auto-calculate dimensions
            updateTextDimensions(textEditingObject);
            
            if (typeof IWB.requestRender === 'function') {
                IWB.requestRender();
            }
        });

        // Handle cursor position changes
        textInputElement.addEventListener('click', () => {
            if (textInputElement && textEditingActive) {
                textCursor = textInputElement.selectionStart || 0;
            }
        });
        
        textInputElement.addEventListener('keyup', () => {
            if (textInputElement && textEditingActive) {
                textCursor = textInputElement.selectionStart || 0;
            }
        });

        document.body.appendChild(textInputElement);
        
        // Focus with a slight delay to ensure it's attached
        setTimeout(() => {
            if (textInputElement) {
                textInputElement.focus();
                textInputElement.setSelectionRange(textCursor, textCursor);
            }
        }, 10);
    }

    /**
     * Calculate text dimensions for proper bounding box
     * Supports word wrapping - wraps at 10 words per line
     */
    function updateTextDimensions(textObj) {
        if (!textObj || !textObj.text) {
            textObj.width = 20;
            textObj.height = textObj.fontSize * 1.2;
            return;
        }

        // Create temporary canvas for measurement
        const tempCanvas = document.createElement('canvas');
        const tempCtx = tempCanvas.getContext('2d');
        
        const fontStyle = `${textObj.italic ? 'italic ' : ''}${textObj.bold ? 'bold ' : ''}${textObj.fontSize}px ${textObj.fontFamily}`;
        tempCtx.font = fontStyle;
        
        const lines = textObj.text.split('\n');
        let wrappedLines = [];
        let maxWidth = 0;
        
        // Apply word wrapping: 10 words per line
        const WORDS_PER_LINE = 10;
        
        lines.forEach(line => {
            // Handle empty lines
            if (!line || line.trim() === '') {
                wrappedLines.push('');
                return;
            }
            
            const words = line.split(' ').filter(w => w); // Filter out empty strings
            
            // Split into chunks of 10 words
            for (let i = 0; i < words.length; i += WORDS_PER_LINE) {
                const chunk = words.slice(i, i + WORDS_PER_LINE).join(' ');
                wrappedLines.push(chunk);
                const metrics = tempCtx.measureText(chunk);
                maxWidth = Math.max(maxWidth, metrics.width);
            }
        });
        
        // Store wrapped lines for rendering
        textObj.wrappedLines = wrappedLines;
        
        textObj.width = maxWidth + 8; // Add padding
        textObj.height = wrappedLines.length * textObj.fontSize * 1.4; // Line height multiplier
    }

    /**
     * Finish text editing and commit changes
     */
    IWB.finishTextEditing = function() {
        if (!textEditingActive) return null;
        
        console.log('[TEXT] Finishing text editing');
        
        // Stop cursor blink animation
        stopCursorBlink();
        
        const finalTextObj = textEditingObject;
        
        // Remove empty text objects
        if (!finalTextObj.text || finalTextObj.text.trim() === '') {
            textEditingActive = false;
            textEditingObject = null;
            textEditingPosition = null;
            originalTextContent = null;
            
            if (textInputElement) {
                textInputElement.remove();
                textInputElement = null;
            }
            
            return null;
        }

        // Track text content changes for undo/redo
        if (originalTextContent !== null && originalTextContent !== finalTextObj.text) {
            // Text was edited (not newly created)
            if (typeof IWB.addToUndoStack === 'function') {
                IWB.addToUndoStack({
                    type: 'textEdit',
                    objectId: finalTextObj.id,
                    oldText: originalTextContent,
                    newText: finalTextObj.text
                });
                console.log('[TEXT] Recorded text edit for undo:', {
                    oldLength: originalTextContent.length,
                    newLength: finalTextObj.text.length
                });
            }
        }

        // Final dimension update
        updateTextDimensions(finalTextObj);
        
        // Clean up
        textEditingActive = false;
        textEditingObject = null;
        textEditingPosition = null;
        originalTextContent = null;
        
        if (textInputElement) {
            textInputElement.remove();
            textInputElement = null;
        }
        
        return finalTextObj;
    };

    /**
     * Cancel text editing without committing
     */
    IWB.cancelTextEditing = function() {
        console.log('[TEXT] Canceling text editing');
        
        // Stop cursor blink animation
        stopCursorBlink();
        
        textEditingActive = false;
        textEditingObject = null;
        textEditingPosition = null;
        
        if (textInputElement) {
            textInputElement.remove();
            textInputElement = null;
        }
    };

    /**
     * Check if text editing is active
     */
    IWB.isTextEditing = function() {
        return textEditingActive;
    };

    /**
     * Get current text editing object
     */
    IWB.getCurrentTextObject = function() {
        return textEditingObject;
    };

    /**
     * Draw text object on canvas
     * Uses wrapped lines if available (when maxWidth is set)
     */
    IWB.drawTextObject = function(ctx, textObj) {
        if (!textObj || textObj.type !== 'text') return;
        
        ctx.save();
        
        const fontStyle = `${textObj.italic ? 'italic ' : ''}${textObj.bold ? 'bold ' : ''}${textObj.fontSize || 18}px ${textObj.fontFamily || 'sans-serif'}`;
        ctx.font = fontStyle;
        ctx.fillStyle = textObj.color || '#14b8a6'; // Teal default
        ctx.textAlign = textObj.align || 'left';
        ctx.textBaseline = 'top';
        
        // Use wrapped lines if available, otherwise split by newlines
        const lines = textObj.wrappedLines || (textObj.text || '').split('\n');
        const lineHeight = (textObj.fontSize || 18) * 1.4;
        
        lines.forEach((line, index) => {
            const y = textObj.y + (index * lineHeight);
            ctx.fillText(line, textObj.x, y);
        });
        
        ctx.restore();
    };

    /**
     * Draw text editing cursor (blinking cursor when editing)
     */
    IWB.drawTextCursor = function(ctx) {
        if (!textEditingActive || !textEditingObject) return;
        
        ctx.save();
        
        const fontStyle = `${textEditingObject.italic ? 'italic ' : ''}${textEditingObject.bold ? 'bold ' : ''}${textEditingObject.fontSize || 18}px ${textEditingObject.fontFamily || 'sans-serif'}`;
        ctx.font = fontStyle;
        
        const text = textEditingObject.text || '';
        // Use wrapped lines if available, otherwise split by newlines
        const lines = textEditingObject.wrappedLines || text.split('\n');
        const lineHeight = (textEditingObject.fontSize || 18) * 1.4;
        
        // Draw the actual text with current color
        ctx.fillStyle = textEditingObject.color || '#14b8a6';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';
        
        lines.forEach((line, index) => {
            const y = textEditingObject.y + (index * lineHeight);
            ctx.fillText(line, textEditingObject.x, y);
        });
        
        // Find cursor line and position
        let cursorLine = 0;
        let cursorCharInLine = textCursor;
        let charCount = 0;
        
        // If using wrapped lines, we need to map cursor position differently
        if (textEditingObject.wrappedLines) {
            // Map cursor position to wrapped line
            for (let i = 0; i < lines.length; i++) {
                if (charCount + lines[i].length + 1 > textCursor) {
                    cursorLine = i;
                    cursorCharInLine = textCursor - charCount;
                    break;
                }
                charCount += lines[i].length + 1; // +1 for space between words
            }
        } else {
            // Original newline-based logic
            for (let i = 0; i < lines.length; i++) {
                if (charCount + lines[i].length + 1 > textCursor) {
                    cursorLine = i;
                    cursorCharInLine = textCursor - charCount;
                    break;
                }
                charCount += lines[i].length + 1; // +1 for newline
            }
        }
        
        const textBeforeCursor = lines[cursorLine]?.substring(0, cursorCharInLine) || '';
        const cursorX = textEditingObject.x + ctx.measureText(textBeforeCursor).width;
        const cursorY = textEditingObject.y + (cursorLine * lineHeight);
        
        // Blinking cursor effect (controlled by interval timer)
        if (cursorBlinkState) {
            ctx.strokeStyle = textEditingObject.color || '#14b8a6';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(cursorX, cursorY);
            ctx.lineTo(cursorX, cursorY + (textEditingObject.fontSize || 18));
            ctx.stroke();
        }
        
        // Draw text box outline when editing
        ctx.strokeStyle = '#14b8a6';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);
        ctx.strokeRect(
            textEditingObject.x - 4,
            textEditingObject.y - 2,
            (textEditingObject.width || 20) + 8,
            (textEditingObject.height || lineHeight) + 4
        );
        ctx.setLineDash([]);
        
        ctx.restore();
    };

    /**
     * Check if a point is inside a text object
     */
    IWB.isPointInText = function(worldX, worldY, textObj) {
        if (!textObj || textObj.type !== 'text') return false;
        
        const bounds = IWB.getTextBounds(textObj);
        if (!bounds) return false;
        
        return worldX >= bounds.x &&
               worldX <= bounds.x + bounds.w &&
               worldY >= bounds.y &&
               worldY <= bounds.y + bounds.h;
    };

    /**
     * Get bounding box for text object
     */
    IWB.getTextBounds = function(textObj) {
        if (!textObj || textObj.type !== 'text') return null;
        
        // Ensure dimensions are calculated
        if (!textObj.width || !textObj.height) {
            updateTextDimensions(textObj);
        }
        
        return {
            x: textObj.x - 4,
            y: textObj.y - 2,
            w: (textObj.width || 20) + 8,
            h: (textObj.height || 20) + 4
        };
    };

    /**
     * Handle keyboard input for text editing
     */
    IWB.handleTextKeydown = function(e) {
        if (!textEditingActive || !textEditingObject) return false;
        
        // Let the textarea handle most input
        // Only intercept special keys we need
        
        if (e.key === 'Escape') {
            e.preventDefault();
            IWB.cancelTextEditing();
            return true;
        }
        
        // Allow default behavior for text input element
        return false;
    };

    /**
     * Update text object formatting
     */
    IWB.setTextBold = function(bold) {
        if (textEditingObject) {
            textEditingObject.bold = bold;
            updateTextDimensions(textEditingObject);
        }
    };

    IWB.setTextItalic = function(italic) {
        if (textEditingObject) {
            textEditingObject.italic = italic;
            updateTextDimensions(textEditingObject);
        }
    };

    IWB.setTextFontSize = function(fontSize) {
        if (textEditingObject) {
            textEditingObject.fontSize = fontSize;
            updateTextDimensions(textEditingObject);
        }
    };

    IWB.setTextColor = function(color) {
        if (textEditingObject) {
            textEditingObject.color = color;
        }
    };
    
    /**
     * Update text color from toolbar color picker
     * Called when color picker changes while text editing is active
     */
    IWB.updateTextColorFromToolbar = function(color) {
        if (textEditingActive && textEditingObject) {
            textEditingObject.color = color;
            if (typeof IWB.requestRender === 'function') {
                IWB.requestRender();
            }
        }
    };

    /**
     * Move text object
     */
    IWB.moveTextObject = function(textObj, dx, dy) {
        if (!textObj || textObj.type !== 'text') return;
        textObj.x += dx;
        textObj.y += dy;
    };

    console.log('Infinite Whiteboard Text module loaded');

})(window);
