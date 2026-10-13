# 🧠 Portable Brainvibing — Plug-and-Play AI Infrastructure

[![Version](https://img.shields.io/badge/version-v0.0.6-blue)](VERSION)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Runtime Tested](https://img.shields.io/badge/Runtime%20Tested-Antigravity%20%2F%20Gemini-brightgreen)](#-the-core-philosophy)
[![Porting Targets](https://img.shields.io/badge/Porting%20Targets-Cursor%20%7C%20Claude%20%7C%20Windsurf%20%7C%20Copilot%20(WIP)-orange)](#-quickstart--deployment)

A plug-and-play `.agents` ecosystem that transforms generic AI coding assistants into **deterministic engineering instruments**. This repository contains the **Universal Framework**—a language-agnostic, OS-agnostic blueprint designed to enforce absolute reproducibility and minimize AI hallucination.

> ⚠️ **PERSONAL DOGFOODING REPOSITORY & RADICAL CANDOR**: 
> This repository is a personal engineering framework shared openly with the community. It is 100% architected and iterated through AI pair-programming. All core mechanics—deterministic Python AST gates, SQLite GraphRAG, token clipping, and TDD rollbacks—are actively dogfooded daily in Google Antigravity (Gemini). Scaffolding generators for Cursor, Windsurf, Claude Code, and Copilot are provided, but empirical multi-turn validation on those platforms is currently an ongoing open-source experiment.

---

## 📖 Table of Contents
- [The Core Philosophy](#-the-core-philosophy)
- [Why AI Coding Assistants Fail (Before vs After)](#-why-ai-coding-assistants-fail-before-vs-after)
- [Universal Mechanics & Principles](#-universal-mechanics--principles)
- [Autonomous Pipeline Logic (Output-as-Input)](#-autonomous-pipeline-logic-output-as-input)
- [DevSecOps & Algorithmic Governance](#-devsecops--algorithmic-governance)
- [Architecture & Taxonomy](#-architecture--taxonomy)
- [Quickstart & Deployment](#-quickstart--deployment)
- [Credits & External Modules](#-credits--external-modules)

---

## 💡 The Core Philosophy
AI coding assistants suffer from three structural flaws when dealing with complex codebases:
1. **Agentic Amnesia**: They forget rules defined earlier in the context window.
2. **Attention Decay**: They lose track of the overarching goal during complex, multi-file tasks.
3. **Token Inefficiency**: They waste context window space explaining basic concepts or reading raw terminal logs.

The Universal Framework mitigates this by pairing **autonomous behavioral mandates** (strict prompt-level guardrails) with **mechanical validation scripts** (Python linters, link verifiers, and preflight security checks).

---

## ⚡ Why AI Coding Assistants Fail (Before vs After)

| Problem (Vanilla LLM in Cursor / Copilot / Gemini) | Mechanical Solution (Portable Brainvibing Engine) |
| :--- | :--- |
| **"Should work now!"**: AI claims success without running tests or inspecting output. | **Iron Evidence Law**: Success claims strictly forbidden without verified Exit Code 0 and stdout/stderr assertions in the same turn. |
| **Untested Bloat**: AI writes 300 lines of complex code before creating any test harness. | **Compulsory TDD Rollback**: Implementation code written before a failing test triggers an automated `git stash` rollback. |
| **Runaway Guessing Loops**: AI guesses 15 times, burns $5 in API tokens, and still fails. | **3-Attempt Circuit Breaker**: Hard execution halt after 3 consecutive failures; forces voluntary yield to human engineer. |
| **Context Exhaustion**: 1,000 lines of compiler noise or `npm` output flood the prompt. | **RTK & Lessword Protocol**: CLI proxy filters 80%+ log noise; telegraphic prompts compress context by ~75%. |
| **Agentic Amnesia**: AI forgets architectural decisions and types chosen 2 hours ago. | **Zero-Cloud Local GraphRAG**: Pure SQLite FTS5 + JSON vector embeddings recall past decisions in 15ms on an 8GB laptop. |

---

## ⚙️ Universal Mechanics & Principles

These core concepts bridge custom architectural terminology with standard software engineering patterns:

### 1. ⚡ The Lessword Protocol (Telegraphic Context Compression)
A high-efficiency communication mode that structurally eliminates polite AI fluff while preserving 100% technical substance, exact code blocks, and blueprints.
- **AI before (140 tokens):** *"I apologize for the confusion! Let's go ahead and fix the null pointer issue by adding a check..."*
- **AI now (18 tokens):** `Auth crash. User null. Adding null-check in auth_service.dart#L42. Exit Code 0.` 
*Result: Context windows last longer. Compute cost drops significantly (~75% reduction).*
> **Default Behavior:** Built-in and active by default across technical turns to maximize token efficiency and prevent amnesia. Reverts to standard conversational English on demand when the user requests `"normal mode"` or `"stop lessword"`.


### 2. 🧠 IDE Agent Delegation & Modular CLI (Deterministic `run_command` Protocol)
Instead of forcing the AI to manually search for rules or parse fragile CLI outputs, the system relies on structured IDE Agent Delegation. Your IDE AI explicitly triggers specialized CLI tools via standard `run_command` protocols. The standard CLI (`orion.py`) acts as the primary interface for both background cron-jobs and human/AI-driven task orchestration.

### 3. 📡 The Omni-Buffer (IDE Tab State & Memory Sync)
To prevent the AI from hallucinating about which file the user is currently looking at, we utilize the `context.json` Omni-Buffer. Instead of heavy background daemons, a lightweight pre-invocation script reads the IDE's native metadata and silently writes the active tab state to the buffer. The AI reads it magically on its first turn—no manual copy-pasting required.

### 4. ⚔️ Adversarial Twin Protocol (Isolated Context Red-Team Auditing)
The AI is instructed to enter an attack/defend cycle by isolating contexts.
1. **The Builder**: Writes implementation code.
2. **The Sentinel**: A separately invoked agent (with a fresh context) designed specifically to break the implementation by writing a unit test.
3. **The Loop**: Mutate the code iteratively until the terminal outputs `Exit Code 0`.
*Note: This must be done across distinct agent contexts to prevent confirmation bias.*

### 5. ✂️ Output Filtering & Universal AST Ingestion (AST Structural Extraction)
Verbose terminal logs (e.g., `npm install` or `cargo build`) flood the AI's context window.
- **RTK (Rust Token Killer)**: Proxies all terminal commands and strips >80% of log output.
- **Universal AST Parser**: Before saving source code to the `.orion` SQLite database, the system performs shallow structural extraction. It uses a 3-tier engine: 1) Native Python `ast` for Python files, 2) C-bindings via `tree-sitter` for JS/TS/Dart, and 3) Regex heuristics as a last resort. This strips out deep logic and noise, reducing SQLite database bloat by 90%.
> **⚠️ REALITY CHECK (Anti-GIGO):** AST Ingestion causes "Agentic Blindness" because the AI cannot see the actual function implementation. Agents MUST use `view_file` to read the full source code before proposing any bug fixes to avoid hallucinations.

### 6. 🧬 Human-Curated Evolution Loop (Post-Mortem Ledger & Pattern Extraction)
*Core mechanical loops for knowledge retention:*
- **Contradiction Engine (Manual)**: Employs `orion.py context-lint` to detect collisions in the knowledge graph, requiring human review to resolve rule conflicts.
- **Activity-Based Temporal Pulse**: Replaces calendar-based summaries with activity-based epochs (Session/Milestone/Epoch), synthesizing memories cleanly even on paused projects.
- **Manual Upstream Contribution**: New learnings are drafted into `LEARNINGS.md`. If validated by the developer, they are merged into the central Foundation ruleset. We strictly avoid autonomous rule mutation to prevent policy drift.

### 7. 🦖 Hybrid SQLite Knowledge Graph (FTS5 BM25 + Flat Vectors + 1-Hop Traversal)
To bypass heavy vector databases and bloated background daemons, we use a hybrid semantic engine requiring zero C-extensions:
- **SQLite FTS5 + JSON Vectors**: Fast lexical search combined with native JSON vector embeddings. Cosine similarity is calculated in pure Python `math` to ensure 100% OS portability without `sqlite-vss` compilation errors.
- **Active 1-Hop Graph Traversal (`orion.db`)**: Explicit semantic linking of code symbols stored purely in SQLite `edges` and `nodes` tables. When a document is queried, the engine traverses 1-hop connected neighbors (outgoing, incoming, and semantic entity triplets) and automatically pulls connected assets into the active context packet.
- **Granular State Routing (NanoBrain)**: Natively integrated with Ollama (`nomic-embed-text` for vectors). Because small local LLMs are often unreliable ("dumb") for complex reasoning, we do not force them. Users can strictly configure state (e.g., `EMBED_ONLY`) to activate world-class vector search while keeping generative local LLMs fully disabled (**Graceful Degradation**), delegating deep logic to Cloud Agents and saving massive amounts of RAM.
> **⚠️ REALITY CHECK (Graceful Degradation Flaw):** If Ollama is offline, the Semantic Keyword Expansion fails entirely. This must be bypassed by forcing the Cloud Agent to mentally generate synonyms before querying the database (Fixed via Mental Semantic Expansion hook in Master BIOS).
- **Highly Portable OS-Agnostic Execution**: Most components run natively via standard `python` without hardcoded aliases, ensuring broad plug-and-play compatibility across Windows, macOS, and Linux virtual environments.
- **Native Obsidian Vault Integration**: The entire `.orion/` graph and `context/` directory are physically structured to be readable as an Obsidian Vault. The `linkify.py` script automatically injects `[[wikilinks]]` to bridge technical files with human notes.
- **Raw-to-Wiki Pipeline**: Unstructured data (meeting notes, raw text) dumped into `context/raw/` is automatically processed, tagged, and migrated to structured markdown in `context/wiki/` via the lightweight `raw_ingest.py` worker.
- **Proactive Git Hooks**: The Brain Graph does not wait for manual updates. A `.git/hooks/post-commit` hook automatically triggers `python .agents/scripts/orion.py brain sync` to ensure the AI's internal state is always synchronized with the latest commits.

### 8. 🌐 IDE-Agnostic Native Tooling (Abstract Slash-Command Dispatch)
The framework avoids vendor lock-in by utilizing an abstract tooling policy. Whether running inside Antigravity, Cursor, Copilot, or Windsurf, the AI is instructed to dynamically map abstract workflows ("ask the user", "execute long task") to its specific native slash-commands (like `/grill-me`, `/goal`, or `Composer Ask`).

### 9. 🛡️ Resilient Formal State Machine (Atomic Multi-Step Crash Recovery)
The `.agents` architecture strongly isolates **static environment data** from **active execution state**. A formal state machine engine (`execution_state.json`) tracks AI tasks and phase transitions. If the IDE crashes midway through a 20-file generation task, the Omni-Buffer hook catches the dangling state on the next boot and instructs the AI to resume exactly where it crashed.

---

## 🔄 Autonomous Pipeline Logic (Output-as-Input)

Skills and Subagents do not operate in a vacuum. The framework chains them together using a **State Machine**:
- **Strategist** writes `.orion/CONTEXT.md`.
- **Architect** ingests `CONTEXT.md` before generating `.orion/BLUEPRINT.md`.
- **Coder** reads `BLUEPRINT.md` and generates source code.

**The Unified Footer**: Every single AI response must end with a standard footer that automatically queues the exact next terminal command. The AI reads the Exit Code and executes the next state block.

---

## 🛡️ DevSecOps & Algorithmic Governance

We do not trust the AI to implicitly follow prompt rules. The Universal template enforces rules mechanically via Python scripts:

| Traditional Prompt | Universal Framework (Algorithmic Governance) |
| :--- | :--- |
| *"Don't commit API keys"* | **`orion.py preflight`** intercepts and throws `[FAIL]` if regex matches a key. |
| *"Follow the taxonomy"* | **`orion.py context-lint`** crashes if a file is created outside the approved mapping. |
| *"Don't break internal links"* | **`orion.py verify`** acts as a compiler for markdown, verifying all cross-references. |
| *"What file am I looking at?"* | **Omni-Buffer (`context.json`)** intercepts the IDE's native metadata to prevent the AI from modifying the wrong file. |
| *"Write tests first"* | **`.agents/skills/strict-tdd/SKILL.md`** triggers an automated `git stash` rollback if code changes before a failing test is proven. |

---

## 🏗️ Architecture & Taxonomy

The Foundation Hub repository is an empty, stack-agnostic template hub containing the core AI engine:

1. **`.agents/`** (The Agnostic Core / Foundation Brain)
   The baseline truth. Contains the core pipelines, the Lessword Protocol, DevSecOps Python scripts, and the overarching AI logic. 
2. **The Spokes (Target Projects & Consumers)**
   Target consumer projects deployed via `orion.py foundation deploy`. Spokes receive the `.agents/` runtime and a scaffolded `context/` knowledge base (4 Lean Pillars: `BLUEPRINT.md`, `ROADMAP.md`, `STYLE_GUIDE.md`, `ARCHITECTURE.md`).
3. **Runtime & Local State (Strictly Excluded from Hub Repo)**
   Local SQLite caches (`.orion/`), temporary working scratchpads (`scratch/`), and consumer project directories are completely excluded from git via root `/*` blacklisting.

```text
_foundation/
├── .agents/             # The Universal Foundation Engine (Brain)
│   ├── archive/         # Archived legacy assets and deprecated workflows
│   ├── canons/          # Immutable structural laws and recipes
│   ├── docs/            # Complete 12-volume Master Encyclopedia
│   ├── evals/           # Aesthetic and architectural evaluators
│   ├── hooks/           # Antigravity lifecycle hooks & Omni-Buffer
│   ├── rules/           # Context-aware guardrails (Security, Tiers, Memory)
│   ├── scripts/         # Modular CLI ecosystem (`orion.py`)
│   ├── skills/          # Domain expertise skills & procedural playbooks
│   └── templates/       # 12 DRY templates for IDE Master BIOS files
├── CHANGELOG.md         # Foundation Evolution History
├── GEMINI.md            # Master BIOS Template
├── LICENSE              # Open-Source License
├── PREREQUISITES.md     # Environment Setup
├── README.md            # Hub Overview
└── VERSION              # Engine Version
```

👉 **Full Documentation:** Explore the 12-volume Master Encyclopedia in [`.agents/docs/00-intro.md`](.agents/docs/00-intro.md).

### The Hub-and-Spoke Model

The framework operates as a distributed architecture to share knowledge across all your codebases:

- **The Hub (Foundation)**: Your global Second Brain storing universal engineering laws and skills.
- **The Spokes (Target Projects)**: Local `.agents` folders deployed to your apps, remaining tethered to the Hub.
- **Cross-Project Sync**: If the AI learns a new optimization in Project A, the developer can run `orion.py foundation push-upstream` to manually propose it to the Hub. When deployed to Project B, it instantly inherits those curated learnings.

---

## 🚀 Quickstart & Deployment

The Universal template can be injected into any repository (Node, Rust, Flutter, Python, Go) to align the AI workflow.

### 📌 Prerequisites
- **Python 3.10+** must be installed on your machine.
- Works best with **RTK** and a **Local LLM for Embeddings** (e.g. Ollama `nomic-embed-text`).
- Your target project must have a basic structure initialized.

### ⚡ 1. Direct Terminal Drop-In (Recommended)

In your target project directory:
```bash
# Clone the foundation engine into your target project as .agents
git clone https://github.com/Echo-Scion/portable-brainvibing.git .agents

# Run the deployment engine to scaffold IDE rules (GEMINI.md, CLAUDE.md, .cursorrules)
python .agents/scripts/orion.py foundation deploy --target .
```

To preview changes before modifying anything:
```bash
python .agents/scripts/orion.py foundation deploy --target . --dry-run
```

### 🤖 2. Agentic Installation (AI-Assisted)
If you prefer your AI agent to perform the deployment, copy and paste this prompt into your IDE chat (Gemini, Cursor, Copilot, Windsurf, Claude Code):

> *"Hey AI, please read the deployment manual at `[path-to-foundation]/.agents/DEPLOY_ME.md` and execute the python deployment engine to inject this foundation into my current project."*

👉 **Full Manual:** **[Agentic Deployment Guide (.agents/DEPLOY_ME.md)](.agents/DEPLOY_ME.md)**

### 🩺 Mechanical Health Verification
Run the diagnostic suite anytime to verify workspace integrity and rule compliance:
```bash
python .agents/scripts/orion.py verify_agents
```

---

## 🤝 Credits & External Modules

This foundation synthesizes principles from top open-source optimization tools:
- **[rtk-ai/rtk](https://github.com/rtk-ai/rtk)**: (Active Binary) Compresses and filters verbose terminal output.
- **[JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman)**: (Protocol) Telegraphic communication mapping for token reduction.
- **[morluto/rea](https://github.com/morluto/rea)**: (Protocol) Reverse engineering architecture, evidence-quad deduction, and binary-to-code clean-room reconstruction.


---
**License**: MIT

---
**Note**: Built and maintained actively by the author (dogfooded daily in Google Antigravity). Please support with a star!