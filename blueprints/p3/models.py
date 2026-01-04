# p3/models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from extensions import db
from sqlalchemy.dialects.mysql import JSON, LONGTEXT


class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False, default='New chat')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # MioSpace folder integration
    session_folder_id = db.Column(db.Integer, db.ForeignKey('folder.id'), nullable=True)

    # Relations
    messages = db.relationship('ChatMessage', backref='session', lazy=True, cascade='all, delete-orphan')
    memories = db.relationship('ChatMemory', backref='session', lazy=True, cascade='all, delete-orphan')
    session_folder = db.relationship('Folder', backref='chat_sessions')

    user = db.relationship('User', backref=db.backref('chat_sessions', cascade='all, delete-orphan'))


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id'), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(LONGTEXT(collation='utf8mb4_unicode_ci'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChatMemory(db.Model):
    __tablename__ = 'chat_memories'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id'), nullable=False)
    text = db.Column(LONGTEXT(collation='utf8mb4_unicode_ci'), nullable=False)
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChatAttachment(db.Model):
    """Links chat sessions to file attachments with summarization support"""
    __tablename__ = 'chat_attachments'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id'), nullable=False, index=True)
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=False)
    
    # Summary management
    summary_file_id = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=True)
    summary_status = db.Column(db.String(20), default='pending')  # pending, processing, completed, failed
    summary_error = db.Column(db.Text, nullable=True)  # Error message if failed
    original_content_hash = db.Column(db.String(64), nullable=True, index=True)
    summary_is_stale = db.Column(db.Boolean, default=False, nullable=False)
    word_count = db.Column(db.Integer, nullable=True)
    summary_word_count = db.Column(db.Integer, nullable=True)
    
    # Metadata (denormalized for performance)
    original_filename = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)  # pdf, docx, image, xlsx, etc.
    file_size = db.Column(db.Integer, nullable=False)  # Bytes
    file_hash = db.Column(db.String(64), index=True)  # SHA256 for deduplication
    file_path = db.Column(db.String(500), nullable=True)  # Disk path for non-DB storage (e.g., PDFs)
    
    # Timestamps
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    summarized_at = db.Column(db.DateTime, nullable=True)
    
    # Context control
    is_active = db.Column(db.Boolean, default=True, nullable=False)  # Include in chat context?
    
    # Relationships
    session = db.relationship('ChatSession', backref=db.backref('attachments', lazy='dynamic'))
    file = db.relationship('File', foreign_keys=[file_id], backref='chat_attachments')
    summary_file = db.relationship('File', foreign_keys=[summary_file_id])
    
    def get_display_name(self):
        """Returns shortened filename for UI display"""
        name = self.original_filename
        if len(name) > 30:
            return name[:27] + '...'
        return name
    
    def get_file_icon(self):
        """Returns Font Awesome icon class for file type"""
        icons = {
            'pdf': 'fa-file-pdf',
            'docx': 'fa-file-word',
            'doc': 'fa-file-word',
            'xlsx': 'fa-file-excel',
            'xls': 'fa-file-excel',
            'image': 'fa-file-image',
            'py': 'fa-file-code',
            'js': 'fa-file-code',
            'html': 'fa-file-code',
            'css': 'fa-file-code',
            'ts': 'fa-file-code',
            'md': 'fa-file-alt',
            'txt': 'fa-file-alt',
            'yaml': 'fa-file-alt',
            'json': 'fa-file-code',
        }
        return icons.get(self.file_type, 'fa-file')

