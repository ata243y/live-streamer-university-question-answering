import { TalkingHead } from './talkinghead.mjs';

let head;
let audioContext;
let audioSource;
let analyser;
let isPlaying = false;
let audioBuffer = null;

async function init() {
    const nodeAvatar = document.getElementById('avatar');
    const loading = document.getElementById('loading');

    loading.style.display = 'block';

    try {
        head = new TalkingHead(nodeAvatar, {
            ttsEndpoint: "https://eu-texttospeech.googleapis.com/v1beta1/text:synthesize",
            cameraView: "head",
            cameraDistance: 0.5,
            cameraX: -1.1,
            cameraY: 0.3,
            cameraRotateY: -0.6, // Rotate character to left
            update: updateLoop
        });

        // Load the avatar
        await head.showAvatar({
            url: './assets/avatar.glb',
            body: 'F',
            avatarMood: 'neutral',
            lipsyncLang: 'en'
        }, (ev) => {
            if (ev.lengthComputable) {
                const percent = Math.round((ev.loaded / ev.total) * 100);
                loading.textContent = `Loading Avatar... ${percent}%`;
            }
        });

        loading.style.display = 'none';

        // Setup audio handler
        setupAudioUI();

    } catch (error) {
        console.error("Error initializing avatar:", error);
        loading.textContent = "Error loading avatar: " + error.message;
    }
}

function updateLoop(t) {
    if (isPlaying && analyser) {
        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteFrequencyData(dataArray);

        // Calculate average volume
        let sum = 0;
        const limit = Math.floor(dataArray.length / 4);
        for (let i = 0; i < limit; i++) {
            sum += dataArray[i];
        }
        const average = sum / limit;

        // Map to mouthOpen (0 to 1)
        // Average is 0-255.
        // Super sensitive: threshold 5, range 25
        let openVal = Math.max(0, (average - 5) / 200);
        openVal = Math.min(1, openVal);

        head.setFixedValue('mouthOpen', openVal);
    } else {
        if (!isPlaying && head) {
            head.setFixedValue('mouthOpen', 0);
        }
    }
}

function setupAudioUI() {
    const audioInput = document.getElementById('audioInput');
    const playBtn = document.getElementById('playBtn');

    if (audioInput) {
        audioInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            if (playBtn) {
                playBtn.disabled = true;
                playBtn.textContent = "Processing Audio...";
            }

            try {
                await window.playTalkingHeadAudio(file);
                if (playBtn) {
                    playBtn.disabled = false;
                    playBtn.textContent = "Stop";
                }
            } catch (err) {
                console.error(err);
                if (playBtn) {
                    playBtn.textContent = "Error";
                    playBtn.disabled = false;
                }
            }
        });
    }

    if (playBtn) {
        playBtn.addEventListener('click', () => {
            if (isPlaying) {
                stopAudio();
                playBtn.textContent = "Play";
            } else {
                // Replay existing buffer if available
                if (audioBuffer) {
                    playAudioBuffer(audioBuffer);
                    playBtn.textContent = "Stop";
                }
            }
        });
    }
}

// Global API
window.playTalkingHeadAudio = async function (fileOrBlob) {
    stopAudio(); // Stop any current playback

    try {
        let arrayBuffer;

        // Handle URL string input
        if (typeof fileOrBlob === 'string') {
            const response = await fetch(fileOrBlob);
            if (!response.ok) throw new Error(`Failed to fetch audio from URL: ${fileOrBlob}`);
            arrayBuffer = await response.arrayBuffer();
        } else if (fileOrBlob instanceof Blob || fileOrBlob instanceof File) {
            arrayBuffer = await fileOrBlob.arrayBuffer();
        } else {
            throw new Error("Invalid input: Expected File, Blob, or URL string.");
        }

        if (!audioContext) {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (audioContext.state === 'suspended') {
            await audioContext.resume();
        }

        audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
        playAudioBuffer(audioBuffer);

    } catch (err) {
        console.error("Error playing audio:", err);
        throw err;
    }
};

function playAudioBuffer(buffer) {
    if (!audioContext) return;

    audioSource = audioContext.createBufferSource();
    audioSource.buffer = buffer;

    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.06; // 0.1 = Very jerky/fast. 0.8 = Smooth/slow.

    audioSource.connect(analyser);
    analyser.connect(audioContext.destination);

    audioSource.start(0);
    isPlaying = true;

    // Update UI if needed
    const playBtn = document.getElementById('playBtn');
    if (playBtn) playBtn.textContent = "Stop";

    audioSource.onended = () => {
        isPlaying = false;
        if (playBtn) playBtn.textContent = "Play";
        if (head) head.setFixedValue('mouthOpen', 0);
    };
}

function stopAudio() {
    if (audioSource) {
        try {
            audioSource.stop();
        } catch (e) { /* ignore if already stopped */ }
        isPlaying = false;
        if (head) head.setFixedValue('mouthOpen', 0);
    }
}

// Chatbox API
// Legacy single message function (optional use)
window.addChatMessage = function (text, sender) {
    // If used, just wrap it in a single bubble
    const chatbox = document.getElementById('chatbox');
    const wrapper = document.createElement('div');
    wrapper.classList.add('chat-entry'); // New shared container style

    // ... we will focus on addQA for the requested look
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('message-line');
    msgDiv.classList.add(sender);

    const iconSpan = document.createElement('span');
    iconSpan.className = 'icon';
    msgDiv.appendChild(iconSpan);

    const textSpan = document.createElement('span');
    textSpan.className = 'text';
    textSpan.textContent = text;
    msgDiv.appendChild(textSpan);

    wrapper.appendChild(msgDiv);
    chatbox.appendChild(wrapper);
    chatbox.scrollTop = chatbox.scrollHeight;
};

// New paired Q&A function
window.addQA = function (question, answer) {
    const chatbox = document.getElementById('chatbox');

    // Container for both
    const entry = document.createElement('div');
    entry.classList.add('chat-entry');

    // Question part
    const qDiv = document.createElement('div');
    qDiv.className = 'message-line student';

    const qIcon = document.createElement('span');
    qIcon.className = 'icon';
    qDiv.appendChild(qIcon);

    const qText = document.createElement('span');
    qText.className = 'text';
    qText.textContent = question;
    qDiv.appendChild(qText);

    entry.appendChild(qDiv);

    // Answer part
    const aDiv = document.createElement('div');
    aDiv.className = 'message-line model';

    const aIcon = document.createElement('span');
    aIcon.className = 'icon';
    aDiv.appendChild(aIcon);

    const aText = document.createElement('span');
    aText.className = 'text';
    aText.textContent = answer;
    aDiv.appendChild(aText);

    entry.appendChild(aDiv);

    entry.appendChild(aDiv);

    chatbox.appendChild(entry);

    // Auto-discard logic: Keep only the last 2 entries to prevent clutter
    // and ensure "old ones not visible" are removed.
    const entries = chatbox.getElementsByClassName('chat-entry');
    while (entries.length > 2) {
        chatbox.removeChild(entries[0]);
    }

    chatbox.scrollTop = chatbox.scrollHeight;
}

document.addEventListener('DOMContentLoaded', init);
