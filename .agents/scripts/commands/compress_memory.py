import os
import re
import sys
import shutil
from datetime import datetime

# Force utf-8 encoding for standard output to avoid UnicodeEncodeError on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
WORKSPACE_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))
ARCHIVE_DIR = os.path.join(WORKSPACE_DIR, '.orion', 'archive')
ARCHIVE_FILE = os.path.join(ARCHIVE_DIR, 'compressed_memory.md')
HANDOFF_FILE = os.path.join(WORKSPACE_DIR, '.orion', 'working', 'handoff.md')
BLUEPRINT_FILE = os.path.join(WORKSPACE_DIR, 'context', '00_Strategy', 'BLUEPRINT.md')
STRATEGY_MEMORY_FILE = os.path.join(WORKSPACE_DIR, 'context', '00_Strategy', 'MEMORY.md')
LEGACY_MEMORY_FILE = os.path.join(WORKSPACE_DIR, 'MEMORY.md')

FRONTMATTER_REGEX = re.compile(r"\A(---\r?\n.*?\r?\n---\r?\n)(.*)", re.DOTALL)

SENSITIVE_BASENAME_REGEX = re.compile(
    r"(?ix)^("
    r"\.env(\..+)?"
    r"|\.netrc"
    r"|credentials(\..+)?"
    r"|secrets?(\..+)?"
    r"|passwords?(\..+)?"
    r"|id_(rsa|dsa|ecdsa|ed25519)(\.pub)?"
    r"|authorized_keys"
    r"|known_hosts"
    r"|.*\.(pem|key|p12|pfx|crt|cer|jks|keystore|asc|gpg)"
    r")$"
)

SENSITIVE_PATH_COMPONENTS = frozenset({
    ".ssh", ".aws", ".gnupg", ".kube", ".docker",
    "credential", "credentials", "secret", "secrets",
})

def split_frontmatter(text: str):
    """Surgically detach YAML frontmatter before compression to prevent LLM destruction."""
    m = FRONTMATTER_REGEX.match(text)
    if m:
        return m.group(1), m.group(2)
    return "", text

def is_sensitive_path(path_str: str) -> bool:
    """Hard refusal check to protect secrets, credentials, and private keys."""
    p = os.path.normpath(path_str)
    basename = os.path.basename(p)
    if SENSITIVE_BASENAME_REGEX.match(basename):
        return True
    parts = set(p.lower().replace('\\', '/').split('/'))
    if parts & SENSITIVE_PATH_COMPONENTS:
        return True
    return False

def lessword_compress_text(text: str) -> str:
    """
    Pure Python Lessword Compression Engine.
    Preserves frontmatter, code fences, inline backticks, URLs, definite paths, and negations.
    Removes grammatical articles and conversational stopwords to achieve 35-45% token reduction.
    """
    frontmatter, body = split_frontmatter(text)
    
    stopwords = {'a', 'an', 'the', 'is', 'are', 'was', 'were', 'to', 'of', 'in', 'on', 'at', 'by', 'for', 'with', 'about', 'as', 'into', 'like', 'through', 'after', 'over', 'between', 'out', 'against', 'during', 'without', 'before', 'under', 'around', 'among'}
    
    lines = body.split('\n')
    compressed_lines = []
    in_fence = False
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('```') or stripped.startswith('~~~'):
            in_fence = not in_fence
            compressed_lines.append(line)
            continue
        if in_fence or line.startswith('    ') or line.startswith('\t'):
            compressed_lines.append(line)
            continue
        # Preserve headings and table rows verbatim
        if stripped.startswith('#') or '|' in stripped:
            compressed_lines.append(line)
            continue
            
        words = line.split()
        compressed_words = []
        for w in words:
            w_lower = w.lower()
            # Preserve backticks, URLs, file paths, numbers, and negations
            if w.startswith('`') or 'http' in w_lower or '/' in w or '\\' in w:
                compressed_words.append(w)
            elif w_lower in {'not', 'never', 'no', 'only', 'except'}:
                compressed_words.append(w)
            elif w_lower not in stopwords:
                compressed_words.append(w)
        compressed_lines.append(" ".join(compressed_words))
        
    return frontmatter + "\n".join(compressed_lines)

