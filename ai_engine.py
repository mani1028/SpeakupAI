import os
import json
import time
import hashlib
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

class GrammarBot:
    def __init__(self):
        self.api_key = os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            print("⚠️ WARNING: GROQ_API_KEY not found in .env")
        
        self.client = Groq(api_key=self.api_key)
        self.model_id = "llama-3.1-8b-instant"
        print(f"✅ AI Connected to Groq ({self.model_id})")
        
        # In-memory cache for API responses
        self.request_cache = {}
        self.cache_timeout = 300 # 5 minutes

    def generate_intro(self, mode, native_lang="Hindi"):
        """Generates the initial message when a user clicks a card."""
        if mode == 'reflex_drill':
            return f"Welcome to Speed Drill! I will give you a sentence in {native_lang}, and you translate it to English. Ready?"
        elif mode == 'job_interview':
            return "Hello. I am the Hiring Manager. Let's start the interview. Tell me about yourself."
        elif mode == 'topic_talk':
            return "Welcome to Topic Talk. Choose a topic (e.g., 'Artificial Intelligence', 'My Hometown') and speak about it for a minute. Go ahead!"
        elif mode == 'email_drafter':
            return "I am your Email Assistant. Tell me: Who are you emailing and what is the key message? (e.g., 'Tell boss I am sick')"
        else:
            return "Hi there! I'm SpeakUp, your English tutor. Let's practice conversation. How was your day?"

    def analyze(self, text, history=[], mode="conversation", native_lang="Hindi"):
        if not text or not text.strip():
            return {"corrected": "I didn't hear anything.", "score": "0", "corrections": []}

        # --- 0. CHECK CACHE ---
        # Create unique key based on inputs
        history_str = str([h.get('content', '') for h in history[-2:]]) # Only use recent history
        cache_key = f"{mode}_{hashlib.md5(text.encode()).hexdigest()}_{hashlib.md5(history_str.encode()).hexdigest()}"
        
        current_time = time.time()
        if cache_key in self.request_cache:
            cached_data, timestamp = self.request_cache[cache_key]
            if current_time - timestamp < self.cache_timeout:
                print(f"📦 Using cached response for: {text[:30]}...")
                return cached_data
            else:
                # Expired
                del self.request_cache[cache_key]

        # --- 1. ZERO-COST GREETINGS ---
        greetings = ["hi", "hello", "hey", "good morning", "good evening", "namaste", "hola"]
        closings = ["bye", "goodbye", "see you", "exit", "quit"]
        
        text_lower = text.lower().strip().strip("!.")
        
        if text_lower in greetings and mode == "conversation":
            return {
                "corrected": text,
                "reply": f"Hello! I'm ready to help you practice {native_lang} to English translation or conversation.",
                "score": "100",
                "corrections": []
            }
            
        if text_lower in closings:
            return {
                "corrected": text,
                "reply": "Goodbye! Great practice session today.",
                "score": "100",
                "corrections": []
            }

        # --- 2. FREE GUARDRAIL (Keyword Blocking) ---
        forbidden_keywords = ["python", "java", "code", "html", "css", "solve", "math", "president", "calculate"]
        if any(word in text_lower for word in forbidden_keywords) and mode != "topic_talk":
            return {
                "corrected": text,
                "reply": "I am tuned to help you with English only. Let's get back to practice!",
                "score": "0",
                "corrections": ["Topic violation"]
            }

        # --- 3. OPTIMIZED SYSTEM PROMPTS ---
        guardrail = (
            "ROLE: English Tutor ONLY. Reject math/coding/GK requests politely. "
            "Focus: Grammar, vocabulary, fluency. "
            "If mode is Topic Talk: Listen to content but grade English skills."
        )

        if mode == 'email_drafter':
            system_msg = (
                f"{guardrail} "
                f"Role: Executive Assistant. Task: Convert notes to professional email. "
                f"JSON Output Format: "
                f'{{"corrected": "Subject: [Subject]\\n\\nDear [Name],\\n\\n[Body]\\n\\nSincerely,\\n[User]", '
                f'"reply": "Draft ready. I used [professional phrase].", '
                f'"score": "100", "corrections": ["Drafted Email"]}}'
            )
        elif mode == 'job_interview':
            system_msg = (
                f"{guardrail} "
                f"Role: Strict HR Interviewer. 1. Grade grammar. 2. Ask ONE follow-up. 3. No repeats. "
                f"JSON Output: "
                f'{{"corrected": "[Better version]", '
                f'"reply": "[Feedback] + [Next Question]", '
                f'"score": "[0-100]", "corrections": ["[Fix 1]", "[Fix 2]"]}}'
            )
        elif mode == 'reflex_drill':
            system_msg = (
                f"{guardrail} "
                f"Role: Drill Sergeant. 1. Check previous translation. 2. New sentence in {native_lang}. "
                f"JSON Output: "
                f'{{"corrected": "[Correct translation]", '
                f'"reply": "Status. Next: Translate: [New {native_lang} Sentence]", '
                f'"score": "[0-100]", "corrections": ["Errors"]}}'
            )
        elif mode == 'topic_talk':
            system_msg = (
                f"{guardrail} "
                f"Role: Speech Evaluator. 1. Rate fluency/vocab. 2. Ask deep follow-up. "
                f"JSON Output: "
                f'{{"corrected": "[Polished speech]", '
                f'"reply": "Interesting point. [Follow-up?]", '
                f'"score": "[0-100]", "corrections": ["Vocab suggestion"]}}'
            )
        else:
            system_msg = (
                f"{guardrail} "
                f"Role: Friendly Tutor (SpeakUp). Chat casually. Correct mistakes gently. "
                f"JSON Output: "
                f'{{"corrected": "[Grammar fix]", '
                f'"reply": "[Natural response]", '
                f'"score": "[0-100]", "corrections": ["Fix 1"]}}'
            )

        messages = [{"role": "system", "content": system_msg}]

        if mode != 'email_drafter':
            for turn in history[-4:]:
                role = "assistant" if turn.get('role') in ['model', 'ai'] else "user"
                content = turn.get('parts', [""])[0] if isinstance(turn.get('parts'), list) else turn.get('content', "")
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": text})

        retries = 2
        for attempt in range(retries):
            try:
                chat_completion = self.client.chat.completions.create(
                    messages=messages,
                    model=self.model_id,
                    temperature=0.7,
                    response_format={"type": "json_object"}
                )
                result = json.loads(chat_completion.choices[0].message.content)
                
                # Cache successful result
                self.request_cache[cache_key] = (result, time.time())
                return result
            
            except json.JSONDecodeError:
                print(f"⚠️ JSON Error on attempt {attempt+1}. Retrying...")
                continue
            except Exception as e:
                print(f"❌ Groq API Error: {e}")
                break

        return {
            "corrected": text,
            "reply": "I'm having trouble processing that thought. Could you rephrase?",
            "score": "0",
            "corrections": []
        }