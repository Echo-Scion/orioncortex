# VOLUME IX: HUMAN-CURATED LEARNING LOOP

---

## Chapter 21: Friction Mining (Manual Curation)

### 21.1. Mechanism
1. AI makes an error → terminal returns Exit Code > 0.
2. Error is written to `LEARNINGS.md` as a draft lesson.
3. The AI reviews friction logs to propose structural changes to `.agents/rules/`.
4. The agent writes a post-mortem and suggests preventive rules for the developer to review.

### 21.2. Developer Review & Promotion
New rules are not applied autonomously to prevent policy drift. 
1. **Draft**: AI proposes a rule change in `LEARNINGS.md`.
2. **Review**: The developer manually reviews the proposed change.
3. **Promotion**: If the rule is sound and globally applicable, the developer moves the rule from `LEARNINGS.md` into the formal `GEMINI.md` or `.agents/rules/` directory.

### 21.3. Cross-Project Knowledge Transfer
Once a rule is manually approved in one project, the developer can choose to port it upstream to the Hub repository, where it will be distributed to future projects. We strictly avoid autonomous genetic merging.

---
