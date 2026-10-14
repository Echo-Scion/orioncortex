import os
import sys
import time
import json
import uuid
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any, Union

def _log_telemetry(err: Exception, context: str = "") -> None:
    """Non-fatal telemetry catch for degraded operations."""
    if os.environ.get("ORION_DEBUG"):
        msg = f": {err}" if err else ""
        sys.stderr.write(f"[ORION_TELEMETRY] Non-fatal catch in {context}{msg}\n")


if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception as _e:
        _log_telemetry(_e, 'event_stream.py:reconfigure')


@dataclass(slots=True)
class Event:
    """
    Structured Action-Observation Trajectory Event.
    """
    event_id: str
    kind: str  # 'action' | 'observation' | 'system'
    source: str
    payload: Dict[str, Any]
    action_type: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


class ActionObservationStream:
    """
    Pillar 1: Autonomous Developer Action-Observation Trajectory Stream.
    Distilled from OpenHands.
    Maintains append-only JSON-L trajectory records, event replay,
    and stuck-loop / cyclical execution detection.
    """

    def __init__(self, log_path: Union[str, Path]):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        kind: str,
        source: str,
        payload: Dict[str, Any],
        action_type: Optional[str] = None
    ) -> Event:
        """Appends a new Event to the trajectory log."""
        evt = Event(
            event_id=f"evt_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
            kind=kind,
            source=source,
            payload=payload,
            action_type=action_type,
            timestamp=time.time()
        )
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(evt), default=str) + "\n")
        except Exception as e:
            _log_telemetry(e, f"ActionObservationStream:record:{kind}")
        return evt

    def record_action(self, source: str, action_type: str, payload: Dict[str, Any]) -> Event:
        """Convenience method for recording an action."""
        return self.record(kind="action", source=source, payload=payload, action_type=action_type)

    def record_observation(self, source: str, payload: Dict[str, Any]) -> Event:
        """Convenience method for recording an environment observation."""
        return self.record(kind="observation", source=source, payload=payload)

    def read_trajectory(self) -> List[Event]:
        """Reads all events from the trajectory log."""
        if not self.log_path.is_file():
            return []

        events: List[Event] = []
        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped:
                        data = json.loads(stripped)
                        events.append(Event(
                            event_id=data.get("event_id", ""),
                            kind=data.get("kind", ""),
                            source=data.get("source", ""),
                            payload=data.get("payload", {}),
                            action_type=data.get("action_type"),
                            timestamp=data.get("timestamp", 0.0)
                        ))
        except Exception as e:
            _log_telemetry(e, "ActionObservationStream:read_trajectory")
        return events

    def get_last_action(self) -> Optional[Event]:
        """Returns the most recent action event."""
        traj = self.read_trajectory()
        for evt in reversed(traj):
            if evt.kind == "action":
                return evt
        return None

    def get_last_observation(self) -> Optional[Event]:
        """Returns the most recent observation event."""
        traj = self.read_trajectory()
        for evt in reversed(traj):
            if evt.kind == "observation":
                return evt
        return None

    def detect_stuck_loop(self, window_size: int = 3) -> bool:
        """
        Detects repeating identical actions or cyclical loops in trajectory.
        """
        traj = self.read_trajectory()
        actions = [evt for evt in traj if evt.kind == "action"]
        if len(actions) < window_size:
            return False

        recent = actions[-window_size:]
        # 1. Identical repeated actions check
        first_sig = (recent[0].action_type, json.dumps(recent[0].payload, sort_keys=True))
        all_identical = all(
            (a.action_type, json.dumps(a.payload, sort_keys=True)) == first_sig
            for a in recent
        )
        if all_identical:
            return True

        # 2. 2-cycle oscillation check (A -> B -> A -> B) if window >= 4
        if len(actions) >= 4 and window_size >= 4:
            r4 = actions[-4:]
            sig0 = (r4[0].action_type, json.dumps(r4[0].payload, sort_keys=True))
            sig1 = (r4[1].action_type, json.dumps(r4[1].payload, sort_keys=True))
            sig2 = (r4[2].action_type, json.dumps(r4[2].payload, sort_keys=True))
            sig3 = (r4[3].action_type, json.dumps(r4[3].payload, sort_keys=True))
            if sig0 == sig2 and sig1 == sig3 and sig0 != sig1:
                return True

        return False

    def replay_trajectory(self, filter_kind: Optional[str] = None) -> List[Dict[str, Any]]:
        """Serializes trajectory events into a list of dictionaries."""
        traj = self.read_trajectory()
        if filter_kind:
            traj = [e for e in traj if e.kind == filter_kind]
        return [asdict(e) for e in traj]


def main():
    parser = argparse.ArgumentParser(description="Pillar 1: Action-Observation Event Stream (OpenHands Distillation)")
    parser.add_argument("action", choices=["view", "replay", "stuck"], default="view", nargs="?", help="Action to perform")
    parser.add_argument("--log", type=str, default=".agents/logs/trajectory.jsonl", help="Path to trajectory JSON-L file")
    parser.add_argument("--window", type=int, default=3, help="Window size for stuck loop detection")
    args = parser.parse_args()

    stream = ActionObservationStream(args.log)

    if args.action == "view" or args.action == "replay":
        events = stream.read_trajectory()
        print(f"[EVENT STREAM: {args.log}] Total events: {len(events)}")
        for idx, evt in enumerate(events, start=1):
            act_tag = f"({evt.action_type})" if evt.action_type else ""
            print(f"  {idx:3d}. [{evt.kind.upper()}] from {evt.source} {act_tag}: {json.dumps(evt.payload)}")

    elif args.action == "stuck":
        stuck = stream.detect_stuck_loop(window_size=args.window)
        if stuck:
            print(f"⚠️ [STUCK LOOP DETECTED] Agent trajectory exhibits repeating/cyclical actions in the last {args.window} steps.")
            sys.exit(1)
        else:
            print(f"[PROGRESS NORMAL] No stuck loop detected in the last {args.window} actions.")
            sys.exit(0)


if __name__ == "__main__":
    main()
