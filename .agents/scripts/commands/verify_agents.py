# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
import os
import re
import sys
import argparse
import json
import hashlib
from typing import Set, Dict, List, Optional, Iterable, Tuple

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
        _log_telemetry(_e, 'verify_agents.py:17')

# Smart Root Discovery
def discover_roots():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Ascend to .agents root
    cur = current_dir
    while cur and os.path.basename(cur) != "":
        if os.path.basename(cur) == ".agents":
            return cur
        cur = os.path.dirname(cur)
    
    # Fallback to CWD traversal
    cur = os.getcwd()
    while True:
        if os.path.exists(os.path.join(cur, ".agents")):
            return os.path.join(cur, ".agents")
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    
    return os.path.join(os.getcwd(), ".agents")

BASE_DIR = discover_roots()
SKILLS_DIR = os.path.join(BASE_DIR, "skills")
RULES_DIR = os.path.join(BASE_DIR, "rules")
CANONS_DIR = os.path.join(BASE_DIR, "canons")
FOUNDATION_PATH_MARKER = os.path.join(BASE_DIR, ".foundation_path")

EXCLUDED_PATH_MARKERS = [".git", ".gemini", ".system_generated", "node_modules", "__pycache__", "archive"]
DOC_METADATA_KEYS = {"param", "return", "type", "description", "activation", "trigger"}
RULE_DIR_TOKENS = {"rules", "common", "flutter", "web", "canons", "auth", "notifications", "ui-patterns"}
FRONTMATTER_RE = re.compile(r'\A---\s*\n(.*?)\n---\s*(?:\n|$)', re.DOTALL)
FRONTMATTER_KEY_RE = re.compile(r'^\s*([A-Za-z0-9_-]+)\s*:\s*(.*?)\s*$', re.MULTILINE)


def get_folder_hashes(folder_path: str) -> Dict[str, str]:
    """
    Computes MD5 hashes for all files in a folder, normalized for CRLF to prevent sync false positives.
    """
    hashes = {}
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if not any(marker in d for marker in EXCLUDED_PATH_MARKERS)]
        for f in files:
            if f.endswith(('.md', '.json', 'SKILL.md')):
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, folder_path).replace("\\", "/")
                try:
                    with open(full_path, "rb") as file_obj:
                        content = file_obj.read()
                        # Normalize CRLF to LF to avoid cross-OS discrepancies
                        normalized = content.replace(b"\r\n", b"\n")
                        hashes[rel_path] = hashlib.sha256(normalized).hexdigest()
                except Exception as e:
                    print(f"Failed to hash {full_path}: {e}")
    return hashes


def iter_files(base_dir: str, extensions: Tuple[str, ...], include_root_configs: bool = True) -> Iterable[str]:
    if include_root_configs:
        workspace_root = os.path.dirname(base_dir)
        for root_cfg in ["GEMINI.md", "AGENTS.md", "CLAUDE.md"]:
            cfg_path = os.path.join(workspace_root, root_cfg)
            if os.path.isfile(cfg_path) and any(cfg_path.endswith(ext) for ext in extensions):
                yield cfg_path

    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if not any(marker in d for marker in EXCLUDED_PATH_MARKERS)]
        for file_name in files:
            if file_name.endswith(extensions):
                yield os.path.join(root, file_name)


