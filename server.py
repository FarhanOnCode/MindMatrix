from flask import Flask, request, jsonify
from flask_cors import CORS
from fuzzywuzzy import process, fuzz
import json
import os
import traceback
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import datetime


app = Flask(__name__)
CORS(app)

# MongoDB Connection
client = MongoClient("mongodb+srv://farhanshaik600:Farhan%231474@cluster0.gpnjw.mongodb.net/chatbotDB?retryWrites=true&w=majority&appName=Cluster0")
db = client["chatbotDB"]
interactions_collection = db["interactions"]  # Changed name to better reflect purpose
users_collection = db["users"]

# Load JSON files
json_path = r"bca_data.json"
generic_responses_path = r"generic_responses.json"

# Ensure JSON files exist before loading
if not os.path.exists(json_path):
    raise FileNotFoundError(f"Missing JSON file: {json_path}")
if not os.path.exists(generic_responses_path):
    raise FileNotFoundError(f"Missing JSON file: {generic_responses_path}")

with open(json_path, "r", encoding="utf-8") as file:
    json_data = json.load(file)

with open(generic_responses_path, "r", encoding="utf-8") as file:
    generic_responses = json.load(file)

# Flatten generic responses
flat_responses = {}
for category, responses in generic_responses.items():
    flat_responses.update(responses)

# Extract subjects and all related terms from JSON for better matching
json_subjects = list(json_data["subjects"].keys())
subject_aliases = {}

# Build a list of alternative ways to refer to each subject
subject_aliases = {}

for subject in json_subjects:
    aliases = [subject.lower()]
    
    if "computer" in subject.lower():
        aliases.extend(["comp", "computer", "computers", "fundamentals"])
    if "programming" in subject.lower():
        aliases.extend(["program", "programming", "coding"])
    if "c" in subject.lower() and "programming" in subject.lower():
        aliases.extend(["c programming", "c language",])
    if "java" in subject.lower():
        aliases.extend(["java", "java programming", "j2ee", "javaa"])
    if "database" in subject.lower():
        aliases.extend(["db", "database", "dbms", "sql"])
    if "artificial" in subject.lower():
        aliases.extend([ "artificial intelligence","artificial","Artificial"])
    if "cloud" in subject.lower():
        aliases.extend(["cloud", "aws", "azure"])
    if "cyber" in subject.lower():
        aliases.extend(["security", "cyber", "hacking", "cybersecurity"])
    if "machine" in subject.lower():
        aliases.extend(["ml", "machine learning", "data science"])
    if "blockchain" in subject.lower():
        aliases.extend(["blockchain", "bitcoin", "crypto"])
    if "operating system" in subject.lower():
        aliases.extend(["os", "operating systems", "linux", "windows"])
    if "network" in subject.lower():
        aliases.extend(["networking", "cn", "computer networks"])
    if "software engineering" in subject.lower():
        aliases.extend(["se", "software engg", "software development", "sdlc"])
    if "data structures" in subject.lower() or "algorithms" in subject.lower():
        aliases.extend(["dsa", "data structures", "algorithms", "coding problems"])
    if "web development" in subject.lower():
        aliases.extend(["web dev", "frontend", "backend", "full stack"])
    if "embedded" in subject.lower():
        aliases.extend(["embedded", "microcontrollers", "hardware programming"])
    if "python" in subject.lower():
        aliases.extend(["python", "python programming"])
    if "advanced java" in subject.lower():
        aliases.extend(["java advanced", "spring", "hibernate", "j2ee"])
    if "information technology" in subject.lower():
        aliases.extend(["it", "information tech", "infotech", "it security"])
    if "big data" in subject.lower():
        aliases.extend(["big data", "hadoop", "spark", "data analytics"])
    
    subject_aliases[subject] = aliases

# Track conversation context
conversation_context = {}

@app.route('/signup', methods=['POST'])
def signup():
    try:
        username = request.json.get('username')
        email = request.json.get('email')
        password = request.json.get('password')

        # Check if user already exists
        if users_collection.find_one({"$or": [{"username": username}, {"email": email}]}):
            return jsonify({"message": "Username or email already exists"}), 400

        # Hash the password
        hashed_password = generate_password_hash(password)

        # Create new user
        users_collection.insert_one({
            "username": username,
            "email": email,
            "password": hashed_password
        })

        return jsonify({"message": "User created successfully"}), 201

    except Exception as e:
        print("Error:", traceback.format_exc())
        return jsonify({"message": "Server error"}), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        username = request.json.get('username')
        password = request.json.get('password')

        # Find user
        user = users_collection.find_one({"username": username})
        if not user or not check_password_hash(user['password'], password):
            return jsonify({"message": "Invalid credentials"}), 401

        # Initialize context for user if needed
        user_id = str(user['_id'])
        if user_id not in conversation_context:
            conversation_context[user_id] = {
                "last_subject": None
            }

        return jsonify({"message": "Login successful", "user_id": user_id}), 200

    except Exception as e:
        print("Error:", traceback.format_exc())
        return jsonify({"message": "Server error"}), 500

