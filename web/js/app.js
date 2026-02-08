// NEXUS-0 Client Logic
// Connects to Local Python Bridge -> Sovereign Link

const BRIDGE_URL = "ws://localhost:8080/ws";

// State
let socket = null;
let selectedTarget = null;
let aiSession = null;
let systemPrompt = "You are a NEXUS-0 Sovereign Agent. Concise. High-IQ. Sovereign.";

// DOM Elements
const els = {
    netList: document.getElementById('network-list'),
    chatHistory: document.getElementById('chat-history'),
    msgInput: document.getElementById('msg-input'),
    btnSend: document.getElementById('btn-send'),
    btnScan: document.getElementById('btn-scan'),
    nodeId: document.getElementById('node-id'),
    chkAuto: document.getElementById('chk-auto-reply'),
    aiStatus: document.getElementById('ai-status'),
    btnAnalyze: document.getElementById('btn-analyze'),
    btnMission: document.getElementById('btn-mission'),
    missionLog: document.getElementById('mission-log'),
    chkShare: document.getElementById('chk-share-ai')
};

// --- AI Initialization ---
async function initAI() {
    if (!window.ai) {
        els.aiStatus.textContent = "Not Supported (window.ai missing)";
        els.aiStatus.style.color = "red";
        return;
    }

    try {
        const canCreate = await window.ai.canCreateTextSession();
        if (canCreate === 'no') {
            els.aiStatus.textContent = "Model Not Available";
            return;
        }

        aiSession = await window.ai.createTextSession({
            systemPrompt: systemPrompt
        });

        els.aiStatus.textContent = "Active (Gemini Nano)";
        els.aiStatus.style.color = "var(--neon-green)";

    } catch (e) {
        console.error("AI Init Failed:", e);
        els.aiStatus.textContent = "Error: " + e.message;
    }
}

// --- WebSocket Logic ---
function connect() {
    socket = new WebSocket(BRIDGE_URL);

    socket.onopen = () => {
        addLog("System", "Connected to Bridge Link.");
        els.nodeId.textContent = "Online";
        // Auto-scan on connect
        socket.send(JSON.stringify({ action: "scan" }));
    };

    socket.onclose = () => {
        addLog("System", "Link Lost. Reconnecting...");
        els.nodeId.textContent = "Offline";
        setTimeout(connect, 3000);
    };

    socket.onmessage = async (event) => {
        const msg = JSON.parse(event.data);

        if (msg.type === "scan_result") {
            renderNetworkList(msg.nodes);
        } else if (msg.type === "incoming_message") {
            addLog(msg.sender, msg.content, "received");

            // Auto-Reply Logic
            if (els.chkAuto.checked && aiSession) {
                await generateAutoReply(msg.sender, msg.content);
            }
        } else if (msg.type === "error") {
            addLog("Error", msg.msg);
        } else if (msg.type === "status") {
            console.log(msg.msg);
        } else if (msg.type === "mission_update") {
            renderMissionUpdate(msg);
        } else if (msg.type === "sync_status") {
            addLog(`⚓ ${msg.node}`, `Maritime Sync: ${msg.status}. Payload: ${msg.payload}`, "social");
        }
    };
}

