import time
import socket
import logging
import json
import threading
import psutil
import hashlib
import hmac
import re
import os
import struct
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nx0mesh")

# NEXUS-0 Multicast (NMC) Configuration
NMC_GROUP = "ff02::1"
NMC_PORT = 19541 # Sovereign Port

@dataclass
class NX0Node:
    name: str  # Hashed in standard operation
    type: str  # Hashed in standard operation
    zone: str
    address: str
    ego_score: int = 50 
    compute_load: int = 0
    uptime: float = field(default_factory=time.time)
    first_seen_ts: float = field(default_factory=time.time) # Local Peer Aging
    signature: str = "UNSIGNED" 
    status: str = "HEALTHY"

class NX0Mesh:
    def __init__(self, name: str, zone: str = "NEXUS-0", port: int = 8080, node_type: str = "Bridge", ego_score: int = 100):
        self.name = name
        self.zone = zone
        self.port = port
        self.type = node_type
        self.ego_score = ego_score
        self.start_time = time.time()
        self.status = "HEALTHY"
        
        self.nodes = {} 
        self._shunned = set() 
        self._pulse_cache = {} 
        self._salt = os.getenv("NX0_SALT", "SOVEREIGN-DEFAULT")
        
        # Security Anchor & Failover State
        self._is_anchor = False
        self._anchor_id = None 
        self._anchor_pubkey = None
        self._epoch_key = os.urandom(32) # Fallback key
        self._last_epoch_ts = 0
        self._last_anchor_pulse_ts = 0
        self._last_epoch_response_ts = 0 # Rate-limiting
        self._failover_hysteresis_ts = 0 # Confirmation buffer
        
        # Sovereign Identity (Volatile Session Key)
        self._private_key = ed25519.Ed25519PrivateKey.generate()
        self.public_key_bytes = self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        self.pubkey_hex = self.public_key_bytes.hex()
        
        self._running = False
        self._listen_thread = None
        self._adv_thread = None
        
        # Network Identity
        self.ipv6_ll, self.interface = self._get_ipv6_ll()
        if not self.ipv6_ll:
            logger.warning("No IPv6 Link-Local address found.")
        else:
            logger.info(f"Initialized Anchor Node: {self.name} on {self.ipv6_ll}")

    def _get_ipv6_ll(self):
        try:
            for interface, addrs in psutil.net_if_addrs().items():
                if 'loopback' in interface.lower() or 'veth' in interface.lower():
                    continue
                for addr in addrs:
                    if addr.family == socket.AF_INET6 and addr.address.startswith('fe80:'):
                        return addr.address.split('%')[0], interface
        except Exception as e:
            logger.error(f"IP Detect Error: {e}")
        return None, None

    def _hash_id(self, value: str) -> str:
        return hashlib.sha256(f"{value}:{self._salt}".encode()).hexdigest()[:16]

    def register(self):
        self._running = True
        self._listen_thread = threading.Thread(target=self._listen_for_peers, daemon=True)
        self._adv_thread = threading.Thread(target=self._advertise_presence, daemon=True)
        self._listen_thread.start()
        self._adv_thread.start()
        
        # Immediate Sync: Demand the truth from the Anchor
        self._request_epoch()
        logger.info("NEXUS-0 Deterministic Anchor Truth Active. Triggering Rapid Sync.")

    def _request_epoch(self):
        """Broadcast a demand for immediate truth synchronization."""
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        msg = {
            "type": "REQ_EPOCH",
            "requester": self.name,
            "pubkey": self.pubkey_hex,
            "ts": time.time()
        }
        # Sign it
        raw_req = json.dumps(msg, sort_keys=True).encode('utf-8')
        msg["signature"] = self._private_key.sign(raw_req).hex()
        
        sock.sendto(json.dumps(msg).encode('utf-8'), (NMC_GROUP, NMC_PORT))
        logger.debug("Sent REQ_EPOCH pulse.")

    def stop(self):
        """Gracefully shut down the mesh node."""
        self._running = False
        logger.info(f"Shutting down node: {self.name}")

    def _advertise_presence(self):
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_HOPS, 1)
        
        while self._running:
            try:
                # 1. Deterministic Failover Check
                # If the Anchor is silent for 15s, evaluate promotion
                if not self._is_anchor and (time.time() - self._last_anchor_pulse_ts > 15):
                    self._evaluate_failover()

                # 2. Anchor: Scheduled Epoch Broadcast (60s)
                if self._is_anchor and (time.time() - self._last_epoch_ts > 60):
                    self._broadcast_epoch(sock)

                # 3. Standard Pulse (ANN)
                node_data = {
                    "name_hash": self._hash_id(self.name),
                    "type_hash": self._hash_id(self.type),
                    "zone": self.zone,
                    "address": f"[{self.ipv6_ll}]:{self.port}",
                    "ego_score": self.ego_score,
                    "uptime": time.time() - self.start_time,
                    "pubkey": self.pubkey_hex,
                    "status": self.status
                }
                
                msg = {
                    "type": "ANN",
                    "node": node_data,
                    "ts": time.time()
                }
                
                # Sign with Ed25519
                raw_data = json.dumps(node_data, sort_keys=True).encode('utf-8')
                msg["signature"] = self._private_key.sign(raw_data).hex()
                
                # Add Integrity HMAC (If Epoch is known)
                msg["hmac"] = hmac.new(self._epoch_key, raw_data, hashlib.sha256).hexdigest()
                
                sock.sendto(json.dumps(msg).encode('utf-8'), (NMC_GROUP, NMC_PORT))
            except Exception as e:
                logger.debug(f"ADV Error: {e}")
            time.sleep(5)

    def _evaluate_failover(self):
        """Autonomous Promotion: Highest Ego/Seniority node becomes Anchor."""
        peers = list(self.nodes.values())
        if not peers:
            if not self._is_anchor:
                self._is_anchor = True
                logger.info("GENESIS: I am the only node. Assuming Anchor status.")
            return

        # Selection formula: Max(Ego, FirstSeen, ID)
        top_ego = max([p.ego_score for p in peers] + [self.ego_score])
        if self.ego_score >= top_ego:
            # Local Peer Aging: Use local 'first_seen' for seniority
            # My own 'first seen' is my start_time
            my_seniority = self.start_time
            top_seniority = min([p.first_seen_ts for p in peers] + [my_seniority])
            
            if my_seniority <= top_seniority:
                # Hysteresis: Require silence + 5s buffer to prevent Promotion Storms
                if self._failover_hysteresis_ts == 0:
                    self._failover_hysteresis_ts = time.time()
                    logger.info("FAILOVER: Anchor silent. Initiating hysteresis buffer...")
                
                if time.time() - self._failover_hysteresis_ts > 5:
                    self._is_anchor = True
                    logger.warning("FAILOVER: Succession confirmed. I am promoting myself.")
                    self._last_epoch_ts = 0 
                    self._failover_hysteresis_ts = 0
        else:
            self._failover_hysteresis_ts = 0

    def _broadcast_epoch(self, sock=None):
        """Anchor Only: Broadcast Truth pulse."""
        if sock is None:
            sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            
        new_key = os.urandom(32)
        self._epoch_key = new_key
        self._last_epoch_ts = time.time()
        
        epoch_msg = {
            "type": "EPOCH",
            "key_hex": new_key.hex(),
            "anchor_id": self.ipv6_ll,
            "anchor_pubkey": self.pubkey_hex,
            "ego": self.ego_score,
            "ts": self._last_epoch_ts
        }
        
        raw_epoch = json.dumps(epoch_msg, sort_keys=True).encode('utf-8')
        epoch_msg["signature"] = self._private_key.sign(raw_epoch).hex()
        
        sock.sendto(json.dumps(epoch_msg).encode('utf-8'), (NMC_GROUP, NMC_PORT))
        logger.info(f"ANCHOR: Broadasting New Epoch Key (TS: {epoch_msg['ts']})")

    def _listen_for_peers(self):
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('::', NMC_PORT))
        
        if self.interface:
            try:
                if_idx = socket.if_nametoindex(self.interface)
                mreq = struct.pack("16sI", socket.inet_pton(socket.AF_INET6, NMC_GROUP), if_idx)
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)
            except Exception as e:
                logger.error(f"Group Join Error: {e}")

        while self._running:
            try:
                data, addr = sock.recvfrom(8192)
                peer_id = addr[0]
                
                msg = json.loads(data.decode('utf-8'))
                m_type = msg.get("type")

                if m_type == "EPOCH":
                    self._handle_epoch(msg, peer_id)
                elif m_type == "ANN":
                    self._handle_announcement(msg, peer_id)
                elif m_type == "REQ_EPOCH":
                    self._handle_epoch_request(msg, peer_id)

            except Exception as e:
                logger.debug(f"Listen Error: {e}")

    def _handle_epoch_request(self, msg, peer_id):
        """Sentient Defense: Respond to rapid sync requests if I am Anchor."""
        if self._is_anchor:
            # Rate-limiting: Max 1 response per 2 seconds (Anti-DDoS)
            if time.time() - self._last_epoch_response_ts < 2:
                return 
                
            logger.info(f"ANCHOR: Received REQ_EPOCH from {peer_id}. Responding.")
            self._broadcast_epoch()
            self._last_epoch_response_ts = time.time()

    def _handle_epoch(self, msg, peer_id):
        """Validate and adopt a new Anchor Truth."""
        peer_ego = msg.get("ego", 0)
        peer_pubkey = msg.get("anchor_pubkey")
        sig = msg.get("signature")
        
        # 1. Selection logic: Only accept if they have higher or equal authority
        if peer_ego < self.ego_score:
            return 

        # 2. Cryptographic Validation
        try:
            pubkey = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(peer_pubkey))
            raw_msg = json.dumps({k: v for k, v in msg.items() if k != "signature"}, sort_keys=True).encode('utf-8')
            pubkey.verify(bytes.fromhex(sig), raw_msg)
        except Exception as e:
            logger.warning(f"SECURITY ALERT: Forged EPOCH from {peer_id}: {e}")
            return

        # 3. Adopt the truth
        self._epoch_key = bytes.fromhex(msg["key_hex"])
        self._anchor_id = peer_id
        self._anchor_pubkey = peer_pubkey
        self._last_anchor_pulse_ts = time.time()
        
        if peer_id != self.ipv6_ll:
            self._is_anchor = False
            logger.info(f"TRUTH ADOPTED: Anchor confirmed at {peer_id}")
        else:
            self._is_anchor = True

    def _handle_announcement(self, msg, peer_id):
        node_data = msg.get("node")
        sig = msg.get("signature")
        hmac_val = msg.get("hmac")
        pubkey_hex = node_data.get("pubkey")
        
        if not node_data or not sig:
            return # Silent Drop

        # 1. Deterministic Verification: HMAC (Noise Filter)
        if hmac_val:
            raw_data = json.dumps(node_data, sort_keys=True).encode('utf-8')
            expected_hmac = hmac.new(self._epoch_key, raw_data, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(hmac_val, expected_hmac):
                return # Silent Drop

        # Update Last contact
        if peer_id == self._anchor_id:
            self._last_anchor_pulse_ts = time.time()

        # 2. Cryptographic Verification: Ed25519 (Identity Filter)
        try:
            pubkey = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(pubkey_hex))
            raw_data = json.dumps(node_data, sort_keys=True).encode('utf-8')
            pubkey.verify(bytes.fromhex(sig), raw_data)
        except Exception:
            return # Silent Drop

        # Peer is Verified
        name_hash = node_data.get("name_hash", peer_id)
        if peer_id != self.ipv6_ll:
            # Local Peer Aging: Record when we FIRST saw this node
            first_seen = time.time()
            if name_hash in self.nodes:
                first_seen = self.nodes[name_hash].first_seen_ts

            self.nodes[name_hash] = NX0Node(
                name=name_hash, 
                type=node_data.get("type_hash", "Unknown"),
                zone=node_data.get("zone"),
                address=node_data.get("address"),
                ego_score=node_data.get("ego_score"),
                uptime=node_data.get("uptime", 0),
                first_seen_ts=first_seen,
                signature=sig,
                status=node_data.get("status")
            )

    def discover(self, zone: str = "*") -> List[NX0Node]:
        return [n for n in self.nodes.values() if zone == "*" or n.zone == zone]

    def close(self):
        self._running = False
        logger.info("NEXUS-0 Node Shutting Down.")
