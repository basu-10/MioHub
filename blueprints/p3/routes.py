from flask import render_template, request, jsonify, session, redirect, url_for, flash
from flask_login import login_required, current_user
from . import p3_blueprint
from .models import ChatSession, ChatMessage, ChatMemory
from extensions import db
from datetime import datetime
import os
import requests
from providers import LLMClient
from sqlalchemy.orm.attributes import flag_modified
from blueprints.p3.chat_attachment_service import (
    create_attachment_from_upload,
    create_summary_for_attachment,
    get_or_create_session_folder,
    build_chat_context_with_summaries
)
import config
import logging

# Keep SQLAlchemy engine logging quiet by default; allow opt-in via env variable
SQL_ENGINE_LOG_LEVEL = os.getenv("SQL_ENGINE_LOG_LEVEL", "WARNING").upper()
logging.getLogger('sqlalchemy.engine').setLevel(
    getattr(logging, SQL_ENGINE_LOG_LEVEL, logging.WARNING)
)

# Initialize LLM client (supports Groq, OpenRouter, Fireworks, Together)
llm_client = LLMClient()
logger = logging.getLogger(__name__)


def _build_llm_messages(user_message: str, memory_items: list[str]) -> list[dict]:
    """Create the LLM messages payload using memory first, then the user prompt."""
    llm_messages: list[dict] = []

    if memory_items:
        memory_items_formatted = "\n".join(
            config.CHAT_MEMORY_ITEM_FORMAT.format(item=item) for item in memory_items
        )
        memory_context = config.CHAT_MEMORY_TEMPLATE.format(memory_items=memory_items_formatted)
        llm_messages.append({"role": "system", "content": memory_context})

    llm_messages.append({"role": "user", "content": user_message})
    return llm_messages


def _generate_ai_reply(user_message: str, memory_items: list[str], model: str) -> str:
    """Call the configured LLM provider and return the assistant reply."""
    llm_messages = _build_llm_messages(user_message, memory_items)
    try:
        llm_client.model = model
        ai_response = llm_client.chat(
            messages=llm_messages,
            temperature=0.7,
            max_tokens=2048
        )
    except requests.exceptions.RequestException as exc:
        logger.error("LLM API error: %s", exc)
        print(
            f"[LLM API ERROR] provider={config.PROVIDER} model={model} error={exc}",
            flush=True,
        )
        ai_response = "Connection error. Please check your API configuration."
    except Exception as exc:  # noqa: BLE001
        logger.error("LLM error: %s", exc)
        print(
            f"[LLM ERROR] provider={config.PROVIDER} model={model} error={exc}",
            flush=True,
        )
        ai_response = f"Error: {str(exc)}"

    return ai_response

@p3_blueprint.route('/chatbot')
@login_required
def chatbot():
    import time
    from sqlalchemy import event
    
    start_time = time.time()
    
    # Track query count
    query_count = {'count': 0}
    
    def receive_after_cursor_execute(conn, cursor, statement, params, context, executemany):
        query_count['count'] += 1
        print(f"[QUERY {query_count['count']}] {statement[:100]}...")
    
    event.listen(db.engine, "after_cursor_execute", receive_after_cursor_execute)
    
    # Get current session or create new one
    current_session_id = session.get('current_chat_session_id')
    if not current_session_id:
        # Create a new session
        new_session = ChatSession(user_id=current_user.id, title='New chat')
        db.session.add(new_session)
        db.session.commit()
        session['current_chat_session_id'] = new_session.id
        current_session_id = new_session.id
    
    after_session_check = time.time()
    print(f"[DEBUG] Session check/create: {after_session_check - start_time:.3f}s")

    # Get all sessions for sidebar
    user_sessions = ChatSession.query.filter_by(user_id=current_user.id).order_by(ChatSession.updated_at.desc()).all()
    
    after_sessions_query = time.time()
    print(f"[DEBUG] Get all sessions ({len(user_sessions)} sessions): {after_sessions_query - after_session_check:.3f}s")

    # Get current session messages
    current_session = ChatSession.query.filter_by(id=current_session_id, user_id=current_user.id).first()
    messages = []
    if current_session:
        messages = ChatMessage.query.filter_by(session_id=current_session_id).order_by(ChatMessage.created_at).all()

    session_folder = None
    session_folder_name = None
    session_folder_url = None
    if current_session:
        session_folder = get_or_create_session_folder(current_session.id, current_user.id)
        session_folder_name = session_folder.name
        session_folder_url = url_for('folders.view_folder', folder_id=session_folder.id)
    
    after_messages_query = time.time()
    print(f"[DEBUG] Get current session messages ({len(messages)} messages): {after_messages_query - after_sessions_query:.3f}s")

    # Get current model from session or default
    current_model = session.get('current_model', config.DEFAULT_CHAT_MODEL)
    
    before_render = time.time()
    print(f"[DEBUG] Model config: {before_render - after_messages_query:.3f}s")

    result = render_template('p3/miochat.html',
                         sessions=user_sessions,
                         chats=messages,
                         current_session=current_session,
                         session_folder_name=session_folder_name,
                         session_folder_url=session_folder_url,
                         models=config.AVAILABLE_CHAT_MODELS,
                         current_model=current_model)
    
    after_render = time.time()
    print(f"[DEBUG] Template render: {after_render - before_render:.3f}s")
    print(f"[DEBUG] Total queries executed: {query_count['count']}")
    print(f"[DEBUG] TOTAL chatbot route time: {after_render - start_time:.3f}s")
    
    # Remove listener to avoid memory leak
    event.remove(db.engine, "after_cursor_execute", receive_after_cursor_execute)
    
    return result

