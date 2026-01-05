import boto3
import uuid
from datetime import datetime, UTC
from dotenv import load_dotenv
import os
import tempfile
from groq import Groq
from flask import Flask, request, jsonify
from flask_cors import CORS
from deepgram import DeepgramClient, PrerecordedOptions

# ------------------------------
# LOAD ENVIRONMENT VARIABLES
# ------------------------------
load_dotenv()

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
AWS_REGION = os.getenv("AWS_REGION")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "be0da791afd11bf54bd1308572ee18533852e273")

# ------------------------------
# FLASK APP INITIALIZATION
# ------------------------------
app = Flask(__name__)
CORS(
    app,
    resources={r"/*": {
        "origins": [
            "http://localhost:3000",
            "https://major-rbn1.onrender.com"
        ]
    }},
    supports_credentials=True
)


# ------------------------------
# CONNECT TO AWS DYNAMODB
# ------------------------------
dynamodb = boto3.resource(
    "dynamodb",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

# ------------------------------
# SERVICE TABLE MAP
# ------------------------------
TABLE_MAP = {
    1: "DoctorQueries",
    2: "HomeAppliances",
    3: "Police",
    4: "Plumber",
    5: "Electrician",
    6: "Carpenter",
    7: "Banking",
    8: "Education",
    9: "FoodHomeNeeds",
    10: "SocietyProblems",
    11: "TechnicalSupport",
    12: "Transportation",
    13: "other"
}

# ------------------------------
# LOGIN CREDENTIALS MAP
# ------------------------------
LOGIN_CREDENTIALS = {
    "DoctorQueries": {"username": "DoctorQueries", "password": "password", "category": 1},
    "HomeAppliances": {"username": "HomeAppliances", "password": "password", "category": 2},
    "Police": {"username": "Police", "password": "password", "category": 3},
    "Plumber": {"username": "Plumber", "password": "password", "category": 4},
    "Electrician": {"username": "Electrician", "password": "password", "category": 5},
    "Carpenter": {"username": "Carpenter", "password": "password", "category": 6},
    "Banking": {"username": "Banking", "password": "password", "category": 7},
    "Education": {"username": "Education", "password": "password", "category": 8},
    "FoodHomeNeeds": {"username": "FoodHomeNeeds", "password": "password", "category": 9},
    "SocietyProblems": {"username": "SocietyProblems", "password": "password", "category": 10},
    "TechnicalSupport": {"username": "TechnicalSupport", "password": "password", "category": 11},
    "Transportation": {"username": "Transportation", "password": "password", "category": 12},
    "other": {"username": "other", "password": "password", "category": 13},
}

# ------------------------------
# GENERATE SUMMARY FOR QUERY
# ------------------------------
def generate_summary(query_text):
    """Generate a brief summary of the query using Groq"""
    try:
        if not query_text or len(query_text.strip()) == 0:
            return "No summary available"
        
        client = Groq(api_key=GROQ_API_KEY)
        
        prompt = (
            f"Provide a brief, concise summary (maximum 2-3 sentences) of the following query: \"{query_text}\". "
            "Focus on the main request or concern. Keep it professional and clear."
        )
        
        print(f"🤖 Generating summary...")
        
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.5,
            max_tokens=150
        )
        
        summary = completion.choices[0].message.content.strip()
        print(f"✅ Summary generated")
        return summary if summary else "Summary unavailable"
        
    except Exception as e:
        print(f"❌ Error generating summary: {str(e)}")
        return query_text[:100] + "..." if len(query_text) > 100 else query_text

# ------------------------------
# FETCH ALL ITEMS
# ------------------------------
def fetch_all_items(table_name):
    """Fetch all items from DynamoDB table"""
    try:
        table = dynamodb.Table(table_name)
        response = table.scan()
        items = response.get("Items", [])
        
        if not items:
            return []
        
        # Sort by timestamp ascending (oldest first, newest last)
        items.sort(key=lambda x: x.get("timestamp", ""))
        return items
    except Exception as e:
        print(f"❌ Error fetching items from {table_name}: {str(e)}")
        raise

