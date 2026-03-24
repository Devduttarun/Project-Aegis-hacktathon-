import hashlib, hmac, json, time, uuid
from dataclasses import dataclass, field, asdict
from typing import Optional
from os import environ

SECRET_KEY = environ.get("SECRET_KEY", "dev-secret")

@dataclass
class ProvenanceRecord:
    record_id: str
    session_id: str
    parent_id: Optional[str]
    agent_name: str
    action_type: str
    original_intent: str
    action_description: str
    token_scope: str
    hop_count: int
    timestamp: float
    payload_hash: str
    previous_hash: str
    signature: str = ""

    def to_dict(self):
        return asdict(self)

class ProvenanceTracker:
    def __init__(self, session_id: str, original_intent: str):
        self.session_id = session_id
        self.original_intent = original_intent
        self.chain: list[ProvenanceRecord] = []
        self.max_hops = 3

    def _hash_payload(self, payload: dict) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]

    def _previous_hash(self) -> str:
        if not self.chain:
            return "genesis"
        last = self.chain[-1]
        return hashlib.sha256(f"{last.record_id}{last.timestamp}{last.payload_hash}".encode()).hexdigest()[:16]

    def _sign(self, record: ProvenanceRecord) -> str:
        data = json.dumps({"record_id": record.record_id, "agent_name": record.agent_name,
            "action_type": record.action_type, "payload_hash": record.payload_hash,
            "previous_hash": record.previous_hash, "timestamp": record.timestamp}, sort_keys=True)
        return hmac.new(SECRET_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()[:24]

    def record(self, agent_name, action_type, action_description, token_scope, payload,
               parent_id=None, hop_count=0) -> ProvenanceRecord:
        if hop_count > self.max_hops:
            raise ValueError(f"Token delegation depth {hop_count} exceeds max {self.max_hops}")
        r = ProvenanceRecord(
            record_id=str(uuid.uuid4())[:8], session_id=self.session_id, parent_id=parent_id,
            agent_name=agent_name, action_type=action_type, original_intent=self.original_intent,
            action_description=action_description, token_scope=token_scope, hop_count=hop_count,
            timestamp=time.time(), payload_hash=self._hash_payload(payload),
            previous_hash=self._previous_hash())
        r.signature = self._sign(r)
        self.chain.append(r)
        return r

    def verify_chain(self) -> bool:
        for i, record in enumerate(self.chain):
            if record.signature != self._sign(record):
                return False
            if i > 0:
                prev = self.chain[i-1]
                expected = hashlib.sha256(f"{prev.record_id}{prev.timestamp}{prev.payload_hash}".encode()).hexdigest()[:16]
                if record.previous_hash != expected:
                    return False
        return True

    def to_audit_trail(self) -> list[dict]:
        return [r.to_dict() for r in self.chain]