@p3_blueprint.route('/chat', methods=['POST'])
@login_required
def chat():
    data = request.get_json()
    user_message = data.get('message', '').strip()
    memory_items = data.get('memory', [])  # Get memory items from frontend
    if not user_message:
        return jsonify({'error': 'Message cannot be empty'}), 400

    current_session_id = session.get('current_chat_session_id')
    if not current_session_id:
        return jsonify({'error': 'No active session'}), 400

    # Get current model
    current_model = session.get('current_model', config.DEFAULT_CHAT_MODEL)

    # Update session title if it's still "New chat"
    chat_session = ChatSession.query.filter_by(id=current_session_id, user_id=current_user.id).first()
    if chat_session and chat_session.title == 'New chat':
        # Create a title from the message
        title = datetime.now().strftime("%Y-%m-%d") + " • " + user_message[:20]
        chat_session.title = title
        chat_session.updated_at = datetime.utcnow()
        db.session.commit()  # Commit title update immediately

    # Build context from attachment summaries (Phase 4)
    attachment_context = build_chat_context_with_summaries(current_session_id)
    
    # Combine memory items with attachment context
    combined_memory = memory_items.copy()
    if attachment_context:
        combined_memory.insert(0, attachment_context)

    # Save user message
    user_message_obj = ChatMessage(
        session_id=current_session_id,
        model=current_model,
        role='user',
        content=user_message
    )
    db.session.add(user_message_obj)
    db.session.commit()

    llm_messages = _build_llm_messages(user_message, combined_memory)

    print(f"Sending to LLM: {llm_messages}")
    print(f"Using model: {current_model}")
    print(f"Using provider: {config.PROVIDER}")

    ai_response = _generate_ai_reply(user_message, combined_memory, current_model)

    # Save AI response
    ai_message = ChatMessage(
        session_id=current_session_id,
        model=current_model,
        role='assistant',
        content=ai_response
    )
    db.session.add(ai_message)

    # Update session timestamp
    if chat_session:
        chat_session.updated_at = datetime.utcnow()

    db.session.commit()

    return jsonify({
        'reply': ai_response,
        'model': current_model,
        'user_message_id': user_message_obj.id,
        'assistant_message_id': ai_message.id
    })


