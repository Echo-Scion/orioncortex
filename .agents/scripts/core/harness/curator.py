"""
Skill Library Prefix-Cluster Curator & Umbrella Consolidator.
Pure Python 3 standard library implementation.
Detects narrow skill fragmentation and clusters near-duplicate skills under unified umbrella domains.
"""
import os
import re
from typing import Dict, Any, List, Set, Tuple
from dataclasses import dataclass, field


@dataclass
class ConsolidationProposal:
    cluster_prefix: str
    suggested_umbrella: str
    member_skills: List[str]
    descriptions: Dict[str, str]
    category: str = "general"
    rationale: str = ""


class ClusterCurator:
    """
    Analyzes registered skills and generates umbrella consolidation proposals.
    Prevents one-session-one-rule micro-rule fragmentation.
    """

    def __init__(self, skills_dir: str):
        self.skills_dir = skills_dir

    def scan_skills(self) -> Dict[str, Dict[str, Any]]:
        """
        Reads all skills in skills_dir and extracts metadata from SKILL.md.
        """
        skills = {}
        if not os.path.exists(self.skills_dir):
            return skills

        for entry in os.listdir(self.skills_dir):
            if entry.startswith(".") or entry == "archive" or entry == ".archive":
                continue
            skill_path = os.path.join(self.skills_dir, entry)
            if not os.path.isdir(skill_path):
                continue

            md_path = os.path.join(skill_path, "SKILL.md")
            desc = ""
            category = "general"
            if os.path.exists(md_path):
                try:
                    with open(md_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        # Extract frontmatter block
                        fm_match = re.search(r"\A---\r?\n(.*?)\r?\n---", content, re.DOTALL)
                        if fm_match:
                            fm_text = fm_match.group(1)
                            # Check multi-line description (>- or > or |)
                            m_desc_block = re.search(r"^description:\s*(?:>[-+]?|\|[-+]?)\s*\r?\n((?:[ \t]+[^\r\n]+(?:\r?\n|$))+)", fm_text, re.MULTILINE)
                            if m_desc_block:
                                lines = [l.strip() for l in m_desc_block.group(1).splitlines() if l.strip()]
                                desc = " ".join(lines)
                            else:
                                m_desc = re.search(r"^description:\s*([^\n\r]+)", fm_text, re.MULTILINE)
                                if m_desc:
                                    val = m_desc.group(1).strip().strip("\"'")
                                    if val not in (">-", ">", "|", "|-"):
                                        desc = val

                            m_cat = re.search(r"^category:\s*([^\n\r]+)", fm_text, re.MULTILINE)
                            if m_cat:
                                category = m_cat.group(1).strip().strip("\"'")
                except Exception:
                    pass

            skills[entry] = {
                "name": entry,
                "path": skill_path,
                "description": desc,
                "category": category
            }
        return skills

    def find_clusters(self, min_cluster_size: int = 2) -> List[ConsolidationProposal]:
        """
        Groups skills by common hyphenated prefix (e.g. 'flutter-auth', 'flutter-nav' -> 'flutter').
        """
        skills = self.scan_skills()
        prefix_groups: Dict[str, List[str]] = {}

        for name in skills:
            parts = name.split("-")
            if len(parts) >= 2:
                prefix = parts[0]
                if len(prefix) >= 3:  # Ignore trivial 1-2 char prefixes
                    prefix_groups.setdefault(prefix, []).append(name)

        proposals = []
        for prefix, members in sorted(prefix_groups.items()):
            if len(members) >= min_cluster_size:
                descs = {m: skills[m]["description"] for m in members}
                categories = [skills[m]["category"] for m in members if skills[m]["category"] != "general"]
                chosen_category = categories[0] if categories else prefix

                proposals.append(
                    ConsolidationProposal(
                        cluster_prefix=prefix,
                        suggested_umbrella=prefix,
                        member_skills=sorted(members),
                        descriptions=descs,
                        category=chosen_category,
                        rationale=f"Cluster has {len(members)} narrow skills sharing prefix '{prefix}-*'. Recommend absorbing into umbrella '{prefix}' with labeled subsections."
                    )
                )

        return proposals