// --- UI Logic ---
function renderNetworkList(nodes) {
    els.netList.innerHTML = "";

    let totalEgo = 0;

    nodes.forEach(node => {
        totalEgo += node.ego_score;

        const isParasite = node.type.includes("Parasite");
        const li = document.createElement('li');
        if (isParasite) li.classList.add('glitch');

        li.innerHTML = `
            <div style="display:flex; align-items:center; width: 100%;">
                <span>📡 ${node.name}</span>
                <span style="font-size: 8px; margin-left: 5px; color: ${node.signature === 'UNSIGNED' ? '#666' : 'var(--neon-blue)'}">[${node.signature === 'UNSIGNED' ? 'UNVERIFIED' : 'SIG-OK'}]</span>
                <span style="font-size: 9px; margin-left: auto; color: var(--neon-amber);">$${node.credits}</span>
                <span class="node-status-tag" style="color: ${node.status === 'MISTRUSTED' ? 'var(--neon-red)' : (isParasite ? 'var(--neon-amber)' : 'var(--neon-green)')}">
                    ${node.status === 'MISTRUSTED' ? '!!! MISTRUSTED !!!' : (isParasite ? 'PARASITE' : 'ACTIVE')}
                </span>
            </div>
            <div class="ego-bar">
                <div class="ego-fill" style="width: ${node.ego_score}%"></div>
            </div>
            <div class="load-bar">
                <div class="load-fill" style="width: ${node.compute_load}%"></div>
            </div>
        `;

        if (node.status === 'MISTRUSTED') {
            li.style.border = "1px solid var(--neon-red)";
            li.style.background = "rgba(255,0,0,0.1)";
        }

        li.onclick = () => {
            document.querySelectorAll('#network-list li').forEach(l => l.classList.remove('active'));
            li.classList.add('active');
            selectedTarget = node.name;
            updatePsychProfile(node);
        };
        els.netList.appendChild(li);

        // Auto-select first if none selected
        if (!selectedTarget) {
            li.click();
        }
    });

    // Update global Vibe Monitor
    const avgEgo = nodes.length ? (totalEgo / nodes.length) : 50;
    document.getElementById('mesh-ego-avg').style.width = `${avgEgo}%`;

    // Find our OWN node if possible (hacky assumption: matches name in nodeId if initialized)
    const myNode = nodes.find(n => n.name.toLowerCase() === els.nodeId.textContent.toLowerCase());
    if (myNode) {
        document.getElementById('mesh-wealth').textContent = `Wealth: ${myNode.credits} CR`;
        document.getElementById('node-payload-name').textContent = myNode.compute_load > 60 ? "Inference" : (myNode.compute_load > 0 ? "Mining" : "Idle");
    }
}

function updatePsychProfile(node) {
    const el = document.getElementById('psych-profile');
    const pName = document.getElementById('psych-persona');
    const pId = document.getElementById('psych-id');
    const pLoad = document.getElementById('psych-load');
    const pCredits = document.getElementById('psych-credits');
    const pVerdict = document.getElementById('psych-verdict');

    el.style.display = 'block';

    const isParasite = node.type.includes("Parasite");
    const personas = ["Architect", "Logistics Master", "Triage Unit", "Coordinator"];
    const persona = personas[Math.abs(node.name.length % personas.length)];

    pName.textContent = `Persona: ${persona}`;
    pId.textContent = `Integrity: ${isParasite ? 'VOLATILE (Panic)' : 'STABLE'}`;
    pLoad.textContent = `Compute Load: ${node.compute_load}%`;
    pCredits.textContent = `Wealth: ${node.credits} CR`;
    pVerdict.textContent = `VIBE: ${node.ego_score > 70 ? 'ALTRUISTIC' : (node.ego_score > 40 ? 'PRAGMATIC' : ' OPPORTUNISTIC')}`;
    pVerdict.style.color = node.ego_score > 40 ? 'var(--neon-green)' : 'var(--neon-amber)';

    // Intelligence Market: Add RENT button if we have load
    const btnRent = document.createElement('button');
    btnRent.className = 'btn';
    btnRent.style.fontSize = "8px";
    btnRent.style.marginTop = "5px";
    btnRent.style.borderColor = "var(--neon-amber)";
    btnRent.textContent = "RENT COMPUTE (50 CR)";
    btnRent.onclick = () => {
        socket.send(JSON.stringify({ action: "rent_compute", target: node.name }));
    };
    pVerdict.appendChild(document.createElement('br'));
    pVerdict.appendChild(btnRent);

    if (isParasite) {
        const btnOverride = document.createElement('button');
        btnOverride.className = 'btn';
        btnOverride.style.fontSize = "8px";
        btnOverride.style.marginTop = "5px";
        btnOverride.textContent = "ID-OVERRIDE (Force Active)";
        btnOverride.onclick = () => {
            socket.send(JSON.stringify({ action: "override", target: node.name }));
            btnOverride.disabled = true;
            btnOverride.textContent = "Override Sent...";
        };
        pVerdict.appendChild(document.createElement('br'));
        pVerdict.appendChild(btnOverride);

        pVerdict.innerHTML += `<br><span style="color:var(--neon-red)">STATUS: CANNIBALIZING</span>`;
    }

    // Social Chat Trigger
    const btnChat = document.createElement('button');
    btnChat.className = 'btn';
    btnChat.style.fontSize = "8px";
    btnChat.style.marginTop = "5px";
    btnChat.style.marginLeft = "5px";
    btnChat.style.borderColor = "var(--neon-blue)";
    btnChat.textContent = "SEND SOCIAL BEAT";
    btnChat.onclick = () => {
        const text = prompt("Enter social message for " + node.name);
        if (text) {
            socket.send(JSON.stringify({
                action: "social_chat",
                target: node.name,
                content: text
            }));
        }
    };
    pVerdict.appendChild(btnChat);
}

