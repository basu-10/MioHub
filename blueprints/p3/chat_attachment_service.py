"""
Service layer for chat attachment operations
Handles file storage, summarization, and folder management

Phase 3: Backend Routes & Services
Created: December 30, 2024
"""
from datetime import datetime
from pathlib import Path
import hashlib
import html
import os
import tempfile

from extensions import db
from blueprints.p2.models import File, Folder
from blueprints.p3.models import ChatSession, ChatAttachment, ChatMessage
from blueprints.p2.pdf_utils import save_pdf_for_user
from utilities_main import (
    calculate_content_size,
    calculate_file_hash,
    parse_document_for_chat,
    get_file_type_from_extension,
    update_user_data_size,
)
from providers import LLMClient
from flask import current_app


def convert_docx_to_note_html(file_path):
    """Convert a DOCX/DOC file to HTML paragraphs for MioNote.

    Returns a safe HTML string where each paragraph from the source document
    becomes a `<p>` element. Newlines are preserved as separate paragraphs.
    Raises the underlying parsing error so callers can decide on fallbacks.
    """
    text_content = parse_docx_to_text(file_path)
    # If primary extraction yields nothing, signal an error to trigger fallback
    if not text_content or not text_content.strip():
        raise ValueError("No extractable text found in DOCX/DOC file")

    paragraphs = [html.escape(line.strip()) for line in text_content.splitlines() if line.strip()]
    return "".join(f"<p>{para}</p>" for para in paragraphs) or "<p></p>"


def count_words(text: str) -> int:
    """Return a simple word count for threshold checks."""
    if not text:
        return 0
    return len(text.split())


def compute_text_hash(text: str | None) -> str | None:
    """Create a stable SHA256 hash for text content."""
    if text is None:
        return None
    hasher = hashlib.sha256()
    hasher.update(text.encode('utf-8', errors='ignore'))
    return hasher.hexdigest()


def build_summary_title(original_filename: str) -> str:
    """Generate the standardized summary filename."""
    return f"{original_filename}__summary.md"


def should_auto_summarize(attachment) -> bool:
    """Check if attachment needs automatic summarization based on word count threshold."""
    import config
    
    # Skip if already has summary or is processing
    if attachment.summary_status in ('completed', 'processing'):
        return False
    
    # Skip binary files that can't be easily parsed for text
    if attachment.file_type in ('image', 'pdf'):
        # PDFs can be summarized but are expensive; only manual for now
        return False
    
    # Get file record to check content size
    file_record = attachment.file
    if not file_record:
        return False
    
    # Extract text content for word counting
    text_content = None
    if file_record.content_text:
        text_content = file_record.content_text
    elif file_record.content_html:
        # Strip HTML tags for word counting
        import re
        text_content = re.sub(r'<[^>]+>', '', file_record.content_html)
    
    if not text_content:
        return False
    
    # Cache word count and check threshold
    word_count = count_words(text_content)
    attachment.word_count = word_count
    
    return word_count > config.SUMMARY_WORD_THRESHOLD


def trigger_auto_summarization(attachment_id: int):
    """Trigger background summarization for attachment (async using threading)."""
    import threading
    import logging
    
    logger = logging.getLogger(__name__)
    
    def background_summarize():
        """Background worker to create summary."""
        from flask import current_app
        from extensions import db as _db
        
        # Need app context for database operations
        with current_app.app_context():
            try:
                attachment = ChatAttachment.query.get(attachment_id)
                if not attachment:
                    logger.error(f"Attachment {attachment_id} not found for auto-summarization")
                    return
                
                # Double-check status to avoid race conditions
                if attachment.summary_status != 'pending':
                    logger.info(f"Attachment {attachment_id} already processing/completed")
                    return
                
                # Create summary
                create_summary_for_attachment(attachment_id)
                logger.info(f"Auto-summarization completed for attachment {attachment_id}")
                
            except Exception as e:
                logger.error(f"Auto-summarization failed for attachment {attachment_id}: {e}")
                # Update attachment status to failed
                try:
                    attachment = ChatAttachment.query.get(attachment_id)
                    if attachment:
                        attachment.summary_status = 'failed'
                        attachment.summary_error = f"Auto-summarization error: {str(e)[:200]}"
                        _db.session.commit()
                except Exception as db_error:
                    logger.error(f"Failed to update error status: {db_error}")
    
    # Start background thread
    thread = threading.Thread(target=background_summarize, daemon=True)
    thread.start()
    logger.info(f"Started auto-summarization thread for attachment {attachment_id}")


