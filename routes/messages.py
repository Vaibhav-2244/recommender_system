from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from database import get_db
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime, timedelta
import logging
from .smart_reply import get_smart_reply

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

    # Fetch unique users who had a conversation with their last message
    cursor.execute("""
        WITH LastMessages AS (
            SELECT 
                CASE 
                    WHEN m.sender_id = %s THEN m.receiver_id
                    ELSE m.sender_id
                END as other_user_id,
                m.content as last_message,
                m.timestamp as last_message_time,
                ROW_NUMBER() OVER (
                    PARTITION BY CASE 
                        WHEN m.sender_id = %s THEN m.receiver_id
                        ELSE m.sender_id
                    END 
                    ORDER BY m.timestamp DESC
                ) as rn
            FROM messages m
            WHERE m.sender_id = %s OR m.receiver_id = %s
        )
        SELECT 
            u.id,
            u.username,
            p.profile_pic,
            lm.last_message,
            lm.last_message_time
        FROM users u
        JOIN profiles p ON u.id = p.user_id
        JOIN LastMessages lm ON u.id = lm.other_user_id
        WHERE lm.rn = 1
        ORDER BY lm.last_message_time DESC
    """, (user_id, user_id, user_id, user_id))
    
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
    if 'user_id' not in session or session['user_id'] != receiver_id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    # Check if there are any unseen messages from sender to receiver
    db = get_db()
    cursor = db.cursor()
    
    # Get the last seen timestamp from memory
    last_seen = message_read_status.get((sender_id, receiver_id), datetime.min)
    
    cursor.execute("""
        SELECT COUNT(*) as unseen_count
        FROM messages
        WHERE sender_id = %s AND receiver_id = %s
        AND timestamp > %s
    """, (sender_id, receiver_id, last_seen))
    
    result = cursor.fetchone()
    db.close()
    
    if result['unseen_count'] > 0:
        return jsonify({'status': 'unseen'})
    else:
        return jsonify({'status': 'seen'})

# Add new route for getting smart replies
@messages_bp.route('/get_smart_reply', methods=['POST'])
def get_smart_reply_endpoint():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    message = request.json.get('message', '')
    if not message:
        return jsonify({'status': 'error', 'message': 'No message provided'}), 400
    
    try:
        logger.info(f"Received request for smart reply with message: {message}")
        suggestions = get_smart_reply(message)
        logger.info(f"Returning suggestions: {suggestions}")
        return jsonify({'status': 'success', 'suggestions': suggestions})
    except Exception as e:
        logger.error(f"Error in get_smart_reply_endpoint: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500