# ------------------------------
# SAVE QUERY WITH SUMMARY
# ------------------------------
def save_query(service_number, query_text):
    """Save query to DynamoDB with auto-generated summary"""
    table_name = TABLE_MAP[service_number]
    table = dynamodb.Table(table_name)

    # Generate summary ONCE when saving
    print(f"\n{'='*60}")
    print(f"📝 GENERATING SUMMARY FOR NEW QUERY")
    print(f"{'='*60}")
    summary = generate_summary(query_text)
    print(f"📋 Summary: {summary}")

    item = {
        "query_id": str(uuid.uuid4()),
        "query_text": query_text,
        "summary_text": summary,  # ✅ CHANGED: Using summary_text instead of summary
        "timestamp": datetime.now(UTC).isoformat()
    }

    try:
        table.put_item(Item=item)
        print(f"\n{'='*60}")
        print(f"✅ QUERY + SUMMARY SAVED TO AWS DYNAMODB")
        print(f"{'='*60}")
        print(f"📝 Query: {query_text[:50]}...")
        print(f"📋 Summary: {summary[:50]}...")
        print(f"🔢 Category: {service_number}")
        print(f"📊 Table: {table_name}")
        print(f"🆔 Query ID: {item['query_id']}")
        print(f"⏰ Timestamp: {item['timestamp']}")
        print(f"{'='*60}\n")
        return item
    except Exception as e:
        print(f"\n❌ ERROR SAVING TO DYNAMODB")
        print(f"Error: {str(e)}\n")
        raise

# ------------------------------
# CLASSIFY QUERY
# ------------------------------
def classify_query(user_query):
    """Classify user query into categories using Groq"""
    client = Groq(api_key=GROQ_API_KEY)

    prompt = (
        "You are a classification model. "
        "Classify the user query into one of the following categories: "
        "1. DoctorQueries, "
        "2. HomeAppliances, "
        "3. Police, "
        "4. Plumber, "
        "5. Electrician, "
        "6. Carpenter, "
        "7. Banking, "
        "8. Education, "
        "9. FoodHomeNeeds, "
        "10. SocietyProblems, "
        "11. TechnicalSupport, "
        "12. Transportation. "
        f'Input Query: "{user_query}". '
        "Respond with only the category number. "
        "If the query is meaningless, random text (e.g., tycdvhjdvd), or does not match any category, return 0. "
        "Try your best to match to the closest category. "
        "Return ONLY the number with no extra text."
    )

    print(f"\n{'='*60}")
    print(f"🤖 CLASSIFYING QUERY")
    print(f"{'='*60}")
    print(f"📝 Query: \"{user_query}\"")

    try:
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=10
        )

        response_text = completion.choices[0].message.content.strip()
        print(f"📥 API Response: \"{response_text}\"")

        category_num = int(response_text)
        print(f"✅ Category: {category_num}")
    except:
        category_num = 0
        print(f"⚠️  Failed to parse, defaulting to 0")

    if category_num == 0 or category_num not in TABLE_MAP:
        category_num = 13  # OTHER
        print(f"🔄 Mapping to category 13 (other)")

    print(f"🎯 Final Category: {category_num} → {TABLE_MAP[category_num]}")
    print(f"{'='*60}\n")

    return category_num

