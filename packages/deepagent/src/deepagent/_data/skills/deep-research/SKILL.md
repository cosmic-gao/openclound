---
name: deep-research
description: Multi-source research on a topic that produces a cited report with conclusions. Use when the user asks to research, compare, survey, or fact-check a topic.
---

# Deep research workflow

Drive the work through these steps, writing intermediate notes to the file
system (so they survive context summarization and can be reused across turns):

1. **Decompose** — use `write_todos` to break the topic into 3–6 independently
   answerable sub-questions.
2. **Search in parallel** — research each sub-question, preferring search/fetch
   tools provided by the caller. Append each source's "citation + key fact" to
   `notes/<sub-question>.md`.
3. **Cross-verify** — back every key conclusion with at least two independent
   sources. On conflict, record the disagreement and a credibility judgement;
   never rely on a single source.
4. **Synthesize** — fold verified facts into conclusions; separate "fact",
   "inference", and "uncertain".
5. **Report** — write `report.md` as "executive summary → per-topic argument →
   source list", citing the source for every conclusion.

Before finishing, self-check: is every sub-question answered? Does every key
conclusion have a source? Did you miss any counter-evidence?
