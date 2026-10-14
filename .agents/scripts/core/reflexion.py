# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Native Reflexion & Self-Evolution Engine for .agents
Pure Python 3 standard library implementation.
Absorbs NoahShinn/Reflexion (linguistic error reflection) and StanfordNLP/DSPy (rule enforcement compilation).
"""
import os
import sys
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

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
    Linguistic Self-Reflection & Persistent Learning (Reflexion pattern).
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

                    learnings.append({
                        "date": date,
                        "title": title,
                        "tier": tier,
                        "trigger": trigger,
                        "evidence": evidence,
                        "intervention": intervention,
                        "guard": guard,
                        "root_cause": cause,
                        "rule": rule
                    })
        except Exception as e:
            _log_telemetry(e, 'reflexion.py:list_learnings')
        return learnings


class PromptRuleCompiler:
    """
    Declarative Rule & Enforcement Compiler (DSPy pattern).
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


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Reflexion & Self-Evolution Engine (Reflexion + DSPy pattern)")
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
    audit_parser = subparsers.add_parser("audit", help="Audit rule enforcement coverage (DSPy pattern)")
    audit_parser.add_argument("--json", action="store_true", help="JSON output")

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
            print(f"[REFLEXION] Learning recorded in {LEARNINGS_FILE}: '{args.title}' [Lowest Viable Tier: {args.tier.upper()}]")
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
            print(f"\n⚖️ Declarative Rule Enforcement Audit (DSPy Anti-Graveyard Gate)")
            print("=" * 60)
            print(f"Total Rules Indexed  : {report['total_rules']}")
            print(f"Mechanically Enforced: {report['enforced_count']} ({report['mechanical_coverage_pct']}%)")
            print(f"Advisory Only        : {report['advisory_count']}")
            print(f"Status               : {'PASS' if report['mechanical_coverage_pct'] >= 40.0 else 'WARN'}\n")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