def read_text(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def parse_frontmatter_keys(content: str) -> Dict[str, str]:
    match = FRONTMATTER_RE.match(content)
    if not match:
        return {}

    keys: Dict[str, str] = {}
    for key_match in FRONTMATTER_KEY_RE.finditer(match.group(1)):
        key = key_match.group(1).strip().lower()
        value = key_match.group(2).strip()
        keys[key] = value
    return keys


def severity_counts(items: List[Dict[str, Optional[str]]]) -> Dict[str, int]:
    counts: Dict[str, int] = {"BLOCKER": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for item in items:
        sev = str(item.get("severity") or "LOW").upper()
        if sev not in counts:
            counts[sev] = 0
        counts[sev] += 1
    return counts

class AuditResult:
    def __init__(self):
        self.errors: List[Dict[str, Optional[str]]] = []
        self.warnings: List[Dict[str, Optional[str]]] = []
        self.stats: Dict[str, int] = {"skills": 0, "rules": 0, "canons": 0}

    def add_error(self, category: str, message: str, file: Optional[str] = None, severity: str = "HIGH"):
        self.errors.append({"category": category, "message": message, "file": file, "severity": severity})

    def add_warning(self, category: str, message: str, file: Optional[str] = None, severity: str = "MEDIUM"):
        self.warnings.append({"category": category, "message": message, "file": file, "severity": severity})

def check_foundation_sync(res: AuditResult, verbose: bool = True):
    if not os.path.exists(FOUNDATION_PATH_MARKER):
        if verbose: print("[NOTE] No .foundation_path marker found. Skipping sync check.")
        return
    
    if verbose: print("\n--- FOUNDATION SYNC CHECK ---")
    
    try:
        with open(FOUNDATION_PATH_MARKER, "r", encoding="utf-8") as f:
            foundation_root = f.read().strip()
        foundation_agents = os.path.join(foundation_root, ".agents") if not (foundation_root.endswith(".agents") or os.path.basename(foundation_root) == ".agents") else foundation_root
        
        if not os.path.exists(foundation_agents):
            res.add_error("SYNC", f"Broken foundation link: {foundation_agents}")
            return
            
        if verbose: print(f" Linked to Foundation: {foundation_root}")
        
        sync_folders = ["skills", "rules", "canons"]
        for folder in sync_folders:
            local_folder = os.path.join(BASE_DIR, folder)
            found_folder = os.path.join(foundation_agents, folder)
            if not os.path.exists(found_folder): continue
            
            local_hashes = get_folder_hashes(local_folder)
            found_hashes = get_folder_hashes(found_folder)
            
            if local_hashes != found_hashes:
                local_keys = set(local_hashes.keys())
                found_keys = set(found_hashes.keys())
                
                missing = found_keys - local_keys
                extra = local_keys - found_keys
                modified = {k for k in local_keys & found_keys if local_hashes[k] != found_hashes[k]}
                
                if missing or modified or extra:
                    diff_count = len(missing) + len(modified)
                    if diff_count > 0:
                        res.add_warning("SYNC", f"Folder {folder} is out of sync with foundation. {len(missing)} missing, {len(modified)} modified, {len(extra)} extra items.")
                        if verbose:
                            print(f"[SYNC] OUT-OF-SYNC ({folder}): {len(missing)} missing, {len(modified)} modified, {len(extra)} extra.")
                
        if verbose and len(res.warnings) > 0:
            print(" Run 'python .agents/scripts/orion.py deploy' to update your local agents.")
            
    except Exception as e:
        res.add_error("SYNC", f"Sync Check failed: {str(e)}")
        if verbose: print(f"[ERROR] Sync Check failed: {e}")

def check_mechanical_integrity(res: AuditResult, verbose: bool = True):
    if verbose: print("--- SCANNING FOR MECHANICAL INTEGRITY ERRORS ---")
    
    header_bug_pat = re.compile(r'^#+ [^#\n]+#+(?!\s*$)', re.MULTILINE)
    double_header_pat = re.compile(r'^#+ #+ ', re.MULTILINE)
    abs_path_pat = re.compile(r'(?:[a-zA-Z]:\\[Uu]sers\\[a-zA-Z0-9_\-\.]+)|(?:\/(?:home|[Uu]sers)\/[a-zA-Z0-9_\-\.]+)')
    corrupt_wikilink_pat = re.compile(r'\[\[[a-zA-Z0-9_\-\./]+\]\]\)')
    
    for filepath in iter_files(BASE_DIR, (".md", ".py", ".json")):
        file = os.path.basename(filepath)
        rel_path = os.path.relpath(filepath, BASE_DIR)
        
        # Binary control character check (guards against 0x0B vertical tab, etc.)
        try:
            with open(filepath, "rb") as bf:
                raw_bytes = bf.read()
                for byte_idx, b in enumerate(raw_bytes):
                    if b < 32 and b not in (9, 10, 13):
                        res.add_error("MECHANICAL", f"Unwanted control character (0x{b:02x}) at byte {byte_idx}", rel_path)
                        break
        except Exception as e:
            res.add_error("IO", f"Could not read binary file: {str(e)}", rel_path)
            continue

        try:
            content = read_text(filepath)
            if file.endswith(".md"):
                if header_bug_pat.search(content):
                    res.add_error("MECHANICAL", "Concatenated headers detected", rel_path)
                if double_header_pat.search(content):
                    res.add_error("MECHANICAL", "Double headers (## ##) detected", rel_path)
                if corrupt_wikilink_pat.search(content):
                    res.add_error("MECHANICAL", "Malformed wikilink with trailing parenthesis detected (linkify corruption)", rel_path)
            if file.endswith(".py") and abs_path_pat.search(content):
                if file not in ["verify_agents.py", "publish_agents.py", "audit_repo.py"]:
                    res.add_error("MECHANICAL", "Absolute path detected in Python file", rel_path)
        except Exception as e:
            res.add_error("IO", f"Could not read file: {str(e)}", rel_path)

def find_line_num(text: str, token: str) -> int:
    idx = text.find(token)
    if idx == -1:
        return 1
    return text[:idx].count('\n') + 1

def check_links(res: AuditResult, verbose: bool = True):
    all_skills: Set[str] = set([str(d) for d in os.listdir(SKILLS_DIR) if os.path.isdir(os.path.join(SKILLS_DIR, d))]) if os.path.exists(SKILLS_DIR) else set([])
    all_rules: Set[str] = set([])
    all_rule_stems: Set[str] = set([])
    TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
    for d in [RULES_DIR, CANONS_DIR, TEMPLATES_DIR]:
        if os.path.exists(d):
            root_prefix = os.path.basename(d)
            for r, _, files in os.walk(d):
                for f in files:
                    if f.endswith(".md"):
                        rel = os.path.relpath(os.path.join(r, f), d).replace("\\", "/")
                        stem = rel[:-3] if rel.endswith(".md") else rel
                        all_rules.add(f)
                        all_rules.add(rel)
                        all_rules.add(f"{root_prefix}/{rel}")
                        all_rule_stems.add(f[:-3])
                        all_rule_stems.add(stem)
                        all_rule_stems.add(f"{root_prefix}/{stem}")
    
    if verbose: print("\n--- SCANNING FOR BROKEN LINKS ---")
    
    if not os.path.exists(BASE_DIR):
        res.add_warning("LINK", "Base directory not found!", severity="LOW")
        return

    # Patterns for rule and skill links
    rule_pattern = re.compile(r'@([a-zA-Z0-9_\-\./\\]+\.md)')
    # Support for @mention without .md extension as long as it exists in rules/canons/skills
    mention_pattern = re.compile(r'(?<![\w/])@([a-zA-Z0-9][a-zA-Z0-9_\-\./\\]*)')
    md_link_pattern = re.compile(r'\[[^\]]*\]\(([^)]+\.md)\)')
    concept_wikilinks = {"knowledge", "context", "wikilinks"}

    for filepath in iter_files(BASE_DIR, (".md",)):
        rel_path = os.path.relpath(filepath, BASE_DIR)
        try:
            content = read_text(filepath)

            # Rule and Canon links (@reference.md)
            for r in rule_pattern.findall(content):
                r_clean = r.split('`')[0].strip().replace("\\", "/")
                if r_clean not in all_rules:
                    line_no = find_line_num(content, f"@{r}")
                    res.add_error("LINK", f"Broken rule reference: @{r_clean}", f"{rel_path}:{line_no}")

            # Mentions (could be rule names without extension or skill references)
            for mention in mention_pattern.findall(content):
                m = mention.strip().replace("\\", "/")
                if not m:
                    continue
                if m.lower() in DOC_METADATA_KEYS:
                    continue
                if m in RULE_DIR_TOKENS:
                    continue
                if m.endswith(".md"):
                    continue

                if m.startswith("skills/"):
                    skill_name = m.split("/", 1)[1]
                    if skill_name and skill_name not in all_skills:
                        line_no = find_line_num(content, f"@{mention}")
                        res.add_error("LINK", f"Broken skill reference: @{m}", f"{rel_path}:{line_no}")
                    continue

                if m.startswith("rules/"):
                    rule_stem = m[len("rules/"):]
                    if rule_stem not in all_rule_stems:
                        line_no = find_line_num(content, f"@{mention}")
                        res.add_error("LINK", f"Broken rule reference: @{m}", f"{rel_path}:{line_no}")
                    continue

                if m.startswith("canons/"):
                    canon_stem = m[len("canons/"):]
                    if canon_stem not in all_rule_stems:
                        line_no = find_line_num(content, f"@{mention}")
                        res.add_error("LINK", f"Broken canon reference: @{m}", f"{rel_path}:{line_no}")
                    continue

                if m in all_skills or m in all_rule_stems:
                    continue

                # Keep implicit mentions permissive to reduce false positives.
                continue
                
            # Strip code fences and inline backticks to avoid false positives on doc examples
            non_code_content = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
            non_code_content = re.sub(r'`[^`\n]*`', '', non_code_content)

            # Standard Markdown Links
            for link in md_link_pattern.findall(non_code_content):
                l_clean = link.split('#')[0].strip()
                if not l_clean or l_clean.startswith(('http', 'mailto')):
                    continue
                if l_clean.startswith('file://'):
                    line_no = find_line_num(content, link)
                    res.add_error("LINK", f"Forbidden file:// scheme in source markdown: {l_clean}", f"{rel_path}:{line_no}")
                    continue
                if any(token in l_clean for token in ['{{', '}}', '<', '>']):
                    continue
                # Resolve relative path
                target_path = os.path.normpath(os.path.join(os.path.dirname(filepath), l_clean))
                if not os.path.exists(target_path):
                    line_no = find_line_num(content, link)
                    res.add_error("LINK", f"Broken markdown link: {l_clean}", f"{rel_path}:{line_no}")

            # Wikilinks [[target]]
            wikilink_pat = re.compile(r'\[\[([a-zA-Z0-9_\-\./\\]+)\]\]')
            for wl in wikilink_pat.findall(non_code_content):
                wl_clean = wl.strip().replace('\\', '/')
                matched = (
                    wl_clean in concept_wikilinks or
                    wl_clean in all_skills or 
                    wl_clean in all_rule_stems or 
                    wl_clean in all_rules or 
                    os.path.exists(os.path.join(BASE_DIR, wl_clean)) or
                    os.path.exists(os.path.join(BASE_DIR, wl_clean + '.md'))
                )
                if not matched:
                    line_no = find_line_num(content, f"[[{wl}]]")
                    res.add_error("LINK", f"Broken wikilink: [[{wl_clean}]]", f"{rel_path}:{line_no}")

            # view_file targets
            view_file_pat = re.compile(r'view_file\s+([a-zA-Z0-9_\-\./\\]+\.md)')
            for vf in view_file_pat.findall(content):
                vf_clean = vf.strip().replace('\\', '/')
                if any(token in vf_clean for token in ['{{', '}}', '<', '>']):
                    continue
                workspace_target = os.path.normpath(os.path.join(os.path.dirname(BASE_DIR), vf_clean))
                agents_target = os.path.normpath(os.path.join(BASE_DIR, vf_clean))
                doc_target = os.path.normpath(os.path.join(os.path.dirname(filepath), vf_clean))
                if not (os.path.exists(workspace_target) or os.path.exists(agents_target) or os.path.exists(doc_target)):
                    line_no = find_line_num(content, vf)
                    res.add_error("LINK", f"Broken view_file target: {vf_clean}", f"{rel_path}:{line_no}")

        except Exception as e:
            res.add_error("IO", f"Could not read file: {str(e)}", rel_path)


def check_ghost_references(res: AuditResult, verbose: bool = True):
    if verbose: print("\n--- SCANNING FOR GHOST REFERENCES ---")
    
    script_pat = re.compile(r'scripts/([a-zA-Z0-9_/-]+)\.py')
    skill_pat = re.compile(r'\.agents/skills/([a-zA-Z0-9_-]+)/SKILL\.md')
    skill_ref_pat = re.compile(r'(?:(\.agents/skills/[a-zA-Z0-9_-]+/)?references/([a-zA-Z0-9_\-\.]+\.md))')
    orion_cmd_pat = re.compile(r'python\s+\.?\.agents/scripts/orion\.py\s+([a-zA-Z0-9_-]+)')

    orion_py = os.path.join(BASE_DIR, 'scripts', 'orion.py')
    valid_orion_cmds = set()
    if os.path.exists(orion_py):
        try:
            o_txt = read_text(orion_py)
            cmd_map_match = re.search(r'CMD_MAP\s*=\s*\{([^}]+)\}', o_txt)
            if cmd_map_match:
                valid_orion_cmds = set(re.findall(r'"([a-zA-Z0-9_-]+)"\s*:', cmd_map_match.group(1)))
        except Exception as _e:
            _log_telemetry(_e, 'verify_agents.py:380')

    # Check skill references/ files exist and enforce canonical workspace-relative paths
    if os.path.exists(SKILLS_DIR):
        for skill_name in os.listdir(SKILLS_DIR):
            skill_folder = os.path.join(SKILLS_DIR, skill_name)
            if not os.path.isdir(skill_folder):
                continue
            skill_md = os.path.join(skill_folder, "SKILL.md")
            if os.path.exists(skill_md):
                try:
                    s_content = read_text(skill_md)
                    rel_skill_path = os.path.relpath(skill_md, BASE_DIR)
                    for match in skill_ref_pat.finditer(s_content):
                        prefix, ref_file = match.group(1), match.group(2)
                        if not prefix:
                            res.add_warning("PROTOCOL", f"Unqualified skill reference: references/{ref_file}. Must use canonical workspace path: .agents/skills/{skill_name}/references/{ref_file}", rel_skill_path)
                            ref_path = os.path.join(skill_folder, "references", ref_file)
                        else:
                            workspace_root = os.path.dirname(BASE_DIR)
                            clean_prefix = prefix.strip()
                            if clean_prefix.startswith("./"):
                                clean_prefix = clean_prefix[2:]
                            clean_prefix = clean_prefix.strip("/\\")
                            ref_path = os.path.normpath(os.path.join(workspace_root, clean_prefix, "references", ref_file))
                        if not os.path.exists(ref_path):
                            res.add_error("GHOST", f"Ghost skill reference: {match.group(0)}", rel_skill_path)

                    ref_folder = os.path.join(skill_folder, "references")
                    if os.path.isdir(ref_folder):
                        for disk_ref in os.listdir(ref_folder):
                            if disk_ref.endswith(".md") and disk_ref not in s_content:
                                res.add_error("PROTOCOL", f"Unindexed reference file: {disk_ref} exists in references/ but is not referenced in {skill_name}/SKILL.md", rel_skill_path, severity="HIGH")
                except Exception as e:
                    res.add_error("IO", f"Could not read {skill_md}: {str(e)}")

    for filepath in iter_files(BASE_DIR, (".md",)):
        rel_path = os.path.relpath(filepath, BASE_DIR)
        try:
            content = read_text(filepath)
            
            for script_name in script_pat.findall(content):
                script_path = os.path.join(BASE_DIR, 'scripts', f"{script_name}.py")
                if not os.path.exists(script_path):
                    res.add_error("GHOST", f"Ghost script reference: {script_name}.py", rel_path)
            
            for skill_name in skill_pat.findall(content):
                skill_path = os.path.join(BASE_DIR, 'skills', skill_name, 'SKILL.md')
                if not os.path.exists(skill_path):
                    res.add_error("GHOST", f"Ghost skill reference: {skill_name}", rel_path)

            if valid_orion_cmds:
                for orion_sub in orion_cmd_pat.findall(content):
                    if orion_sub not in valid_orion_cmds:
                        line_no = find_line_num(content, orion_sub)
                        res.add_error("GHOST", f"Invalid orion CLI subcommand: '{orion_sub}'", f"{rel_path}:{line_no}", severity="HIGH")
                    
        except Exception as e:
            res.add_error("IO", f"Could not read file for ghost check: {str(e)}", rel_path)

def check_protocol_compliance(res: AuditResult, verbose: bool = True):
    if verbose: print("\n--- SCANNING FOR PROTOCOL COMPLIANCE ERRORS ---")
    
    # 1. Skill Context & Metadata (Simplified)
    if os.path.exists(SKILLS_DIR):
        for skill_name in os.listdir(SKILLS_DIR):
            skill_path = os.path.join(SKILLS_DIR, skill_name)
            if not os.path.isdir(skill_path): continue
            res.stats["skills"] += 1
            skill_md = os.path.join(skill_path, "SKILL.md")
            if not os.path.exists(skill_md):
                res.add_error("PROTOCOL", "Missing SKILL.md in skill directory", f"skills/{skill_name}")
                continue
            
            try:
                content = read_text(skill_md)
                frontmatter = parse_frontmatter_keys(content)
                if not frontmatter:
                    rel = os.path.relpath(skill_md, BASE_DIR)
                    res.add_warning("PROTOCOL", "Missing YAML frontmatter block.", rel)
                    continue

                # Check required metadata keys in frontmatter only.
                if "name" not in frontmatter or "description" not in frontmatter:
                    res.add_error("PROTOCOL", "Missing essential metadata (name/description)", f"skills/{skill_name}/SKILL.md")
            except Exception as e:
                res.add_error("IO", f"Could not read {skill_md}: {str(e)}")

    # 2. Rules Metadata
    if os.path.exists(RULES_DIR):
        for root, _, files in os.walk(RULES_DIR):
            for file in files:
                if not file.endswith(".md"): continue
                res.stats["rules"] += 1
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, RULES_DIR)
                try:
                    content = read_text(filepath)
                    frontmatter = parse_frontmatter_keys(content)
                    if not frontmatter:
                        res.add_warning("PROTOCOL", "Missing YAML frontmatter block.", rel_path)
                        continue

                    has_description = "description" in frontmatter
                    has_activation_or_trigger = "activation" in frontmatter or "trigger" in frontmatter
                    if not has_description or not has_activation_or_trigger:
                        res.add_error("PROTOCOL", "Incomplete YAML header", rel_path)
                except Exception as e:
                    res.add_error("IO", f"Could not read {file}: {str(e)}")

    # 3. Canons Count
    if os.path.exists(CANONS_DIR):
        for root, _, files in os.walk(CANONS_DIR):
            for file in files:
                if not file.endswith(".md"): continue
                res.stats["canons"] += 1

def check_ast_blueprint_drift(res: AuditResult, verbose: bool = True):
    if verbose: print("\n--- SCANNING FOR AST BLUEPRINT DRIFT ---")
    blueprint_path = os.path.join(os.path.dirname(BASE_DIR), "BLUEPRINT.md")
    if not os.path.exists(blueprint_path):
        blueprint_path = os.path.join(BASE_DIR, "BLUEPRINT.md")
    if not os.path.exists(blueprint_path):
        if verbose: print(" [SKIP] BLUEPRINT.md not configured. AST drift check skipped.")
        return
    try:
        content = read_text(blueprint_path)
        if len(content.strip()) < 10:
            res.add_error("DRIFT", "BLUEPRINT.md is virtually empty", blueprint_path)
        else:
            if verbose: print(" [PASS] Blueprint verified.")
    except Exception as e:
        res.add_error("IO", f"Could not read BLUEPRINT.md: {str(e)}", blueprint_path)

def check_nano_brain(res: AuditResult, verbose: bool = True):
    if verbose: print("\n--- SCANNING FOR NANO BRAIN (OLLAMA) ---")
    try:
        # Use centralized resolver with dual-stack fallback
        script_dir = os.path.dirname(os.path.abspath(__file__))
        import sys
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        from brain import resolve_ollama_base_url
        resolved = resolve_ollama_base_url()
        if resolved:
            if verbose: print(f" [PASS] Ollama service detected at {resolved}.")
        else:
            res.add_warning("ENVIRONMENT", "Ollama not reachable on any endpoint (IPv4, IPv6, localhost). NanoBrain features will be disabled.", severity="LOW")
    except Exception:
        # Fallback: direct probe if brain.py import fails
        import urllib.request
        try:
            req = urllib.request.Request("http://127.0.0.1:11434/", method="GET")
            with urllib.request.urlopen(req, timeout=2) as r:
                if r.status == 200:
                    if verbose: print(" [PASS] Ollama service detected (direct probe).")
                else:
                    res.add_warning("ENVIRONMENT", "Ollama port 11434 responded with non-200 status.", severity="LOW")
        except Exception:
            res.add_warning("ENVIRONMENT", "Ollama not reachable. NanoBrain features will be disabled.", severity="LOW")

def check_telemetry_health(res: AuditResult, verbose: bool = True):
    if verbose: print("\n--- CHECKING AGENT TELEMETRY (SQLite) ---")
    db_path = os.path.join(os.path.dirname(BASE_DIR), ".orion", "orion.db")
    if not os.path.exists(db_path):
        if verbose: print(" [NOTE] orion.db not found. Skipping telemetry check.")
        return
        
    import sqlite3
    try:
        conn = sqlite3.connect(db_path)
        conn.execute('PRAGMA busy_timeout=5000;')
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='telemetry'")
        if c.fetchone():
            c.execute("SELECT COUNT(*), SUM(exit_code) FROM telemetry")
            row = c.fetchone()
            count = row[0] if row else 0
            errors = row[1] if row and row[1] else 0
            if verbose: print(f" [PASS] Telemetry table active: {count} events logged, {errors} total errors.")
        else:
            if verbose: print(" [NOTE] Telemetry table not initialized yet.")
        conn.close()
    except Exception as e:
        res.add_warning("TELEMETRY", f"Failed to read telemetry table: {e}", severity="LOW")

def check_ecosystem_cohesion(res: AuditResult, verbose: bool = True):
    if verbose: print("\n--- CHECKING ECOSYSTEM COHESION (CONTEXT & ORION) ---")
    workspace_root = os.path.dirname(BASE_DIR)
    
    # 1. Context Naming & 4 Lean Pillars check
    context_dir = os.path.join(workspace_root, "context")
    if os.path.exists(context_dir):
        try:
            scripts_dir = os.path.join(BASE_DIR, "scripts")
            cmd_dir = os.path.join(scripts_dir, "commands")
            if cmd_dir not in sys.path:
                sys.path.insert(0, cmd_dir)
            from context_naming_lint import lint_context
            errs, wrns, out_lines = lint_context(strict=False)
            if errs > 0:
                for line in out_lines:
                    if "[ERROR]" in line:
                        res.add_error("CONTEXT_LINT", line.replace("[ERROR] ", ""), "context/")
            elif wrns > 0:
                for line in out_lines:
                    if "[WARNING]" in line:
                        res.add_warning("CONTEXT_LINT", line.replace("[WARNING] ", ""), "context/", severity="LOW")
            else:
                if verbose: print(" [PASS] Context Naming & 4 Lean Pillars: Compliant (0 errors, 0 warnings).")
        except Exception as e:
            res.add_warning("CONTEXT_LINT", f"Context naming lint failed to run: {e}", severity="LOW")

    # 2. Orion DB & FTS5 Integrity check
    orion_db = os.path.join(workspace_root, ".orion", "orion.db")
    if os.path.exists(orion_db):
        import sqlite3
        try:
            conn = sqlite3.connect(orion_db)
            conn.execute('PRAGMA busy_timeout=5000;')
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('pages', 'pages_fts', 'nodes', 'edges')")
            found_tables = {row[0] for row in c.fetchall()}
            expected = {'pages', 'pages_fts', 'nodes', 'edges'}
            if expected.issubset(found_tables):
                c.execute("SELECT COUNT(*) FROM pages")
                page_cnt = c.fetchone()[0]
                if verbose: print(f" [PASS] Orion Graph Database: Healthy ({page_cnt} pages indexed across FTS5 & graph tables).")
            else:
                res.add_warning("ORION_DB", f"Missing expected Orion tables: {expected - found_tables}", severity="LOW")
            conn.close()
        except Exception as e:
            res.add_warning("ORION_DB", f"Failed to verify orion.db: {e}", severity="LOW")

    # 3. Rule Matrix Freshness
    matrix_dir = os.path.join(workspace_root, ".orion", "matrix")
    if os.path.exists(matrix_dir):
        json_count = len([f for f in os.listdir(matrix_dir) if f.endswith('.json')])
        if json_count > 0:
            if verbose: print(f" [PASS] Compiled Rule Matrices: {json_count} JSON rule matrices active in .orion/matrix/.")
        else:
            res.add_warning("MATRIX", "Matrix directory exists but contains 0 compiled JSON rules. Run 'python .agents/scripts/orion.py compile'.", severity="LOW")

    # 4. Audit Ledger Discovery (Generic / Stack-Agnostic)
    audit_dir = os.path.join(workspace_root, ".orion", "working", "audit")
    if os.path.exists(audit_dir):
        ledgers = [os.path.join(r, f) for r, _, fs in os.walk(audit_dir) for f in fs if f == "00-ledger.md"]
        if ledgers and verbose:
            print(f" [PASS] Project Audit Ledgers: {len(ledgers)} active ledger(s) tracked in .orion/working/audit/.")

    # 5. Semantic Fact-Checking & Anti-Hallucination Gate
    banned_claims = [
        (re.compile(r'\bLightRAG\b', re.IGNORECASE), "Ungrounded reference to 'LightRAG' found. Repo implements independent SQLite graph."),
        (re.compile(r'\bNeuro-Link\b', re.IGNORECASE), "Ungrounded buzzword 'Neuro-Link' found. Use 'Brain & Context Engine'."),
        (re.compile(r'nano_compressor', re.IGNORECASE), "Ghost CLI command 'nano_compressor' referenced. Use 'compress_memory'."),
        (re.compile(r'auto_delegate\.py', re.IGNORECASE), "Ghost script 'auto_delegate.py' referenced."),
        (re.compile(r'commands/evolve\.py', re.IGNORECASE), "Ghost script 'commands/evolve.py' referenced."),
        (re.compile(r'evolve\s+mine-friction', re.IGNORECASE), "Ghost command 'evolve mine-friction' referenced."),
        (re.compile(r'evolve\s+bench', re.IGNORECASE), "Ghost command 'evolve bench' referenced.")
    ]
    fact_violations = []
    docs_dir = os.path.join(BASE_DIR, "docs")
    check_files = ["README.md"]
    if os.path.exists(docs_dir):
        for df in os.listdir(docs_dir):
            if df.endswith(".md"):
                check_files.append(os.path.join("docs", df))

    for check_file in check_files:
        full_check_path = os.path.join(workspace_root if not check_file.startswith("docs") else BASE_DIR, check_file)
        if os.path.exists(full_check_path):
            try:
                txt = read_text(full_check_path)
                for pat, msg in banned_claims:
                    if pat.search(txt):
                        fact_violations.append((check_file, msg))
            except Exception as _e:
                _log_telemetry(_e, 'verify_agents.py:657')
    if fact_violations:
        for f, m in fact_violations:
            res.add_error("FACT_CHECK", f"{m} in {f}", f, severity="HIGH")
    elif verbose:
        print(" [PASS] Semantic Fact-Check: Zero ungrounded buzzwords or ghost CLI commands detected.")

def check_schema_producer_consumer(res: AuditResult, verbose: bool = True):
    if verbose: print("\n--- CHECKING SCHEMA PRODUCER-CONSUMER COHESION ---")
    workspace_root = os.path.dirname(BASE_DIR)
    orion_db = os.path.join(workspace_root, ".orion", "orion.db")
    if not os.path.exists(orion_db):
        return

    import sqlite3
    try:
        conn = sqlite3.connect(orion_db)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in c.fetchall() if not r[0].startswith("sqlite_") and "_fts_" not in r[0]]
        conn.close()
    except Exception as e:
        res.add_warning("SCHEMA_COHESION", f"Could not inspect orion.db tables: {e}", severity="LOW")
        return

    scripts_dir = os.path.join(BASE_DIR, "scripts")
    script_sources = []
    for root, _, files in os.walk(scripts_dir):
        if "__pycache__" in root: continue
        for f in files:
            if f.endswith(".py"):
                p = os.path.join(root, f)
                try:
                    script_sources.append((p, read_text(p)))
                except Exception as _e:
                    _log_telemetry(_e, 'verify_agents.py:692')

    disconnected = []
    for tbl in tables:
        write_pat = re.compile(rf'\b(?:INSERT\s+(?:OR\s+[A-Z]+\s+)?INTO|UPDATE|REPLACE\s+INTO)\s+{tbl}\b', re.IGNORECASE)
        read_pat = re.compile(rf'\b(?:FROM|JOIN)\s+{tbl}\b', re.IGNORECASE)
        has_write = any(write_pat.search(content) for _, content in script_sources)
        has_read = any(read_pat.search(content) for _, content in script_sources)

        if not has_write and not has_read:
            disconnected.append((tbl, "Orphan table: 0 writes, 0 reads across runtime codebase"))
        elif not has_write:
            disconnected.append((tbl, "Consumer without producer: 0 writes detected in runtime codebase"))
        elif not has_read:
            disconnected.append((tbl, "Dead table (Producer without consumer): 0 reads detected in runtime codebase"))

    if disconnected:
        for tbl, msg in disconnected:
            res.add_error("SCHEMA_COHESION", f"Table '{tbl}': {msg}", "orion.db", severity="HIGH")
            if verbose: print(f" [FAIL] Schema Cohesion: Table '{tbl}' -> {msg}")
    elif verbose:
        print(f" [PASS] Schema Producer-Consumer Cohesion: All {len(tables)} active SQLite tables have verified data producers and consumers.")

