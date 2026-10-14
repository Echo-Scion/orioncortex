import os
import sys
import time
import uuid
import asyncio
import argparse
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Union

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
        _log_telemetry(_e, 'delegation.py:reconfigure')


@dataclass(slots=True)
class MessageEnvelope:
    """
    Typed message envelope for inter-agent communication.
    Guarantees deterministic serialization and topic routing.
    """
    message_id: str
    sender: str
    recipient: str
    topic: str
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


class PredicateGate:
    """
    Deterministic termination conditions for agent conversations and delegations.
    """
    @staticmethod
    def max_turns(max_count: int) -> Callable[[List[MessageEnvelope]], bool]:
        """Terminates when conversation history reaches max turns."""
        return lambda history: len(history) >= max_count

    @staticmethod
    def text_mention(keyword: str) -> Callable[[List[MessageEnvelope]], bool]:
        """Terminates when the latest message contains a specific token."""
        def _check(history: List[MessageEnvelope]) -> bool:
            if not history:
                return False
            latest = history[-1]
            content = str(latest.payload.get("content", ""))
            return keyword.lower() in content.lower()
        return _check

    @staticmethod
    def compound_any(*predicates: Callable[[List[MessageEnvelope]], bool]) -> Callable[[List[MessageEnvelope]], bool]:
        """Terminates if ANY predicate evaluates to True."""
        return lambda history: any(p(history) for p in predicates)


class SovereignAgent:
    """
    Single-threaded conversable actor agent.
    Processes incoming messages and produces outbound responses.
    """
    def __init__(self, name: str, role: str, handler: Optional[Callable[[MessageEnvelope], Optional[Dict[str, Any]]]] = None):
        self.name = name
        self.role = role
        self.handler = handler or (lambda env: {"content": f"Acknowledged by {self.name}"})

    def process_message(self, envelope: MessageEnvelope) -> Optional[MessageEnvelope]:
        try:
            res_payload = self.handler(envelope)
            if res_payload is None:
                return None
            return MessageEnvelope(
                message_id=f"msg_{uuid.uuid4().hex[:10]}",
                sender=self.name,
                recipient=envelope.sender,
                topic=envelope.topic,
                payload=res_payload,
                timestamp=time.time()
            )
        except Exception as e:
            _log_telemetry(e, f"SovereignAgent:{self.name}:process_message")
            return MessageEnvelope(
                message_id=f"msg_{uuid.uuid4().hex[:10]}",
                sender=self.name,
                recipient=envelope.sender,
                topic="error",
                payload={"error": str(e)},
                timestamp=time.time()
            )


class NativeActorRuntime:
    """
    Pillar 1: Single-Threaded Actor Runtime & FIFO Dispatcher.
    Distilled from AutoGen (autogen-core single threaded runtime).
    Executes in-memory message passing with typed envelopes, subscription tables,
    and synchronous step execution without distributed network daemons.
    """

    def __init__(self):
        self._handlers: Dict[str, List[Callable[[MessageEnvelope], Any]]] = {}
        self._agents: Dict[str, SovereignAgent] = {}
        self._queue: List[MessageEnvelope] = []
        self._history: List[MessageEnvelope] = []

    def register_agent(self, agent: SovereignAgent) -> None:
        """Registers a named actor agent."""
        self._agents[agent.name] = agent

    def subscribe(self, topic: str, handler: Callable[[MessageEnvelope], Any]) -> None:
        """Subscribes a callable handler to a message topic."""
        self._handlers.setdefault(topic, []).append(handler)

    def publish(self, env: MessageEnvelope) -> None:
        """Pushes a message envelope onto the FIFO queue."""
        self._queue.append(env)
        self._history.append(env)

    def step(self) -> Optional[MessageEnvelope]:
        """
        Executes a single FIFO dispatch step.
        Dispatches to registered topic handlers and named recipient agents.
        """
        if not self._queue:
            return None

        env = self._queue.pop(0)

        # 1. Topic subscriptions
        for handler in self._handlers.get(env.topic, []):
            try:
                handler(env)
            except Exception as e:
                _log_telemetry(e, f"NativeActorRuntime:topic_handler:{env.topic}")

        # 2. Named recipient dispatch
        if env.recipient in self._agents:
            agent = self._agents[env.recipient]
            reply = agent.process_message(env)
            if reply:
                self.publish(reply)

        return env

    def run_until_empty(self, max_steps: int = 100) -> int:
        """Drains the message queue up to max_steps."""
        steps = 0
        while self._queue and steps < max_steps:
            self.step()
            steps += 1
        return steps

    def get_history(self) -> List[MessageEnvelope]:
        """Returns chronological conversation history."""
        return list(self._history)


