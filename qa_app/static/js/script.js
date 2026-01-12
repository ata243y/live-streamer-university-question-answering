document.addEventListener("DOMContentLoaded", () => {
    const chatMessages = document.getElementById("chatMessages");
    const sendButton = document.getElementById("sendButton");
    const ttsButton = document.getElementById("ttsButton");

    let isTTSEnabled = false; // Varsayılan kapalı

    // TTS Toggle Logic
    ttsButton.addEventListener("click", () => {
        isTTSEnabled = !isTTSEnabled;
        ttsButton.classList.toggle("active", isTTSEnabled);
        const icon = ttsButton.querySelector("i");
        if (isTTSEnabled) {
            icon.classList.remove("fa-volume-up");
            icon.classList.add("fa-volume-high");
        } else {
            icon.classList.remove("fa-volume-high");
            icon.classList.add("fa-volume-up");
        }
    });

    const playAudio = async (text) => {
        if (!isTTSEnabled || !text) return;

        try {
            const response = await fetch("/api/tts", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text })
            });

            if (response.ok) {
                const blob = await response.blob();
                const audioUrl = URL.createObjectURL(blob);
                const audio = new Audio(audioUrl);
                audio.play();
            } else {
                console.error("TTS Hatası:", await response.text());
            }
        } catch (error) {
            console.error("Audio playback error:", error);
        }
    };

    const addMessage = (message, sender) => {
        const messageDiv = document.createElement("div");
        messageDiv.classList.add("message", sender);

        const avatarImg = document.createElement("img");
        if (sender === "bot") {
            avatarImg.src = "../static/images/bot.png";
        } else {
            avatarImg.src = "../static/images/user.png";
        }
        avatarImg.classList.add("avatar");

        const bubbleDiv = document.createElement("div");
        bubbleDiv.classList.add("bubble");
        bubbleDiv.innerHTML = marked.parse(message);

        messageDiv.appendChild(avatarImg);
        messageDiv.appendChild(bubbleDiv);
        chatMessages.appendChild(messageDiv);

        chatMessages.scrollTop = chatMessages.scrollHeight;
        return bubbleDiv; // Balonu döndür
    };

    // Açılış mesajları
    addMessage("Merhaba! Ben Gebze Teknik Üniversitesi için özelleştirilmiş yapay zeka asistanıyım.", "bot");
    addMessage("Bugün sana nasıl yardımcı olabilirim?", "bot");

    const sendMessage = async () => {
        const question = userInput.value.trim();
        if (!question) {
            addMessage("Soru sorman gerekiyor. Lütfen çekinme!", "bot");
            return;
        }

        addMessage(question, "user");
        userInput.value = "";

        const botBubble = addMessage("Düşünüyor...", "bot");

        try {
            const response = await fetch("/predict", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question })
            });

            if (!response.ok) {
                throw new Error(`Sunucu hatası: ${response.statusText}`);
            }

            const contentType = response.headers.get("content-type");

            if (contentType && contentType.includes("text/plain")) {
                // STREAMING CEVAP
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let isFirstChunk = true;

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    const chunk = decoder.decode(value, { stream: true });
                    if (isFirstChunk) {
                        botBubble.innerHTML = "";
                        isFirstChunk = false;
                    }
                    botBubble.innerHTML += chunk;
                    chatMessages.scrollTop = chatMessages.scrollHeight;
                }
            } else {
                // JSON CEVAP (CHITCHAT)
                const data = await response.json();
                if (data.answer) {
                    botBubble.innerHTML = marked.parse(data.answer);
                } else {
                    throw new Error("JSON cevap formatı hatalı.");
                }
                if (data.answer) {
                    botBubble.innerHTML = marked.parse(data.answer);
                    // Play audio for chitchat
                    await playAudio(data.answer);
                } else {
                    throw new Error("JSON cevap formatı hatalı.");
                }
            }

            // Play audio for streaming response (after stream ends)
            if (contentType && contentType.includes("text/plain")) {
                const fullText = botBubble.innerText; // Get raw text
                await playAudio(fullText);
            }

        } catch (error) {
            console.error("İletişim hatası:", error);
            botBubble.innerHTML = "Bir hata oluştu. Lütfen tekrar deneyin.";
        }
    };

    userInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    sendButton.addEventListener("click", sendMessage);
});