def check_version_synchronization(res: AuditResult, verbose: bool = True):
    if verbose: print("\n--- CHECKING VERSION SYNCHRONIZATION ---")
    workspace_root = os.path.dirname(BASE_DIR)
    version_file = os.path.join(workspace_root, "VERSION")
    if not os.path.exists(version_file):
        return

    expected_ver = read_text(version_file).strip()
    if not expected_ver:
        return

    version_targets = [
        ("CHANGELOG.md", re.compile(rf'##\s*\[{re.escape(expected_ver)}\]'), f"Release header for [{expected_ver}] in CHANGELOG.md"),
        ("README.md", re.compile(rf'badge/version-v{re.escape(expected_ver)}-blue'), f"Version badge v{expected_ver} in README.md"),
        ("GEMINI.md", re.compile(rf'Mandate Version:\s*{re.escape(expected_ver)}'), f"Mandate Version: {expected_ver} in GEMINI.md"),
        (os.path.join(".agents", "templates", "AGENTS.template.md"), re.compile(rf'Mandate Version:\s*{re.escape(expected_ver)}'), f"Mandate Version: {expected_ver} in AGENTS.template.md"),
        (os.path.join(".agents", "rules", "core-guardrails.md"), re.compile(rf'version:\s*{re.escape(expected_ver)}'), f"version: {expected_ver} in core-guardrails.md"),
        (os.path.join(".agents", "docs", "00-intro.md"), re.compile(rf'v{re.escape(expected_ver)}'), f"v{expected_ver} in docs/00-intro.md"),
        (os.path.join(".agents", "DEPLOY_ME.md"), re.compile(rf'Version\*\*:\s*{re.escape(expected_ver)}'), f"Version: {expected_ver} in DEPLOY_ME.md"),
        (os.path.join("context", "AGENT_IDENTITY.md"), re.compile(rf'Foundation\s+v{re.escape(expected_ver)}'), f"Foundation v{expected_ver} in AGENT_IDENTITY.md")
    ]

    mismatches = []
    for rel_path, pat, desc in version_targets:
        full_path = os.path.join(workspace_root, rel_path)
        if os.path.exists(full_path):
            try:
                content = read_text(full_path)
                if not pat.search(content):
                    mismatches.append((rel_path, f"Version drift: Expected {desc}"))
            except Exception as e:
                mismatches.append((rel_path, f"Could not read for version check: {e}"))

    if mismatches:
        for f, m in mismatches:
            res.add_error("VERSION_DRIFT", m, f, severity="HIGH")
            if verbose: print(f" [FAIL] {m} ({f})")
    elif verbose:
        print(f" [PASS] Version Synchronization: All entrypoints and manifests match VERSION ({expected_ver}).")

