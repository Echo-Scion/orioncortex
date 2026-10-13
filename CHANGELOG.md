# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v0.0.1.html).

## [0.0.6] - 2026-10-14
### Added
- **Maintainer Workflow Isolation (Pattern A)**: Isolated maintainer-only `knowledge-sync` workflow into dedicated internal skill `.agents/skills/internal/`, excluding it from public git tracking and JIT routing while preserving developer automation.
- **Local Override Sandboxes in `.gitignore`**: Added `.agents/skills/internal/`, `.agents/archive/`, `.agents/scratch/`, `.agents/rules/local/*`, and `.agents/canons/local/*` to `.gitignore` to prevent private scripts and experiments from polluting public distribution repositories.

### Changed
- **100% Skills-Only Architecture Migration**: Sunset deprecated `.agents/workflows/` directory in favor of Antigravity modern Skills-only architecture, eliminating forward shims and slash command menu bloat. Safely archived legacy procedural workflows to `.agents/archive/workflows/` and rewired all 78 callers across rules, skills, templates, scripts, and docs.
- **Antigravity Skill Specification Alignment**: Audited and refined all 21 core domain skills to adhere strictly to Google Antigravity Skill specifications (declarative guidance, canonical workspace links, clean YAML metadata, and eliminated SOP fluff).
- **Single-Commit Clean Release Protocol**: Upgraded `knowledge-sync` release protocol to squash working branches into a single clean release commit for remote publishing while retaining granular local commits in `backup-local`.

### Fixed
- **Engine Reliability & Decoder Hardening**: Hardened Windows CP1252 subprocess decoders with UTF-8 fallback, eliminated broad AST exception swallows in Python engine scripts, and added automated JIT skill parity checks to `verify_agents.py`.

## [0.0.5] - 2026-10-13
### Added
- **Visual Craft & Aesthetic Archetypes**: Added 12 craft floor checks, category default refusals, and 3-axis dark mode compensation in `craft_floor.md`; codified 4 production design token systems (Minimalist, Neobrutalist, Warm Tactile, Cold Luxury) in `aesthetic_archetypes.md`; added asymmetric bento grid mathematics in `bento_and_macrostructures.md`.
- **Prose Authenticity & Anti-Slop Writing**: Codified 54-pattern tell taxonomy, binary contrast reversals, false agency elimination, and 3-tier lexical purge in `standards/prose_authenticity.md` and `core-guardrails.md § 11.2`; added automated regex detectors in `audit_aesthetics.py`.
- **Reverse Engineering & Evidence Quad Architecture**: Ingested Evidence Quad deduction (`[OBSERVATION]`, `[DERIVATION]`, `[INFERENCE]`, `[UNKNOWN]`), 7-target reverse engineering routing, and 4-step clean-room reconstruction loop into `integrity-sentinel/references/security.md`.
- **Dual-Level Graph Extraction & Entity Normalization**: Ingested zero-dependency dual-level retrieval taxonomy (Low-Level precision vs High-Level global synthesis), canonical entity typing (7 classes), TitleCase normalization, and N-ary relation decomposition into `brain-graph/references/knowledge-extraction.md`.

### Changed
- **Lessword Protocol Standard & Expansion**: Standardized telegraphic communication under native `lessword` mode across all rules, skills, templates, scripts, and docs; ingested ASD-STE100 floor, bounded status runs, subagent contracts, and frontmatter preservation.
- **Skill Consolidation into 21 Domain Pillars**: Consolidated 31 skills into 21 high-signal domain pillars, relocating discrete workflow skills to parent Tier-3 `references/` directories with backward-compatible forwarding shims in `.agents/workflows/`.
- **Master Routing Alignment**: Synchronized `GEMINI.md § 4`, `AGENTS.template.md § 4`, `AGENTS_INDEX.md`, and Documentation Volume V (`05-skill___persona___skills.md`) to 21 active pillars.
- **Orion Graph Hydration**: Pruned stale pages in `.orion/orion.db` and injected semantic triplets covering consolidated skill domains.


## [0.0.4] - 2026-10-12
### Fixed
- **Token Bloat & Target Exclusion in `scanner.py`**: Added `scratch/`, `.orion/`, and `.gemini/` to default directory ignore lists across `cmd_targets`, `cmd_map`, and `cmd_tokens`, reducing token scan bloat by 95.4%.
- **Hook Lockfile PID Liveness in `auto_sync.py`**: Upgraded `.auto_sync_lock` to store PID and verify process liveness with `psutil`/`os.kill`, eliminating dead lock hangs and isolating sync logs to `.orion/working/`.
- **Pre-Invocation Hook Portability in `hooks.json`**: Replaced fragile inline escaped `python -c` execution with clean direct script entrypoint.

