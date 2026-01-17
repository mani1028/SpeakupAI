# **SpeakUp AI \- Your Intelligent English Tutor 🚀**

**SpeakUp AI** is a web-based English learning platform designed to help users improve their speaking, grammar, and vocabulary through interactive AI conversations. Powered by **Groq (Llama 3\)** for ultra-fast text generation and **Edge TTS** for realistic neural voice output.

*(Replace with an actual screenshot of your app)*

## **✨ Key Features**

* **🎙️ Real-Time Conversation Practice:** Chat with "Nova," your AI tutor, who corrects your grammar instantly.  
* **🔊 Neural Text-to-Speech:** Hear responses in a high-quality, human-like voice (powered by Edge TTS).  
* **🧠 "Word of the Day":** Daily vocabulary building with definitions, examples, and pronunciation.  
* **📝 Specialized Modes:**  
  * **Coffee Chat:** Casual conversation practice.  
  * **Job Interview:** Mock HR interview questions and feedback.  
  * **Email Drafter:** Convert spoken notes into professional emails.  
  * **Reflex Drill:** Speed translation exercises.  
  * **Topic Talk:** 1-minute speech practice on specific topics.  
* **📱 Mobile-First Design:** Fully responsive layout that works like a native app on mobile browsers.  
* **⚡ Ultra-Fast & Efficient:** Optimized with aggressive caching, rate limiting, and request queuing to minimize API costs and latency.

## **🛠️ Tech Stack**

* **Backend:** Python, Flask  
* **AI Engine:** Groq API (Llama 3.1 8b Instant)  
* **Text-to-Speech:** edge-tts (Microsoft Edge Neural Voice)  
* **Frontend:** HTML5, CSS3 (Mobile Responsive), Vanilla JavaScript  
* **Storage:** Local JSON Caching (for daily words), File System (for audio cache)

## **🚀 Installation & Setup**

### **Prerequisites**

* Python 3.9+  
* A [Groq API Key](https://console.groq.com/) (Free beta available)

### **1\. Clone the Repository**

git clone \[https://github.com/yourusername/SpeakUp-AI-Tutor.git\](https://github.com/yourusername/SpeakUp-AI-Tutor.git)  
cd SpeakUp-AI-Tutor

### **2\. Create a Virtual Environment**

python \-m venv venv  
\# Windows  
venv\\Scripts\\activate  
\# Mac/Linux  
source venv/bin/activate

### **3\. Install Dependencies**

pip install \-r requirements.txt

### **4\. Configure Environment Variables**

Create a .env file in the root directory:

GROQ\_API\_KEY=gsk\_your\_groq\_api\_key\_here  
FLASK\_SECRET=your\_random\_secret\_key\_here

### **5\. Run the Application**

python app.py

Open your browser and navigate to http://localhost:7860 (or the port shown in your terminal).

## **🐳 Docker Support**

You can also run SpeakUp AI using Docker:

\# Build the image  
docker build \-t speakup-ai .

\# Run the container  
docker run \-p 7860:7860 \--env-file .env speakup-ai

## **📂 Project Structure**

speak/  
├── app.py              \# Main Flask application  
├── ai\_engine.py        \# Logic for interacting with Groq API  
├── requirements.txt    \# Python dependencies  
├── daily\_word\_cache.json \# Cache for Word of the Day  
├── static/             \# Static assets (CSS, JS, Audio)  
│   ├── css/  
│   ├── js/  
│   └── audio\_cache/    \# Generated TTS audio files  
└── templates/          \# HTML Templates (Jinja2)

## **🤝 Contributing**

Contributions are welcome\! Please feel free to submit a Pull Request.

1. Fork the project  
2. Create your feature branch (git checkout \-b feature/AmazingFeature)  
3. Commit your changes (git commit \-m 'Add some AmazingFeature')  
4. Push to the branch (git push origin feature/AmazingFeature)  
5. Open a Pull Request

## **📄 License**

This project is licensed under the MIT License \- see the LICENSE file for details.

*Built with ❤️ for English learners everywhere.*