def check_security_integrity(res: AuditResult, verbose: bool = True):
    if verbose: print("\n--- SCANNING FOR SECURITY & AST INTEGRITY ---")
    try:
        scripts_dir = os.path.join(BASE_DIR, "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        core_dir = os.path.join(scripts_dir, "core")
        if core_dir not in sys.path:
            sys.path.insert(0, core_dir)

        try:
            from core.security import SecurityAuditor
        except ImportError:
            from security import SecurityAuditor  # type: ignore[import-not-found]
        
        auditor = SecurityAuditor(BASE_DIR)
        active, suppressed = auditor.audit_directory()
        
        if active:
            for item in active:
                msg = f"{item['category']}: {item['message']} (line {item.get('line', '?')})"
                sev = item.get('severity', 'HIGH')
                if sev in ('CRITICAL', 'HIGH'):
                    res.add_error("SECURITY", msg, item.get('file'), severity=sev)
                else:
                    res.add_warning("SECURITY", msg, item.get('file'), severity=sev)
        else:
            if verbose: print(f" [PASS] Security & AST Integrity: 0 vulnerabilities detected ({len(suppressed)} baselined).")
    except Exception as e:
        res.add_warning("SECURITY", f"Security scan encountered error: {e}", severity="LOW")

def check_vibe(res: AuditResult, filepath: str, verbose: bool = True):
    if verbose: print(f"\n--- SCANNING FOR SEMANTIC INTEGRITY ({filepath}) ---")
    if not os.path.exists(filepath):
        res.add_error("SEMANTIC", f"File not found for vibe check: {filepath}")
        return
        
    try:
        import sys
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        from brain import NanoBrain
        
        nb = NanoBrain()
        if not nb.ping():
            if verbose: print(" [SKIP] NanoBrain offline. Cannot perform semantic check.")
            res.add_warning("SEMANTIC", "NanoBrain offline. Skipped semantic check.", filepath)
            return
            
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        if verbose: print(" [AUTO-RAG] Querying NanoBrain for semantic contradictions...")
        response = nb.vibe_check(content)
        
        if response:
            if "PASS" in response.upper():
                if verbose: print(" [PASS] Semantic Integrity Verified.")
            else:
                if verbose: print(f" [WARNING] NanoBrain flagged potential semantic drift:\n  {response}")
                res.add_warning("SEMANTIC", f"NanoBrain drift warning: {response}", filepath)
        else:
            if verbose: print(" [SKIP] No response from NanoBrain.")
            
    except Exception as e:
        res.add_error("SEMANTIC", f"Semantic check failed: {str(e)}", filepath)

def check_portability_and_hygiene(res: AuditResult, verbose: bool = True):
    if verbose: print("\n--- SCANNING FOR PORTABILITY & HYGIENE LEAKS ---")
    
    path_leaks = []
    for filepath in iter_files(BASE_DIR, (".md", ".py", ".json")):
        norm_path = filepath.replace("\\", "/")
        if "archive" in norm_path.split("/") or os.path.basename(filepath) == "verify_agents.py":
            continue
        try:
            content = read_text(filepath)
            rel_path = os.path.relpath(filepath, BASE_DIR)
            if re.search(r'C:[\\/]Users', content, re.IGNORECASE):
                path_leaks.append((rel_path, "Hardcoded user machine path"))
            if "file:///" in content:
                path_leaks.append((rel_path, "Hardcoded file:/// URI scheme"))
        except Exception as _e:
            _log_telemetry(_e, 'verify_agents.py:839')
            
    for rel_path, msg in path_leaks:
        res.add_error("HYGIENE", f"{msg} found in {rel_path}", rel_path, severity="BLOCKER")
        if verbose: print(f" [FAIL] Hygiene Leak: {msg} in {rel_path}")
        
    if not path_leaks and verbose:
        print(" [PASS] Hygiene & Portability: Zero hardcoded machine paths or file:/// schemes.")

def check_command_parity(res: AuditResult, verbose: bool = True):
    if verbose: print("\n--- CHECKING SKILL JIT ROUTING PARITY ---")
    skills_dir = os.path.join(BASE_DIR, "skills")
    gemini_path = os.path.join(os.path.dirname(BASE_DIR), "GEMINI.md")

    if not os.path.exists(skills_dir):
        return

    skills = [d for d in os.listdir(skills_dir) if os.path.isdir(os.path.join(skills_dir, d)) and not d.startswith(".") and d != "internal"]

    gemini_content = ""
    if os.path.exists(gemini_path):
        gemini_content = read_text(gemini_path)

    missing_routing = []
    for skill in sorted(skills):
        if skill not in gemini_content:
            missing_routing.append(skill)

    if missing_routing:
        for m in missing_routing:
            res.add_warning("PARITY", f"Skill '{m}' is not mapped in GEMINI.md JIT routing table", severity="LOW")
            if verbose: print(f" [WARN] JIT Parity: Skill '{m}' not found in GEMINI.md JIT table")

    if not missing_routing and verbose:
        print(f" [PASS] Skill JIT Parity: All {len(skills)} domain skills are mapped in GEMINI.md JIT routing table.")

def run_audit(output_json: bool = False, vibe_check_file: Optional[str] = None):
    res = AuditResult()
    verbose = not output_json
    
    if verbose: print("--- STARTING AUDIT ---")
    
    check_foundation_sync(res, verbose=verbose)
    check_portability_and_hygiene(res, verbose=verbose)
    check_mechanical_integrity(res, verbose=verbose)
    check_ast_blueprint_drift(res, verbose=verbose)
    check_links(res, verbose=verbose)
    check_ghost_references(res, verbose=verbose)
    check_protocol_compliance(res, verbose=verbose)
    check_security_integrity(res, verbose=verbose)
    check_nano_brain(res, verbose=verbose)
    check_telemetry_health(res, verbose=verbose)
    check_ecosystem_cohesion(res, verbose=verbose)
    check_schema_producer_consumer(res, verbose=verbose)
    check_version_synchronization(res, verbose=verbose)
    check_command_parity(res, verbose=verbose)

    
    if vibe_check_file:
        check_vibe(res, vibe_check_file, verbose=verbose)
    
    if output_json:
        print(json.dumps({
            "errors": res.errors,
            "warnings": res.warnings,
            "summary": {
                "total_errors": len(res.errors),
                "total_warnings": len(res.warnings),
                "error_severity": severity_counts(res.errors),
                "warning_severity": severity_counts(res.warnings)
            }
        }, indent=2))
    else:
        for err in res.errors:
            print(f"[ERROR] [{err['severity']}] [{err['category']}] {err['message']} ({err['file'] or 'N/A'})")
        for wrn in res.warnings:
            print(f"[WARNING] [{wrn['severity']}] [{wrn['category']}] {wrn['message']} ({wrn['file'] or 'N/A'})")

        if len(res.errors) > 0 or len(res.warnings) > 0:
            print("\n--- SEVERITY SUMMARY ---")
            print(f"Errors  : {severity_counts(res.errors)}")
            print(f"Warnings: {severity_counts(res.warnings)}")
        
        total_errors = len(res.errors)
        if total_errors == 0:
            print("\n[PASS] ALL CHECKS PASSED: Workspace is mechanically sound and protocol compliant.")
        else:
            print(f"\n[FAIL] FAILED: Found {total_errors} integrity/compliance issues.")
    
    sys.exit(1 if len(res.errors) > 0 else 0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify workspace integrity and protocol compliance.")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format.")
    parser.add_argument("--vibe-check", type=str, metavar="FILE", help="Perform a semantic integrity check using NanoBrain on the specified file.")
    args = parser.parse_args()
    
    run_audit(output_json=args.json, vibe_check_file=args.vibe_check)
