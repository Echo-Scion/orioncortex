# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Native VerbalReflectiveLearner & Self-Evolution Engine for .agents
Pure Python 3 standard library implementation.
Absorbs VerbalReflectiveLearner (linguistic error reflection) and DeclarativePromptPipeline (rule enforcement compilation).
"""
import os
import sys
import json
import re
import uuid
import subprocess
import shlex
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple, Union

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
        _log_telemetry(_e, 'reflexion.py:reconfigure')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
WORKSPACE_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))
LEARNINGS_FILE = os.path.join(BASE_DIR, 'LEARNINGS.md')
MATRIX_DIR = os.path.join(WORKSPACE_DIR, '.orion', 'matrix')


class ReflexionEngine:
    """
    Linguistic Self-Reflection & Persistent Learning (VerbalReflectiveLearner pattern).
    Captures post-error reflections and converts them into durable invariants in LEARNINGS.md.
    """
    def __init__(self, learnings_path: str = LEARNINGS_FILE):
        self.learnings_path = learnings_path

    def record_learning(
        self,
        title: str,
        root_cause: str = "",
        fix_applied: str = "",
        self_evolve_rule: str = "",
        trigger: str = "",
        evidence: str = "",
        intervention: str = "",
        guard: str = "",
        resting_tier: str = "TIER-0"
    ) -> bool:
        date_str = datetime.now().strftime("%Y-%m-%d")
        tier_upper = resting_tier.upper()
        if not tier_upper.startswith("TIER-"):
            tier_upper = f"TIER-{tier_upper}"

        lines = [
            "",
            "---",
            "",
            f"## {date_str} — {title.strip()} [Lowest Viable Tier: {tier_upper}]",
            ""
        ]

        if trigger:
            lines.append(f"- **Trigger**: {trigger.strip()}")
        if evidence:
            lines.append(f"- **Evidence**: {evidence.strip()}")
        if intervention:
            lines.append(f"- **Intervention (Action Recipe)**: {intervention.strip()}")
        if guard:
            lines.append(f"- **Do-Not-Trigger Guard**: {guard.strip()}")
        if root_cause:
            lines.append(f"- **Root Cause**: {root_cause.strip()}")
        if fix_applied:
            lines.append(f"- **Fix Applied**: {fix_applied.strip()}")
        if self_evolve_rule:
            lines.append(f"- **Self-Evolve Invariant**: {self_evolve_rule.strip()}")
        lines.append("")

        entry = "\n".join(lines)
        try:
            with open(self.learnings_path, 'a', encoding='utf-8') as f:
                f.write(entry)
            return True
        except Exception as e:
            _log_telemetry(e, 'reflexion.py:record_learning')
            return False

    def list_learnings(self) -> List[Dict[str, str]]:
        if not os.path.exists(self.learnings_path):
            return []
        learnings = []
        try:
            with open(self.learnings_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            sections = re.split(r'\n---\n', content)
            for sec in sections:
                title_match = re.search(r'##\s*(\d{4}-\d{2}-\d{2})\s*—\s*([^\[\n]+)(?:\[Lowest Viable Tier:\s*([^\]]+)\])?', sec)
                if title_match:
                    date = title_match.group(1)
                    title = title_match.group(2).strip()
                    tier = title_match.group(3).strip() if title_match.group(3) else "TIER-0"

                    def _extract(field_name):
                        m = re.search(rf'\*\*{re.escape(field_name)}\*\*:\s*(.+?)(?=\n\s*-\s*\*\*|\n\n\*\*|$)', sec, re.DOTALL)
                        return m.group(1).strip() if m else ""

                    trigger = _extract("Trigger")
                    evidence = _extract("Evidence")
                    intervention = _extract("Intervention (Action Recipe)")
                    guard = _extract("Do-Not-Trigger Guard")
                    cause = _extract("Root Cause")
                    rule = _extract("Self-Evolve Invariant") or _extract("Self-Evolve Rule")

                    fix = _extract("Fix Applied")

                    learnings.append({
                        "date": date,
                        "title": title,
                        "tier": tier,
                        "trigger": trigger,
                        "evidence": evidence,
                        "intervention": intervention,
                        "guard": guard,
                        "root_cause": cause,
                        "fix_applied": fix,
                        "rule": rule
                    })
        except Exception as e:
            _log_telemetry(e, 'reflexion.py:list_learnings')
        return learnings

    def graduate_learning(self, title_query: str, skill_name: Optional[str] = None, intents_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Graduates a recurring failure learning from LEARNINGS.md into a Sovereign Harness skill intent.
        Converts the text bullet into a modular skill proposal (SKILL.md + references/remediation.md).
        """
        learnings = self.list_learnings()
        target = None
        for item in learnings:
            if title_query.lower() in item["title"].lower():
                target = item
                break

        if not target:
            return {"ok": False, "error": f"Learning with title containing '{title_query}' not found"}

        # Generate clean slug name if not provided
        if not skill_name:
            clean = re.sub(r"[^a-z0-9]+", "-", target["title"].lower()).strip("-")
            clean_slug = clean[:25].rstrip("-")
            skill_name = f"rule-{clean_slug}" if not clean_slug.startswith("rule-") else clean_slug

        # Ensure valid name pattern
        if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", skill_name):
            skill_name = "rule-" + re.sub(r"[^a-z0-9]+", "-", skill_name).strip("-")

        # Generate rule-altitude SKILL.md body
        rule_text = target.get("rule") or target.get("intervention") or target.get("root_cause") or "Execute remediation before commit."
        trigger_cue = target.get("trigger") or f"encountering {target['title']}"
        if not re.search(r"(?i)\bwhen\b|[\"'][^\"']+[\"']|`[^`]+`", trigger_cue):
            trigger_cue = f"Use when {trigger_cue}"

        body = (
            f"---\n"
            f"name: {skill_name}\n"
            f"description: {trigger_cue}\n"
            f"category: learning\n"
            f"---\n"
            f"# {target['title']}\n\n"
            f"## Invariant Rule\n"
            f"{rule_text}\n\n"
            f"See references/remediation.md for full root cause and evidence.\n"
        )

        remediation_content = (
            f"# Remediation Trace: {target['title']}\n\n"
            f"- **Date Recorded**: {target.get('date', '')}\n"
            f"- **Lowest Viable Tier**: {target.get('tier', 'TIER-0')}\n"
            f"- **Root Cause**: {target.get('root_cause', '')}\n"
            f"- **Fix Applied**: {target.get('fix_applied', '')}\n"
            f"- **Intervention**: {target.get('intervention', '')}\n"
            f"- **Guard**: {target.get('guard', '')}\n"
        )

        evidence_text = target.get("evidence") or target.get("root_cause") or "Observed recurring error trace in LEARNINGS.md"
        reason_text = f"Graduated recurring learning: {target['title']}"

        # Stage through Sovereign Harness IntentQueue
        from core.harness.staging import IntentQueue, StagedIntent
        target_intents_dir = intents_dir or os.path.join(WORKSPACE_DIR, '.orion', 'harness', 'intents')
        queue = IntentQueue(target_intents_dir)

        intent_id = str(uuid.uuid4())[:8]
        intent = StagedIntent(
            id=intent_id,
            action="create",
            name=skill_name,
            reason=reason_text,
            evidence=evidence_text,
            level="project",
            body=body,
            files={"references/remediation.md": remediation_content}
        )

        target_path = queue.enqueue(intent)

        # Mark in LEARNINGS.md
        try:
            with open(self.learnings_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if target['title'] in content and f"[Graduated to Skill: {skill_name}]" not in content:
                content = content.replace(
                    f"— {target['title']}",
                    f"— {target['title']} [Graduated to Skill: {skill_name}]"
                )
                with open(self.learnings_path, 'w', encoding='utf-8') as f:
                    f.write(content)
        except Exception as _e:
            _log_telemetry(_e, "reflexion.graduate_learning.mark")

        rel_path = os.path.relpath(target_path, WORKSPACE_DIR).replace(os.sep, '/')
        return {
            "ok": True,
            "intent_id": intent_id,
            "skill_name": skill_name,
            "staged_path": rel_path
        }

    def detect_and_graduate_recurring(self, intents_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        """Scans all learnings and graduates any that exhibit recurring patterns."""
        learnings = self.list_learnings()
        graduated = []
        seen_titles: Dict[str, int] = {}
        for l in learnings:
            t_clean = re.sub(r"\[Graduated.*\]", "", l["title"]).strip().lower()
            seen_titles[t_clean] = seen_titles.get(t_clean, 0) + 1

        for t_clean, count in seen_titles.items():
            if count >= 2:
                res = self.graduate_learning(t_clean, intents_dir=intents_dir)
                if res.get("ok"):
                    graduated.append(res)
        return graduated


class PromptRuleCompiler:
    """
    Declarative Rule & Enforcement Compiler (DeclarativePromptPipeline pattern).
    Audits active rule matrices and verifies executable enforcement gates (Anti-Graveyard Gate).
    """
    def __init__(self, matrix_dir: str = MATRIX_DIR, scripts_dir: str = os.path.join(BASE_DIR, 'scripts')):
        self.matrix_dir = matrix_dir
        self.scripts_dir = scripts_dir

    def audit_rule_enforcement(self) -> Dict[str, Any]:
        """
        Scans rule matrices and checks whether each rule has an executable enforcement check
        in security.py, verify_agents.py, or adversarial.py.
        """
        # Load compiled rule matrices
        rules: List[Dict[str, Any]] = []
        if os.path.exists(self.matrix_dir):
            for fname in os.listdir(self.matrix_dir):
                if fname.endswith('.json'):
                    fp = os.path.join(self.matrix_dir, fname)
                    try:
                        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                            data = json.load(f)
                            if isinstance(data, dict):
                                for k, v in data.items():
                                    if k == "global":
                                        continue
                                    rules.append({
                                        "source_matrix": fname,
                                        "id": k,
                                        "description": str(v)[:120] if v else ""
                                    })
                    except Exception as e:
                        _log_telemetry(e, 'reflexion.py:audit_rules:load')

        # Load scripts source code to detect AST/mechanical patterns
        script_sources = ""
        for root, _, files in os.walk(self.scripts_dir):
            for f in files:
                if f.endswith('.py'):
                    try:
                        with open(os.path.join(root, f), 'r', encoding='utf-8', errors='ignore') as fp:
                            script_sources += fp.read() + "\n"
                    except Exception as e:
                        _log_telemetry(e, 'reflexion.py:read_scripts')

        enforced = []
        advisory_only = []

        for r in rules:
            rid = str(r['id']).lower()
            clean_words = [w for w in re.findall(r'[a-zA-Z]{4,}', rid) if w not in ('extends', 'rules', 'protocol', 'section', 'standard')]
            is_enforced = any(w in script_sources.lower() for w in clean_words) if clean_words else False
            if is_enforced:
                enforced.append(r)
            else:
                advisory_only.append(r)

        total = len(rules)
        coverage_pct = (len(enforced) / total * 100.0) if total > 0 else 100.0

        return {
            "total_rules": total,
            "enforced_count": len(enforced),
            "advisory_count": len(advisory_only),
            "mechanical_coverage_pct": round(coverage_pct, 1),
            "enforced_sample": enforced[:5],
            "advisory_sample": advisory_only[:5]
        }


@dataclass(slots=True)
class TrialAttempt:
    """Represents a single trial within an epistemic reflection loop."""
    trial_number: int
    solution: str
    error_output: str
    reflection: str


class ReflexionLoop:
    """
    In-session verbal reinforcement learning & epistemic trial coordinator.
    Distilled from Reflexion.
    Coordinates Actor-Evaluator-Reflector triad, captures error stack traces,
    synthesizes verbal critique, and halts at 3-trial circuit breaker.
    """
    def __init__(self, max_trials: int = 3):
        self.max_trials = max_trials
        self.history: List[TrialAttempt] = []

    def record_attempt(self, solution: str, error_output: str, reflection: str) -> TrialAttempt:
        trial_num = len(self.history) + 1
        attempt = TrialAttempt(
            trial_number=trial_num,
            solution=solution,
            error_output=error_output,
            reflection=reflection
        )
        self.history.append(attempt)
        return attempt

    def is_circuit_broken(self) -> bool:
        """Returns True if trial attempts reach or exceed max_trials."""
        return len(self.history) >= self.max_trials

    def run_evaluator(self, test_cmd: Union[str, List[str]], timeout: float = 30.0) -> Tuple[int, str]:
        """Executes mechanical verification command safely without shell=True."""
        try:
            if isinstance(test_cmd, list):
                cmd = test_cmd
            else:
                cmd = shlex.split(test_cmd)

            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout
            )
            combined = f"{res.stdout}\n{res.stderr}".strip() if res.stdout and res.stderr else (res.stdout or res.stderr or "").strip()
            return res.returncode, combined
        except subprocess.TimeoutExpired:
            return 124, f"TimeoutExpired: Evaluator exceeded {timeout}s"
        except Exception as e:
            _log_telemetry(e, f"ReflexionLoop:run_evaluator:{test_cmd}")
            return 1, str(e)

    def synthesize_critique(self, error_output: str) -> str:
        """Deterministic verbal critique extraction when LLM is offline or in pure-heuristic mode."""
        lower = error_output.lower()
        if "syntaxerror" in lower or "indentationerror" in lower:
            return "Syntax/Formatting Violation: Code fails AST parse. Ensure balanced delimiters and proper indentation."
        elif "assertionerror" in lower or "assert" in lower:
            return "Assertion Boundary Failure: The output did not match expected contract invariants. Inspect state deltas."
        elif "timeout" in lower:
            return "Resource/Complexity Exhaustion: Execution hung or timed out. Check for infinite loops or blocking I/O."
        elif "nameerror" in lower or "attributeerror" in lower:
            return "Symbol Resolution Failure: Unbound variable or missing attribute. Verify import paths and member definitions."
        return "Runtime Exception: Unhandled error in implementation. Review stack trace."

    def build_reflection_prompt(self, problem: str) -> str:
        """Constructs context prompt prepending previous failed trials and verbal reflections."""
        prompt = [f"Task Objective: {problem}\n"]
        for t in self.history:
            prompt.append(f"--- Trial {t.trial_number} Failed ---")
            prompt.append(f"Error Diagnostic:\n{t.error_output}")
            prompt.append(f"Verbal Self-Reflection:\n{t.reflection}\n")
        prompt.append("Instruction: Provide a corrected implementation resolving the flaws diagnosed above.")
        return "\n".join(prompt)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="VerbalReflectiveLearner & Self-Evolution Engine")
    subparsers = parser.add_subparsers(dest="command")

    # Record reflection
    rec_parser = subparsers.add_parser("record", help="Record a failure reflection in LEARNINGS.md")
    rec_parser.add_argument("--title", required=True, help="Title of the learning")
    rec_parser.add_argument("--trigger", default="", help="Harness-Zero recognizable trigger condition")
    rec_parser.add_argument("--evidence", default="", help="Harness-Zero concrete trajectory evidence")
    rec_parser.add_argument("--intervention", default="", help="Harness-Zero action recipe / intervention")
    rec_parser.add_argument("--guard", default="", help="Harness-Zero do-not-trigger boundary")
    rec_parser.add_argument("--tier", default="tier-0", choices=["tier-0", "tier-1", "tier-2", "tier-3"], help="Lowest Viable Tier")
    rec_parser.add_argument("--cause", default="", help="Root cause of the failure")
    rec_parser.add_argument("--fix", default="", help="Fix applied")
    rec_parser.add_argument("--rule", default="", help="Self-evolve invariant rule")

    # List reflections
    subparsers.add_parser("list", help="List all recorded self-evolution learnings")

    # Audit rules
    audit_parser = subparsers.add_parser("audit", help="Audit rule enforcement coverage")
    audit_parser.add_argument("--json", action="store_true", help="JSON output")

    # Trial loop reflect
    reflect_parser = subparsers.add_parser("reflect", help="Run verbal reflection evaluation loop")
    reflect_parser.add_argument("--test", required=True, help="Test command to run")
    reflect_parser.add_argument("--max-trials", type=int, default=3, help="Max trials before circuit breaking")

    # Graduate recurring learning to harness
    grad_parser = subparsers.add_parser("graduate", help="Graduate a learning from LEARNINGS.md into a staged harness skill")
    grad_parser.add_argument("--title", required=True, help="Substring of learning title to graduate")
    grad_parser.add_argument("--name", default="", help="Optional explicit skill name slug")
    grad_parser.add_argument("--json", action="store_true", help="JSON output")

    # Detect recurring learnings and auto-graduate
    recur_parser = subparsers.add_parser("detect-recurring", help="Scan learnings for recurring failures and auto-graduate to harness")
    recur_parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()

    engine = ReflexionEngine()

    if args.command == "record":
        ok = engine.record_learning(
            title=args.title,
            root_cause=args.cause,
            fix_applied=args.fix,
            self_evolve_rule=args.rule,
            trigger=args.trigger,
            evidence=args.evidence,
            intervention=args.intervention,
            guard=args.guard,
            resting_tier=args.tier
        )
        if ok:
            print(f"[REFLECTIVE_LEARNER] Learning recorded in {LEARNINGS_FILE}: '{args.title}' [Lowest Viable Tier: {args.tier.upper()}]")
        else:
            print("[ERROR] Failed to record learning.")
            sys.exit(1)

    elif args.command == "list":
        items = engine.list_learnings()
        print(f"\n🧠 Systemic Learnings Log ({len(items)} entries)")
        print("=" * 60)
        for idx, item in enumerate(items, 1):
            print(f"[{idx:02d}] {item['date']} — {item['title']}")
            print(f"     Cause: {item['root_cause'][:100]}")
            print(f"     Rule : {item['rule'][:100]}\n")

    elif args.command == "audit":
        compiler = PromptRuleCompiler()
        report = compiler.audit_rule_enforcement()
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"\n⚖️ Declarative Rule Enforcement Audit (DeclarativePromptPipeline Anti-Graveyard Gate)")
            print("=" * 60)
            print(f"Total Rules Indexed  : {report['total_rules']}")
            print(f"Mechanically Enforced: {report['enforced_count']} ({report['mechanical_coverage_pct']}%)")
            print(f"Advisory Only        : {report['advisory_count']}")
            print(f"Status               : {'PASS' if report['mechanical_coverage_pct'] >= 40.0 else 'WARN'}\n")

    elif args.command == "reflect":
        loop = ReflexionLoop(max_trials=args.max_trials)
        code, output = loop.run_evaluator(args.test)
        if code == 0:
            print(f"[EVALUATOR_PASS] Command passed on initial trial (Exit Code 0).")
        else:
            critique = loop.synthesize_critique(output)
            loop.record_attempt(solution=args.test, error_output=output, reflection=critique)
            print(f"[EVALUATOR_FAIL] Trial 1 failed (Exit Code {code}).")
            print(f"Critique: {critique}")

    elif args.command == "graduate":
        res = engine.graduate_learning(
            title_query=args.title,
            skill_name=args.name if args.name else None
        )
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res.get("ok"):
                print(f"[GRADUATION_OK] Graduated '{args.title}' -> staged skill '{res['skill_name']}'")
                print(f"                Intent ID  : {res['intent_id']}")
                print(f"                Staged Path: {res['staged_path']}")
            else:
                print(f"[GRADUATION_ERROR] {res.get('error', 'Unknown error')}")
                sys.exit(1)

    elif args.command == "detect-recurring":
        res = engine.detect_and_graduate_recurring()
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"[RECURRING_SCAN] Found {len(res)} recurring learnings graduated:")
            for item in res:
                print(f"  - Graduated to '{item['skill_name']}' (Intent: {item['intent_id']})")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
