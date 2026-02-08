// Vision Logic with OCR Fallback
// Loaded via CDN in agent_ui.html (assumed) or dynamically here
const TESSERACT_CDN = "https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js";

async function loadTesseract() {
    if (window.Tesseract) return;
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = TESSERACT_CDN;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

const video = document.getElementById('video-feed');
const canvas = document.getElementById('vision-canvas');
const ctx = canvas.getContext('2d');
const btnAnalyze = document.getElementById('btn-analyze');

async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        video.srcObject = stream;
    } catch (e) {
        console.error("Camera Error:", e);
        // Fallback for demo if no camera
        video.poster = "https://via.placeholder.com/320x240?text=NO+SIGNAL";
    }
}

btnAnalyze.onclick = async () => {
    if (!aiSession) {
        alert("AI Model not loaded!");
        return;
    }

    // 1. Capture Frame
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // 2. Prepare for Nano (Blob or Base64)
    // NOTE: Current window.ai implementations vary on Image support.
    // If image support is missing, we mock the "seeing" part for the MVP 
    // or use a separate OCR library if strictly required. 
    // Assuming the user has the Multimodal-enabled build.

    try {
        const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg'));

        // Check if session supports image (speculative API)
        // If not, we might need to destroy and recreate session with multimodal config?
        // OR prompt with image data.

        // PROMPT:
        const prompt = "Describe what you see in this wristband image. Look for ID numbers.";

        // Attempt to pass blob if supported
        // If not supported by this exact Chrome Canary build, we might need a workaround.
        // Workaround: We will use Tesseract.js for OCR if we really need to read text, 
        // but for now let's try the speculative Multimodal prompt.

        console.log("Analyzing image...", blob.size);

        // Warning: window.ai API is unstable. 
        try {
            const result = await aiSession.prompt(prompt, {
                images: [blob]
            });
            document.getElementById('msg-input').value = `[VISUAL SCAN]: ${result}`;
        } catch (e) {
            console.warn("Multimodal Scan failed, falling back to Tesseract OCR...", e);

            try {
                await loadTesseract();
                const { data: { text } } = await Tesseract.recognize(canvas, 'eng');

                if (text.trim()) {
                    document.getElementById('msg-input').value = `[OCR FALLBACK]: I see text that says: "${text.trim()}". (Gemini Nano vision unavailable).`;
                } else {
                    document.getElementById('msg-input').value = `[VISUAL SCAN FAILED]: Could not recognize text or objects.`;
                }
            } catch (ocrError) {
                console.error("OCR Error:", ocrError);
                document.getElementById('msg-input').value = `[VISUAL SCAN ERROR]: All vision systems failed.`;
            }
        }

    } catch (e) {
        console.error(e);
    }
};
