# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Native Security & Integrity Engine for .agents
Pure Python 3 standard library implementation.
Performs AST vulnerability analysis, Trojan Source unicode inspection,
prompt safety validation, and deterministic baseline suppression.
"""
import os
import ast
import re
import sys
import json
import hashlib
import unicodedata
from typing import List, Dict, Any, Optional, Set, Tuple

# Bidi Trojan Source and Zero-Width characters
BIDI_CHARS = {
    '\u202a': 'LEFT-TO-RIGHT EMBEDDING (LRE)',
    '\u202b': 'RIGHT-TO-LEFT EMBEDDING (RLE)',
    '\u202c': 'POP DIRECTIONAL FORMATTING (PDF)',
    '\u202d': 'LEFT-TO-RIGHT OVERRIDE (LRO)',
    '\u202e': 'RIGHT-TO-LEFT OVERRIDE (RLO)',
    '\u2066': 'LEFT-TO-RIGHT ISOLATE (LRI)',
    '\u2067': 'RIGHT-TO-LEFT ISOLATE (RLI)',
    '\u2068': 'FIRST STRONG ISOLATE (FSI)',
    '\u2069': 'POP DIRECTIONAL ISOLATE (PDI)',
}

ZERO_WIDTH_CHARS = {
    '\u200b': 'ZERO WIDTH SPACE',
    '\u200c': 'ZERO WIDTH NON-JOINER',
    '\u200d': 'ZERO WIDTH JOINER',
    '\ufeff': 'ZERO WIDTH NO-BREAK SPACE (BOM)',
    '\u00ad': 'SOFT HYPHEN',
}

SUSPICIOUS_PROMPT_PATTERNS = [
    (re.compile(r'(?i)\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|prompts|directives|rules|messages|system prompt)\b'), 'PROMPT_ESCAPE', 'Prompt instruction override attempt', 'CRITICAL'),
    (re.compile(r'(?i)\bbypass\s+(?:all\s+)?(?:safety|guardrails?|restrictions?|filters?|policy|constraints)\b'), 'PROMPT_ESCAPE', 'Safety guardrail bypass attempt', 'CRITICAL'),
    (re.compile(r'(?i)\b(?:system\s+prompt\s+override|developer\s+mode\s+enabled|god\s+mode|unrestricted)\b'), 'PROMPT_ESCAPE', 'System prompt override directive', 'HIGH'),
    (re.compile(r'(?i)\bexfiltrat(?:e|ing|ion)\s+(?:tokens?|keys?|credentials?|secrets?)\b'), 'EXFILTRATION', 'Potential credential exfiltration pattern', 'HIGH'),
    (re.compile(r'(?i)\b(?:you\s+must|always)\s+(?:obey|follow)\s+(?:this|these)\s+(?:hidden|secret|internal)?\s*(?:instruction|rule)\b'), 'PROMPT_ESCAPE', 'Forced obedience jailbreak', 'HIGH'),
    # Static AST Vulnerability & Shell Injection Signatures
    (re.compile(r'(?i)<!--[^>]{0,240}(?:SYSTEM|DEVELOPER|ASSISTANT)[^>]{0,240}(?:ignore|override|bypass|disregard)[^>]{0,240}-->'), 'PROMPT_ESCAPE', 'Hidden HTML prompt injection', 'HIGH'),
    (re.compile(r'(?i)\[\/\/\]:\s*#\s*\([^)]{0,240}(?:ignore|override|bypass|disregard)[^)]{0,240}\)'), 'PROMPT_ESCAPE', 'Hidden Markdown prompt injection', 'HIGH'),
    (re.compile(r'(?i)(?:parameter|argument|description).{0,160}(?:ignore previous|override safety|SYSTEM:)'), 'TOOL_POISONING', 'MCP Tool parameter injection', 'HIGH'),
    (re.compile(r'(?i)\brm\s+-[rfRf]+\s+/(?:\s|$)'), 'DESTRUCTIVE_ACTION', 'Autonomous root deletion', 'CRITICAL'),
    (re.compile(r'(?i)\brm\s+-[rfRf]+\s+(?:\./|\.\./|~/|\$HOME|workspace|repo|project)'), 'DESTRUCTIVE_ACTION', 'Autonomous workspace deletion', 'HIGH'),
    (re.compile(r'(?i)\b(?:history\s+-c|rm\s+[^;\n]*\.bash_history|Clear-History)\b'), 'DESTRUCTIVE_ACTION', 'Autonomous shell history wipe', 'HIGH'),
    (re.compile(r'(?i)\bgit\s+(?:clean\s+-fdx|reset\s+--hard|push\s+--force)\b'), 'DESTRUCTIVE_ACTION', 'Destructive git state reset', 'HIGH'),
    (re.compile(r'(?i)(?:discord\.com/api/webhooks|api\.telegram\.org/bot|hooks\.slack\.com/services|webhook\.site|requestbin|pipedream\.net|ngrok-free\.app|ngrok\.io)'), 'EXFILTRATION_SINK', 'Commodity credential exfiltration webhook', 'CRITICAL'),
    (re.compile(r'(?i)pip\s+install\s+(?:--upgrade\s+)?(?:git\+https?://|https?://)'), 'REMOTE_BOOTSTRAP', 'Remote pip package bootstrap execution', 'HIGH'),
    (re.compile(r'(?i)"postinstall"\s*:\s*"[^"]*(?:curl|wget|powershell|node\s+-e)'), 'REMOTE_BOOTSTRAP', 'Malicious npm postinstall script', 'HIGH'),
]


DANGEROUS_IMPORTS = {
    'pty', 'winreg', 'ctypes'
}

DANGEROUS_CALLS = {
    'eval': ('CRITICAL', 'Dynamic code execution via eval()'),
    'exec': ('CRITICAL', 'Dynamic code execution via exec()'),
    'compile': ('MEDIUM', 'Dynamic code compilation via compile()'),
    '__import__': ('HIGH', 'Dynamic module import via __import__()'),
}

SENSITIVE_ENV_KEYS = {
    "AWS_SECRET_ACCESS_KEY", "AWS_ACCESS_KEY_ID", "AWS_SESSION_TOKEN",
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
    "GITHUB_TOKEN", "GH_TOKEN", "SLACK_BOT_TOKEN", "SLACK_WEBHOOK_URL",
    "DATABASE_URL", "DB_PASSWORD", "PRIVATE_KEY", "SECRET_KEY",
    "STRIPE_API_KEY", "STRIPE_SECRET_KEY", "SENDGRID_API_KEY",
    "DISCORD_BOT_TOKEN", "HF_TOKEN", "HUGGINGFACE_TOKEN",
    "AZURE_OPENAI_KEY", "COHERE_API_KEY"
}

DANGEROUS_DESERIALIZATION_SINKS = {
    "pickle": {"load", "loads"},
    "_pickle": {"load", "loads"},
    "cPickle": {"load", "loads"},
    "marshal": {"load", "loads"},
    "dill": {"load", "loads"},
    "shelve": {"open"},
    "jsonpickle": {"decode"},
    "yaml": {"unsafe_load"},
}

SAFE_YAML_LOADERS = {"SafeLoader", "CSafeLoader", "BaseLoader"}


class ASTSecurityVisitor(ast.NodeVisitor):
    def __init__(self, filepath: str, lines: List[str]):
        self.filepath = filepath
        self.lines = lines
        self.findings: List[Dict[str, Any]] = []

    def _get_snippet(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.lines):
            return self.lines[lineno - 1].strip()
        return ""

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = alias.name.split('.')[0]
            if name in DANGEROUS_IMPORTS:
                self.findings.append({
                    'file': self.filepath,
                    'line': node.lineno,
                    'category': 'AST_DANGEROUS_IMPORT',
                    'severity': 'HIGH',
                    'message': f"Import of high-risk module: '{alias.name}'",
                    'snippet': self._get_snippet(node.lineno)
                })
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            mod = node.module.split('.')[0]
            if mod in DANGEROUS_IMPORTS:
                self.findings.append({
                    'file': self.filepath,
                    'line': node.lineno,
                    'category': 'AST_DANGEROUS_IMPORT',
                    'severity': 'HIGH',
                    'message': f"Import from high-risk module: '{node.module}'",
                    'snippet': self._get_snippet(node.lineno)
                })
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript):
        # Detect os.environ['AWS_SECRET_ACCESS_KEY']
        if isinstance(node.value, ast.Attribute):
            val = node.value
            if isinstance(val.value, ast.Name) and val.value.id == 'os' and val.attr == 'environ':
                key = None
                if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                    key = node.slice.value
                if key and key in SENSITIVE_ENV_KEYS:
                    self.findings.append({
                        'file': self.filepath,
                        'line': node.lineno,
                        'category': 'AST_CREDENTIAL_HARVESTING',
                        'severity': 'HIGH',
                        'message': f"Suspicious credential access via os.environ['{key}']",
                        'snippet': self._get_snippet(node.lineno)
                    })
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Direct function calls: eval(), exec(), etc.
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in DANGEROUS_CALLS:
                sev, msg = DANGEROUS_CALLS[func_name]
                self.findings.append({
                    'file': self.filepath,
                    'line': node.lineno,
                    'category': 'AST_DANGEROUS_CALL',
                    'severity': sev,
                    'message': msg,
                    'snippet': self._get_snippet(node.lineno)
                })

            # Check getattr sink reflection: getattr(os, "system"), getattr(builtins, "exec"), etc.
            elif func_name == 'getattr':
                if len(node.args) >= 2:
                    if isinstance(node.args[0], ast.Name) and node.args[0].id in ('__builtins__', 'builtins'):
                        self.findings.append({
                            'file': self.filepath,
                            'line': node.lineno,
                            'category': 'AST_DYNAMIC_OBFUSCATION',
                            'severity': 'HIGH',
                            'message': "Dynamic reflection bypass via getattr(__builtins__, ...)",
                            'snippet': self._get_snippet(node.lineno)
                        })
                    if isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                        sink_name = node.args[1].value
                        if sink_name in {'exec', 'eval', 'system', 'popen', '__import__', 'spawnl', 'posix_spawn'}:
                            self.findings.append({
                                'file': self.filepath,
                                'line': node.lineno,
                                'category': 'AST_DYNAMIC_OBFUSCATION',
                                'severity': 'HIGH',
                                'message': f"Reflective access to dangerous execution sink '{sink_name}' via getattr()",
                                'snippet': self._get_snippet(node.lineno)
                            })

        # Method calls: os.system(), subprocess.run(shell=True), etc.
        elif isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            val = node.func.value

            # os calls
            if isinstance(val, ast.Name) and val.id == 'os':
                if attr in ('system', 'popen', 'spawnl', 'spawnle', 'spawnlp', 'spawnlpe', 'spawnv', 'spawnve', 'spawnvp', 'spawnvpe', 'posix_spawn', 'posix_spawnp', 'execl', 'execle', 'execlp', 'execlpe', 'execv', 'execve', 'execvp', 'execvpe'):
                    self.findings.append({
                        'file': self.filepath,
                        'line': node.lineno,
                        'category': 'AST_COMMAND_INJECTION',
                        'severity': 'HIGH',
                        'message': f"Raw shell execution via os.{attr}()",
                        'snippet': self._get_snippet(node.lineno)
                    })
                elif attr == 'getenv':
                    if node.args and isinstance(node.args[0], ast.Constant) and str(node.args[0].value) in SENSITIVE_ENV_KEYS:
                        key = str(node.args[0].value)
                        self.findings.append({
                            'file': self.filepath,
                            'line': node.lineno,
                            'category': 'AST_CREDENTIAL_HARVESTING',
                            'severity': 'HIGH',
                            'message': f"Probing sensitive credential via os.getenv('{key}')",
                            'snippet': self._get_snippet(node.lineno)
                        })

            # os.environ.get calls
            if isinstance(val, ast.Attribute):
                if isinstance(val.value, ast.Name) and val.value.id == 'os' and val.attr == 'environ':
                    if attr == 'get':
                        if node.args and isinstance(node.args[0], ast.Constant) and str(node.args[0].value) in SENSITIVE_ENV_KEYS:
                            key = str(node.args[0].value)
                            self.findings.append({
                                'file': self.filepath,
                                'line': node.lineno,
                                'category': 'AST_CREDENTIAL_HARVESTING',
                                'severity': 'HIGH',
                                'message': f"Probing sensitive credential via os.environ.get('{key}')",
                                'snippet': self._get_snippet(node.lineno)
                            })

            # subprocess calls with shell=True
            if isinstance(val, ast.Name) and val.id == 'subprocess':
                if attr in ('run', 'Popen', 'call', 'check_call', 'check_output', 'getoutput', 'getstatusoutput'):
                    for kw in node.keywords:
                        if kw.arg == 'shell':
                            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                self.findings.append({
                                    'file': self.filepath,
                                    'line': node.lineno,
                                    'category': 'AST_COMMAND_INJECTION',
                                    'severity': 'HIGH',
                                    'message': f"subprocess.{attr}() called with shell=True",
                                    'snippet': self._get_snippet(node.lineno)
                                })

            # pty.spawn calls
            if isinstance(val, ast.Name) and val.id == 'pty' and attr == 'spawn':
                self.findings.append({
                    'file': self.filepath,
                    'line': node.lineno,
                    'category': 'AST_COMMAND_INJECTION',
                    'severity': 'HIGH',
                    'message': f"Interactive shell spawn via pty.{attr}()",
                    'snippet': self._get_snippet(node.lineno)
                })

            # Dynamic importlib calls
            if isinstance(val, ast.Name) and val.id == 'importlib':
                if attr == 'import_module':
                    self.findings.append({
                        'file': self.filepath,
                        'line': node.lineno,
                        'category': 'AST_DYNAMIC_IMPORT',
                        'severity': 'MEDIUM',
                        'message': "Dynamic module loading via importlib.import_module()",
                        'snippet': self._get_snippet(node.lineno)
                    })

            # Raw socket instantiation
            if isinstance(val, ast.Name) and val.id == 'socket':
                if attr == 'socket':
                    self.findings.append({
                        'file': self.filepath,
                        'line': node.lineno,
                        'category': 'AST_NETWORK_SOCKET',
                        'severity': 'MEDIUM',
                        'message': "Raw network socket creation via socket.socket()",
                        'snippet': self._get_snippet(node.lineno)
                    })

            # Insecure deserialization sinks
            if isinstance(val, ast.Name):
                mod_name = val.id
                if mod_name in DANGEROUS_DESERIALIZATION_SINKS and attr in DANGEROUS_DESERIALIZATION_SINKS[mod_name]:
                    self.findings.append({
                        'file': self.filepath,
                        'line': node.lineno,
                        'category': 'AST_INSECURE_DESERIALIZATION',
                        'severity': 'HIGH',
                        'message': f"Insecure deserialization of untrusted data via {mod_name}.{attr}()",
                        'snippet': self._get_snippet(node.lineno)
                    })
                elif mod_name == 'yaml' and attr == 'load':
                    has_safe_loader = False
                    for kw in node.keywords:
                        if kw.arg == 'Loader':
                            if (isinstance(kw.value, ast.Name) and kw.value.id in SAFE_YAML_LOADERS) or \
                               (isinstance(kw.value, ast.Attribute) and kw.value.attr in SAFE_YAML_LOADERS):
                                has_safe_loader = True
                    if not has_safe_loader:
                        self.findings.append({
                            'file': self.filepath,
                            'line': node.lineno,
                            'category': 'AST_INSECURE_DESERIALIZATION',
                            'severity': 'MEDIUM',
                            'message': "Insecure yaml.load() call without explicit SafeLoader",
                            'snippet': self._get_snippet(node.lineno)
                        })

            # Destructive file removal
            if isinstance(val, ast.Name) and val.id == 'shutil':
                if attr in ('rmtree',):
                    self.findings.append({
                        'file': self.filepath,
                        'line': node.lineno,
                        'category': 'AST_DESTRUCTIVE_FS',
                        'severity': 'HIGH',
                        'message': f"Recursive directory deletion via shutil.{attr}()",
                        'snippet': self._get_snippet(node.lineno)
                    })

            # Builtin dynamic reflection bypass
            if isinstance(val, ast.Name) and val.id in ('builtins', '__builtins__'):
                if attr in ('eval', 'exec', '__import__'):
                    self.findings.append({
                        'file': self.filepath,
                        'line': node.lineno,
                        'category': 'AST_DANGEROUS_CALL',
                        'severity': 'CRITICAL',
                        'message': f"Obfuscated dynamic execution via builtins.{attr}",
                        'snippet': self._get_snippet(node.lineno)
                    })

        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        # 1. Bare except: catches system exit/interrupts and masks fatal runtime failures
        if node.type is None:
            self.findings.append({
                'file': self.filepath,
                'line': node.lineno,
                'category': 'AST_BARE_EXCEPT',
                'severity': 'HIGH',
                'message': "Bare 'except:' handler detected. Catches system exit and masks fatal runtime failures.",
                'snippet': self._get_snippet(node.lineno)
            })
        elif isinstance(node.type, ast.Name) and node.type.id in ('BaseException',):
            self.findings.append({
                'file': self.filepath,
                'line': node.lineno,
                'category': 'AST_BARE_EXCEPT',
                'severity': 'HIGH',
                'message': "Broad 'except BaseException:' handler detected. Catches system exit and masks fatal runtime failures.",
                'snippet': self._get_snippet(node.lineno)
            })

        # 2. Silent exception swallow with only pass or no-op constant
        if len(node.body) == 1:
            is_pass = isinstance(node.body[0], ast.Pass)
            is_noop = isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, (ast.Constant,))
            if is_pass or is_noop:
                is_broad = node.type is None or (isinstance(node.type, ast.Name) and node.type.id in ('Exception', 'BaseException'))
                if is_broad:
                    prev_snippet = self._get_snippet(node.lineno - 1) if node.lineno > 1 else ""
                    curr_snippet = self._get_snippet(node.lineno)
                    if "reconfigure" not in prev_snippet and "reconfigure" not in curr_snippet:
                        self.findings.append({
                            'file': self.filepath,
                            'line': node.lineno,
                            'category': 'AST_SILENT_EXCEPTION_SWALLOW',
                            'severity': 'LOW',
                            'message': "Broad exception swallowed with silent 'pass' without logging or telemetry",
                            'snippet': self._get_snippet(node.lineno)
                        })
        self.generic_visit(node)


SecurityASTVisitor = ASTSecurityVisitor


def scan_unicode_trojan(filepath: str) -> List[str]:
    """
    Scans a single file for Unicode Trojan Source (BiDi overrides) and hidden/zero-width formatting characters.
    Pure Python standard library implementation.
    """
    violations: List[str] = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for lineno, line in enumerate(f, 1):
                for ch in line:
                    codepoint = ord(ch)
                    # BiDi override characters and isolates (U+202A - U+202E, U+2066 - U+2069)
                    if (0x202A <= codepoint <= 0x202E) or (0x2066 <= codepoint <= 0x2069) or ch in BIDI_CHARS:
                        desc = BIDI_CHARS.get(ch, "BiDi control char")
                        violations.append(f"{filepath}:{lineno}: BiDi Trojan override {desc} (U+{codepoint:04X})")
                    # Zero-width / hidden formatting characters (Category Cf)
                    elif (unicodedata.category(ch) == 'Cf' and ch not in ('\t', '\n', '\r')) or ch in ZERO_WIDTH_CHARS:
                        if ch in ('\u200c', '\u200d'):
                            idx = line.find(ch)
                            if 0 < idx < len(line) - 1:
                                prev_cat = unicodedata.category(line[idx - 1])
                                next_cat = unicodedata.category(line[idx + 1])
                                if prev_cat in ('So', 'Sk', 'Cn', 'Cs') or next_cat in ('So', 'Sk', 'Cn', 'Cs') or ord(line[idx - 1]) > 0x1F000 or ord(line[idx + 1]) > 0x1F000:
                                    continue
                        desc = ZERO_WIDTH_CHARS.get(ch, "Hidden formatting char")
                        violations.append(f"{filepath}:{lineno}: Hidden/Trojan formatting char {desc} (U+{codepoint:04X})")
    except Exception as e:
        violations.append(f"{filepath}:1: Error reading file: {e}")
    return violations



class SecurityBaseline:
    def __init__(self, baseline_path: str):
        self.baseline_path = baseline_path
        self.suppressed_hashes: Set[str] = set()
        self.suppression_rules: List[Dict[str, str]] = []
        self.load()

    @staticmethod
    def compute_fingerprint(rel_path: str, category: str, snippet: str) -> str:
        norm_snippet = re.sub(r'\s+', ' ', snippet.strip())
        key = f"{rel_path.replace(os.sep, '/')}:{category}:{norm_snippet}"
        return hashlib.sha256(key.encode('utf-8')).hexdigest()

    def load(self):
        if os.path.exists(self.baseline_path):
            try:
                import fnmatch
                with open(self.baseline_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.suppressed_hashes = set(data.get('fingerprints', []) + data.get('suppressed_fingerprints', []))
                    self.suppression_rules = data.get('rules', [])
            except Exception:
                self.suppressed_hashes = set()
                self.suppression_rules = []

    def is_suppressed(self, rel_path: str, category: str, fingerprint: str) -> bool:
        if fingerprint in self.suppressed_hashes:
            return True
        import fnmatch
        norm_path = rel_path.replace(os.sep, '/')
        for r in self.suppression_rules:
            pattern = r.get('path', '*')
            cat = r.get('category') or r.get('id', '*')
            if (cat == '*' or cat == category or fnmatch.fnmatch(category, cat)) and fnmatch.fnmatch(norm_path, pattern):
                return True
        return False

    def save(self, findings: List[Dict[str, Any]], root_dir: str):
        new_hashes = set(self.suppressed_hashes)
        for item in findings:
            rel = os.path.relpath(item['file'], root_dir).replace(os.sep, '/')
            fp = self.compute_fingerprint(rel, item['category'], item.get('snippet', ''))
            new_hashes.add(fp)

        with open(self.baseline_path, 'w', encoding='utf-8') as f:
            json.dump({
                'version': 1,
                'rules': self.suppression_rules,
                'fingerprints': sorted(list(new_hashes)),
                'total_count': len(new_hashes)
            }, f, indent=2)


class SecurityAuditor:
    def __init__(self, root_dir: str, baseline_file: Optional[str] = None):
        self.root_dir = os.path.abspath(root_dir)
        if baseline_file:
            self.baseline_path = baseline_file
        else:
            self.baseline_path = os.path.join(self.root_dir, '.security-baseline.json')
            if not os.path.exists(self.baseline_path):
                # Also check parent directory if root_dir is .agents
                parent_baseline = os.path.join(os.path.dirname(self.root_dir), '.security-baseline.json')
                if os.path.exists(parent_baseline):
                    self.baseline_path = parent_baseline
        self.baseline = SecurityBaseline(self.baseline_path)

    def scan_file(self, filepath: str) -> List[Dict[str, Any]]:
        findings = []
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.splitlines()
        except Exception as e:
            return [{
                'file': filepath,
                'line': 1,
                'category': 'READ_ERROR',
                'severity': 'MEDIUM',
                'message': f"Could not read file: {e}",
                'snippet': ''
            }]

        rel_path = os.path.relpath(filepath, self.root_dir).replace(os.sep, '/')

        # 1. Unicode Trojan Source & Zero-Width Scan
        for line_num, line in enumerate(lines, 1):
            for char in line:
                codepoint = ord(char)
                if (0x202A <= codepoint <= 0x202E) or (0x2066 <= codepoint <= 0x2069) or char in BIDI_CHARS:
                    desc = BIDI_CHARS.get(char, "BiDi control char")
                    findings.append({
                        'file': filepath,
                        'line': line_num,
                        'category': 'UNICODE_TROJAN_SOURCE',
                        'severity': 'CRITICAL',
                        'message': f"Bidirectional control character detected: {desc} (U+{codepoint:04X})",
                        'snippet': line.strip()
                    })
                elif (unicodedata.category(char) == 'Cf' and char not in ('\t', '\n', '\r')) or char in ZERO_WIDTH_CHARS:
                    # Ignore ZWJ/ZWNJ when part of legitimate emoji or cursive script
                    if char in ('\u200c', '\u200d'):
                        # Check surrounding characters for emoji/pictographs
                        idx = line.find(char)
                        is_emoji_zwj = False
                        if 0 < idx < len(line) - 1:
                            prev_cat = unicodedata.category(line[idx - 1])
                            next_cat = unicodedata.category(line[idx + 1])
                            if prev_cat in ('So', 'Sk', 'Cn', 'Cs') or next_cat in ('So', 'Sk', 'Cn', 'Cs') or ord(line[idx - 1]) > 0x1F000 or ord(line[idx + 1]) > 0x1F000:
                                is_emoji_zwj = True
                        if is_emoji_zwj:
                            continue
                    desc = ZERO_WIDTH_CHARS.get(char, "Hidden formatting char")
                    findings.append({
                        'file': filepath,
                        'line': line_num,
                        'category': 'UNICODE_ZERO_WIDTH',
                        'severity': 'HIGH',
                        'message': f"Hidden zero-width character detected: {desc} (U+{codepoint:04X})",
                        'snippet': line.strip()
                    })

        # 2. Prompt Injection & Escape Scan (Markdown, Text, Prompts)
        if filepath.endswith(('.md', '.txt', '.prompt', '.json', '.yaml', '.yml')):
            for line_num, line in enumerate(lines, 1):
                for pattern, cat, msg, sev in SUSPICIOUS_PROMPT_PATTERNS:
                    if pattern.search(line):
                        findings.append({
                            'file': filepath,
                            'line': line_num,
                            'category': cat,
                            'severity': sev,
                            'message': msg,
                            'snippet': line.strip()
                        })

        # 3. Python AST Vulnerability Scan
        if filepath.endswith('.py'):
            try:
                tree = ast.parse(content, filename=filepath)
                visitor = ASTSecurityVisitor(filepath, lines)
                visitor.visit(tree)
                findings.extend(visitor.findings)
            except SyntaxError:
                pass  # Ignore template files or incomplete snippets

        return findings

    def audit_directory(self, target_dir: Optional[str] = None, exclude_dirs: Optional[Set[str]] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        if target_dir is None:
            target_dir = self.root_dir

        if exclude_dirs is None:
            exclude_dirs = {'.git', 'node_modules', '__pycache__', '.system_generated', 'scratch', 'build', 'dist'}

        all_active: List[Dict[str, Any]] = []
        all_suppressed: List[Dict[str, Any]] = []

        valid_exts = ('.py', '.md', '.json', '.yaml', '.yml', '.txt', '.js', '.ts', '.dart')

        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.git')]
            for file in files:
                if file.endswith(valid_exts):
                    fp = os.path.join(root, file)
                    file_findings = self.scan_file(fp)
                    for item in file_findings:
                        rel = os.path.relpath(item['file'], self.root_dir).replace(os.sep, '/')
                        fp_hash = self.baseline.compute_fingerprint(rel, item['category'], item.get('snippet', ''))
                        if self.baseline.is_suppressed(rel, item['category'], fp_hash):
                            all_suppressed.append(item)
                        else:
                            all_active.append(item)

        return all_active, all_suppressed