class TeamCoordinator:
    """
    Multi-Agent Group Chat & Cyclic Turn Coordinator.
    Coordinates sequential turn-taking between multiple SovereignAgents
    with configurable termination predicate gates.
    """

    def __init__(self, agents: List[SovereignAgent], termination: Optional[Callable[[List[MessageEnvelope]], bool]] = None):
        self.agents = agents
        self.runtime = NativeActorRuntime()
        for a in self.agents:
            self.runtime.register_agent(a)
        self.termination = termination or PredicateGate.compound_any(
            PredicateGate.max_turns(20),
            PredicateGate.text_mention("TASK_COMPLETE")
        )

    def run_conversation(self, initial_prompt: str, initiator: str = "user", topic: str = "task") -> List[MessageEnvelope]:
        """
        Runs round-robin group chat turn cycle until termination predicate fires.
        """
        if not self.agents:
            return []

        # Seed initial message to first agent
        first_recipient = self.agents[0].name
        seed_env = MessageEnvelope(
            message_id=f"msg_{uuid.uuid4().hex[:10]}",
            sender=initiator,
            recipient=first_recipient,
            topic=topic,
            payload={"content": initial_prompt}
        )
        self.runtime.publish(seed_env)

        agent_idx = 0
        while not self.termination(self.runtime.get_history()):
            # Step runtime to process current message
            stepped = self.runtime.step()
            if not stepped and not self.runtime._queue:
                # If queue is empty, route next turn to next agent in round-robin cycle
                curr_agent = self.agents[agent_idx % len(self.agents)]
                next_agent = self.agents[(agent_idx + 1) % len(self.agents)]
                agent_idx += 1

                # Generate turn handoff
                history = self.runtime.get_history()
                last_content = history[-1].payload.get("content", "") if history else initial_prompt
                handoff = MessageEnvelope(
                    message_id=f"msg_{uuid.uuid4().hex[:10]}",
                    sender=curr_agent.name,
                    recipient=next_agent.name,
                    topic=topic,
                    payload={"content": last_content}
                )
                self.runtime.publish(handoff)

            if len(self.runtime.get_history()) >= 100:
                break  # Hard circuit breaker

        return self.runtime.get_history()


def main():
    parser = argparse.ArgumentParser(description="Pillar 1: Sovereign Actor Delegation Runtime")
    parser.add_argument("--demo", action="store_true", help="Run multi-agent round-robin demo")
    parser.add_argument("--turns", type=int, default=4, help="Max turns for demo")
    args = parser.parse_args()

    if args.demo or len(sys.argv) == 1:
        agent_a = SovereignAgent("researcher", "investigator", lambda e: {"content": "Found 3 relevant files. Forwarding to builder."})
        agent_b = SovereignAgent("builder", "code_modifier", lambda e: {"content": "Patched implementation cleanly. TASK_COMPLETE."})

        coordinator = TeamCoordinator(
            agents=[agent_a, agent_b],
            termination=PredicateGate.compound_any(
                PredicateGate.max_turns(args.turns),
                PredicateGate.text_mention("TASK_COMPLETE")
            )
        )
        history = coordinator.run_conversation("Investigate and fix issue #42")
        print(f"[DELEGATION RUN COMPLETE] Total turns: {len(history)}")
        for idx, env in enumerate(history):
            content = env.payload.get("content", "")
            print(f"  {idx + 1}. [{env.sender} -> {env.recipient}] ({env.topic}): {content}")


if __name__ == "__main__":
    main()
