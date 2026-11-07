#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Observation Ledger & Signal Capture System.
Pure Python 3 standard library implementation.
Lives in core (Tier 3) to prevent architectural circular dependencies from core/db.py.
"""
import os
import sys
import re
import json
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional

_CORE_DIR = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR = os.path.dirname(_CORE_DIR)
_BASE_DIR = os.path.dirname(_SCRIPTS_DIR) # .agents
_WORKSPACE_DIR = os.path.dirname(_BASE_DIR)

OBSERVATIONS_FILE = os.path.join(_BASE_DIR, 'OBSERVATIONS.md')
OBSERVATIONS_ARCHIVE_FILE = os.path.join(_BASE_DIR, 'OBSERVATIONS.archive.md')

try:
    from core.db import log_telemetry as _log_telemetry, atomic_write_text
except ImportError:
    def _log_telemetry(err: Optional[Exception] = None, context: str = "") -> None:
        if os.environ.get("ORION_DEBUG"):
            msg = f": {err}" if err else ""
            sys.stderr.write(f"[ORION_TELEMETRY] Non-fatal catch in {context}{msg}\n")
    def atomic_write_text(filepath: str, content: str) -> None:
        import uuid
        abs_path = os.path.abspath(str(filepath))
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        temp_file = f"{abs_path}.tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}"
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(temp_file, abs_path)
        finally:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass


class ObservationLedger:
    """
    Observation Ledger & Signal Capture System.
    Manages raw observations in .agents/OBSERVATIONS.md and .agents/OBSERVATIONS.archive.md.
    """
    def __init__(self, active_path: str = None, archive_path: str = None, ledger_path: str = None):
        self.active_path = active_path or ledger_path or OBSERVATIONS_FILE
        self.archive_path = archive_path or OBSERVATIONS_ARCHIVE_FILE
        self._ensure_files_exist()

    def _ensure_files_exist(self):
        if not os.path.exists(self.active_path):
            header = (
                "# Observation Ledger (Active & Parked Signals)\n\n"
                "> Raw signals: corrections, tool failures, mechanical catches, verify fails, rule violations.\n\n"
            )
            atomic_write_text(self.active_path, header)
        if not os.path.exists(self.archive_path):
            header = (
                "# Observation Ledger Archive (Resolved Signals)\n\n"
                "> Resolved, declined, or superseded observations.\n\n"
            )
            atomic_write_text(self.archive_path, header)

    def _parse_file(self, filepath: str) -> List[Dict[str, Any]]:
        if not os.path.exists(filepath):
            return []
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        entries = []
        blocks = re.split(r"(?m)^(?=##\s+Observation\s+)", content)
        for block in blocks:
            if not block.strip().startswith("## Observation "):
                continue
            lines = block.strip().splitlines()
            title_line = lines[0]
            m_title = re.match(r"##\s+Observation\s+#?(\d+):\s*(.+)", title_line)
            if not m_title:
                continue
            obs_id = int(m_title.group(1))
            title = m_title.group(2).strip()

            entry = {
                "id": obs_id,
                "anchor_id": f"O{obs_id}",
                "title": title,
                "fingerprint": "",
                "status": "open",
                "kind": "improve",
                "target": "",
                "rule_id": "",
                "siblings_checked": "true",
                "scope": "project",
                "parked_until": "",
                "evidence": "",
                "created": "",
                "resolved": "",
                "resolution": "",
                "superseded_by": "",
                "count": 1,
                "seen_in": "",
                "applies_to": ""
            }

            for line in lines[1:]:
                m_kv = re.match(r"^\s*-\s*\*\*([a-zA-Z0-9_]+)\*\*\s*:\s*(.*)$", line)
                if m_kv:
                    k = m_kv.group(1).lower()
                    v = m_kv.group(2).strip()
                    if k == "id":
                        try:
                            entry["id"] = int(v)
                        except ValueError:
                            pass
                    elif k == "count":
                        try:
                            entry["count"] = int(v)
                        except ValueError:
                            entry["count"] = 1
                    elif k in entry:
                        entry[k] = v

            entries.append(entry)
        return entries

    def get_all_observations(self) -> List[Dict[str, Any]]:
        return self._parse_file(self.active_path)

    def get_archive_observations(self) -> List[Dict[str, Any]]:
        return self._parse_file(self.archive_path)

    def get_next_id(self) -> int:
        active = self.get_all_observations()
        arch = self.get_archive_observations()
        max_id = 0
        for item in active + arch:
            if item["id"] > max_id:
                max_id = item["id"]
        return max_id + 1

    def compute_fingerprint(self, kind: str, target_or_rule: str, title: str) -> str:
        raw = f"{kind.strip().lower()}:{target_or_rule.strip().lower()}:{title.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]

    def add_observation(
        self,
        title: str,
        kind: str = "improve",
        target: str = "",
        rule_id: str = "",
        scope: str = "project",
        evidence: str = "",
        status: str = "open",
        parked_until: str = "",
        siblings_checked: str = "true",
        count: int = 1,
        seen_in: str = "",
        applies_to: str = ""
    ) -> Dict[str, Any]:
        if status == "parked" and not parked_until.strip():
            raise ValueError("Observations with status 'parked' require a valid 'parked_until' date (YYYY-MM-DD)")

        is_subagent = (
            os.environ.get("ANTIGRAVITY_SUBAGENT") == "1" or
            os.environ.get("SUBAGENT") == "1" or
            os.environ.get("WORKER_DELEGATE") == "1"
        )
        if is_subagent:
            return {
                "id": -1,
                "fingerprint": "subagent_refused",
                "title": title,
                "status": "refused_subagent",
                "kind": kind,
                "target": target,
                "rule_id": rule_id,
                "siblings_checked": siblings_checked,
                "scope": scope,
                "parked_until": parked_until,
                "evidence": evidence,
                "created": "",
                "resolved": "",
                "resolution": "subagents write nothing",
                "count": count,
                "seen_in": seen_in,
                "applies_to": applies_to
            }

        ws_dir = os.path.abspath(_WORKSPACE_DIR)
        if target and os.path.isabs(target):
            norm_target = os.path.abspath(target)
            if norm_target.startswith(ws_dir):
                target = os.path.relpath(norm_target, ws_dir).replace("\\", "/")

        if evidence:
            if ws_dir in evidence:
                evidence = evidence.replace(ws_dir, ".").replace(ws_dir.replace("\\", "/"), ".")
            if "file://" in evidence:
                evidence = re.sub(r"file://[^\s)]+", lambda m: m.group(0).replace("file://", ""), evidence)

        target_or_rule = rule_id if rule_id else target
        fp = self.compute_fingerprint(kind, target_or_rule, title)

        # Negative Memory Barrier: Check if this fingerprint was previously declined in archive
        arch = self.get_archive_observations()
        for arch_item in arch:
            if arch_item.get("fingerprint") == fp and arch_item.get("status") == "declined":
                arch_item_copy = dict(arch_item)
                arch_item_copy["status"] = "blocked_declined_fingerprint"
                arch_item_copy["resolution"] = f"Blocked re-observation: previously declined in archive as #{arch_item.get('id')}"
                return arch_item_copy

        active = self.get_all_observations()
        for item in active:
            if item.get("fingerprint") == fp and item.get("status") in ("open", "parked"):
                if evidence:
                    existing_ev_parts = [p.strip() for p in item.get("evidence", "").split(" | ") if p.strip()]
                    if evidence.strip() not in existing_ev_parts:
                        existing_ev_parts.append(evidence.strip())
                    item["evidence"] = " | ".join(existing_ev_parts)
                item["count"] = int(item.get("count", 1)) + 1
                if seen_in and seen_in not in item.get("seen_in", ""):
                    item["seen_in"] = (item.get("seen_in", "") + ", " + seen_in).strip(", ")
                if applies_to and applies_to not in item.get("applies_to", ""):
                    item["applies_to"] = (item.get("applies_to", "") + ", " + applies_to).strip(", ")
                self._write_active_list(active)
                return item

        obs_id = self.get_next_id()
        now_str = datetime.now().isoformat()

        entry = {
            "id": obs_id,
            "fingerprint": fp,
            "title": title.strip(),
            "status": status.strip(),
            "kind": kind.strip(),
            "target": target.strip(),
            "rule_id": rule_id.strip(),
            "siblings_checked": siblings_checked.strip() or "true",
            "scope": scope.strip() or "project",
            "parked_until": parked_until.strip(),
            "evidence": evidence.strip(),
            "created": now_str,
            "resolved": "",
            "resolution": "",
            "count": count,
            "seen_in": seen_in.strip(),
            "applies_to": applies_to.strip()
        }

        if status.strip() in ("actioned", "resolved", "declined"):
            entry["resolved"] = now_str
            entry["resolution"] = "Added directly with resolved status"
            self._append_to_archive(entry)
            return entry

        active.append(entry)
        self._write_active_list(active)
        return entry

    def _format_entry(self, entry: Dict[str, Any]) -> str:
        lines = [
            f"## Observation {entry['id']}: {entry['title']}",
            f"- **id**: {entry['id']}",
            f"- **fingerprint**: {entry['fingerprint']}",
            f"- **status**: {entry['status']}",
            f"- **kind**: {entry['kind']}",
            f"- **target**: {entry['target']}",
            f"- **rule_id**: {entry['rule_id']}",
            f"- **siblings_checked**: {entry['siblings_checked']}",
            f"- **scope**: {entry['scope']}",
        ]
        if entry.get("count") and int(entry.get("count", 1)) > 1:
            lines.append(f"- **count**: {entry['count']}")
        if entry.get("seen_in"):
            lines.append(f"- **seen_in**: {entry['seen_in']}")
        if entry.get("applies_to"):
            lines.append(f"- **applies_to**: {entry['applies_to']}")
        if entry.get("parked_until"):
            lines.append(f"- **parked_until**: {entry['parked_until']}")
        if entry.get("evidence"):
            lines.append(f"- **evidence**: {entry['evidence']}")
        if entry.get("created"):
            lines.append(f"- **created**: {entry['created']}")
        if entry.get("resolved"):
            lines.append(f"- **resolved**: {entry['resolved']}")
        if entry.get("resolution"):
            lines.append(f"- **resolution**: {entry['resolution']}")
        if entry.get("superseded_by"):
            lines.append(f"- **superseded_by**: {entry['superseded_by']}")
        lines.append("")
        return "\n".join(lines)

    def _write_active_list(self, entries: List[Dict[str, Any]]):
        header = (
            "# Observation Ledger (Active & Parked Signals)\n\n"
            "> Raw signals: corrections, tool failures, mechanical catches, verify fails, rule violations.\n\n"
        )
        content = header + "\n".join(self._format_entry(e) for e in entries)
        atomic_write_text(self.active_path, content)

    def _write_archive_list(self, entries: List[Dict[str, Any]]):
        header = (
            "# Observation Ledger Archive (Resolved Signals)\n\n"
            "> Resolved, declined, or superseded observations.\n\n"
        )
        content = header + "\n".join(self._format_entry(e) for e in entries)
        atomic_write_text(self.archive_path, content)

    def _append_to_archive(self, entry: Dict[str, Any]) -> None:
        arch = self.get_archive_observations()
        arch.append(entry)
        self._write_archive_list(arch)

    def list_observations(self, status: str = None, limit: int = None) -> List[Dict[str, Any]]:
        active = self.get_all_observations()
        if status:
            active = [e for e in active if e.get("status") == status]
        if limit and limit > 0:
            active = active[:limit]
        return active

    def check_rule_violations(self, rule_id: str) -> Dict[str, Any]:
        if not rule_id:
            return {"rule_id": "", "count": 0, "forced_tier0": False, "observations": []}
        active = self.get_all_observations()
        arch = self.get_archive_observations()
        matching_active = [e for e in active if e.get("rule_id") == rule_id and e.get("status") in ("open", "parked")]
        matching_rolled = [e for e in arch if e.get("rule_id") == rule_id and e.get("kind") == "violation" and e.get("status") == "superseded"]
        all_matching = matching_active + matching_rolled
        count = sum(int(e.get("count", 1)) for e in all_matching)
        forced_tier0 = count >= 2
        return {
            "rule_id": rule_id,
            "count": count,
            "forced_tier0": forced_tier0,
            "observations": all_matching
        }

    def get_digest(self) -> str:
        active = self.get_all_observations()

        if os.path.exists(self.active_path):
            with open(self.active_path, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
            if "## Observation " in raw and len(active) == 0:
                return "OBSERVATION SCAN BROKEN"

        open_count = sum(1 for e in active if e.get("status") == "open")
        parked_count = sum(1 for e in active if e.get("status") == "parked")
        targets = [e.get("target") or e.get("rule_id") for e in active if e.get("target") or e.get("rule_id")]
        top_target = targets[0] if targets else "none"

        head_gen_label = "none"
        try:
            from core.memory import RecallMemoryManager
            with RecallMemoryManager() as rm:
                head = rm.get_head_generation()
                if head:
                    head_gen_label = f"G{head.get('generation_count', 0)}"
        except Exception:
            pass

        return f"gen={head_gen_label} open={open_count} parked={parked_count} top-target={top_target}"
