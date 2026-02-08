
import os
import asyncio
import logging
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import urllib.request
import urllib.error
import psutil
import hashlib
import time
import httpx
import subprocess
import sys

from nx0mesh_sdk import NX0Mesh

# Configuration: Transition to NEXUS-0 Vars
ZONE = os.getenv("NX0_ZONE", "Unknown")
NAME = os.getenv("NX0_NAME", "Unknown")
PORT = 8080

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("NX0Bridge")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serving static files for the UI
# We move the mount to the end to avoid shadowing

# Initialize NEXUS-0 Mesh
mesh = NX0Mesh(NAME, ZONE, PORT)

# Sub-process Tracking
sub_processes = {}
node_cache = []
cache_lock = asyncio.Lock()
SALT = os.getenv("NX0_SALT", "SOVEREIGN-DEFAULT")

def hash_id(value: str) -> str:
    """Helper to match SDK metadata hashes."""
    return hashlib.sha256(f"{value}:{SALT}".encode()).hexdigest()[:16]

RIG_HASH = hash_id("Rig-Hub")
MULE_HASH = hash_id("Data-Mule")

async def discovery_loop():
    """Background task to refresh NEXUS-0 nodes."""
    global node_cache
    logger.info("Starting NEXUS-0 discovery loop")
    
    while True:
        try:
            loop = asyncio.get_event_loop()
            nodes = await loop.run_in_executor(None, mesh.discover)

            async with cache_lock:
                node_cache = nodes
                anchor_status = "(Anchor)" if mesh._is_anchor else f"(Peering to {mesh._anchor_id})"
                logger.info(f"📍 MESH: {len(node_cache)} nodes | My State: {anchor_status}")
            
            # Auto-Sync Logic: The 'Maritime Clique' Handshake
            # If we are a Rig and see a Ship (or vice versa), we sync payloads.
            for peer in nodes:
                is_rig = peer.type == RIG_HASH
                is_mule = peer.type == MULE_HASH
                
                if (mesh.type == "Rig-Hub" and is_mule) or \
                   (mesh.type == "Data-Mule" and is_rig):
                    
                    # Diva: "The sovereign handshake is the sound of truth crossing the waves."
                    logger.info(f"⚓ MARITIME CLIQUE: Sovereign Handshake with {peer.name}")
                    
                    # Notify UI for animation
                    await manager.broadcast({
                        "type": "maritime_sync",
                        "source": mesh.name,
                        "target": peer.name,
                        "status": "Transferred"
                    })
                
            await manager.broadcast({
                "type": "mesh_update",
                "nodes": [n.__dict__ for n in nodes],
                "anchor_id": mesh._anchor_id,
                "is_anchor": mesh._is_anchor,
                "epoch_ts": mesh._last_epoch_ts
            })
        except Exception as e:
            logger.error(f"Discovery loop error: {e}")
        
        await asyncio.sleep(5)

@app.get("/")
async def root():
    """Serve the high-impact landing page."""
    from fastapi.responses import FileResponse
    return FileResponse("web/index.html")

@app.get("/simulation")
async def simulation():
    """Serve the Sovereign Link dashboard."""
    from fastapi.responses import FileResponse
    return FileResponse("web/dashboard.html")

@app.get("/specs")
async def specs():
    """Serve the technical specifications."""
    from fastapi.responses import FileResponse
    return FileResponse("web/specs.html")

@app.get("/health")
async def health():
    """Cloud Run health check."""
    return {"status": "ok", "mesh_nodes": len(sub_processes), "mode": "Sovereign"}

async def id_loop():
    """NEXUS-0 Survival Instincts."""
    while True:
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            mem_usage = psutil.virtual_memory().percent
            logger.info(f"Heartbeat: CPU {cpu_usage}% | RAM {mem_usage}%")
            
            if mem_usage > 90:
                mesh.status = "STRESSED"
            elif mesh.status == "STRESSED":
                mesh.status = "HEALTHY"
            
            # Anchor Heartbeat
            if mesh._is_anchor:
                # Diva: "The Anchor's heartbeat is the rhythm of the mesh."
                logger.debug("I am the Anchor. Truth is steady.")
        except Exception as e:
            logger.error(f"Id-Loop error: {e}")
        await asyncio.sleep(10)

@app.on_event("startup")
async def startup_event():
    # Diva: "Launch the NEXUS-0 Sovereign Link."
    logger.info(f"STARTUP: Node {NAME} | Zone {ZONE} | Type {os.getenv('NX0_TYPE')} | Ego {os.getenv('NX0_EGO')}")
    mesh.type = os.getenv("NX0_TYPE", "Bridge")
    mesh.ego_score = int(os.getenv("NX0_EGO", 0))
    
    mesh.register()
    asyncio.create_task(discovery_loop())
    asyncio.create_task(id_loop())

    if os.getenv("NX0_SIMULATION_MODE") != "1":
        # Launch the 10-node Sovereign Mesh
        node_names = [
            "Alpha", "Beta", "Gamma", "Delta", "Epsilon", 
            "Zeta", "Eta", "Theta", "Iota", "Kappa"
        ]
        # Start from 50 (Alpha=100, others cascade)
        for i, name in enumerate(node_names):
            # Alpha is Anchor (100), others descending
            # We use distinct UDP ports to avoid multicast loopback collision in Cloud Run env
            ego = 100 if name == "Alpha" else (90 - (i * 5))
            spawn_node(name, "Agent", str(ego), base_port=19541 + i)
            time.sleep(0.5)

    # ORCHESTRATION: If this is the main dashboard, spawn the mesh
    if mesh.type == "Bridge":
        logger.info("ORCHESTRATOR: Spawning simulated mesh nodes...")
        spawn_node("Alpha", "Rig-Hub", "100")
        spawn_node("Beta", "Rig-Hub", "90")
        spawn_node("Gamma", "Data-Mule", "50")