@p3_blueprint.route('/chat/requery', methods=['POST'])
@login_required
def requery_chat_message():
    data = request.get_json() or {}
    message_id = data.get('message_id')
    new_message = (data.get('message') or '').strip()
    memory_items = data.get('memory', [])

    try:
        message_id = int(message_id)
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid message id'}), 400

    if not message_id or not new_message:
        return jsonify({'error': 'Message id and updated text are required'}), 400

    current_session_id = session.get('current_chat_session_id')
    if not current_session_id:
        return jsonify({'error': 'No active session'}), 400

    chat_session = ChatSession.query.filter_by(
        id=current_session_id,
        user_id=current_user.id
    ).first()
    if not chat_session:
        return jsonify({'error': 'Session not found'}), 404

    user_message = ChatMessage.query.filter_by(
        id=message_id,
        session_id=current_session_id,
        role='user'
    ).first()
    if not user_message:
        return jsonify({'error': 'Message not found'}), 404

    # Find the assistant reply that immediately follows this user message (oldest assistant after it)
    assistant_message = ChatMessage.query.filter(
        ChatMessage.session_id == current_session_id,
        ChatMessage.role == 'assistant',
        ChatMessage.created_at > user_message.created_at
    ).order_by(ChatMessage.created_at.asc()).first()

    replaced_assistant_id = assistant_message.id if assistant_message else None
    target_created_at = assistant_message.created_at if assistant_message else datetime.utcnow()

    if assistant_message:
        db.session.delete(assistant_message)

    current_model = session.get('current_model', config.DEFAULT_CHAT_MODEL)

    # Build context from attachment summaries (Phase 4) - same as /chat route
    attachment_context = build_chat_context_with_summaries(current_session_id)
    
    # Combine memory items with attachment context
    combined_memory = memory_items.copy()
    if attachment_context:
        combined_memory.insert(0, attachment_context)

    # Update the existing user message with new text and model context
    user_message.content = new_message
    user_message.model = current_model

    ai_response = _generate_ai_reply(new_message, combined_memory, current_model)

    # Ensure chronological ordering: assistant timestamp should not precede user message
    if target_created_at < user_message.created_at:
        target_created_at = user_message.created_at

    new_assistant_message = ChatMessage(
        session_id=current_session_id,
        model=current_model,
        role='assistant',
        content=ai_response,
        created_at=target_created_at
    )

    db.session.add(new_assistant_message)
    chat_session.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'reply': ai_response,
        'model': current_model,
        'user_message_id': user_message.id,
        'assistant_message_id': new_assistant_message.id,
        'replaced_assistant_id': replaced_assistant_id
    })


@p3_blueprint.route('/chat/report', methods=['POST'])
@login_required
def report_chat_message():
    data = request.get_json() or {}
    message_id = data.get('message_id')
    reason = (data.get('reason') or '').strip()

    try:
        message_id = int(message_id)
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'Invalid message id'}), 400

    current_session_id = session.get('current_chat_session_id')
    if not current_session_id:
        return jsonify({'status': 'error', 'message': 'No active session'}), 400

    chat_session = ChatSession.query.filter_by(
        id=current_session_id,
        user_id=current_user.id
    ).first()
    if not chat_session:
        return jsonify({'status': 'error', 'message': 'Session not found'}), 404

    message = ChatMessage.query.filter_by(
        id=message_id,
        session_id=current_session_id
    ).first()

    if not message:
        return jsonify({'status': 'error', 'message': 'Message not found'}), 404

    logger.info(
        "Chat message flagged by user %s in session %s (message %s): %s",
        current_user.id,
        current_session_id,
        message_id,
        reason or 'No reason provided'
    )

    return jsonify({'status': 'ok'})

@p3_blueprint.route('/get_memory')
@login_required
def get_memory():
    current_session_id = session.get('current_chat_session_id')
    if not current_session_id:
        return jsonify({'memory': []})

    memories = ChatMemory.query.filter_by(session_id=current_session_id).order_by(ChatMemory.created_at).all()
    memory_data = []
    for memory in memories:
        memory_data.append({
            'text': memory.text,
            'enabled': memory.enabled
        })

    return jsonify({'memory': memory_data})

@p3_blueprint.route('/add_memory', methods=['POST'])
@login_required
def add_memory():
    data = request.get_json()
    text = data.get('text', '').strip()
    if not text:
        return jsonify({'status': 'error', 'message': 'Memory text cannot be empty'}), 400

    current_session_id = session.get('current_chat_session_id')
    if not current_session_id:
        return jsonify({'status': 'error', 'message': 'No active session'}), 400

    memory = ChatMemory(session_id=current_session_id, text=text)
    db.session.add(memory)
    db.session.commit()

    return jsonify({'status': 'ok'})

@p3_blueprint.route('/toggle_memory', methods=['POST'])
@login_required
def toggle_memory():
    data = request.get_json()
    index = data.get('index')  # This is the array index from frontend
    enabled = data.get('enabled', True)

    current_session_id = session.get('current_chat_session_id')
    if not current_session_id:
        return jsonify({'status': 'error', 'message': 'No active session'}), 400

    # Get all memories for this session, ordered by creation time
    memories = ChatMemory.query.filter_by(session_id=current_session_id).order_by(ChatMemory.created_at).all()

    if index >= len(memories):
        return jsonify({'status': 'error', 'message': 'Memory not found'}), 404

    memory = memories[index]
    memory.enabled = enabled
    db.session.commit()

    return jsonify({'status': 'ok'})

