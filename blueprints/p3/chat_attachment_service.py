"""
Service layer for chat attachment operations
Handles file storage, summarization, and folder management

Phase 3: Backend Routes & Services
Created: December 30, 2024
"""
from extensions import db
from blueprints.p2.models import File, Folder
from blueprints.p3.models import ChatSession, ChatAttachment
from utilities_main import (
    calculate_file_hash, parse_document_for_chat, 
    get_file_type_from_extension, update_user_data_size
)
from providers import LLMClient
from flask import current_app
from datetime import datetime
import os
import tempfile


def get_or_create_session_folder(session_id, user_id):
    """
    Get or create MioSpace folder for chat session
    Path: /ChatSessions/session_{id}_{date}/
    
    Args:
        session_id: ChatSession ID
        user_id: User ID (for folder ownership)
        
    Returns:
        Folder: Session folder object
        
    Raises:
        ValueError: If session not found
    """
    session = ChatSession.query.get(session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")
    
    # Return existing folder if already created
    if session.session_folder_id:
        return Folder.query.get(session.session_folder_id)
    
    # Find or create root ChatSessions folder
    chat_sessions_root = Folder.query.filter_by(
        user_id=user_id,
        name='ChatSessions',
        parent_id=None
    ).first()
    
    if not chat_sessions_root:
        chat_sessions_root = Folder(
            user_id=user_id,
            name='ChatSessions',
            parent_id=None,
            description='Auto-generated folders for chat session attachments and exports'
        )
        db.session.add(chat_sessions_root)
        db.session.flush()
    
    # Create session-specific folder
    session_date = session.created_at.strftime('%Y-%m-%d')
    folder_name = f"session_{session_id}_{session_date}"
    
    session_folder = Folder(
        user_id=user_id,
        name=folder_name,
        parent_id=chat_sessions_root.id,
        description=f"Attachments and exports for chat session: {session.title}"
    )
    db.session.add(session_folder)
    db.session.flush()
    
    # Link folder to session
    session.session_folder_id = session_folder.id
    db.session.commit()
    
    return session_folder


def check_duplicate_attachment(file_hash, user_id):
    """
    Check if file with same hash already exists for user
    
    Args:
        file_hash: SHA256 hash of file
        user_id: User ID
        
    Returns:
        File: Existing File record or None
    """
    if not file_hash:
        return None
    
    # Find existing attachment with same hash
    existing_attachment = ChatAttachment.query.join(
        ChatSession
    ).filter(
        ChatSession.user_id == user_id,
        ChatAttachment.file_hash == file_hash
    ).first()
    
    if existing_attachment:
        return existing_attachment.file
    
    return None


def create_attachment_from_upload(session_id, user_id, uploaded_file):
    """
    Process uploaded file and create ChatAttachment record
    
    Args:
        session_id: ChatSession ID
        user_id: User ID
        uploaded_file: Werkzeug FileStorage object
        
    Returns:
        tuple: (ChatAttachment, bytes_added)
        
    Raises:
        ValueError: If session not found or file processing fails
    """
    # Get session folder
    session_folder = get_or_create_session_folder(session_id, user_id)
    
    # Create temp directory if it doesn't exist
    temp_dir = os.path.join(tempfile.gettempdir(), 'miohub_attachments')
    os.makedirs(temp_dir, exist_ok=True)
    
    # Save file temporarily to calculate hash
    temp_path = os.path.join(temp_dir, uploaded_file.filename)
    uploaded_file.save(temp_path)
    
    try:
        # Calculate hash for deduplication
        file_hash = calculate_file_hash(temp_path)
        upload_type, db_type, language = get_file_type_from_extension(uploaded_file.filename)
        file_size = os.path.getsize(temp_path)
        
        # Check for duplicate
        existing_file = check_duplicate_attachment(file_hash, user_id)
        
        if existing_file:
            # Reuse existing file (zero storage cost)
            file_record = existing_file
            bytes_added = 0
        else:
            # Create new File record with mapped type
            # Determine content storage based on database type
            metadata = {
                'original_filename': uploaded_file.filename,
                'original_type': upload_type,  # Preserve original extension
            }
            
            if db_type == 'image':
                # Use existing image handling from p2
                from blueprints.p2.utils import save_uploaded_image_for_user
                image_filename, img_bytes = save_uploaded_image_for_user(temp_path, user_id)
                
                file_record = File(
                    owner_id=user_id,
                    folder_id=session_folder.id,
                    type='image',
                    title=uploaded_file.filename,
                    content_text=f"/static/uploads/images/{image_filename}",
                    metadata_json=metadata
                )
                bytes_added = img_bytes
                
            elif db_type == 'code':
                # Text/code files → content_text with language metadata
                with open(temp_path, 'r', encoding='utf-8', errors='ignore') as f:
                    file_content = f.read()
                
                metadata['language'] = language  # Monaco language identifier
                file_record = File(
                    owner_id=user_id,
                    folder_id=session_folder.id,
                    type='code',
                    title=uploaded_file.filename,
                    content_text=file_content,
                    metadata_json=metadata
                )
                bytes_added = file_size
                
            elif db_type == 'pdf':
                # PDF → content_blob (view only)
                with open(temp_path, 'rb') as f:
                    file_content = f.read()
                
                metadata['mime_type'] = 'application/pdf'
                file_record = File(
                    owner_id=user_id,
                    folder_id=session_folder.id,
                    type='pdf',
                    title=uploaded_file.filename,
                    content_blob=file_content,
                    metadata_json=metadata
                )
                bytes_added = file_size
                
            elif db_type in ['proprietary_note', 'table']:
                # Documents requiring conversion (docx, xlsx) → store as blob temporarily
                # TODO: Implement proper conversion to note/table formats
                with open(temp_path, 'rb') as f:
                    file_content = f.read()
                
                metadata['needs_conversion'] = True
                metadata['target_type'] = db_type
                metadata['mime_type'] = f'application/{upload_type}'
                
                file_record = File(
                    owner_id=user_id,
                    folder_id=session_folder.id,
                    type=db_type,
                    title=uploaded_file.filename,
                    content_blob=file_content,  # Temporary blob storage
                    metadata_json=metadata
                )
                bytes_added = file_size
                
            else:
                # Fallback: store as blob
                with open(temp_path, 'rb') as f:
                    file_content = f.read()
                
                file_record = File(
                    owner_id=user_id,
                    folder_id=session_folder.id,
                    type=db_type,
                    title=uploaded_file.filename,
                    content_blob=file_content,
                    metadata_json=metadata
                )
                bytes_added = file_size
            
            db.session.add(file_record)
            db.session.flush()
        
        # Create ChatAttachment link (store upload_type for UI display)
        attachment = ChatAttachment(
            session_id=session_id,
            file_id=file_record.id,
            original_filename=uploaded_file.filename,
            file_type=upload_type,  # Use upload_type for UI/icon display
            file_size=file_size,
            file_hash=file_hash,
            summary_status='pending'
        )
        db.session.add(attachment)
        
        # Update user storage quota
        if bytes_added > 0:
            from blueprints.p2.models import User
            user = User.query.get(user_id)
            update_user_data_size(user, bytes_added)
        
        db.session.commit()
        return attachment, bytes_added
    
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)


