# p2/models.py

'''
user_prefs column now stores:
{
  "theme": "flatly",
  "isPinned": false,
  "display": {
    "columns": 3,
    "view_mode": "grid",
    "card_size": "normal",
    "show_previews": true
  }
}
'''

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from extensions import db
from sqlalchemy.dialects.mysql import JSON, LONGTEXT, VARCHAR, TEXT
from sqlalchemy.orm import validates

# Valid file type discriminators
VALID_FILE_TYPES = {
    # Proprietary products (with proprietary_ prefix)
    'proprietary_note',              # MioNote (rich HTML editor)
    'proprietary_whiteboard',        # MioDraw (canvas drawing)
    'proprietary_blocks',            # MioBook (combined documents)
    'proprietary_infinite_whiteboard',  # Infinite Canvas
    'proprietary_graph',             # Graph knowledge workspace
    
    # Third-party integrations (no prefix)
    'markdown',     # Toast UI Editor (markdown and plain text)
    'code',         # Monaco Editor
    'todo',         # SortableJS
    'diagram',      # Monaco JSON
    'table',        # Luckysheet
    'blocks',       # Editor.js
    'timeline',     # Timeline with events
    
    # Binary/Upload types
    'pdf',          # PDF files (binary storage) (not yet implemented)
}


class GraphWorkspace(db.Model):
    """Graph workspace metadata linked to a File of type 'proprietary_graph'."""
    __tablename__ = 'graph_workspaces'

    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=False, unique=True, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    folder_id = db.Column(db.Integer, db.ForeignKey('folder.id'), nullable=True)
    settings_json = db.Column(JSON, default={})  # Canvas and view preferences
    metadata_json = db.Column(JSON, default={})  # Aux info (tags, theme)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    file = db.relationship('File', backref=db.backref('graph_workspace', uselist=False))
    owner = db.relationship('User')
    folder = db.relationship('Folder')


class GraphNode(db.Model):
    """Node within a graph workspace, representing a micro-workspace."""
    __tablename__ = 'graph_nodes'

    id = db.Column(db.Integer, primary_key=True)
    graph_id = db.Column(db.Integer, db.ForeignKey('graph_workspaces.id'), nullable=False, index=True)
    title = db.Column(VARCHAR(255, charset='utf8mb4', collation='utf8mb4_unicode_ci'), nullable=False)
    summary = db.Column(TEXT(charset='utf8mb4', collation='utf8mb4_unicode_ci'), nullable=True)
    position_json = db.Column(JSON, default={})  # {x, y}
    size_json = db.Column(JSON, default={})      # {w, h}
    style_json = db.Column(JSON, default={})     # colors, badges
    metadata_json = db.Column(JSON, default={})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    graph = db.relationship('GraphWorkspace', backref='nodes')


class GraphEdge(db.Model):
    """Directed edge between graph nodes."""
    __tablename__ = 'graph_edges'

    id = db.Column(db.Integer, primary_key=True)
    graph_id = db.Column(db.Integer, db.ForeignKey('graph_workspaces.id'), nullable=False, index=True)
    source_node_id = db.Column(db.Integer, db.ForeignKey('graph_nodes.id'), nullable=False, index=True)
    target_node_id = db.Column(db.Integer, db.ForeignKey('graph_nodes.id'), nullable=False, index=True)
    label = db.Column(db.String(255), nullable=True)
    edge_type = db.Column(db.String(50), default='directed')
    metadata_json = db.Column(JSON, default={})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    graph = db.relationship('GraphWorkspace', backref='edges')
    source_node = db.relationship('GraphNode', foreign_keys=[source_node_id])
    target_node = db.relationship('GraphNode', foreign_keys=[target_node_id])


class GraphNodeAttachment(db.Model):
    """Attachment linking nodes to files/folders/urls/tasks."""
    __tablename__ = 'graph_node_attachments'

    id = db.Column(db.Integer, primary_key=True)
    node_id = db.Column(db.Integer, db.ForeignKey('graph_nodes.id'), nullable=False, index=True)
    attachment_type = db.Column(db.String(32), nullable=False)  # file|folder|url|task
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=True)
    folder_id = db.Column(db.Integer, db.ForeignKey('folder.id'), nullable=True)
    url = db.Column(db.String(1000), nullable=True)
    metadata_json = db.Column(JSON, default={})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    node = db.relationship('GraphNode', backref='attachments')
    file = db.relationship('File', foreign_keys=[file_id])
    folder = db.relationship('Folder', foreign_keys=[folder_id])


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(128))
    password_hash = db.Column(db.String(256))  
    security_answer = db.Column(db.String(128))

    user_type = db.Column(db.String(20), nullable=False, default='guest')  # spelling must be exact 'user'(uncapped), 'guest'(50mb cap), 'admin'(uncapped), 'moderator', etc.
    total_data_size = db.Column(db.BigInteger, default=0) 

    user_prefs = db.Column(JSON, default={"theme": "flatly", "isPinned": False})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    profile_pic_url = db.Column(db.String(256))

    # Relations
    folders = db.relationship('Folder', backref='user', lazy=True, cascade='all, delete-orphan')

    @property
    def is_admin(self):
        return self.user_type == 'admin'


