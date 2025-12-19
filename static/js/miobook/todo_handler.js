/**
 * Todo Block Handler
 * Handles checkbox lists with drag-reorder
 */

class TodoHandler {
    constructor() {
        this.sortables = new Map(); // blockId -> sortable instance
    }
    
    initialize(blockEl) {
        const todoList = blockEl.querySelector('.todo-list');
        if (!todoList) return;
        
        const blockId = blockEl.dataset.blockId;
        
        // Load existing todos
        try {
            const dataContent = todoList.dataset.content;
            if (dataContent && dataContent !== '""' && dataContent !== 'null' && dataContent !== '[]') {
                const todos = JSON.parse(dataContent);
                if (Array.isArray(todos) && todos.length > 0) {
                    todoList.innerHTML = '';
                    todos.forEach(todo => {
                        this.addItemElement(todoList, todo.text, todo.completed);
                    });
                }
            }
        } catch (e) {
            console.warn('[Todo] Could not parse content:', e);
        }
        
        // If empty, add one item
        if (todoList.children.length === 0) {
            this.addItemElement(todoList, '', false);
        }
        
        // Initialize sortable
        const sortable = Sortable.create(todoList, {
            animation: 150,
            ghostClass: 'sortable-ghost',
            handle: '.todo-item',
            onEnd: () => {
                if (window.MioBook) {
                    window.MioBook.markDirty();
                }
            }
        });
        
        this.sortables.set(blockId, sortable);
    }
    
    addItem(button) {
        const blockEl = button.closest('.block-item');
        const todoList = blockEl.querySelector('.todo-list');
        this.addItemElement(todoList, '', false);
        
        if (window.MioBook) {
            window.MioBook.markDirty();
        }
    }
    
    addItemElement(todoList, text, completed) {
        const itemHTML = `
            <div class="todo-item">
                <input type="checkbox" class="todo-checkbox" ${completed ? 'checked' : ''}>
                <input type="text" class="todo-text" value="${this.escapeHtml(text)}" placeholder="Task...">
                <button type="button" class="todo-delete" onclick="window.TodoHandler.deleteItem(this)">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        todoList.insertAdjacentHTML('beforeend', itemHTML);
        
        // Focus the new input
        const newItem = todoList.lastElementChild;
        const input = newItem.querySelector('.todo-text');
        if (input) {
            input.focus();
        }
        
        // Add change listener
        const checkbox = newItem.querySelector('.todo-checkbox');
        if (checkbox) {
            checkbox.addEventListener('change', () => {
                if (window.MioBook) {
                    window.MioBook.markDirty();
                }
            });
        }
        if (input) {
            input.addEventListener('input', () => {
                if (window.MioBook) {
                    window.MioBook.markDirty();
                }
            });
        }
    }
    
    deleteItem(button) {
        const item = button.closest('.todo-item');
        const todoList = item.parentElement;
        
        item.remove();
        
        // Keep at least one item
        if (todoList.children.length === 0) {
            this.addItemElement(todoList, '', false);
        }
        
        if (window.MioBook) {
            window.MioBook.markDirty();
        }
    }
    
    getContent(blockEl) {
        const todoList = blockEl.querySelector('.todo-list');
        if (!todoList) return [];
        
        const todos = [];
        const items = todoList.querySelectorAll('.todo-item');
        
        items.forEach(item => {
            const checkbox = item.querySelector('.todo-checkbox');
            const textInput = item.querySelector('.todo-text');
            
            if (textInput) {
                todos.push({
                    text: textInput.value,
                    completed: checkbox ? checkbox.checked : false
                });
            }
        });
        
        return todos;
    }
    
    destroy(blockEl) {
        const blockId = blockEl.dataset.blockId;
        const sortable = this.sortables.get(blockId);
        
        if (sortable) {
            sortable.destroy();
            this.sortables.delete(blockId);
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Export to window
window.TodoHandler = new TodoHandler();
