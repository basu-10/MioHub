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

    # Relations
    messages = db.relationship('ChatMessage', backref='session', lazy=True, cascade='all, delete-orphan')
    memories = db.relationship('ChatMemory', backref='session', lazy=True, cascade='all, delete-orphan')

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