class Folder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    # Use TEXT (~64KB for MySQL TEXT) to allow longer folder descriptions without using LONGTEXT
    description = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('folder.id'), nullable=True)
    # is_root identifies the single home folder per user; root_key enforces uniqueness when is_root is true
    is_root = db.Column(db.Boolean, default=False, nullable=False, index=True)
    root_key = db.Column(
        db.Integer,
        db.Computed("CASE WHEN is_root THEN user_id ELSE NULL END", persisted=True),
        unique=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_modified = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent = db.relationship('Folder', remote_side=[id], backref='children')
    # Public visibility for folders: allow sharing entire folder trees
    is_public = db.Column(db.Boolean, default=False, nullable=False)

    __table_args__ = (
        db.CheckConstraint('NOT is_root OR parent_id IS NULL', name='ck_folder_root_parent_null'),
    )
    
    # Properties for templates to access specific file types
    @property
    def boards(self):
        """Return all whiteboards (Files with type='proprietary_whiteboard') in this folder."""
        return [f for f in self.files if f.type == 'proprietary_whiteboard']
    
    @property
    def notes(self):
        """Return all notes (Files with type='proprietary_note') in this folder."""
        return [f for f in self.files if f.type == 'proprietary_note']




class File(db.Model):
    """Universal content storage for future file types.
    
    Coexists with legacy Note/Board models during transition.
    Supports: markdown, PDFs, todos, diagrams, uploaded docs, and future content types.
    
    Content Storage Strategy:
    - Only ONE content column should be populated per record (based on type)
    - content_text: Plain text, markdown source
    - content_html: Rich formatted HTML (like current notes)
    - content_json: Structured data (canvas elements, diagrams, todos)
    - content_blob: Binary files (PDFs, images, uploaded documents)
    
    Metadata JSON Guidelines:
    - Store AUXILIARY info only (descriptions, UI state, file properties)
    - Never store primary content in metadata_json
    - Examples: {"description": "...", "file_size": 2048, "mime_type": "...", "is_pinned": false}
    """
    __tablename__ = 'files'
    
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    folder_id = db.Column(db.Integer, db.ForeignKey('folder.id'), nullable=True)
    
    # Type discriminator: 'markdown', 'pdf', 'todo', 'diagram', 'note', 'whiteboard', 'book', etc.
    type = db.Column(db.String(50), nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False)
    
    # Content storage columns (only one populated per record based on type)
    content_text = db.Column(db.Text, nullable=True)  # Plain text, markdown
    content_html = db.Column(LONGTEXT(collation='utf8mb4_unicode_ci'), nullable=True)  # Rich HTML
    content_json = db.Column(JSON, nullable=True)  # Structured data (canvas, diagrams, todos)
    content_blob = db.Column(db.LargeBinary, nullable=True)  # Binary files (PDFs, images)
    
    # Auxiliary metadata (NOT primary content)
    # Examples: display settings, file properties, UI state
    metadata_json = db.Column(JSON, default={})
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    last_modified = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    is_public = db.Column(db.Boolean, default=False, nullable=False)
    
    # Cached thumbnail for visual content types (whiteboards, diagrams, etc.)
    thumbnail_path = db.Column(db.String(500), nullable=True)
    
    # Relationships
    owner = db.relationship('User', backref='files', foreign_keys=[owner_id])
    folder = db.relationship('Folder', backref='files')
    
    def get_content(self):
        """Return the appropriate content field based on type."""
        if self.content_text is not None:
            return self.content_text
        elif self.content_html is not None:
            return self.content_html
        elif self.content_json is not None:
            return self.content_json
        elif self.content_blob is not None:
            return self.content_blob
        return None
    
    def get_content_size(self):
        """Calculate content size in bytes for storage quota tracking."""
        content = self.get_content()
        if content is None:
            return 0
        if isinstance(content, str):
            return len(content.encode('utf-8'))
        elif isinstance(content, bytes):
            return len(content)
        elif isinstance(content, (dict, list)):
            import json
            return len(json.dumps(content).encode('utf-8'))
        return 0
    
    @property
    def description(self):
        """Convenient access to description from metadata_json."""
        if self.metadata_json and isinstance(self.metadata_json, dict):
            return self.metadata_json.get('description', '')
        return ''
    
    @property
    def is_pinned(self):
        """Check if file is pinned from metadata_json."""
        if self.metadata_json and isinstance(self.metadata_json, dict):
            return self.metadata_json.get('is_pinned', False)
        return False
    
    @validates('type')
    def validate_type(self, key, value):
        """Validate file type is in allowed list."""
        if value not in VALID_FILE_TYPES:
            raise ValueError(f"Invalid file type: {value}. Must be one of: {', '.join(sorted(VALID_FILE_TYPES))}")
        return value


class Notification(db.Model):
    """System notifications for user activity tracking.
    
    Stores recent activity notifications (save operations, transfers, etc.)
    with automatic cleanup to maintain only the last 50 per user.
    """
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    message = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Type discriminator: 'save', 'transfer', 'delete', 'error', 'info', etc.
    type = db.Column(db.String(20), default='info', nullable=False)
    
    # Relationship
    user = db.relationship('User', backref='notifications')
    
    def to_dict(self):
        """Convert notification to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'type': self.type
        }
