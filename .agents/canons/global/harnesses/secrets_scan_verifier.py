import os
import sys
import re
import argparse

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


# Common patterns for secrets
SECRET_PATTERNS = {
    'AWS Access Key': r'AKIA[0-9A-Z]{16}',
    'Stripe Standard Key': r'sk_live_[0-9a-zA-Z]{24}',
    'Stripe Test Key': r'sk_test_[0-9a-zA-Z]{24}',
    'Google API Key': r'AIza[0-9A-Za-z\-_]{35}',
    'Bearer Token': r'Bearer\s+[a-zA-Z0-9\-\._~+/]+=*',
    'Generic Private Key': r'-----BEGIN PRIVATE KEY-----',
    'OpenAI API Key': r'sk-[a-zA-Z0-9]{48}',
    'GitHub Token': r'ghp_[a-zA-Z0-9]{36}',
    'Telegram Bot Token': r'[0-9]{9,10}:[a-zA-Z0-9_-]{35}',
    'JWT / Supabase Key': r'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\.[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+'
}

IGNORE_DIRS = {'.git', 'node_modules', '__pycache__', '.orion', 'venv', 'env', 'scratch', 'build', 'dist'}

def scan_file(filepath):
    # Avoid scanning self to prevent matching own regex patterns
    if os.path.basename(filepath) == 'secrets_scan_verifier.py':
        return []
    findings = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f, 1):
                for key_name, pattern in SECRET_PATTERNS.items():
                    if re.search(pattern, line):
                        # Simple masking to prevent logging the actual secret
                        findings.append((i, key_name))
    except Exception as e:
        sys.stderr.write(f"[WARN] Secrets scan could not read {filepath}: {e}\n")
    return findings

def main():
    parser = argparse.ArgumentParser(description="Scan for hardcoded secrets.")
    parser.add_argument("--path", default=".", help="Directory to scan")
    args = parser.parse_args()

    target_dir = os.path.abspath(args.path)
    total_findings = 0

    print(f"Scanning for secrets in: {target_dir}...")
    for root, dirs, files in os.walk(target_dir):
        # Exclude ignored directories, but allow .agents
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and (not d.startswith('.') or d == '.agents')]
        
        for file in files:
            # Skip likely binary, minified, or sample/example files
            if file.endswith(('.jpg', '.png', '.mp4', '.sqlite', '.db', '.min.js', '.map', '.example')) or file.startswith('.env.example'):
                continue
                
            filepath = os.path.join(root, file)
            findings = scan_file(filepath)
            if findings:
                rel_path = os.path.relpath(filepath, target_dir)
                for line_num, key_name in findings:
                    print(f" [FAIL] Found possible {key_name} in {rel_path} on line {line_num}")
                total_findings += len(findings)

    if total_findings > 0:
        print(f"\n [ERROR] {total_findings} potential secret(s) found. Release blocked.")
        sys.exit(1)
    else:
        print("\n [OK] No secrets detected.")
        sys.exit(0)

if __name__ == "__main__":
    main()
