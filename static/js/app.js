document.addEventListener('DOMContentLoaded', () => {
    
    // Config
    const mode = window.APP_MODE || 'conversation';
    const nativeLang = localStorage.getItem('sn_native_lang') || 'Hindi';
    let isRecording = false;
    let recognition;
    let currentGems = parseInt(localStorage.getItem('sn_gems') || '840');
    let typingDiv = null;
    let currentAudio = null; // New variable to track the real voice audio
    
    // Request queue for debouncing API calls
    let requestQueue = [];
    let isProcessingQueue = false;
    const API_DEBOUNCE_TIME = 500; // ms

    // Elements
    const micBtn = document.getElementById('mic-btn');
    const statusText = document.getElementById('status-text');
    const chatBox = document.getElementById('chat-box');
    const feedbackPanel = document.getElementById('feedback-panel');
    const gemsDisplay = document.getElementById('gems-count');
    const vizContainer = document.getElementById('viz-container');
    
    if(gemsDisplay) gemsDisplay.textContent = currentGems;

    // Feedback Elements
    const fbScore = document.getElementById('fb-score');
    const fbBetter = document.getElementById('fb-better');
    const fbNative = document.getElementById('fb-native');
    const fbNativeText = document.getElementById('fb-native-text');

    // --- 1. INITIALIZATION ---
    initSession();
    setupSpeech();

    async function initSession() {
        try {
            showTyping(true);
            const res = await fetch('/api/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ mode, native_lang: nativeLang })
            });
            
            if(!res.ok) throw new Error("Server error");
            const data = await res.json();
            
            showTyping(false);
            chatBox.innerHTML = ''; 
            addMessage('ai', data.reply);
            speak(data.reply);
        } catch(e) {
            showTyping(false);
            console.error("Init failed", e);
            addMessage('error', "Could not connect to server. Check your connection.");
        }
    }

    // --- 2. QUEUE PROCESSING ---
    async function processQueue() {
        if (isProcessingQueue || requestQueue.length === 0) return;
        
        isProcessingQueue = true;
        const { text, resolve, reject } = requestQueue.shift();
        
        try {
            const result = await sendAnalysisRequest(text);
            resolve(result);
        } catch (error) {
            reject(error);
        } finally {
            isProcessingQueue = false;
            // Add slight delay before processing next item to respect rate limits
            setTimeout(processQueue, API_DEBOUNCE_TIME);
        }
    }

    async function sendAnalysisRequest(text) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000); // 15s timeout
        
        try {
            const res = await fetch('/api/analyze', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    text: text,
                    mode: mode,
                    native_lang: nativeLang,
                    history: getHistory()
                }),
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            if (!res.ok) {
                if (res.status === 429) {
                    throw new Error("Rate limit exceeded. Please wait a moment.");
                }
                throw new Error(`API Error: ${res.status}`);
            }
            
            return await res.json();
        } catch (error) {
            clearTimeout(timeoutId);
            throw error;
        }
    }

    // --- 3. SPEECH RECOGNITION ---
    function setupSpeech() {
        const Speech = window.webkitSpeechRecognition || window.SpeechRecognition;
        if(!Speech) {
            addMessage('error', "Microphone not supported in this browser. Please use Chrome/Edge.");
            micBtn.style.opacity = "0.5";
            return;
        }
        
        recognition = new Speech();
        recognition.lang = 'en-US';
        recognition.continuous = false;
        recognition.interimResults = false;

        recognition.onstart = () => {
            isRecording = true;
            // CSS handles icon change via this class
            micBtn.classList.add('listening'); 
            statusText.textContent = "Listening...";
            feedbackPanel.classList.remove('visible'); 
            vizContainer.classList.add('active');
            startViz();
        };

        recognition.onend = () => {
            isRecording = false;
            micBtn.classList.remove('listening');
            
            // Only update status if we aren't in the middle of generating voice
            if(statusText.textContent === "Listening...") {
                statusText.textContent = "Processing...";
            }
            vizContainer.classList.remove('active');
            stopViz();
        };

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            if(transcript.trim().length > 0) {
                handleUserSpeech(transcript);
            } else {
                statusText.textContent = "Tap to Speak";
            }
        };

        recognition.onerror = (event) => {
            console.error(event.error);
            statusText.textContent = "Error: " + event.error;
        };
    }

    // --- MIC BUTTON HANDLER (With Debounce) ---
    micBtn.addEventListener('click', () => {
        // Prevent rapid clicking (Debounce)
        if (micBtn.classList.contains('disabled')) return;

        if(isRecording) {
            recognition.stop();
        } else {
            // STOP AI SPEECH IMMEDIATELY when user wants to speak
            stopAISpeech();
            recognition.start();
        }

        // Disable button for 1 second after click to stop spam
        micBtn.classList.add('disabled');
        setTimeout(() => micBtn.classList.remove('disabled'), 1000);
    });

    // --- 4. CORE LOGIC ---
    async function handleUserSpeech(text) {
        // Basic filter for very short noise
        if (text.length < 2) return;

        addMessage('user', text);
        showTyping(true); 
        statusText.textContent = "Thinking...";

        // Use Queue for API request
        try {
            const data = await new Promise((resolve, reject) => {
                requestQueue.push({ text, resolve, reject });
                processQueue();
            });
            
            // Step 2: PREFETCH Audio (Synchronized Output)
            let audioBlobUrl = null;
            if(data.conversational_reply) {
                statusText.textContent = "Streaming Voice..."; // Inform user
                try {
                    const audioRes = await fetch('/api/speak', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ text: data.conversational_reply })
                    });
                    
                    if(audioRes.ok) {
                        const blob = await audioRes.blob();
                        audioBlobUrl = URL.createObjectURL(blob);
                    }
                } catch(e) {
                    console.warn("Audio prefetch failed", e);
                }
            }
            
            showTyping(false); // NOW remove dots (Audio is ready)
            
            // Step 3: Show Text & Play Audio Simultaneously
            if(data.conversational_reply) {
                addMessage('ai', data.conversational_reply);
                
                if(audioBlobUrl) {
                    playAudioDirect(audioBlobUrl); // Play pre-fetched blob
                } else {
                    speak(data.conversational_reply); // Fallback
                }
            } else {
                statusText.textContent = "Tap to Reply";
            }

            // 4. Show Feedback
            showFeedback(data);

            // 5. Rewards
            if(data.score > 70) {
                currentGems += 5;
                localStorage.setItem('sn_gems', currentGems);
                if(gemsDisplay) gemsDisplay.textContent = currentGems;
            }

        } catch(e) {
            showTyping(false);
            console.error(e);
            
            let errMsg = "AI connection failed. Please try again.";
            if (e.message && e.message.includes("Rate limit")) {
                errMsg = "Please wait a moment before speaking again.";
            }
            
            addMessage('error', errMsg);
            statusText.textContent = "Tap to Retry";
        }
    }

    function showFeedback(data) {
        const score = data.score || 0;
        const correction = data.improved_version || "Good job! No major errors.";
        
        fbScore.textContent = score;
        fbScore.style.backgroundColor = score > 80 ? '#10b981' : (score > 60 ? '#f59e0b' : '#ef4444');
        
        fbBetter.textContent = correction;
        
        if(data.native_explanation && data.native_explanation !== "null") {
            fbNative.style.display = 'flex';
            fbNativeText.textContent = data.native_explanation;
        } else {
            fbNative.style.display = 'none';
        }

        feedbackPanel.classList.add('visible');
    }

    // --- 5. UTILS ---
    function addMessage(role, text) {
        const div = document.createElement('div');
        div.className = `msg ${role}`;
        div.textContent = text;
        chatBox.appendChild(div);
        scrollToBottom();
    }

    function showTyping(show) {
        if(show) {
            if(typingDiv) return;
            typingDiv = document.createElement('div');
            typingDiv.className = 'typing';
            typingDiv.innerHTML = '<div class="dot"></div><div class="dot"></div><div class="dot"></div>';
            chatBox.appendChild(typingDiv);
            scrollToBottom();
        } else {
            if(typingDiv) {
                typingDiv.remove();
                typingDiv = null;
            }
        }
    }
    
    function scrollToBottom() {
        chatBox.scrollTo({
            top: chatBox.scrollHeight,
            behavior: 'smooth'
        });
    }

    function getHistory() {
        const msgs = document.querySelectorAll('.msg');
        const history = [];
        msgs.forEach(m => {
            if(m.classList.contains('error')) return;
            history.push({
                role: m.classList.contains('user') ? 'user' : 'model',
                parts: [m.textContent]
            });
        });
        return history.slice(-6); 
    }

    function stopAISpeech() {
        // Stop the robotic browser voice
        window.speechSynthesis.cancel();
        
        // Stop the real human audio if it's playing
        if(currentAudio) {
            currentAudio.pause();
            currentAudio.currentTime = 0;
            currentAudio = null;
        }
    }

    // New helper to play already fetched URL (Blob or Remote)
    function playAudioDirect(url) {
        stopAISpeech();
        currentAudio = new Audio(url);
        currentAudio.onplay = () => { statusText.textContent = "Speaking..."; };
        currentAudio.onended = () => { 
            statusText.textContent = "Tap to Reply";
            // Revoke blob URL to free memory if it is a blob
            if(url.startsWith('blob:')) URL.revokeObjectURL(url);
        };
        currentAudio.play().catch(e => console.error("Playback failed", e));
    }

    function speak(text) {
        if(!text) return;
        
        // Stop any previous speech immediately
        stopAISpeech();
        
        // UX: Tell user we are working on the voice
        statusText.textContent = "Streaming Voice...";
        
        // --- REAL HUMAN VOICE (Edge TTS - Streaming) ---
        fetch('/api/speak', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ text: text })
        })
        .then(async res => {
            if (res.ok) {
                const blob = await res.blob();
                const audioUrl = URL.createObjectURL(blob);
                playAudioDirect(audioUrl);
            } else {
                throw new Error("TTS fetch error");
            }
        })
        .catch(err => {
            console.error("TTS Network Error", err);
            fallbackSpeak(text);
            statusText.textContent = "Tap to Reply";
        });
    }

    function fallbackSpeak(text) {
        const utt = new SpeechSynthesisUtterance(text);
        utt.lang = 'en-US';
        window.speechSynthesis.speak(utt);
    }

    // --- 6. VISUALIZER (Optimized) ---
    let vizReq; // Replaces vizInterval
    const canvas = document.getElementById('audio-visualizer');
    const ctx = canvas ? canvas.getContext('2d') : null;

    function drawViz() {
        if(!ctx) return;
        
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#6366f1'; 
        
        const bars = 50;
        const width = canvas.width / bars;
        
        for(let i=0; i<bars; i++) {
            // Organic wave height
            const h = Math.random() * 20 + 4;
            const x = i * width;
            const y = (canvas.height - h) / 2;
            
            ctx.beginPath();
            ctx.roundRect(x + 1, y, width - 2, h, 4);
            ctx.fill();
        }
        
        // Loop using the screen's native refresh rate
        vizReq = requestAnimationFrame(drawViz);
    }

    function startViz() {
        if(!ctx) return;
        if (!vizReq) drawViz(); // Start loop
    }

    function stopViz() {
        if(vizReq) cancelAnimationFrame(vizReq);
        vizReq = null;
        if(ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
});