def build_chat_context_with_summaries(session_id: int) -> str:
    """
    Build context string from active attachments, preferring summaries when available.
    Implements two-stage summarization:
    - Stage 1: Use individual summaries for each file (already created)
    - Stage 2: If combined context >500 words, create meta-summary
    
    Args:
        session_id: ChatSession ID
        
    Returns:
        str: Context string for LLM or empty string if no attachments
    """
    import config
    from blueprints.p3.models import ChatAttachment
    from blueprints.p2.models import File
    
    # Get active attachments
    attachments = ChatAttachment.query.filter_by(
        session_id=session_id,
        is_active=True
    ).all()
    
    if not attachments:
        return ""
    
    context_parts = []
    
    for att in attachments:
        # Prefer summary if available and not stale
        if att.summary_file_id and att.summary_status == 'completed' and not att.summary_is_stale:
            summary_file = File.query.get(att.summary_file_id)
            if summary_file and summary_file.content_text:
                context_parts.append(f"[Summary of {att.original_filename}]:\n{summary_file.content_text}")
                continue
        
        # Fallback to original content (truncated if needed)
        file_record = att.file
        if file_record:
            content = None
            if file_record.content_text:
                content = file_record.content_text
            elif file_record.content_html:
                # Strip HTML for context
                import re
                content = re.sub(r'<[^>]+>', '', file_record.content_html)
            
            if content:
                # Truncate long content
                if len(content) > 2000:
                    content = content[:2000] + "\n[Content truncated...]"
                context_parts.append(f"[{att.original_filename}]:\n{content}")
    
    if not context_parts:
        return ""
    
    # Stage 1: Combine all summaries/content
    combined_context = "\n\n---\n\n".join(context_parts)
    
    # Stage 2: Meta-summarization if combined context is too large
    word_count = count_words(combined_context)
    if word_count > config.META_SUMMARY_THRESHOLD:
        try:
            meta_summary = create_meta_summary(combined_context, attachments)
            return f"Context from {len(attachments)} attached files:\n\n{meta_summary}"
        except Exception as e:
            # If meta-summarization fails, use truncated original
            logger.warning(f"Meta-summarization failed: {e}, using truncated context")
            # Truncate to reasonable size
            words = combined_context.split()
            if len(words) > config.META_SUMMARY_THRESHOLD:
                truncated = " ".join(words[:config.META_SUMMARY_THRESHOLD])
                return f"Context from {len(attachments)} files (truncated):\n\n{truncated}..."
    
    return f"Context from {len(attachments)} attached file(s):\n\n{combined_context}"


def create_meta_summary(combined_text: str, attachments: list) -> str:
    """
    Create a meta-summary when multiple file summaries are too large.
    Stage 2 summarization for combined context.
    
    Args:
        combined_text: Combined text from all summaries
        attachments: List of ChatAttachment objects for reference
        
    Returns:
        str: Meta-summary text
    """
    import config
    from providers import LLMClient
    
    filenames = [att.original_filename for att in attachments]
    
    prompt = f"""Create a concise meta-summary of the following {len(attachments)} document summaries.
Focus on:
- Main topics covered across all documents
- Key findings and conclusions
- Important details that connect the documents
- Any actionable items or recommendations

Documents: {', '.join(filenames)}

Combined summaries:
{combined_text[:10000]}  # Limit to first 10K chars for safety
"""
    
    llm_client = LLMClient(use_summarizer=True)
    meta_summary = llm_client.chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=config.SUMMARIZATION_TEMPERATURE,
        max_tokens=config.SUMMARIZATION_MAX_TOKENS,
        timeout=config.SUMMARIZATION_TIMEOUT,
        model=config.SUMMARIZATION_MODEL
    )
    
    return meta_summary


