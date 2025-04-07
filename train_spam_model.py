import pickle
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline

# Enhanced training data - add more examples
spam_messages = [
    "Win a free iPhone now! Click here!",
    "Limited time offer! 50% off all products!",
    "You've won $1000! Claim your prize!",
    "Urgent! Your account has been compromised!",
    "Make money fast working from home!",
    "Special promotion just for you!",
    "Congratulations! You're our 1,000,000th visitor!",
    "Your package delivery is pending - click to track",
    "Bank account verification required!",
    "Exclusive deal for you only!",
    "Double your bitcoin in 24 hours!",
    "Nigerian prince needs your help",
    "Claim your inheritance now",
    "You have unclaimed funds",
    "Important security alert for your account"
]

ham_messages = [
    "Hey, how are you doing?",
    "Let's meet for coffee tomorrow",
    "Did you see the game last night?",
    "Can you send me the report when you get a chance?",
    "Thanks for your help with the project",
    "What time should we meet for dinner?",
    "I'll be there in about 15 minutes",
    "Don't forget to bring your laptop",
    "The meeting has been rescheduled to 3pm",
    "Happy birthday! Hope you have a great day!",
    "Can we reschedule our meeting?",
    "I've attached the document you requested",
    "Looking forward to our call tomorrow",
    "Thanks for your email",
    "Let me know if you need anything else"
]

# Create labeled dataset
X = np.array(spam_messages + ham_messages)
y = np.array([1] * len(spam_messages) + [0] * len(ham_messages))

# Split into train/test
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Create and train model - using make_pipeline for cleaner structure
model = make_pipeline(
    TfidfVectorizer(),
    LogisticRegression(max_iter=1000)
)

model.fit(X_train, y_train)

# Evaluate
print(f"Test accuracy: {model.score(X_test, y_test):.2f}")

# Save the ENTIRE pipeline as one file
with open('static/spam_model.pkl', 'wb') as f:
    pickle.dump(model, f)

print("Model pipeline trained and saved successfully")