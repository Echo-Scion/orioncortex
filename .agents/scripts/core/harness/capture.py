"""
Tool-Call Quantum Counter & Secret Egress Redactor.
Pure Python 3 standard library implementation.
Tracks tool calls and ensures egress transcript slices contain zero secrets.
"""
import os
import re
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

REDACTION_PATTERNS = [
    # API Keys & Tokens
    (re.compile(r"(?i)(api[_-]?key|access[_-]?token|auth[_-]?token|secret[_-]?key|bearer)\s*[:=\s]\s*['\"]?([a-zA-Z0-9_\-\.]{16,})['\"]?"), r"\1=[REDACTED]"),
    (re.compile(r"\b(sk-[a-zA-Z0-9]{20,})\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\b(ghp_[a-zA-Z0-9]{36,})\b"), "[REDACTED_GH_TOKEN]"),
    (re.compile(r"\b(gho_[a-zA-Z0-9]{36,})\b"), "[REDACTED_GH_OAUTH]"),
    (re.compile(r"\b(AKIA[0-9A-Z]{16})\b"), "[REDACTED_AWS_KEY]"),
    # Private Keys & Certificates
    (re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
    # Passwords in URLs & Envs
    (re.compile(r"://([^:]+):([^@]+)@"), r"://\1:[REDACTED]@"),
    (re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?([^\s'\"]{6,})['\"]?"), r"\1=[REDACTED]"),
    # JWT Tokens
    (re.compile(r"\beyJ[a-zA-Z0-9_\-]+\.eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+"), "[REDACTED_JWT]"),
]


class SecretRedactor:
    """Deterministic regex sanitizer for session transcripts and evidence slices."""

    @classmethod
    def redact_text(cls, text: str) -> str:
        if not text:
            return ""
        redacted = text
        for pattern, replacement in REDACTION_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        return redacted

    @classmethod
    def redact_data(cls, data: Any) -> Any:
        if isinstance(data, str):
            return cls.redact_text(data)
        elif isinstance(data, dict):
            return {k: cls.redact_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [cls.redact_data(v) for v in data]
        return data


@dataclass
class SessionTelemetryState:
    session_id: str
    tool_call_count: int = 0
    last_reflection_call: int = 0
    total_turns: int = 0
    created_at: str = ""
    active: bool = True


class ToolQuantumCapture:
    """
    Counts tool calls in an active session without resident daemons.
    Determines when an episode reaches quantum maturity (N tool calls).
    """

    def __init__(self, state_dir: str, quantum_threshold: int = 50):
        self.state_dir = state_dir
        self.quantum_threshold = quantum_threshold
        self.sessions_dir = os.path.join(self.state_dir, "sessions")
        os.makedirs(self.sessions_dir, exist_ok=True)

    def _get_session_path(self, session_id: str) -> str:
        safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", session_id)
        return os.path.join(self.sessions_dir, f"{safe_id}.json")

    def load_session(self, session_id: str) -> SessionTelemetryState:
        p = self._get_session_path(session_id)
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return SessionTelemetryState(**data)
            except Exception:
                pass
        return SessionTelemetryState(session_id=session_id)

    def save_session(self, state: SessionTelemetryState) -> None:
        p = self._get_session_path(state.session_id)
        tmp = f"{p}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state.__dict__, f, indent=2)
        os.replace(tmp, p)

    def record_tool_call(self, session_id: str, tool_name: str, args: Dict[str, Any]) -> Tuple[bool, int]:
        """
        Increments tool call count.
        Returns:
            (should_reflect: bool, current_quantum_calls: int)
        """
        state = self.load_session(session_id)
        state.tool_call_count += 1
        state.total_turns += 1
        
        calls_since_reflect = state.tool_call_count - state.last_reflection_call
        should_reflect = calls_since_reflect >= self.quantum_threshold

        if should_reflect:
            state.last_reflection_call = state.tool_call_count

        self.save_session(state)
        return should_reflect, calls_since_reflect

    def reset_reflection_watermark(self, session_id: str) -> None:
        state = self.load_session(session_id)
        state.last_reflection_call = state.tool_call_count
        self.save_session(state)