@p3_blueprint.route('/delete_memory', methods=['POST'])
@login_required
def delete_memory():
    data = request.get_json()
    index = data.get('index')  # This is the array index from frontend

    current_session_id = session.get('current_chat_session_id')
    if not current_session_id:
        return jsonify({'status': 'error', 'message': 'No active session'}), 400

    # Get all memories for this session, ordered by creation time
    memories = ChatMemory.query.filter_by(session_id=current_session_id).order_by(ChatMemory.created_at).all()

    if index >= len(memories):
        return jsonify({'status': 'error', 'message': 'Memory not found'}), 404

    memory = memories[index]
    db.session.delete(memory)
    db.session.commit()

    return jsonify({'status': 'ok'})

@p3_blueprint.route('/update_memory', methods=['POST'])
@login_required
def update_memory():
    data = request.get_json()
    index = data.get('index')  # This is the array index from frontend
    text = data.get('text', '').strip()

    if not text:
        return jsonify({'status': 'error', 'message': 'Memory text cannot be empty'}), 400

    current_session_id = session.get('current_chat_session_id')
    if not current_session_id:
        return jsonify({'status': 'error', 'message': 'No active session'}), 400

    # Get all memories for this session, ordered by creation time
    memories = ChatMemory.query.filter_by(session_id=current_session_id).order_by(ChatMemory.created_at).all()

    if index >= len(memories):
        return jsonify({'status': 'error', 'message': 'Memory not found'}), 404

    memory = memories[index]
    memory.text = text
    db.session.commit()

    return jsonify({'status': 'ok'})

@p3_blueprint.route('/switch_session/<int:session_id>', methods=['POST'])
@login_required
def switch_session(session_id):
    chat_session = ChatSession.query.filter_by(id=session_id, user_id=current_user.id).first()
    if not chat_session:
        return jsonify({'status': 'error', 'message': 'Session not found'}), 404

    session['current_chat_session_id'] = session_id
    return jsonify({'status': 'ok'})

@p3_blueprint.route('/new_session', methods=['POST'])
@login_required
def new_session():
    new_session = ChatSession(user_id=current_user.id, title='New chat')
    db.session.add(new_session)
    db.session.commit()

    session['current_chat_session_id'] = new_session.id
    return jsonify({'status': 'ok'})

@p3_blueprint.route('/delete_session/<int:session_id>', methods=['POST'])
@login_required
def delete_session(session_id):
    chat_session = ChatSession.query.filter_by(id=session_id, user_id=current_user.id).first()
    if not chat_session:
        return jsonify({'status': 'error', 'message': 'Session not found'}), 404

    db.session.delete(chat_session)
    db.session.commit()

    # If this was the current session, clear it
    if session.get('current_chat_session_id') == session_id:
        session.pop('current_chat_session_id', None)

    return jsonify({'status': 'ok'})