# ------------------------------
# AUDIO TRANSCRIPTION
# ------------------------------
def audio_to_text(audio_file_path: str) -> str:
    """Convert audio file to text using Deepgram"""
    try:
        print(f"\n{'='*60}")
        print(f"🎤 TRANSCRIBING AUDIO")
        print(f"{'='*60}")
        print(f"📁 File: {audio_file_path}")
        
        client = DeepgramClient(api_key=DEEPGRAM_API_KEY)
        
        with open(audio_file_path, "rb") as audio_file:
            payload = {"buffer": audio_file}
            
            options = PrerecordedOptions(
                model="nova-2",
                language="en-US",
                punctuate=True,
                smart_format=True,
            )
            
            print("📡 Sending to Deepgram...")
            response = client.listen.rest.v("1").transcribe_file(payload, options)
        
        transcript = response["results"]["channels"][0]["alternatives"][0]["transcript"]
        
        if transcript:
            print(f"✅ Transcription successful")
            print(f"📝 Text: \"{transcript}\"")
            print(f"{'='*60}\n")
            return transcript
        else:
            print("❌ Empty transcript")
            return None
            
    except Exception as e:
        print(f"❌ Transcription error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

# ------------------------------
# FLASK ROUTES
# ------------------------------

@app.route('/process_query', methods=['POST'])
def process_query():
    """Process text query: classify + save with summary"""
    try:
        print(f"\n{'#'*60}")
        print(f"🌐 NEW TEXT QUERY RECEIVED")
        print(f"{'#'*60}")
        
        data = request.get_json()
        user_query = data.get('query', '').strip()
        
        if not user_query:
            return jsonify({"error": "Query is required"}), 400
        
        print(f"📝 Query: \"{user_query}\"")
        
        # Classify
        category_num = classify_query(user_query)
        
        # Save with summary
        saved_item = save_query(category_num, user_query)
        
        return jsonify({
            "success": True,
            "category": category_num,
            "message": "Your query has been submitted."
        }), 200
        
    except Exception as e:
        print(f"\n❌ ERROR IN /process_query")
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/transcribe_audio', methods=['POST'])
def transcribe_audio_endpoint():
    """Transcribe audio and return text only"""
    try:
        print(f"\n{'#'*60}")
        print(f"🎤 AUDIO TRANSCRIPTION REQUEST")
        print(f"{'#'*60}")
        
        if 'audio' not in request.files:
            return jsonify({"error": "No audio file provided"}), 400
        
        audio_file = request.files['audio']
        
        if audio_file.filename == '':
            return jsonify({"error": "No audio file selected"}), 400
        
        file_ext = os.path.splitext(audio_file.filename)[1] or '.mp3'
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
        audio_file.save(temp_file.name)
        temp_file_path = temp_file.name
        temp_file.close()
        
        transcript = audio_to_text(temp_file_path)
        
        try:
            os.unlink(temp_file_path)
        except:
            pass
        
        if not transcript or not transcript.strip():
            return jsonify({"error": "Failed to transcribe audio"}), 500
        
        return jsonify({
            "success": True,
            "transcript": transcript.strip()
        }), 200
        
    except Exception as e:
        print(f"\n❌ ERROR IN /transcribe_audio")
        print(f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/process_audio', methods=['POST'])
def process_audio():
    """Process audio: transcribe + classify + save with summary"""
    try:
        print(f"\n{'#'*60}")
        print(f"🎤 AUDIO QUERY RECEIVED")
        print(f"{'#'*60}")
        
        if 'audio' not in request.files:
            return jsonify({"error": "No audio file provided"}), 400
        
        audio_file = request.files['audio']
        
        if audio_file.filename == '':
            return jsonify({"error": "No audio file selected"}), 400
        
        file_ext = os.path.splitext(audio_file.filename)[1] or '.mp3'
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
        audio_file.save(temp_file.name)
        temp_file_path = temp_file.name
        temp_file.close()
        
        transcript = audio_to_text(temp_file_path)
        
        try:
            os.unlink(temp_file_path)
        except:
            pass
        
        if not transcript or not transcript.strip():
            return jsonify({"error": "Failed to transcribe audio"}), 500
        
        user_query = transcript.strip()
        
        # Classify
        category_num = classify_query(user_query)
        
        # Save with summary
        saved_item = save_query(category_num, user_query)
        
        return jsonify({
            "success": True,
            "category": category_num,
            "message": "Your query has been submitted.",
            "transcript": user_query
        }), 200
        
    except Exception as e:
        print(f"\n❌ ERROR IN /process_audio")
        print(f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/login', methods=['POST', 'OPTIONS'])
def login():
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({"ok": True}), 200

    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        for creds in LOGIN_CREDENTIALS.values():
            if creds['username'] == username and creds['password'] == password:
                return jsonify({
                    "success": True,
                    "category": creds['category'],
                    "username": username
                }), 200

        return jsonify({
            "success": False,
            "error": "Invalid login details."
        }), 401

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_queries/<int:category>', methods=['GET'])
def get_queries(category):
    """
    ✅ FETCH QUERIES FROM AWS DYNAMODB
    Summary is fetched directly from database (NOT generated)
    """
    try:
        print(f"\n{'='*60}")
        print(f"📊 FETCHING QUERIES FROM AWS")
        print(f"{'='*60}")
        print(f"🔢 Category: {category}")
        
        if category not in TABLE_MAP:
            return jsonify({"success": False, "error": "Invalid category"}), 400
        
        table_name = TABLE_MAP[category]
        print(f"📊 Table: {table_name}")
        
        # Fetch from DynamoDB
        items = fetch_all_items(table_name)
        print(f"📦 Found {len(items)} items")
        
        # Format for frontend
        queries = []
        for item in items:
            query_text = item.get("query_text", "")
            summary = item.get("summary_text", "")  # ✅ CHANGED: Using summary_text
            
            # If summary missing (old data), use fallback
            if not summary or summary.strip() == "":
                print(f"⚠️  No summary_text for {item.get('query_id', 'unknown')}, using fallback")
                summary = query_text[:100] + "..." if len(query_text) > 100 else query_text
            
            queries.append({
                "query_id": item.get("query_id", ""),
                "query_text": query_text,
                "summary": summary,  # Frontend expects "summary"
                "category": category,
                "timestamp": item.get("timestamp", "")
            })
        
        print(f"✅ Successfully fetched {len(queries)} queries")
        print(f"✅ All summaries from AWS DynamoDB (summary_text field)")
        print(f"{'='*60}\n")
        
        return jsonify({
            "success": True,
            "queries": queries,
            "category": category,
            "table_name": table_name
        }), 200
        
    except Exception as e:
        print(f"❌ Error in /get_queries: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 FLASK SERVER STARTING")
    print("="*60)
    print("✅ Summary saved as 'summary_text' in AWS")
    print("✅ Dashboard fetches from 'summary_text' field")
    print("="*60 + "\n")
    app.run(debug=True, port=5000, host="0.0.0.0")