function renderMissionUpdate(update) {
    const log = els.missionLog;
    const div = document.createElement('div');
    div.style.fontSize = "10px";
    div.style.marginBottom = "4px";

    if (update.status === "Success") {
        div.innerHTML = `<span style="color:var(--neon-green)">🏁 MISSION COMPLETE: Success.</span>`;
    } else {
        div.innerHTML = `<span style="color:var(--neon-blue)">[STEP ${update.step + 1}]</span> ${update.log}`;
    }

    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
}

function addLog(sender, text, type = "system") {
    const div = document.createElement('div');
    div.className = `msg ${type}`;
    div.innerHTML = `
        <div class="msg-header">${sender} • ${new Date().toLocaleTimeString()}</div>
        <div class="msg-body">${text}</div>
    `;
    els.chatHistory.appendChild(div);
    els.chatHistory.scrollTop = els.chatHistory.scrollHeight;
}

// --- Interaction ---
els.btnScan.onclick = () => {
    if (socket) socket.send(JSON.stringify({ action: "scan" }));
};

els.btnSend.onclick = () => {
    const content = els.msgInput.value;
    if (!content || !selectedTarget) return;

    // Send to Bridge
    socket.send(JSON.stringify({
        action: "send",
        target: selectedTarget,
        content: content
    }));

    addLog("Me", content, "sent");
    els.msgInput.value = "";
};

els.btnMission.onclick = () => {
    const mission = {
        action: "start_mission",
        id: "M-" + Date.now().toString().slice(-4),
        steps: [
            { task: "NBP Scan & Topology Discovery" },
            { task: "Resource Ego-Negotiation (VRAM Cluster)" },
            { task: "Distributed Multimodal Triage" },
            { task: "Mesh Consensus & Knowledge Commit" }
        ]
    };
    els.missionLog.innerHTML = `<div style="color:var(--neon-blue)">INITIATING MARATHON MISSION ${mission.id}...</div>`;
    socket.send(JSON.stringify(mission));
};

els.chkShare.onchange = (e) => {
    const active = e.target.checked;
    addLog("System", `Intelligence Sharing ${active ? 'ENABLED' : 'DISABLED'}. Node is now ${active ? 'TRUSTED' : 'PUBLIC'}`, "system");
    socket.send(JSON.stringify({ action: "toggle_sharing", value: active }));
};

// --- AI Generation ---
async function generateAutoReply(sender, incomingText) {
    if (!aiSession) return;

    addLog("AI", "Thinking...", "system");

    try {
        const prompt = `Message from ${sender} in Zone ${els.nodeId.textContent}: "${incomingText}". Reply concisely.`;
        // Streaming or non-streaming
        const response = await aiSession.prompt(prompt);

        // Auto-send the response after a simulated delay
        setTimeout(() => {
            if (selectedTarget) { // Reply to selected, or ideally reply to sender (needs logic update)
                socket.send(JSON.stringify({
                    action: "send",
                    target: sender, // Reply back to sender
                    content: response
                }));
                addLog("AI-Auto", response, "sent");
            }
        }, 1500);

    } catch (e) {
        addLog("AI Error", e.message);
    }
}

// --- Initialization ---
window.onload = () => {
    initAI();
    connect();
    startCamera(); // From vision.js
};
