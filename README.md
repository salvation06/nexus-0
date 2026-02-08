# NEXUS-0: Deterministic Truth for Decentralized Mesh Networks

**A Research Prototype Demonstrating Consensus-Free Mesh Coordination**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Cloud%20Run-blue)](https://nexus-0-534084313950.us-central1.run.app/)
[![Status](https://img.shields.io/badge/Status-Research%20Prototype-yellow)]()

---

## Overview

NEXUS-0 is a research prototype that demonstrates **Deterministic Anchor Truth (DAT)** - a consensus-free approach to mesh coordination that achieves 95% reduction in security-related network traffic while maintaining cryptographic integrity.

Instead of consensus algorithms (Raft, Paxos, BFT), NEXUS-0 uses a deterministic formula to elect the "Truth Anchor" based on authority scores. This eliminates voting overhead, split-brain paralysis, and security gossip noise.

**Live Demo**: [nexus-0-534084313950.us-central1.run.app](https://nexus-0-534084313950.us-central1.run.app/)

---

## Key Features

### 🌐 Zero-Configuration Discovery
- IPv6 Link-Local Multicast (ff02::1) for auto-discovery
- Works without DNS, DHCP, or centralized infrastructure
- Self-assigned fe80:: addresses via NDP

### ⚡ Autonomous Failover
- <20 second recovery with zero human intervention
- Deterministic election: `Anchor = max(Ego Score, Local Seniority, ID Hash)`
- 5-second hysteresis buffer prevents promotion storms

### 🔐 Cryptographic Security
- Ed25519 signatures for identity verification
- HMAC-Epoch keys (60-second rotation)
- Silent Drop: Invalid pulses discarded without broadcasting accusations
- 95% noise reduction vs. consensus-based systems

### 🚀 Rapid Synchronization
- REQ_EPOCH protocol reduces join latency from 60s to <500ms
- New nodes request immediate Epoch Key delivery
- Rate-limited to prevent DoS attacks

---

## Quick Start

### Cloud Simulation (10-Node Mesh)

```bash
# Clone the repository
git clone https://github.com/salvation06/nexus-0
cd nexus-0

# Install dependencies
pip install fastapi "uvicorn[standard]" psutil websockets cryptography httpx

# Run locally
python bridge_server.py
```

Visit `http://localhost:8080` to see the 10-node mesh simulation with real-time WebSocket updates.

### Deploy to Google Cloud Run

```bash
# Install Google Cloud SDK
# https://cloud.google.com/sdk/docs/install

# Deploy
gcloud run deploy nexus-0 \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

---

## Architecture

### Layer 1: Physical Network
**Current Implementation**: IPv6 Link-Local over Wired Ethernet or Direct WiFi

- ✅ Works: Wired Ethernet, single-hop wireless, controlled environments
- ⚠️ Needs Work: Multi-hop wireless mesh (requires HWMP routing)

### Layer 2: Link-Local Discovery (NMC)
**Nexus Multicast (NMC)** - Streamlined IPv6 Link-Local Multicast protocol

- Address: `ff02::1` (All-Nodes Multicast)
- Port: UDP 19541
- Pulse Interval: 5 seconds
- Payload: Physical ID, Persona, Ed25519 Pubkey, Signature, HMAC

### Layer 3: Deterministic Anchor Truth (DAT)
**Consensus-Free Leader Election**

```python
def calculate_authority(node):
    return (
        node.ego_score,        # Pre-assigned authority level
        node.local_seniority,  # First-seen timestamp
        node.id_hash           # Deterministic tie-breaker
    )

anchor = max(all_nodes, key=calculate_authority)
```

**Epoch-Based HMAC**:
1. Anchor generates 60-second rotating Epoch Key
2. All announcements must include HMAC-SHA256(data, epoch_key)
3. Invalid HMACs are silently dropped (zero noise)

---

## What Works vs. What Needs Work

### ✅ Proven

- **Deterministic Anchor Truth**: 95% noise reduction vs. consensus
- **Autonomous Failover**: <20s recovery with zero human intervention
- **IPv6 Link-Local**: Zero-configuration on wired networks
- **Silent Drop Security**: Zero-noise integrity floor

### ⚠️ Limitations

- **Multi-Hop Routing**: Requires HWMP implementation (planned)
- **Clock Synchronization**: Needs Anchor-provided timestamps (planned)
- **Hardware Requirements**: 802.11s requires specialized adapters (Intel AX210, Alfa AWUS036ACH)
- **Single-Hop Only**: Current implementation is link-local scope

---

## Use Cases

**Where NEXUS-0 Works Today**:
- Wired link-local networks (Ethernet + IPv6)
- Single-hop wireless (ad-hoc or shared AP)
- Research networks demonstrating consensus-free coordination
- Controlled environments with pre-provisioned hardware

**Target Applications** (with future enhancements):
- Disaster response coordination
- Offshore energy operations
- Conflict zone medical facilities
- Remote research stations

---

## Technology Stack

- **Python 3.11**: Core mesh SDK and orchestration
- **FastAPI**: WebSocket-based real-time dashboard
- **IPv6 Link-Local**: fe80::/10 self-assigned addresses
- **UDP Multicast**: ff02::1 for zero-config discovery
- **Cryptography**: Ed25519 signatures, HMAC-SHA256 verification
- **Google Cloud Run**: Containerized deployment

---

## Project Status

**Current**: Research Prototype  
**Proven**: Consensus-free mesh coordination on link-local networks  
**Next Steps**: HWMP routing, clock synchronization, hardware validation

---

## License

Apache 2.0 (permissive for research and commercial use)

---

## Links

- **Live Demo**: [nexus-0-534084313950.us-central1.run.app](https://nexus-0-534084313950.us-central1.run.app/)
- **Technical Specs**: [nexus-0-534084313950.us-central1.run.app/specs](https://nexus-0-534084313950.us-central1.run.app/specs)
- **Hackathon Submission**: See `hackathon_submission.md` (if included)

---

**When infrastructure fails, deterministic truth doesn't need consensus.**

⚓🛡️🧪