def create_summary_for_attachment(attachment_id):
    """
    Parse document and create summary using summarizer LLM
    
    Args:
        attachment_id: ChatAttachment ID
        
    Returns:
        File: Summary file record
        
    Raises:
        ValueError: If attachment not found
        Exception: If parsing or summarization fails
    """
    attachment = ChatAttachment.query.get(attachment_id)
    if not attachment:
        raise ValueError(f"Attachment {attachment_id} not found")
    
    # Update status to processing
    attachment.summary_status = 'processing'
    db.session.commit()
    
    try:
        # Get file path
        file_record = attachment.file
        
        # For blob storage, write to temp file
        if file_record.content_blob:
            temp_dir = os.path.join(tempfile.gettempdir(), 'miohub_attachments')
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, f"chat_attachment_{attachment_id}.tmp")
            with open(temp_path, 'wb') as f:
                f.write(file_record.content_blob)
            file_path = temp_path
        elif file_record.content_text and file_record.type == 'image':
            # Image stored as path
            file_path = os.path.join(current_app.root_path, file_record.content_text.lstrip('/'))
        else:
            raise ValueError(f"Cannot determine file path for attachment {attachment_id}")
        
        # Parse document
        text_content, parse_method = parse_document_for_chat(file_path, attachment.file_type)
        
        # Clean up temp file if created
        if file_record.content_blob and os.path.exists(temp_path):
            os.remove(temp_path)
        
        # Truncate if too long (max 50K characters for summarizer)
        import config
        max_chars = getattr(config, 'MAX_SUMMARY_INPUT_CHARS', 50000)
        if len(text_content) > max_chars:
            text_content = text_content[:max_chars] + "\n\n[Content truncated for summarization]"
        
        # Call summarizer LLM
        llm_client = LLMClient(use_summarizer=True)
        summary_prompt = f"""Summarize the following document concisely. Include:
- Main topics/themes
- Key points and findings
- Important details
- Any actionable items or conclusions

Document content:
{text_content}
"""
        
        summary_text = llm_client.chat([{"role": "user", "content": summary_prompt}])
        
        # Create summary file in MioSpace
        session = attachment.session
        folder = Folder.query.get(session.session_folder_id)
        
        summary_file = File(
            owner_id=session.user_id,
            folder_id=folder.id,
            type='markdown',
            title=f"{attachment.original_filename}_summary.md",
            content_text=summary_text,
            metadata_json={
                'source_attachment_id': attachment_id,
                'parse_method': parse_method,
                'generated_at': datetime.utcnow().isoformat()
            }
        )
        db.session.add(summary_file)
        db.session.flush()
        
        # Update attachment record
        attachment.summary_file_id = summary_file.id
        attachment.summary_status = 'completed'
        attachment.summarized_at = datetime.utcnow()
        db.session.commit()
        
        return summary_file
    
    except Exception as e:
        attachment.summary_status = 'failed'
        attachment.summary_error = str(e)
        db.session.commit()
        raise
