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
import config
import logging

# Set up SQL query logging for debugging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Initialize LLM client (supports Groq, OpenRouter, Fireworks, Together)
llm_client = LLMClient()

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
    
    after_messages_query = time.time()
    print(f"[DEBUG] Get current session messages ({len(messages)} messages): {after_messages_query - after_sessions_query:.3f}s")

    # Get current model from session or default
    current_model = session.get('current_model', config.DEFAULT_CHAT_MODEL)
    
    before_render = time.time()
    print(f"[DEBUG] Model config: {before_render - after_messages_query:.3f}s")

    result = render_template('p3/chatbot_v2.html',
                         sessions=user_sessions,
                         chats=messages,
                         current_session=current_session,
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

    # Save user message
    user_message_obj = ChatMessage(
        session_id=current_session_id,
        model=current_model,
        role='user',
        content=user_message
    )
    db.session.add(user_message_obj)
    db.session.commit()

    # --- Build conversation ONLY from memory_items ---
    llm_messages = []

    if memory_items:
        memory_items_formatted = "\n".join(config.CHAT_MEMORY_ITEM_FORMAT.format(item=item) for item in memory_items)
        memory_context = config.CHAT_MEMORY_TEMPLATE.format(memory_items=memory_items_formatted)
        llm_messages.append({"role": "system", "content": memory_context})

    # Always include the latest user message
    llm_messages.append({"role": "user", "content": user_message})

    print(f"Sending to LLM: {llm_messages}")
    print(f"Using model: {current_model}")
    print(f"Using provider: {config.PROVIDER}")

    try:
        # Use LLMClient for provider-agnostic LLM calls
        llm_client.model = current_model
        ai_response = llm_client.chat(
            messages=llm_messages,
            temperature=0.7,
            max_tokens=2048
        )
    except requests.exceptions.RequestException as e:
        # Network/API errors
        print(f"LLM API Error: {str(e)}")
        ai_response = f"Connection error. Please check your API configuration."
    except Exception as e:
        # Other errors
        print(f"LLM Error: {str(e)}")
        ai_response = f"Error: {str(e)}"

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
        'model': current_model
    })

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