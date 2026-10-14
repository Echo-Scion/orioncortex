"""
Daemon-Free Opportunity-Relative Lifecycle Engine.
Pure Python 3 standard library implementation.
Evaluates skill survival based on usage rate relative to opportunities, with probation and capacity contention.
"""
import os
import shutil
import hashlib
from typing import List, Dict, Any, Set, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class SkillMember:
    name: str
    layer: str = "project"  # "project" or "global"
    anchor: int = 0         # Request count at creation
    use: int = 0            # Active invocations by the model
    view: int = 0           # Directory reads / search hits
    patch: int = 0          # Refinements / updates landed


@dataclass
class LifecycleResult:
    archived: List[str]
    retained: List[str]
    probation: List[str]
    rates: Dict[str, float]


class LifecycleManager:
    """
    Deterministic opportunity-relative lifecycle calculator and archiver.
    Decoupled from wall-clock time; resilient to offline/sleep periods.
    """

    @staticmethod
    def calculate_rate(use: int, denominator: int) -> float:
        return use / denominator if denominator > 0 else 0.0

    @classmethod
    def evaluate(
        cls,
        members: List[Dict[str, Any]],
        request_count: int,
        maturity: int = 100,
        capacity: int = 50,
        review_suspended: bool = False
    ) -> LifecycleResult:
        """
        Pure mathematical lifecycle evaluation without filesystem side-effects.
        """
        to_archive: Set[str] = set()
        in_probation: List[str] = []
        mature_survivors: List[Tuple[float, str]] = []
        rates: Dict[str, float] = {}

        for m in members:
            name = m.get("name", "")
            if not name:
                continue

            anchor = m.get("anchor", 0)
            use = m.get("use", m.get("calls", 0))
            view = m.get("view", 0)
            denom = max(0, request_count - anchor)

            rate = cls.calculate_rate(use, denom)
            rates[name] = round(rate, 4)

            # 1. Probation Gate: protect newly created skills
            if denom < maturity:
                in_probation.append(name)
                continue

            # 2. Graduation Review: dormancy check
            if use == 0:
                # If neither used NOR viewed, it has demonstrated zero recall or execution utility
                if not review_suspended and view == 0:
                    to_archive.add(name)
                continue

            # 3. Qualified graduate
            mature_survivors.append((rate, name))

        # 4. Capacity Contention: archive lowest usage rates if cap exceeded
        if len(mature_survivors) > capacity:
            # Sort ascending by rate, tie-break by deterministic SHA256 of name
            mature_survivors.sort(
                key=lambda item: (
                    item[0],
                    hashlib.sha256(item[1].encode("utf-8")).digest()
                )
            )
            excess_count = len(mature_survivors) - capacity
            for _, excess_name in mature_survivors[:excess_count]:
                to_archive.add(excess_name)

        retained = [
            m.get("name") for m in members 
            if m.get("name") and m.get("name") not in to_archive
        ]

        return LifecycleResult(
            archived=sorted(list(to_archive)),
            retained=sorted(retained),
            probation=sorted(in_probation),
            rates=rates
        )

    @classmethod
    def execute_archival(
        cls,
        skills_dir: str,
        skill_names: List[str],
        archive_subdir: str = ".archive"
    ) -> List[str]:
        """
        Executes physical directory movement to .archive/ without hard deletion.
        """
        archived_successfully = []
        archive_root = os.path.join(skills_dir, archive_subdir)
        os.makedirs(archive_root, exist_ok=True)

        for name in skill_names:
            src = os.path.join(skills_dir, name)
            dst = os.path.join(archive_root, name)

            if os.path.exists(src) and os.path.isdir(src):
                # If collision in archive, append monotonic counter
                final_dst = dst
                counter = 1
                while os.path.exists(final_dst):
                    final_dst = f"{dst}_{counter}"
                    counter += 1

                try:
                    os.replace(src, final_dst)
                    archived_successfully.append(name)
                except Exception:
                    try:
                        shutil.move(src, final_dst)
                        archived_successfully.append(name)
                    except Exception:
                        pass

        return archived_successfully
