---
name: self-evolve
description: >-
  Post-task reflection and deterministic learning loop to extract patterns and prevent recurring mistakes. Use when tasks fail repeatedly, after resolving complex bugs, or when extracting new rules into LEARNINGS.md.
---

# 🧠 Self-Evolve (Mechanical Learning & Reflection Loop)

This workflow defines how the agent ecosystem learns and updates itself to prevent recurring mistakes.

## 1. ERROR EXTRACTION (SYNCHRONOUS)
- [ ] **Trace Extraction**: If a tool call fails (Exit Code > 0) or the user corrects you, mechanically extract the error trace into an XML block `<error_trace>`.
- [ ] **Root Cause Analysis**: Identify if the failure was due to a missing rule, contradictory instruction, or a missing context link.

## 2. MEMORY WRITE (PERSISTENCE)
- [ ] **Update Learnings**: Use the `replace_file_content` or `write_to_file` tool to inject the finding into `.agents/LEARNINGS.md`. Do not wait or queue this action.

## 3. HUMAN-CURATED SKILL EVOLUTION (ANTI-DRIFT & EXECUTABLE PROMOTION)
- [ ] **Evolve Rule (Drafting)**: If a missing or contradictory rule caused the error, you MUST NOT blindly overwrite the rule. Instead, draft the proposed change in `LEARNINGS.md`.
- [ ] **Executable Verification Mandate (Anti-Graveyard Gate)**:
  - Text-only rules without code checks are treated as informal advisories, NEVER promoted to permanent core guardrails.
  - To graduate from `LEARNINGS.md` into an active rule (`.agents/rules/`), the rule MUST include an executable mechanical check:
    1. **AST Pattern Check**: In `.agents/scripts/core/security.py` (e.g., banning an unsafe syntax pattern), OR
    2. **Static/Integration Assertion**: In `.agents/scripts/commands/verify_agents.py` (e.g., schema, link, or path verification), OR
    3. **Deterministic Regression Test**: In `.agents/evals/` or test harness.
- [ ] **Developer Review**: Present the drafted rule AND its mechanical verification test to the developer. Ask for explicit approval.
- [ ] **Promotion**: If the developer approves and the mechanical test passes, apply the changes to the target skill or rule file.

## 3.5. OFFENSIVE OPTIMIZATION (SUCCESS LOOP)
> **ESCAPE HATCH**: Maximum 1 optimization proposal per session. If already triggered once, skip this step.
- [ ] **Token & Path Audit**: If a task succeeds flawlessly, analyze the session for token waste, redundant tool calls, or slow paths.
- [ ] **Propose Compression**: If inefficiency is found, proactively synthesize a skill compression patch (Darwinian evolution driven by optimization, not just failure).

## 4. PATTERN RECOGNITION & SYNTHESIS (DISCOVER)
> **CIRCUIT BREAKER**: Maximum 2 autonomous synthesis operations per session. Beyond that, queue for next session.
- **CRITICAL ACTION**: **Pattern Scan**: At the end of a session, execute `grep_search` on BOTH `.agents/LEARNINGS.md` AND `MEMORY.md` (specifically for `<friction-data>` tags) NOW for repetitive manual tasks to fuse short-term and long-term friction.
- **CRITICAL ACTION**: **Synthesis Matrix (HITL Gate)**: 
  - If a pattern is found, determine its type BEFORE creation:
    - **Rule**: Dictates general AI behavior (e.g., "always use X"). Destination: `.agents/rules/`. **REQUIRES HUMAN APPROVAL via `[DO: YES]` before creation.**
    - **Procedural Playbook / Skill**: Step-by-step situational operation. Destination: `.agents/skills/` (or nested Tier-3 `references/`). Can be generated autonomously.
    - **Skill**: Relies on specific API/Tooling. Destination: `.agents/skills/`. Can be generated autonomously.
- [ ] **Generate Asset**: Use `.agents/templates/custom-rule.template.md` (or equivalent structure) to generate the new file. **WARNING:** Do NOT attach `activation: always on` frontmatter unless it is an explicitly approved Rule.
- [ ] **Integrate & Self-Audit**: Update JIT triggers and ensure the new file is indexed correctly (Rules in `RULES_INDEX.md`). If modifying `.agents/` engine itself, verify against `.agents/skills/meta-agent-admin/references/meta-agent-audit.md` and ensure `python .agents/scripts/orion.py verify` returns Exit Code 0. You MUST execute `python .agents/scripts/orion.py orion_ops ingest` to store them back into `.orion/`.

## 📚 Mandatory Knowledge Routing (JIT References)
*If your current task intersects with these domains, you MUST execute `view_file` on the target BEFORE writing code:*

| If User Prompt/Task Relates To... | Immediately Load (view_file) |
| :--- | :--- |
| **Temporal Pulse, Activity-Based Cadence** | .agents/skills/self-evolve/references/temporal-pulse.md |