def get_or_create_session_folder(session_id, user_id):
    """
    Get or create MioSpace folder for chat session
    Path: /MioChat/session{session_id}/
    
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
    
    # Anchor under the user's root folder
    root_folder = Folder.query.filter_by(user_id=user_id, is_root=True).first()
    if not root_folder:
        root_folder = Folder.query.filter_by(user_id=user_id, parent_id=None).first()
    if not root_folder:
        root_folder = Folder(
            user_id=user_id,
            name='root',
            parent_id=None,
            is_root=True,
            description='Auto-created root for MioChat attachments'
        )
        db.session.add(root_folder)
        db.session.flush()

    # Find or create MioChat folder under root (rehoming if it was created at top-level)
    chat_sessions_root = Folder.query.filter_by(
        user_id=user_id,
        name='MioChat'
    ).first()
    if chat_sessions_root and chat_sessions_root.parent_id != root_folder.id:
        chat_sessions_root.parent_id = root_folder.id
        db.session.flush()
    if not chat_sessions_root:
        chat_sessions_root = Folder(
            user_id=user_id,
            name='MioChat',
            parent_id=root_folder.id,
            description='Auto-generated folders for MioChat attachments and exports'
        )
        db.session.add(chat_sessions_root)
        db.session.flush()
    
    # Create session-specific folder
    folder_name = f"session{session_id}"
    
    session_folder = Folder(
        user_id=user_id,
        name=folder_name,
        parent_id=chat_sessions_root.id,
        description=f"Attachments, summaries, and chat records for chat session: {session.title}"
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


def ensure_chat_history_file(session):
    """Persist chat transcript inside the MioChat session folder."""
    session_folder = get_or_create_session_folder(session.id, session.user_id)
    messages = ChatMessage.query.filter_by(session_id=session.id).order_by(ChatMessage.created_at).all()
    if not messages:
        return None

    transcript_lines = []
    for message in messages:
        role_label = 'User' if message.role == 'user' else 'Assistant'
        timestamp = message.created_at.isoformat()
        transcript_lines.append(
            f"**{role_label} ({message.model}) — {timestamp}**\n{message.content}"
        )

    transcript = "# MioChat Conversation\n\n" + "\n\n---\n\n".join(transcript_lines)
    history_title = "chat_history.md"

    existing_history = File.query.filter_by(
        owner_id=session.user_id,
        folder_id=session_folder.id,
        title=history_title
    ).first()

    previous_size = calculate_content_size(existing_history.content_text) if existing_history else 0

    metadata = (existing_history.metadata_json if existing_history else {}) or {}
    metadata.update({
        'session_id': session.id,
        'last_synced_at': datetime.utcnow().isoformat()
    })

    if existing_history:
        existing_history.content_text = transcript
        existing_history.metadata_json = metadata
        history_file = existing_history
    else:
        history_file = File(
            owner_id=session.user_id,
            folder_id=session_folder.id,
            type='markdown',
            title=history_title,
            content_text=transcript,
            metadata_json=metadata
        )
        db.session.add(history_file)
        db.session.flush()

    # Update storage quota to reflect transcript changes
    size_delta = calculate_content_size(transcript) - previous_size
    if size_delta:
        from blueprints.p2.models import User
        user = User.query.get(session.user_id)
        update_user_data_size(user, size_delta)

    return history_file


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
        # Avoid reusing a duplicate that never completed conversion (e.g., empty note)
        if existing_file and existing_file.type in ('proprietary_note', 'note'):
            if not (existing_file.content_html and existing_file.content_html.strip()):
                existing_file = None
        
        attachment_file_path = None
        attachment_file_size = file_size

        if existing_file:
            # Reuse existing file (zero storage cost)
            file_record = existing_file
            bytes_added = 0
            existing_metadata = existing_file.metadata_json or {}
            if existing_file.type == 'pdf':
                stored_name = existing_metadata.get('pdf_filename')
                if stored_name:
                    attachment_file_path = f"/static/uploads/pdfs/{stored_name}"
                attachment_file_size = existing_metadata.get('pdf_stored_size', file_size)
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
                # PDFs are stored on disk (hash-deduped) instead of content_blob
                stored_filename, bytes_added, stored_size, page_count, file_hash = save_pdf_for_user(
                    temp_path, user_id, uploaded_file.filename
                )

                metadata.update({
                    'mime_type': 'application/pdf',
                    'pdf_filename': stored_filename,
                    'pdf_stored_size': stored_size,
                    'pdf_page_count': page_count,
                    'storage': 'disk',
                    'file_hash': file_hash,
                    'original_size': file_size,
                })

                file_record = File(
                    owner_id=user_id,
                    folder_id=session_folder.id,
                    type='pdf',
                    title=uploaded_file.filename,
                    content_blob=None,
                    metadata_json=metadata
                )
                bytes_added = bytes_added
                attachment_file_path = f"/static/uploads/pdfs/{stored_filename}"
                attachment_file_size = stored_size
                
            elif db_type in ['proprietary_note', 'table']:
                # Documents requiring conversion (docx, xlsx)
                metadata['target_type'] = db_type
                metadata['mime_type'] = f'application/{upload_type}'

                if db_type == 'proprietary_note':
                    try:
                        content_html = convert_docx_to_note_html(temp_path)
                        metadata['converted_from'] = upload_type
                        metadata['converted_at'] = datetime.utcnow().isoformat()

                        file_record = File(
                            owner_id=user_id,
                            folder_id=session_folder.id,
                            type=db_type,
                            title=uploaded_file.filename,
                            content_html=content_html,
                            metadata_json=metadata
                        )
                        bytes_added = calculate_content_size(content_html)
                    except Exception as conversion_error:
                        # Fallback: attempt plain-text extraction to keep note editable
                        try:
                            text_content, _ = parse_document_for_chat(temp_path, upload_type)
                            if text_content and text_content.strip():
                                content_html = "".join(
                                    f"<p>{html.escape(line.strip())}</p>"
                                    for line in text_content.splitlines() if line.strip()
                                ) or "<p></p>"
                                metadata['converted_from'] = upload_type
                                metadata['converted_at'] = datetime.utcnow().isoformat()
                                metadata['conversion_warning'] = str(conversion_error)[:500]

                                file_record = File(
                                    owner_id=user_id,
                                    folder_id=session_folder.id,
                                    type=db_type,
                                    title=uploaded_file.filename,
                                    content_html=content_html,
                                    metadata_json=metadata
                                )
                                bytes_added = calculate_content_size(content_html)
                            else:
                                raise ValueError("Empty text after fallback parse")
                        except Exception as fallback_error:
                            # Keep original blob for manual recovery and surface error metadata
                            metadata['needs_conversion'] = True
                            metadata['conversion_error'] = str(fallback_error)[:500]
                            metadata['conversion_root_error'] = str(conversion_error)[:500]
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
                else:
                    # TODO: Implement proper XLSX→table conversion
                    with open(temp_path, 'rb') as f:
                        file_content = f.read()
                    metadata['needs_conversion'] = True
                    file_record = File(
                        owner_id=user_id,
                        folder_id=session_folder.id,
                        type=db_type,
                        title=uploaded_file.filename,
                        content_blob=file_content,
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
            file_size=attachment_file_size,
            file_hash=file_hash,
            file_path=attachment_file_path,
            summary_status='pending'
        )
        db.session.add(attachment)
        
        # Update user storage quota
        if bytes_added > 0:
            from blueprints.p2.models import User
            user = User.query.get(user_id)
            update_user_data_size(user, bytes_added)
        
        db.session.commit()
        
        # Check if auto-summarization is needed (async, non-blocking)
        if should_auto_summarize(attachment):
            trigger_auto_summarization(attachment.id)
        
        # Persist chat transcript alongside uploaded assets
        ensure_chat_history_file(attachment.session)
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
        file_record = attachment.file
        session = attachment.session
        temp_path = None
        file_path = None
        text_content = None
        parse_method = None

        if file_record.type == 'pdf':
            metadata = file_record.metadata_json or {}
            pdf_name = metadata.get('pdf_filename')
            if pdf_name:
                candidate = Path(current_app.root_path) / 'static' / 'uploads' / 'pdfs' / pdf_name
                if candidate.exists():
                    file_path = str(candidate)
                else:
                    raise ValueError(f"Stored PDF missing on disk: {pdf_name}")
        
        # Materialize file contents when needed
        if file_path:
            # Already resolved (e.g., disk-backed PDF)
            pass
        elif file_record.content_blob:
            temp_dir = os.path.join(tempfile.gettempdir(), 'miohub_attachments')
            os.makedirs(temp_dir, exist_ok=True)
            ext = Path(attachment.original_filename).suffix or '.tmp'
            temp_path = os.path.join(temp_dir, f"chat_attachment_{attachment_id}{ext}")
            with open(temp_path, 'wb') as f:
                f.write(file_record.content_blob)
            file_path = temp_path
        elif file_record.content_text and file_record.type == 'image':
            # Image stored as path
            file_path = os.path.join(current_app.root_path, file_record.content_text.lstrip('/'))
        elif file_record.content_text:
            text_content = file_record.content_text
            parse_method = 'text_content'
        elif file_record.content_html:
            text_content = file_record.content_html
            parse_method = 'html_content'
        else:
            raise ValueError(f"Cannot determine file path for attachment {attachment_id}")
        
        if text_content is None:
            text_content, parse_method = parse_document_for_chat(file_path, attachment.file_type)
        
        # Clean up temp file if created
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        
        if not text_content or not text_content.strip():
            raise ValueError("Attachment contains no extractable text to summarize")
        
        # Cache word count and original hash for staleness tracking
        if attachment.word_count is None:
            attachment.word_count = count_words(text_content)
        content_hash = compute_text_hash(text_content)

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
        
        summary_text = llm_client.chat(
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=config.SUMMARIZATION_TEMPERATURE,
            max_tokens=config.SUMMARIZATION_MAX_TOKENS,
            timeout=config.SUMMARIZATION_TIMEOUT,
            model=config.SUMMARIZATION_MODEL,
        )
        summary_word_count = count_words(summary_text)
        
        # Create summary file in MioSpace
        folder = Folder.query.get(session.session_folder_id)
        
        summary_file = File(
            owner_id=session.user_id,
            folder_id=folder.id,
            type='markdown',
            title=build_summary_title(attachment.original_filename),
            content_text=summary_text,
            metadata_json={
                'source_attachment_id': attachment_id,
                'parse_method': parse_method,
                'generated_at': datetime.utcnow().isoformat(),
                'word_count': attachment.word_count,
                'summary_word_count': summary_word_count,
                'source_content_hash': content_hash
            }
        )
        db.session.add(summary_file)
        db.session.flush()
        
        # Track storage used by summary text
        summary_size = calculate_content_size(summary_text)
        if summary_size > 0:
            from blueprints.p2.models import User
            user = User.query.get(session.user_id)
            update_user_data_size(user, summary_size)
        
        # Update attachment record
        attachment.summary_file_id = summary_file.id
        attachment.summary_status = 'completed'
        attachment.summarized_at = datetime.utcnow()
        attachment.summary_is_stale = False
        attachment.original_content_hash = content_hash
        attachment.summary_word_count = summary_word_count
        attachment.summary_error = None
        db.session.commit()
        ensure_chat_history_file(session)
        
        return summary_file
    
    except Exception as e:
        attachment.summary_status = 'failed'
        attachment.summary_error = str(e)
        db.session.commit()
        raise
    finally:
        if 'temp_path' in locals() and temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