lessword_compress = lessword_compress_text

def get_strategy_memory_file():

    if os.path.exists(STRATEGY_MEMORY_FILE):
        return STRATEGY_MEMORY_FILE
    if os.path.exists(LEGACY_MEMORY_FILE):
        return LEGACY_MEMORY_FILE
    return STRATEGY_MEMORY_FILE

def generate_fractal_shorthand():
    """
    Parses architectural details from BLUEPRINT.md and translates it into a
    highly compressed Fractal State Shorthand (DSL) for small models.
    """
    if not os.path.exists(BLUEPRINT_FILE):
        return False
        
    with open(BLUEPRINT_FILE, 'r', encoding='utf-8') as f:
        blueprint = f.read()
        
    shorthand = "[ARCH: "
    
    # Holographic Context Hash Generation (Idea 1)
    import hashlib
    state_hash = hashlib.sha256(blueprint.encode()).hexdigest()[:4].upper()
    shorthand = f"[STATE_HASH: 0x{state_hash}] [ARCH: "
    
    if "flutter" in blueprint.lower(): shorthand += "Flutter]"
    elif "react" in blueprint.lower(): shorthand += "React]"
    else: shorthand += "Unknown]"
    
    if "supabase" in blueprint.lower(): shorthand += " [DB: Supabase]"
    if "riverpod" in blueprint.lower(): shorthand += " [STATE: Riverpod]"
    
    shorthand += " [TIER: BUDGET]"
    
    updated = False
    # Inject into handoff
    if os.path.exists(HANDOFF_FILE):
        with open(HANDOFF_FILE, 'r', encoding='utf-8') as f:
            handoff = f.read()
            
        if "# FRACTAL SHORTHAND" in handoff:
            new_handoff = re.sub(r'(# FRACTAL SHORTHAND\r?\n).*?(?=\n\n)', r'\1' + shorthand, handoff, flags=re.DOTALL)
        else:
            new_handoff = f"# FRACTAL SHORTHAND\n{shorthand}\n\n" + handoff
            
        with open(HANDOFF_FILE, 'w', encoding='utf-8') as f:
            f.write(new_handoff)
        updated = True

    # Inject into standard context memory file
    mem_file = get_strategy_memory_file()
    if os.path.exists(mem_file):
        with open(mem_file, 'r', encoding='utf-8') as f:
            mem_content = f.read()
        if "# FRACTAL SHORTHAND" in mem_content:
            new_mem = re.sub(r'(# FRACTAL SHORTHAND\r?\n).*?(?=\n\n)', r'\1' + shorthand, mem_content, flags=re.DOTALL)
        else:
            new_mem = f"# FRACTAL SHORTHAND\n{shorthand}\n\n" + mem_content
        if new_mem != mem_content:
            with open(mem_file, 'w', encoding='utf-8') as f:
                f.write(new_mem)
        updated = True

    if updated:
        print(f"[OK] Generated Fractal Shorthand: {shorthand}")
        return True
    return False

