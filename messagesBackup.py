from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from database import get_db
from flask_socketio import SocketIO, emit, join_room, leave_room

messages_bp = Blueprint('messages', __name__)
socketio = SocketIO()

# 🔹 Route to open chat with a user
@messages_bp.route('/chat/<int:receiver_id>')
def chat(receiver_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    sender_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    # Fetch receiver details
    cursor.execute("SELECT id, username FROM users WHERE id=%s", (receiver_id,))
    receiver = cursor.fetchone()

    # Fetch chat history (Ensure latest messages appear last)
    cursor.execute("""
        SELECT sender_id, receiver_id, content, timestamp
        FROM messages
        WHERE (sender_id=%s AND receiver_id=%s) OR (sender_id=%s AND receiver_id=%s)
        ORDER BY timestamp ASC
    """, (sender_id, receiver_id, receiver_id, sender_id))
    
    messages = cursor.fetchall()
    db.close()
    
    return render_template('messages.html', receiver=receiver, messages=messages)

# 🔹 Send a new message (REST API for AJAX/WebSocket)
@messages_bp.route('/send_message', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    sender_id = session['user_id']
    receiver_id = request.json['receiver_id']  # Use JSON data
    content = request.json['content']

    db = get_db()
    cursor = db.cursor()
    
    # Insert message into the database
    cursor.execute("INSERT INTO messages (sender_id, receiver_id, content) VALUES (%s, %s, %s)",
                   (sender_id, receiver_id, content))
    db.commit()
    db.close()

    message_data = {
        'sender_id': sender_id,
        'receiver_id': receiver_id,
        'content': content
    }

    # Emit message to both sender and receiver WebSocket rooms
    socketio.emit('receive_message', message_data, room=str(sender_id))
    socketio.emit('receive_message', message_data, room=str(receiver_id))

    return jsonify({'status': 'success', 'message': message_data})

# 🔹 Inbox Route
@messages_bp.route('/inbox')
def inbox():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    # Fetch unique users who had a conversation with the logged-in user
    cursor.execute("""
        SELECT DISTINCT u.id, u.username 
        FROM users u
        JOIN messages m ON (u.id = m.sender_id OR u.id = m.receiver_id)
        WHERE (m.sender_id = %s OR m.receiver_id = %s) AND u.id != %s
    """, (user_id, user_id, user_id))
    
    conversations = cursor.fetchall()
    db.close()
    
    return render_template('inbox.html', conversations=conversations)

# 🔹 WebSocket: Join user room
@socketio.on('join')
def join(data):
    room = str(data['user_id'])
    join_room(room)
    emit('status', {'msg': f'User {data["user_id"]} connected'}, room=room)

# 🔹 WebSocket: Typing Indicator
@socketio.on('typing')
def typing(data):
    emit('typing_status', {'receiver_id': data['receiver_id'], 'is_typing': True}, room=str(data['receiver_id']))

# 🔹 WebSocket: Send message
@socketio.on('send_message')
def handle_message(data):
    sender_id = data['sender_id']
    receiver_id = data['receiver_id']
    content = data['content']

    message_data = {'sender_id': sender_id, 'receiver_id': receiver_id, 'content': content}
    
    # Send message to both sender and receiver
    emit('receive_message', message_data, room=str(sender_id))
    emit('receive_message', message_data, room=str(receiver_id))
