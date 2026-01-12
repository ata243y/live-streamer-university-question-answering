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

        analyser.getByteFrequencyData(dataArray);

        // --- Frequency-Based Lip Sync ---
        // Simple heuristic: map bands to approximate formants
        // Low (0-500Hz) -> U / O
        // Mid (500-1500Hz) -> aa
        // High (1500Hz+) -> E / I / S

        let totalEnergy = 0;
        let eLow = 0, eMid = 0, eHigh = 0;

        // Bins approx: 44100Hz / 1024 FFT ~ 43Hz per bin
        // But we set fftSize=256 -> 128 bins (~170Hz per bin) in setupAudio() (default is usually 2048/1024)
        // Let's assume standard default for now or check setup. 
        // If fftSize is default 2048, bin is ~21Hz.
        // Let's sum ranges roughly.

        const binSize = dataArray.length; // 1024 usually
        const k = 1; // Scaling factor

        for (let i = 0; i < binSize; i++) {
            const val = dataArray[i];
            totalEnergy += val;
            if (i < 10) eLow += val;       // ~0-400Hz
            else if (i < 50) eMid += val;  // ~400-2000Hz
            else eHigh += val;             // ~2000Hz+
        }

        // Normalize
        eLow /= 10;
        eMid /= 40;
        eHigh /= (binSize - 50);

        // Targets
        let t_aa = 0, t_E = 0, t_O = 0, t_U = 0;

        // Threshold for silence
        if (totalEnergy > 500) { // arbitrary threshold check
            // Determine dominant formant
            // Dampening factor: Increase divisor to reduce sensitivity (was 160 -> 300)
            const sensitivity = 300;

            if (eHigh > eMid && eHigh > eLow * 0.8) {
                t_E = Math.min(0.6, eHigh / sensitivity); // Cap at 0.6
            } else if (eMid > eLow) {
                t_aa = Math.min(0.6, eMid / sensitivity);
            } else {
                t_O = Math.min(0.6, eLow / sensitivity);
                t_U = Math.min(0.6, eLow / sensitivity);
            }
        }

        // --- Smoothing (Lerp) ---
        // We attach these state vars to the head object to persist them
        if (!head.visemeState) head.visemeState = { aa: 0, E: 0, O: 0, U: 0, mouthOpen: 0 };
        const s = head.visemeState;
        const alpha = 0.2; // Slightly smoother (was 0.25)

        s.aa += (t_aa - s.aa) * alpha;
        s.E += (t_E - s.E) * alpha;
        s.O += (t_O - s.O) * alpha;
        s.U += (t_U - s.U) * alpha;

        // Apply to Morph Targets
        // Note: ReadyPlayerMe standard Visemes
        head.setFixedValue('viseme_aa', s.aa);
        head.setFixedValue('viseme_E', s.E * 0.5); // E usually combines with others
        head.setFixedValue('viseme_I', s.E * 0.5);
        head.setFixedValue('viseme_O', s.O);
        head.setFixedValue('viseme_U', s.U);

        // Also drive generic mouthOpen for fallback/layering
        let openTarget = Math.max(t_aa, t_O, t_U * 0.5);
        s.mouthOpen += (openTarget - s.mouthOpen) * alpha;
        head.setFixedValue('mouthOpen', s.mouthOpen * 0.1); // Very subtle generic open (was 0.2)

    } else {
        if (!isPlaying && head) {
            // Reset all
            head.setFixedValue('mouthOpen', 0);
            head.setFixedValue('viseme_aa', 0);
            head.setFixedValue('viseme_E', 0);
            head.setFixedValue('viseme_I', 0);
            head.setFixedValue('viseme_O', 0);
            head.setFixedValue('viseme_U', 0);
            if (head.visemeState) head.visemeState = { aa: 0, E: 0, O: 0, U: 0, mouthOpen: 0 };
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


    // Set busy immediately to prevent overlap and signal external controllers
    isPlaying = true;

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
        isPlaying = false; // Reset on error
        throw err;
    }
};

window.isAvatarPlaying = function () {
    return isPlaying;
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