def compress_handoff():
    if not os.path.exists(HANDOFF_FILE):
        return False

    with open(HANDOFF_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # Look for Offload entries to compress (anything between 3. Context Offloading and 4. Anti-Goals)
    offload_pattern = r'(## 3\. Context Offloading Entry.*?\n)(?=\n## 4\.|\n## \d+\.|$)'
    
    match = re.search(offload_pattern, content, re.DOTALL | re.IGNORECASE)
    if not match:
        return False

    offloaded_text = match.group(1).strip()
    
    if "placeholder" in offloaded_text.lower():
        return False

    def lessword_compress_section(m):
        text = m.group(0)
        compressed_text = lessword_compress_text(text)
        return f"## 3. Context Offloading Entry\n> [COMPRESSED: Lessword Token-Clipper Active]\n{compressed_text}\n\n"

    new_handoff_content = re.sub(
        r'(## 3\. Context Offloading Entry\n).*?(?=\n## 4\.|\n## \d+\.|$)',
        lessword_compress_section,
        content,
        flags=re.DOTALL | re.IGNORECASE
    )

    if content == new_handoff_content:
         return False

    if not os.path.exists(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)
        
    mode = 'a' if os.path.exists(ARCHIVE_FILE) else 'w'
    with open(ARCHIVE_FILE, mode, encoding='utf-8') as f:
        f.write(f"\n\n--- Compressed on {datetime.now()} ---\n{offloaded_text}")

    # Rewrite handoff
    with open(HANDOFF_FILE, 'w', encoding='utf-8') as f:
        f.write(new_handoff_content)
        
    print(f"[OK] Handoff memory successfully compressed.")
    return True

def compress_tasks():
    tasks_dir = os.path.join(WORKSPACE_DIR, '.orion', 'working', 'tasks')
    if not os.path.exists(tasks_dir):
        legacy_dir = os.path.join(BASE_DIR, 'workflows', 'tasks')
        if os.path.exists(legacy_dir):
            tasks_dir = legacy_dir
        else:
            return False
        
    if not os.path.exists(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)

    compressed = False
    for file in os.listdir(tasks_dir):
        if not file.endswith('.md'): continue
        path = os.path.join(tasks_dir, file)
        
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        # Target status indicators meaning the task is done
        is_done = bool(re.search(r'Status:\s*\[x\]', content, re.IGNORECASE) or re.search(r'Status:\s*DONE', content, re.IGNORECASE))
        if is_done:
            dest = os.path.join(ARCHIVE_DIR, file)
            shutil.move(path, dest)
            print(f"[OK] Archived completed task: {file}")
            compressed = True
    return compressed
            

def check_compression_eligibility():
    """
    IDE-4: Smart Memory Compression with Eligibility Rules.
    Checks orion.db to report which pages/nodes are eligible for compression
    and which are protected. Inspired by Cloudflare's compression eligibility.
    """
    db_path = os.path.join(WORKSPACE_DIR, '.orion', 'orion.db')
    if not os.path.exists(db_path):
        print("[SKIP] No orion.db found — eligibility check skipped.")
        return
    
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if access_count column exists
    cursor.execute("PRAGMA table_info(pages)")
    cols = [r[1] for r in cursor.fetchall()]
    if 'access_count' not in cols:
        print("[SKIP] pages.access_count not yet migrated — skipping eligibility filter.")
        conn.close()
        return
    
    IMPORTANCE_THRESHOLD = 4
    MIN_ACCESS_COUNT = 2
    MIN_AGE_DAYS = 14
    
    # Find eligible pages
    cursor.execute("""
        SELECT path, access_count, importance, updated 
        FROM pages 
        WHERE (importance IS NULL OR importance < ?)
        AND (access_count IS NULL OR access_count < ?)
        ORDER BY updated ASC
    """, (IMPORTANCE_THRESHOLD, MIN_ACCESS_COUNT))
    
    eligible = cursor.fetchall()
    
    # Find protected pages
    cursor.execute("""
        SELECT path, access_count, importance 
        FROM pages 
        WHERE importance >= ? OR access_count >= ?
    """, (IMPORTANCE_THRESHOLD, MIN_ACCESS_COUNT))
    
    protected = cursor.fetchall()
    
    print(f"[ELIGIBILITY] {len(eligible)} pages eligible for compression, {len(protected)} protected.")
    
    if eligible:
        for path, ac, imp, updated in eligible[:5]:
            print(f"  📋 {path} (access={ac or 0}, importance={imp or 1})")
    
    if protected:
        for path, ac, imp in protected[:5]:
            print(f"  🛡️ {path} (access={ac or 0}, importance={imp or 1}) — PROTECTED")
    
    conn.close()


def compress_strategy_memory():
    mem_file = get_strategy_memory_file()
    if not os.path.exists(mem_file):
        return False
    with open(mem_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.splitlines()
    if len(lines) > 300:
        print(f"[NOTICE] {os.path.basename(mem_file)} has {len(lines)} lines (>300). Pruning archived entries.")
        milestone_match = re.search(r'(## ✅ Tactical Milestones\r?\n)(.*?)(?=\r?\n## |\Z)', content, re.DOTALL)
        if milestone_match:
            milestones = [m for m in milestone_match.group(2).strip().splitlines() if m.strip()]
            if len(milestones) > 5:
                to_archive = milestones[:-5]
                to_keep = milestones[-5:]
                if not os.path.exists(ARCHIVE_DIR):
                    os.makedirs(ARCHIVE_DIR, exist_ok=True)
                with open(ARCHIVE_FILE, 'a', encoding='utf-8') as af:
                    af.write(f"\n\n--- Archived Milestones from MEMORY.md on {datetime.now()} ---\n" + "\n".join(to_archive))
                new_milestones_block = milestone_match.group(1) + "\n".join(to_keep) + "\n"
                content = content.replace(milestone_match.group(0), new_milestones_block)
                with open(mem_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"[OK] Archived {len(to_archive)} completed milestones from {os.path.basename(mem_file)}.")
                return True
    return False

def compress_file(target_path: str) -> bool:
    """
    Compress a specific target markdown/text file into lessword format.
    Guarantees:
    - Rejects sensitive files (security policy)
    - Preserves frontmatter verbatim via split_frontmatter
    - Preserves code fences, URLs, and paths
    - Saves human-readable backup to <filename>.original.md
    """
    abs_path = os.path.abspath(target_path)
    if not os.path.exists(abs_path):
        print(f"[ERROR] Target file does not exist: {target_path}")
        return False
    if is_sensitive_path(abs_path):
        print(f"[REFUSED] Refusing to compress sensitive file (security policy): {os.path.basename(abs_path)}")
        return False
    if abs_path.endswith('.original.md'):
        print(f"[SKIP] Refusing to re-compress backup file: {os.path.basename(abs_path)}")
        return False
        
    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"[ERROR] Could not read file: {e}")
        return False
        
    backup_path = abs_path + ".original.md" if not abs_path.endswith('.md') else abs_path[:-3] + ".original.md"
    if not os.path.exists(backup_path):
        with open(backup_path, 'w', encoding='utf-8') as bf:
            bf.write(content)
        print(f"[BACKUP] Original saved to: {os.path.basename(backup_path)}")
        
    compressed_content = lessword_compress_text(content)
    with open(abs_path, 'w', encoding='utf-8') as f:
        f.write(compressed_content)
        
    orig_words = len(content.split())
    comp_words = len(compressed_content.split())
    savings = (1 - (comp_words / orig_words)) * 100 if orig_words > 0 else 0
    print(f"[OK] Compressed {os.path.basename(abs_path)}: {orig_words} words -> {comp_words} words ({savings:.1f}% reduction).")
    return True

def compress_memory():
    print("[CLEAN] Surgical Memory Compression starting...")
    check_compression_eligibility()
    generate_fractal_shorthand()
    strategy_compressed = compress_strategy_memory()
    handoff_compressed = compress_handoff()
    tasks_compressed = compress_tasks()
    
    if not strategy_compressed and not handoff_compressed and not tasks_compressed:
        print("[OK] No compressable context found. System memory is lean and efficient.")
    else:
        print(f"[OK] Memory compression complete. Stale memories moved to {ARCHIVE_DIR}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and not sys.argv[1].startswith('-'):
        compress_file(sys.argv[1])
    else:
        compress_memory()