@app.route('/get_response', methods=['POST'])
def get_response():
    try:
        user_message = request.json.get('message', '').lower()
        user_id = request.json.get('user_id', 'anonymous')
        
        print(f"Received from {user_id}: {user_message}")
        
        # Initialize interaction document with user query
        interaction = {
            "user_id": user_id,
            "user_message": user_message,
            "timestamp": datetime.datetime.now()
        }
        
        # Initialize context if needed
        if user_id not in conversation_context:
            conversation_context[user_id] = {
                "last_subject": None
            }
        
        # Get last subject from context
        last_subject = conversation_context[user_id]["last_subject"]

        # Check for generic responses
        best_match, score = process.extractOne(user_message, flat_responses.keys(), scorer=fuzz.partial_ratio)
        if score > 95:
            bot_response = flat_responses[best_match]
            interaction["bot_response"] = bot_response
            interactions_collection.insert_one(interaction)  # Single storage
            return jsonify({"response": bot_response})

        # Check if message contains subject reference
        subject_match = None
        best_score = 0
        
        # First, try to match direct subject names
        for subject in json_subjects:
            for alias in subject_aliases[subject]:
                if alias in user_message:
                    subject_match = subject
                    best_score = 100
                    break
            if best_score == 100:
                break
        
        # If no exact match found, use fuzzy matching
        if not subject_match:
            # Flatten all aliases to find the best match
            all_aliases = []
            for subject, aliases in subject_aliases.items():
                for alias in aliases:
                    all_aliases.append((subject, alias))
            
            # Find best match in aliases
            best_matches = process.extract(user_message, [a[1] for a in all_aliases], limit=5, scorer=fuzz.token_set_ratio)
            for match, score in best_matches:
                if score > 70:  # Higher threshold for better accuracy
                    for subject, alias in all_aliases:
                        if alias == match:
                            subject_match = subject
                            best_score = score
                            break
                    break
        
        # Update context with subject if found
        if subject_match:
            conversation_context[user_id]["last_subject"] = subject_match
            last_subject = subject_match
        
        # Check for information type keywords
        info_types = {
            "books": ["book", "books", "textbook", "reference", "read"],
            "topics": ["topic", "topics", "important topics", "concepts", "study", "syllabus"],
            "pyqs": ["pyq", "pyqs", "previous year", "question", "questions", "past year", "paper", "exam"]
        }
        
        requested_info = None
        for info_type, keywords in info_types.items():
            for keyword in keywords:
                if keyword in user_message:
                    requested_info = info_type
                    break
            if requested_info:
                break
                
        # If no explicit info type found, check with fuzzy matching
        if not requested_info:
            combined_keywords = sum(info_types.values(), [])
            best_match, score = process.extractOne(user_message, combined_keywords, scorer=fuzz.partial_ratio)
            if score > 70:
                for info_type, keywords in info_types.items():
                    if best_match in keywords:
                        requested_info = info_type
                        break
        
        # Generate response based on identified subject and requested info
        if last_subject and requested_info:
            # We have both subject and info type - provide specific information
            subject_data = json_data["subjects"].get(last_subject, {})
            
            if requested_info == "books":
                books = subject_data.get("books", ["No books available"])
                bot_response = f"📚 Books for {last_subject}:\n" + "\n".join(books)
            elif requested_info == "topics":
                topics = subject_data.get("important_topics", ["No topics available"])
                bot_response = f"🔑 Important Topics for {last_subject}:\n" + "\n".join(topics)
            elif requested_info == "pyqs":
                pyqs = subject_data.get("pyqs", ["No previous year questions available"])
                bot_response = f"📝 Previous Year Questions for {last_subject}:\n" + "\n".join(pyqs)
        
        elif last_subject:
            # We have subject but no info type - ask what info they want
            bot_response = f"I have information about {last_subject}. What would you like to explore—recommended books, important topics, or PYQ's? Let me know! 😊📚"
        
        elif requested_info:
            # We have info type but no subject - ask which subject
            subjects_list = ", ".join(json_subjects)
            bot_response = f"For which subject would you like to know about {requested_info}? Available subjects: {subjects_list}"
        
        else:
            # Neither subject nor info type - general help
            subjects_list = ", ".join(json_subjects)
            bot_response = f"⚠️ I couldn't understand your query. I can provide information about BCA subjects like {subjects_list}. Try asking about books, topics, or previous year questions for any subject."
        
        # Store interaction in MongoDB (single storage)
        interaction["bot_response"] = bot_response
        interactions_collection.insert_one(interaction)
        
        return jsonify({"response": bot_response})

    except Exception as e:
        print("Error:", traceback.format_exc())
        bot_response = f"⚠️ Error occurred: {str(e)}"
        
        # Store error interaction
        interaction = {
            "user_id": request.json.get('user_id', 'anonymous'),
            "user_message": request.json.get('message', ''),
            "bot_response": bot_response,
            "error": str(e),
            "timestamp": datetime.datetime.now()
        }
        interactions_collection.insert_one(interaction)
        
        return jsonify({"response": bot_response})

# Add a missing import at the top
import datetime

if __name__ == '__main__':
    app.run(debug=True, port=5000)