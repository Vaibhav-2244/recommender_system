from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from database import get_db
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime, timedelta

messages_bp = Blueprint('messages', __name__)
socketio = SocketIO()

# In-memory storage for user activity
user_activity = {}

# 🔹 Open Chat Page
@messages_bp.route('/chat/<int:receiver_id>')
def chat(receiver_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    sender_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    # Fetch receiver details
    cursor.execute("""
        SELECT u.id, u.username, p.profile_pic 
        FROM users u
        JOIN profiles p ON u.id = p.user_id
        WHERE u.id = %s
    """, (receiver_id,))
    receiver = cursor.fetchone()

    # Fetch chat history
    cursor.execute("""
        SELECT sender_id, receiver_id, content, timestamp
        FROM messages
        WHERE (sender_id=%s AND receiver_id=%s) OR (sender_id=%s AND receiver_id=%s)
        ORDER BY timestamp ASC
    """, (sender_id, receiver_id, receiver_id, sender_id))
    
    messages = cursor.fetchall()
    db.close()

    # Update sender's last activity
    user_activity[sender_id] = datetime.now()
    
    return render_template('messages.html', receiver=receiver, messages=messages)

# 🔹 REST API to send a message
@messages_bp.route('/send_message', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    sender_id = session['user_id']
    receiver_id = request.json['receiver_id']
    content = request.json['content']

    db = get_db()
    cursor = db.cursor()
    
    # Insert message into the database
    cursor.execute("INSERT INTO messages (sender_id, receiver_id, content) VALUES (%s, %s, %s)",
                   (sender_id, receiver_id, content))
    db.commit()

    # Get the latest message ID
    cursor.execute("SELECT LAST_INSERT_ID()")
    message_id = cursor.fetchone()[0]

    db.close()

    message_data = {
        'id': message_id,
        'sender_id': sender_id,
        'receiver_id': receiver_id,
        'content': content
    }

    # Emit message to both sender and receiver rooms
    socketio.emit('receive_message', message_data, room=str(sender_id))
    socketio.emit('receive_message', message_data, room=str(receiver_id))

    # Update sender's last activity
    user_activity[sender_id] = datetime.now()

    return jsonify({'status': 'success', 'message': message_data})

# 🔹 Inbox Route
@messages_bp.route('/inbox')
def inbox():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    # Fetch unique users who had a conversation
    cursor.execute("""
        SELECT DISTINCT u.id, u.username, p.profile_pic
        FROM users u
        JOIN profiles p ON u.id = p.user_id
        JOIN messages m ON (u.id = m.sender_id OR u.id = m.receiver_id)
        WHERE (m.sender_id = %s OR m.receiver_id = %s) AND u.id != %s
    """, (user_id, user_id, user_id))
    
    conversations = cursor.fetchall()
    db.close()

    # Update user's last activity
    user_activity[user_id] = datetime.now()
    
    return render_template('inbox.html', conversations=conversations)

# 🔹 WebSocket: Join Room
@socketio.on('join')
def join(data):
    room = str(data['user_id'])
    join_room(room)
    emit('status', {'msg': f'User {data["user_id"]} connected'}, room=room)

    # Update user's last activity
    user_activity[data['user_id']] = datetime.now()

# 🔹 WebSocket: Send Message (Ensure Storage in DB)
@socketio.on('send_message')
def handle_message(data):
    sender_id = data['sender_id']
    receiver_id = data['receiver_id']
    content = data['content']

    db = get_db()
    cursor = db.cursor()
    
    # Insert into database
    cursor.execute("INSERT INTO messages (sender_id, receiver_id, content) VALUES (%s, %s, %s)",
                   (sender_id, receiver_id, content))
    db.commit()

    cursor.execute("SELECT LAST_INSERT_ID()")
    message_id = cursor.fetchone()[0]

    db.close()

    message_data = {'id': message_id, 'sender_id': sender_id, 'receiver_id': receiver_id, 'content': content}

    # Emit message to both users
    emit('receive_message', message_data, room=str(sender_id))
    emit('receive_message', message_data, room=str(receiver_id))

    # Update sender's last activity
    user_activity[sender_id] = datetime.now()

# 🔹 Check Online Status
@messages_bp.route('/online_status/<int:user_id>')
def online_status(user_id):
    last_seen = user_activity.get(user_id, None)
    if last_seen and datetime.now() - last_seen < timedelta(seconds=30):
        return jsonify({'status': 'online'})
    else:
        return jsonify({'status': 'offline'})
    
# In-memory storage for message read status
message_read_status = {}

# 🔹 Mark Messages as Seen
@messages_bp.route('/mark_as_seen/<int:sender_id>/<int:receiver_id>', methods=['POST'])
def mark_as_seen(sender_id, receiver_id):
    if 'user_id' not in session or session['user_id'] != receiver_id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    # Update the last seen timestamp for the conversation
    message_read_status[(sender_id, receiver_id)] = datetime.now()
    return jsonify({'status': 'success'})

# 🔹 Check if Messages are Seen
@messages_bp.route('/is_seen/<int:sender_id>/<int:receiver_id>')
def is_seen(sender_id, receiver_id):
    last_seen = message_read_status.get((sender_id, receiver_id), None)
    if last_seen:
        return jsonify({'status': 'seen', 'last_seen': last_seen})
    else:
        return jsonify({'status': 'unseen'})