from flask import Flask, render_template, request, jsonify, send_from_directory, send_file, Response, session, g
import os
import re
import json
import time
import io
import asyncio
import hashlib
import edge_tts
from datetime import datetime
from dotenv import load_dotenv
from ai_engine import GrammarBot
from functools import wraps

load_dotenv()

app = Flask(__name__, static_folder='static')

# SECURE: Use environment variable, fallback to dev key only if missing
app.secret_key = os.environ.get("FLASK_SECRET", "dev_fallback_supernova_secret")

# Initialize AI Engine
ai = GrammarBot()

# --- 1. CORS ENABLED (For Mobile App Support) ---
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# --- 2. ENHANCED RATE LIMITER ---
request_log = {}

def rate_limiter(limit=20, window=60, key_prefix="rl_"):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Use user ID if logged in, else IP
            identifier = session.get('user_id', request.remote_addr)
            cache_key = f"{key_prefix}_{identifier}"
            
            current_time = time.time()
            
            # Initialize or clean old requests
            if cache_key not in request_log:
                request_log[cache_key] = []
            
            # Remove old timestamps
            request_log[cache_key] = [
                t for t in request_log[cache_key] 
                if current_time - t < window
            ]
            
            # Check limit
            if len(request_log[cache_key]) >= limit:
                return jsonify({
                    "error": "Rate limit exceeded",
                    "retry_after": window,
                    "limit": limit,
                    "window": window,
                    "conversational_reply": "You are speaking a bit too fast! Please wait a moment.",
                    "improved_version": "Rate limit exceeded.",
                    "score": 0,
                    "native_explanation": "System Cooldown Active"
                }), 429
            
            # Log request
            request_log[cache_key].append(current_time)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- 3. DAILY WORD CACHING LOGIC ---
DAILY_WORD_FILE = "daily_word_cache.json"

def get_daily_word_smart():
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # A. Try to load from cache
    if os.path.exists(DAILY_WORD_FILE):
        try:
            with open(DAILY_WORD_FILE, 'r') as f:
                data = json.load(f)
                if data.get('date') == today_str:
                    return data 
        except:
            pass 

    # B. Cache expired? Fetch from AI
    try:
        prompt = "Give me one sophisticated English word, its definition, and a short example. JSON format: {'word': '...', 'meaning': '...', 'example': '...'}"
        response = ai.client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"}
        )
        new_word = json.loads(response.choices[0].message.content)
        new_word['date'] = today_str 
        
        with open(DAILY_WORD_FILE, 'w') as f:
            json.dump(new_word, f)
            
        return new_word
    except Exception as e:
        print(f"Daily Word Error: {e}")
        return {"word": "Resilience", "meaning": "The capacity to recover quickly from difficulties.", "example": "She showed great resilience."}

# --- ROUTES ---

@app.route('/')
def dashboard():
    word_data = get_daily_word_smart()
    return render_template('dashboard.html', daily_word=word_data)

@app.route('/practice/<mode>')
def practice(mode):
    return render_template('speaking.html', mode=mode)

@app.route('/api/start', methods=['POST'])
def start_session():
    data = request.json
    mode = data.get('mode', 'conversation')
    native_lang = data.get('native_lang', 'Hindi')
    reply = ai.generate_intro(mode, native_lang)
    return jsonify({"reply": reply})

# OFFLINE MODE FLAG
OFFLINE_MODE = False

@app.route('/api/analyze', methods=['POST'])
@rate_limiter(limit=20, window=60)
def analyze():
    if OFFLINE_MODE:
        # Fallback response
        data = request.json
        text = data.get('text', '')
        import random
        responses = [
            "That's interesting. Tell me more.",
            "Good point! How would you say that differently?",
            "I understand. What happened next?",
            "Great! Let's continue practicing."
        ]
        return jsonify({
            "conversational_reply": random.choice(responses),
            "improved_version": text,
            "score": 85,
            "native_explanation": "Practice mode active (Offline)"
        })

    data = request.json
    text = data.get('text', '')
    mode = data.get('mode', 'conversation')
    native_lang = data.get('native_lang', 'Hindi')
    history = data.get('history', [])
    
    ai_result = ai.analyze(text, history=history, mode=mode, native_lang=native_lang)
    
    raw_score = ai_result.get('score', '0')
    try:
        match = re.search(r'\d+', str(raw_score))
        num = int(match.group()) if match else 0
        if num <= 10: num *= 10
        score_val = min(100, num)
    except:
        score_val = 0

    response = {
        "conversational_reply": ai_result.get('reply'),
        "improved_version": ai_result.get('corrected'),
        "score": score_val,
        "native_explanation": " • ".join(ai_result.get('corrections', []))
    }
    
    return jsonify(response)

# Endpoint alias for frontend compatibility
@app.route('/api/analyze_text', methods=['POST'])
def analyze_text():
    return analyze()

# --- HYBRID AUDIO ENDPOINT (Smart Cache + Streaming) ---
@app.route('/api/speak', methods=['POST'])
def speak_text():
    data = request.json
    text = data.get('text', '')
    if not text: return jsonify({"error": "No text provided"}), 400

    # 1. Check Disk Cache (Instant Reply for repeated phrases)
    text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
    cache_dir = os.path.join(app.static_folder, 'audio_cache')
    os.makedirs(cache_dir, exist_ok=True)
    # Ensure proper permissions
    try:
        os.chmod(cache_dir, 0o755)
    except:
        pass
        
    cache_path = os.path.join(cache_dir, f"{text_hash}.mp3")

    if os.path.exists(cache_path):
        # Serve directly from disk (Zero processing latency)
        return send_file(cache_path, mimetype="audio/mpeg")

    # 2. Decide: Cache (Short) or Stream (Long)
    is_short_phrase = len(text) < 100

    if is_short_phrase:
        # Generate full file, save to disk, then send
        async def generate_and_save():
            voice = "en-US-AriaNeural"
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(cache_path)

        try:
            # Create a fresh loop for this sync call
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(generate_and_save())
            loop.close()
            return send_file(cache_path, mimetype="audio/mpeg")
        except Exception as e:
            print(f"Cache Gen Error: {e}")
            # Fallback to streaming if save fails
            pass

    # 3. Stream Audio (Fallback or Long Text)
    def generate_audio_stream():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            voice = "en-US-AriaNeural"
            communicate = edge_tts.Communicate(text, voice)
            
            async def stream_chunks():
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        yield chunk["data"]

            gen = stream_chunks()
            while True:
                try:
                    chunk = loop.run_until_complete(gen.__anext__())
                    yield chunk
                except StopAsyncIteration:
                    break
        finally:
            loop.close()

    return Response(generate_audio_stream(), mimetype="audio/mpeg")

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=7860)