@p3_blueprint.route('/summarize_memory', methods=['POST'])
@login_required
def summarize_memory():
    """Summarize a memory item using LLM, disable original, create new summary"""
    from providers import LLMClient
    
    data = request.get_json()
    index = data.get('index')
    
    if index is None:
        return jsonify({'status': 'error', 'message': 'Index required'}), 400
    
    # Get current session
    current_session_id = session.get('current_chat_session_id')
    if not current_session_id:
        return jsonify({'status': 'error', 'message': 'No active session'}), 400
    
    # Get all memory items for this session
    memory_items = ChatMemory.query.filter_by(
        session_id=current_session_id
    ).order_by(ChatMemory.id).all()
    
    if index < 0 or index >= len(memory_items):
        return jsonify({'status': 'error', 'message': 'Invalid index'}), 400
    
    memory = memory_items[index]
    original_text = memory.text
    
    # Don't summarize very short texts
    if len(original_text) < config.SUMMARIZATION_MIN_CHARS:
        return jsonify({'status': 'error', 'message': f'Text too short to summarize (min {config.SUMMARIZATION_MIN_CHARS} chars)'}), 400
    
    try:
        # Use OpenRouter specifically for summarization (cost-effective)
        import requests
        
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
            "HTTP-Referer": config.OR_SITE_URL,
            "X-Title": config.OR_APP_NAME
        }
        
        messages = [
            {"role": "system", "content": config.SUMMARIZATION_SYSTEM_PROMPT},
            {"role": "user", "content": f"Summarize this memory item concisely:\n\n{original_text}"}
        ]
        
        payload = {
            "model": config.SUMMARIZATION_MODEL,
            "messages": messages,
            "temperature": config.SUMMARIZATION_TEMPERATURE,
            "max_tokens": config.SUMMARIZATION_MAX_TOKENS
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=config.SUMMARIZATION_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        summary = result["choices"][0]["message"]["content"].strip()
        
        if not summary:
            return jsonify({'status': 'error', 'message': 'Empty summary returned'}), 500
        
        # Disable the original memory
        memory.enabled = False
        flag_modified(memory, 'enabled')
        
        # Create new memory with summary (enabled by default)
        new_memory = ChatMemory(
            session_id=current_session_id,
            text=summary,
            enabled=True
        )
        db.session.add(new_memory)
        db.session.commit()
        
        return jsonify({
            'status': 'ok', 
            'summary': summary,
            'original_length': len(original_text),
            'summary_length': len(summary)
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Summarization failed: {str(e)}'}), 500

@p3_blueprint.route('/set_model', methods=['POST'])
@login_required
def set_model():
    data = request.get_json()
    model = data.get('model')

    if model not in config.AVAILABLE_CHAT_MODELS:
        return jsonify({'status': 'error', 'message': 'Invalid model'}), 400

    session['current_model'] = model
    return jsonify({'status': 'ok'})

@p3_blueprint.route('/p3_admin_dashboard')
@login_required
def p3_admin_dashboard():
    # Check if user is admin
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('p2_bp.dashboard'))
    
    # Get admin dashboard data
    total_sessions = ChatSession.query.count()
    total_messages = ChatMessage.query.count()
    total_memories = ChatMemory.query.count()
    
    # Get recent sessions
    recent_sessions = ChatSession.query.order_by(ChatSession.updated_at.desc()).limit(10).all()
    
    # Get message statistics by model
    model_stats = db.session.query(
        ChatMessage.model, 
        db.func.count(ChatMessage.id).label('count')
    ).group_by(ChatMessage.model).all()
    
    return render_template('p3/p3_admin_dashboard.html', 
                         total_sessions=total_sessions,
                         total_messages=total_messages,
                         total_memories=total_memories,
                         recent_sessions=recent_sessions,
                         model_stats=model_stats,
                         available_models=config.AVAILABLE_CHAT_MODELS)


# =============================================================================
# CHAT ATTACHMENTS API ROUTES (Phase 3)
# =============================================================================

from blueprints.p3.models import ChatAttachment
from werkzeug.utils import secure_filename

# Allowed file extensions for attachments
ALLOWED_EXTENSIONS = {
    'pdf', 'docx', 'doc', 'xlsx', 'xls',
    'png', 'jpg', 'jpeg', 'gif', 'webp',
    'py', 'js', 'ts', 'html', 'css',
    'md', 'txt', 'yaml', 'yml', 'json', 'env'
}

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def build_attachment_open_url(file_obj):
    """Resolve the correct editor/view URL for an attachment's underlying file."""
    if not file_obj:
        return None
    if file_obj.type in ('proprietary_note', 'note'):
        return url_for('notes.edit_note', note_id=file_obj.id)
    return url_for('file.view_file', file_id=file_obj.id)


def build_summary_edit_url(summary_file_id):
    """Return the edit URL for a generated summary file."""
    if not summary_file_id:
        return None
    return url_for('file.edit_file', file_id=summary_file_id)


@p3_blueprint.route('/sessions/<int:session_id>/attachments/upload', methods=['POST'])
@login_required
def upload_attachment(session_id):
    """Upload file as attachment to chat session"""
    session_obj = ChatSession.query.get_or_404(session_id)
    
    # Permission check
    if session_obj.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Check file in request
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not supported'}), 400
    
    try:
        attachment, bytes_added = create_attachment_from_upload(
            session_id, current_user.id, file
        )
        
        return jsonify({
            'success': True,
            'attachment': {
                'id': attachment.id,
                'filename': attachment.original_filename,
                'file_type': attachment.file_type,
                'file_size': attachment.file_size,
                'file_id': attachment.file_id,
                'icon': attachment.get_file_icon(),
                'is_active': attachment.is_active,
                'summary_status': attachment.summary_status,
                'summary_file_id': attachment.summary_file_id,
                'summary_is_stale': attachment.summary_is_stale,
                'summary_file_url': build_summary_edit_url(attachment.summary_file_id),
                'open_url': build_attachment_open_url(attachment.file)
            },
            'bytes_added': bytes_added,
            'duplicate': bytes_added == 0
        })
    
    except Exception as e:
        logger.error(f"Upload attachment error: {e}")
        return jsonify({'error': str(e)}), 500


@p3_blueprint.route('/attachments/<int:attachment_id>/summarize', methods=['POST'])
@login_required
def summarize_attachment(attachment_id):
    """Generate summary for attachment"""
    attachment = ChatAttachment.query.get_or_404(attachment_id)
    
    # Permission check
    if attachment.session.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Check if already summarized
    if attachment.summary_status == 'completed':
        return jsonify({
            'success': True,
            'message': 'Summary already exists',
            'summary_file_id': attachment.summary_file_id,
            'summary_file_url': build_summary_edit_url(attachment.summary_file_id),
            'summary_is_stale': attachment.summary_is_stale,
            'summary_status': attachment.summary_status
        })
    
    try:
        summary_file = create_summary_for_attachment(attachment_id)
        
        return jsonify({
            'success': True,
            'summary_file_id': summary_file.id,
            'summary_file_url': build_summary_edit_url(summary_file.id),
            'summary_is_stale': False,
            'summary_status': 'completed'
        })
    
    except Exception as e:
        logger.error(f"Summarize attachment error: {e}")
        return jsonify({'error': str(e)}), 500


@p3_blueprint.route('/attachments/<int:attachment_id>/reset_summary', methods=['POST'])
@login_required
def reset_attachment_summary(attachment_id):
    """Reset attachment summary status to allow regeneration"""
    attachment = ChatAttachment.query.get_or_404(attachment_id)
    
    # Permission check
    if attachment.session.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Reset summary status and clear staleness
    attachment.summary_status = 'pending'
    attachment.summary_is_stale = False
    attachment.summary_error = None
    db.session.commit()
    
    return jsonify({'success': True})


@p3_blueprint.route('/attachments/<int:attachment_id>/toggle', methods=['POST'])
@login_required
def toggle_attachment_active(attachment_id):
    """Toggle attachment active status (include in context or not)"""
    attachment = ChatAttachment.query.get_or_404(attachment_id)
    
    # Permission check
    if attachment.session.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    attachment.is_active = not attachment.is_active
    db.session.commit()
    
    return jsonify({
        'success': True,
        'is_active': attachment.is_active
    })


@p3_blueprint.route('/attachments/<int:attachment_id>/delete', methods=['DELETE'])
@login_required
def delete_attachment(attachment_id):
    """Delete attachment (soft delete - keeps file in MioSpace)"""
    attachment = ChatAttachment.query.get_or_404(attachment_id)
    
    # Permission check
    if attachment.session.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Just remove link, keep file in MioSpace
    db.session.delete(attachment)
    db.session.commit()
    
    return jsonify({'success': True})


@p3_blueprint.route('/sessions/<int:session_id>/attachments', methods=['GET'])
@login_required
def list_attachments(session_id):
    """Get all attachments for session"""
    session_obj = ChatSession.query.get_or_404(session_id)
    
    # Permission check
    if session_obj.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    attachments = ChatAttachment.query.filter_by(session_id=session_id).order_by(
        ChatAttachment.uploaded_at.desc()
    ).all()
    
    return jsonify({
        'attachments': [{
            'id': att.id,
            'filename': att.original_filename,
            'file_type': att.file_type,
            'file_size': att.file_size,
            'file_id': att.file_id,
            'icon': att.get_file_icon(),
            'is_active': att.is_active,
            'summary_status': att.summary_status,
            'summary_file_id': att.summary_file_id,
            'summary_is_stale': att.summary_is_stale,
            'summary_file_url': build_summary_edit_url(att.summary_file_id),
            'uploaded_at': att.uploaded_at.isoformat(),
            'open_url': build_attachment_open_url(att.file)
        } for att in attachments]
    })