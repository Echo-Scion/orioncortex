---
description: Mandatory and optional prerequisites.md for the agent ecosystem and their explicit fallback strategies.
activation: when a tool or command fails
version: 0.0.6
---

# 🛠️ Prerequisites & Graceful Fallbacks

To maintain a "plug and play" environment while avoiding brittle failures, this ecosystem relies on Graceful Fallbacks. If an advanced tool is unavailable on the host machine, the AI **MUST** gracefully degrade to native tools without halting.

## 1. RTK (Rust Token Killer)
- **Role**: Token-optimized CLI proxy for commands. Used specifically for **AST Hollowing** (`rtk read <file> --level aggressive`) to read large files without burning context.
- **Prerequisite**: Installed globally via cargo or binary.
- **Fallback**: If `rtk` commands fail (e.g., `command not found`), **immediately fallback to native tools**:
  - Instead of `rtk read <file> --level aggressive`, use the native `grep_search` tool to find signatures, or `view_file` with narrow `startLine`/`endLine` parameters.
  - Instead of `rtk grep`, use the native `grep_search` tool.

## 2. Orion (Agent Memory & Brain Graph)
- **Role**: Context syncing and knowledge indexing via the `orion.py` CLI.
- **Prerequisite**: Python environment.
- **Fallback Chain**:
  1. **Primary**: Use the local python bridge: `python .agents/scripts/orion.py`.
  2. **Fallback**: If Python fails entirely, use native `grep_search` on the `.orion/` or `.agents/` directories to find context manually.

## 3. Ollama (Local AI Coprocessor)
- **Role**: Zero-cloud local embeddings, binary classification, and pre-distillation (`127.0.0.1:11434`).
- **Prerequisite**: Local Ollama daemon running with designated lightweight models (e.g., Llama 3.2, Qwen 2.5, or Nomic embeddings).
- **Fallback Chain**:
  - If Ollama service is offline or unreachable:
    - Automatically fallback to SQLite FTS5 BM25 lexical search inside `.orion/orion.db`.
    - Rely on native heuristic scanners and static AST parsers in `orion.py`. Zero disruption to coding workflow.

## 4. Subagent Orchestration
- **Role**: Using `invoke_subagent` or similar MCP tools to spawn isolated agents.
- **Fallback**: If the `invoke_subagent` tool is not available in the current IDE environment (like Antigravity), handle the task yourself within the main thread, but aggressively use `grep_search` to keep your context window clean. Do not attempt to call missing tools.

## 5. ast-grep (Polyglot Structural AST Engine)
- **Role**: Concrete Syntax Tree (CST) structural search, linting, symbol extraction, and AST mutation across 20+ programming languages (Dart, TypeScript, Kotlin, Rust, Go, Python, Java, C++, Swift). Powers polyglot Repo-Mapping, structural code security scans, and mutation testing without regex fragility.
- **Prerequisite**: Installed globally via cargo (`cargo install ast-grep --locked`) or standalone binary (`ast-grep` / `sg`).
- **Fallback Chain**:
  - If `ast-grep` is not installed or command `ast-grep` / `sg` is unavailable:
    1. For Python source files, immediately fallback to Python's native standard library `import ast` parser.
    2. For non-Python files (Dart, TypeScript, Kotlin, Rust, Go), fallback gracefully to regex-based structural signature extraction in `scanner.py` and native `grep_search`. Zero disruption to coding workflow.