## [0.0.3] - 2026-10-11
### Added
- **Full Absorption of 9 Ecosystem Repositories**: Absorbed visual aesthetics, static AST integrity, multi-agent harness, SWE discipline, memory consolidation, and curated 12-discipline capabilities into `.agents/` with 100% brand sanitization and pure Python stdlib portability.
- **Modular Workflow Decomposition**: Decomposed oversized workflows `audit-and-test.md` and `app-lifecycle.md` into modular sub-workflows (`strict-tdd.md`, `systematic-debugging.md`, `code-review.md`, `project-init.md`, `app-builder.md`, `feature-sunset.md`) ensuring progressive context disclosure (<7KB per workflow).
- **Security AST Integrity & AST Truth Scanner**: Added Trojan Source Unicode detection (`Cf` category) and credential/reflection/shell AST security visitors in `security.py`; added truth assertion verification and 8pt spatial grid checks in `audit_aesthetics.py`.
- **Episodic Observation Engine**: Implemented pure Python observation parser for JSONL transcripts in `consolidate.py` supporting `[decision]`, `[bugfix]`, `[security_alert]`, `[sensitive]` needle observations.

### Changed
- **JIT Knowledge Routing Alignment**: Updated `GEMINI.md`, `AGENTS.template.md`, and `06-workflow___sop.md` to index all 18 standard operating procedures.
- **Rule Eviction Protection**: Registered new modular workflows in `rule_eviction.py` protected assets.

## [0.0.2] - 2026-10-05
### Fixed
- **Hub Template Protection (`N06.1`)**: Guarded `push-upstream` against spoke framework resolution overwriting generic templates in `skills/` and `canons/`.
- **Heartbeat Guard (`A3`)**: Prevented spawn loops by converting `heartbeat.py` to a pure synchronous parser with regex-based entry parsing.
- **Handoff Protection (`H7`)**: Protected `handoff.md` against silent truncation in `nano_compressor.py`; writes to `.nano.md` by default unless explicitly forced.
- **Database Schema Auto-Migration (`R4`, `E1`)**: Auto-migrated `pages` columns (`fts_synced`, `ast_hash`) in `orion_ops.py` and added `source_path` to `edges` table for clean source-isolated triplet updates without destroying shared entity nodes.
- **UTF-8 Console Encoding on Windows (`N07.3`, `N06.3`, `H1`)**: Added UTF-8 stdout/stderr reconfigure to `auto_delegate.py`, `preflight_check.py`, `verify_agents.py`, `evolve.py`, and `adversarial.py`.
- **Pre-Agent-Wake Hook Resolution (`A1`, `E4`)**: Resolved hook command dynamically from workspace root or `.agents/` directory in `hooks.json`.
- **Link Verifier Robustness (`N04.1`, `D2`)**: Hardened `verify_agents.py` to ignore backticked examples/template variables, validate `[[wikilinks]]`, and verify `view_file` targets; zero broken links.
- **Framework Template Expansion (`N07.1`, `G2`)**: Expanded `resolve_templates()` in `foundation.py` to resolve `{{PACKAGE_FILE}}`, `{{PACKAGE_MANAGER}}`, `{{TEST_RUNNER}}`, and `{project_name}` across stacks.
- **JIT Router Realignment (`N08.1`, `Check 3`)**: Resolved framework routes to active stack in root `GEMINI.md` and added missing `canons/micro/flutter.md`.
- **Memory Path Harmonization (`G3`, `I1`)**: Standardized episodic memory location to `context/00_Strategy/MEMORY.md` across `foundation.py`, `compress_memory.py`, and `evolve.py`.
- **Documentation Truth Alignment (`I2`, `G1`, `D1`, `H4`)**: Aligned `README.md` and docs to accurately describe pre-invocation context injection, deterministic pattern mining, and autonomous behavioral mandates.

## [0.0.1] - 2026-10-03
### Added
- **Initial Release**: Portable Brainvibing Foundation.
- **Universal Master BIOS**: Standardized `GEMINI.md` and `AGENTS.template.md` featuring inlined core guardrails, tier-aware session bootstrap, built-in English First & Lessword protocol, and JIT knowledge routing.
- **4 Lean Pillars Context Architecture**: Canonical knowledge structure in `context/` (`00_Strategy/BLUEPRINT.md`, `01_Product/ROADMAP.md`, `02_Creative/STYLE_GUIDE.md`, `03_Tech/ARCHITECTURE.md`) with 82-file SaaS registry standard.
- **Orion GraphRAG Engine**: Local SQLite FTS5 lexical search, dynamic triplet graph (`nodes`, `edges`, `contradictions`), and token-efficient compiled rule matrices in `.orion/matrix/`.
- **Dual-Stack Network Resolver**: Auto-resolving Ollama connectivity via IPv4 `127.0.0.1` -> IPv6 `::1` -> `localhost` with `.env` self-healing.
- **Cross-Platform Resiliency**: Hardware-aware dynamic auto-scaling supporting macOS Apple Silicon unified memory, Windows CP1252 UTF-8 reconfigure, and POSIX agnostic execution hooks.
- **Micro-Fix Swarm & Delegation**: Local multi-thread speculative syntax fixer and Adversarial Twin TDD verification wrappers.

