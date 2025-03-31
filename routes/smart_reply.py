from transformers import pipeline
from sentence_transformers import SentenceTransformer
import torch
import numpy as np
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from functools import lru_cache
import hashlib

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Quick response templates with context
response_templates = {
    'greeting': {
        'patterns': ['hi', 'hello', 'hey', 'greetings'],
        'responses': [
            "Hi there!",
            "Hello! How are you?",
            "Hey! Nice to hear from you!"
        ]
    },
    'question': {
        'patterns': ['?', 'what', 'how', 'why', 'when', 'where', 'who'],
        'responses': [
            "Let me think about that...",
            "That's an interesting question!",
            "I'll get back to you on that."
        ]
    },
    'agreement': {
        'patterns': ['yes', 'yeah', 'yep', 'correct', 'right', 'agree'],
        'responses': [
            "Absolutely!",
            "I agree!",
            "That's exactly right!"
        ]
    },
    'disagreement': {
        'patterns': ['no', 'nope', 'wrong', 'disagree', 'not', "don't"],
        'responses': [
            "I see your point, but...",
            "I respectfully disagree.",
            "Let's discuss this further."
        ]
    },
    'gratitude': {
        'patterns': ['thanks', 'thank you', 'appreciate it', 'grateful'],
        'responses': [
            "You're welcome!",
            "Glad I could help!",
            "Anytime!"
        ]
    },
    'farewell': {
        'patterns': ['bye', 'goodbye', 'see you', 'later', 'take care'],
        'responses': [
            "See you later!",
            "Take care!",
            "Goodbye!"
        ]
    },
    'generic': {
        'patterns': [],
        'responses': [
            "I understand.",
            "That's interesting!",
            "Tell me more about that.",
            "I see what you mean."
        ]
    }
}

# Initialize ML models with error handling and device optimization
try:
    logger.info("Initializing ML models...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")
    
    # Initialize models with device optimization
    sentiment_analyzer = pipeline("sentiment-analysis", device=device)
    text_generator = pipeline("text-generation", model="gpt2", device=device)
    sentence_transformer = SentenceTransformer('all-MiniLM-L6-v2', device=device)
    
    # Pre-compute embeddings for template responses
    template_embeddings = {}
    for category, data in response_templates.items():
        for response in data['responses']:
            template_embeddings[response] = sentence_transformer.encode(response)
    
    logger.info("ML models initialized successfully")
except Exception as e:
    logger.error(f"Error initializing ML models: {str(e)}")
    # Fallback to simpler response system
    sentiment_analyzer = None
    text_generator = None
    sentence_transformer = None
    template_embeddings = {}

# Cache for message embeddings
message_embedding_cache = {}

def get_message_hash(message):
    """Generate a hash for the message to use as cache key"""
    return hashlib.md5(message.encode()).hexdigest()

@lru_cache(maxsize=1000)
def get_smart_reply(message):
    try:
        logger.info(f"Generating smart reply for message: {message}")
        suggestions = []
        message_lower = message.lower()
        
        # 1. Pattern-based matching (fastest)
        for category, data in response_templates.items():
            if any(pattern in message_lower for pattern in data['patterns']):
                suggestions.extend(data['responses'])
        
        # 2. Sentiment Analysis (if available)
        if sentiment_analyzer:
            try:
                sentiment = sentiment_analyzer(message)[0]
                logger.info(f"Sentiment analysis result: {sentiment}")
                
                if sentiment['label'] == 'POSITIVE':
                    suggestions.extend([
                        "That's great to hear!",
                        "I'm glad you feel that way!",
                        "That sounds wonderful!"
                    ])
                elif sentiment['label'] == 'NEGATIVE':
                    suggestions.extend([
                        "I understand how you feel.",
                        "I'm here to listen.",
                        "That must be difficult."
                    ])
            except Exception as e:
                logger.error(f"Error in sentiment analysis: {str(e)}")
        
        # 3. Contextual Response Generation (if available)
        if text_generator:
            try:
                # Generate contextual response with optimized parameters
                generated = text_generator(
                    message,
                    max_length=50,
                    num_return_sequences=1,
                    pad_token_id=text_generator.tokenizer.eos_token_id,
                    temperature=0.7,
                    top_p=0.9,
                    do_sample=True,
                    early_stopping=True
                )
                if generated and len(generated) > 0:
                    suggestions.append(generated[0]['generated_text'])
            except Exception as e:
                logger.error(f"Error generating text: {str(e)}")
        
        # 4. Semantic Similarity (if available)
        if sentence_transformer and template_embeddings:
            try:
                # Get message embedding (use cache if available)
                message_hash = get_message_hash(message)
                if message_hash in message_embedding_cache:
                    message_embedding = message_embedding_cache[message_hash]
                else:
                    message_embedding = sentence_transformer.encode(message)
                    message_embedding_cache[message_hash] = message_embedding
                
                # Compare with pre-computed template embeddings
                for response, response_embedding in template_embeddings.items():
                    similarity = cosine_similarity(
                        [message_embedding],
                        [response_embedding]
                    )[0][0]
                    
                    if similarity > 0.5:  # Threshold for similarity
                        suggestions.append(response)
            except Exception as e:
                logger.error(f"Error in semantic similarity: {str(e)}")
        
        # Remove duplicates and limit to 3 suggestions
        suggestions = list(dict.fromkeys(suggestions))[:3]
        
        # If no suggestions were generated, use generic responses
        if not suggestions:
            suggestions = response_templates['generic']['responses'][:3]
        
        logger.info(f"Generated suggestions: {suggestions}")
        return suggestions
        
    except Exception as e:
        logger.error(f"Error in get_smart_reply: {str(e)}")
        return response_templates['generic']['responses'][:3] 