def spawn_node(name, ntype, ego, base_port=19541):
    """Spawn an independent NEXUS-0 node as a sub-process."""
    env = os.environ.copy()
    env["NX0_NAME"] = name
    env["NX0_TYPE"] = ntype
    env["NX0_EGO"] = ego
    env["NX0_PORT"] = str(base_port)
    env["NX0_SIMULATION_MODE"] = "1"
    # Allow sub-processes to inherit stdout/stderr for Cloud Run logging (Avoids pipe deadlock)
    proc = subprocess.Popen(
        [sys.executable, "bridge_server.py"],
        env=env
    )
    sub_processes[name] = proc
    logger.info(f"SPAWNED: {name} (PID: {proc.pid}) at Port {base_port}")

@app.on_event("shutdown")
async def shutdown_event():
    mesh.close()

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            
            if action == "scan":
                async with cache_lock:
                    await websocket.send_json({
                        "type": "scan_result",
                        "nodes": [n.__dict__ for n in node_cache]
                    })
            
            elif action == "send":
                target_name = data.get("target")
                content = data.get("content")
                async with cache_lock:
                    target_node = next((n for n in node_cache if n.name == target_name), None)
                
                if target_node:
                    try:
                        url = f"http://{target_node.address}/message"
                        req = urllib.request.Request(
                            url, 
                            data=json.dumps({"sender": NAME, "content": content}).encode('utf-8'),
                            headers={'Content-Type': 'application/json'}
                        )
                        urllib.request.urlopen(req)
                        await websocket.send_json({"type": "status", "msg": f"Sent to {target_name}"})
                    except Exception as e:
                        await websocket.send_json({"type": "error", "msg": str(e)})
                else:
                    await websocket.send_json({"type": "error", "msg": "Target not found"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/demo/kill")
async def kill_node():
    """Simulate a sudden node failure (Nuclear Option for demo)."""
    logger.warning("DEMO: Received KILL signal. Shutting down in 1s...")
    async def shutdown():
        await asyncio.sleep(1)
        os._exit(0) # Immediate exit to simulate crash
    asyncio.create_task(shutdown())
    return {"status": "success", "msg": "Node will terminate in 1s."}

@app.get("/nodes")
async def list_nodes():
    """Diagnostic: List all currently tracked sub-processes."""
    return {
        "tracked": list(sub_processes.keys()),
        "count": len(sub_processes),
        "mesh_type": mesh.type
    }

@app.get("/status")
async def node_status():
    """Returns local mesh state for the dashboard."""
    return {
        "name": mesh.name,
        "is_anchor": mesh._is_anchor,
        "anchor_id": mesh._anchor_id,
        "ego": mesh.ego_score,
        "uptime": time.time() - mesh.start_time
    }

@app.post("/kill")
async def remote_kill(target: str):
    """Orchestrate a kill signal for a sub-process."""
    logger.warning(f"ORCHESTRATOR: Terminating sub-process '{target}'")
    
    # Standardize: remove prefix, handle lowercase/uppercase
    clean_target = target.replace("nx0-", "").lower()
    
    # Find the key (case-insensitive)
    name = next((k for k in sub_processes.keys() if k.lower() == clean_target), None)
    
    if name and name in sub_processes:
        proc = sub_processes[name]
        logger.info(f"ORCHESTRATOR: Found match '{name}' for target '{target}'. Terminating PID {proc.pid}")
        proc.terminate()
        del sub_processes[name]
        return {"status": "success", "msg": f"Terminated {name}"}
    
    logger.error(f"ORCHESTRATOR: Target '{target}' (mapped to '{clean_target}') not found in tracked nodes: {list(sub_processes.keys())}")
    return {"status": "error", "msg": f"Target {target} not found in sub-processes. Tracked: {list(sub_processes.keys())}"}

@app.post("/message")
async def receive_message(msg: dict):
    logger.info(f"Received message: {msg}")
    await manager.broadcast({
        "type": "incoming_message",
        "sender": msg.get("sender"),
        "content": msg.get("content")
    })
    return {"status": "success"}

# Serve static files last
if os.path.exists("web"):
    app.mount("/web", StaticFiles(directory="web"), name="web")

# Serve static images
if os.path.exists("web/static"):
    app.mount("/static", StaticFiles(directory="web/static"), name="static")

if __name__ == "__main__":
    if os.getenv("NX0_SIMULATION_MODE") == "1":
        # MINIMAL SDK LOOP: Run the mesh without the FastAPI overhead
        logger.info(f"SIMULATION: Starting {NAME} in SDK-Only mode.")
        mesh.type = os.getenv("NX0_TYPE", "Agent")
        mesh.ego_score = int(os.getenv("NX0_EGO", 0))
        mesh.register()
        
        async def run_forever():
            # Dummy loop to keep the process alive and responding to UDP pulses
            # The NX0Mesh background thread handles the pulses.
            while True:
                await asyncio.sleep(60)
        
        try:
            asyncio.run(run_forever())
        except KeyboardInterrupt:
            mesh.close()
    else:
        import uvicorn
        # Diva: "We launch with the power of the Sovereign Swarm."
        # Use proxy_headers and forwarded_allow_ips for Cloud Run compatibility
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=int(os.getenv("PORT", 8080)),
            proxy_headers=True,
            forwarded_allow_ips="*"
        )
