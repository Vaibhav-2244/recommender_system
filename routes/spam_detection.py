import logging
import pickle
import numpy as np
from flask import Blueprint, current_app, jsonify, request
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from database import get_db
import re
import os
import json

spam_bp = Blueprint('spam', __name__, url_prefix='/api/spam')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SpamDetector:
    def __init__(self, model, vectorizer):
        self.model = model
        self.vectorizer = vectorizer
        self.threshold = 0.6  # Lowered from 0.7 to 0.6

    def detect(self, text):
        try:
            prediction_prob = self.model.predict_proba([text])[0][1]
            return {
                'is_spam': bool(prediction_prob > self.threshold),  # Now using dynamic threshold
                'confidence': float(prediction_prob),
                'features': extract_features(text)
            }
        except Exception as e:
            logger.error(f"Detection error: {str(e)}")
            return {
                'is_spam': False,
                'confidence': 0.0,
                'features': {}
            }

def init_spam_detection(app):
    try:
        model_path = os.path.join(app.root_path, 'static', 'spam_model.pkl')
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Spam model file not found at {model_path}")
            
        with open(model_path, 'rb') as f:
            pipeline = pickle.load(f)
        
        app.spam_detector = SpamDetector(pipeline, pipeline.named_steps['tfidfvectorizer'])
        app.logger.info("Spam detection initialized successfully")
        
        # Test detection
        test_msg = "WIN FREE PRIZE NOW! Click http://scam.com"
        result = app.spam_detector.detect(test_msg)
        app.logger.info(f"Test detection - '{test_msg}': {result}")
        
    except Exception as e:
        app.logger.error(f"Failed to initialize spam detector: {str(e)}")
        app.spam_detector = None

def extract_features(text):
    features = {
        'num_links': len(re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)),
        'num_emails': len(re.findall(r'[\w\.-]+@[\w\.-]+', text)),
        'num_phone': len(re.findall(r'[\+\(]?[1-9][0-9 .\-\(\)]{8,}[0-9]', text)),
        'num_special_chars': len(re.findall(r'[^\w\s]', text)),
        'num_caps': len(re.findall(r'[A-Z]', text)),
        'num_words': len(text.split()),
        'contains_money': int(bool(re.search(r'\$[\d,]+(\.\d+)?|\d+\s*(dollars|USD)', text))),
        'urgent_language': int(bool(re.search(r'\b(urgent|immediately|quick|fast|limited time|offer expires)\b', text, re.I))),
    }
    return features

@spam_bp.route('/detect', methods=['POST'])
def detect_spam():
    if not hasattr(current_app, 'spam_detector') or not current_app.spam_detector:
        return jsonify({'status': 'error', 'message': 'Spam detection not initialized'}), 503
    
    try:
        data = request.json
        message = data.get('message', '')
        
        if not message:
            return jsonify({'status': 'error', 'message': 'No message provided'}), 400
        
        result = current_app.spam_detector.detect(message)
        return jsonify({'status': 'success', **result})
        
    except Exception as e:
        logger.error(f"Detection failed: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@spam_bp.route('/messages/<int:user_id>')
def get_spam_messages(user_id):
    try:
        db = get_db()
        with db.cursor() as cursor:  # Using context manager
            # Verify user exists
            cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            if not cursor.fetchone():
                return jsonify({'status': 'error', 'message': 'User not found'}), 404

            # Get messages
            cursor.execute("""
                SELECT 
                    m.id, m.content, m.timestamp,
                    m.is_spam, m.spam_confidence, 
                    COALESCE(m.spam_features, '{}') as spam_features,
                    u.username as sender_username,
                    COALESCE(p.profile_pic, 'default_profile_pic.png') as profile_pic
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                LEFT JOIN profiles p ON u.id = p.user_id
                WHERE m.receiver_id = %s 
                AND m.is_spam = TRUE
                ORDER BY m.timestamp DESC
            """, (user_id,))
            
            messages = []
            for row in cursor.fetchall():
                try:
                    messages.append({
                        'id': row['id'],
                        'content': row['content'],
                        'timestamp': row['timestamp'].isoformat() if row['timestamp'] else None,
                        'is_spam': bool(row['is_spam']),
                        'spam_confidence': float(row['spam_confidence']) if row['spam_confidence'] else 0.0,
                        'spam_features': json.loads(row['spam_features']) if row['spam_features'] else {},
                        'sender_username': row['sender_username'],
                        'profile_pic': row['profile_pic']
                    })
                except Exception as e:
                    current_app.logger.error(f"Error processing message: {str(e)}")
                    continue

            return jsonify({
                'status': 'success',
                'messages': messages,
                'count': len(messages)
            })

    except Exception as e:
        current_app.logger.error(f"Database error: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500
    finally:
        if 'db' in locals(): db.close()

@spam_bp.route('/test')
def test_route():
    return jsonify({
        'status': 'success',
        'message': 'Spam routes are working',
        'detector_initialized': hasattr(current_app, 'spam_detector')
    })