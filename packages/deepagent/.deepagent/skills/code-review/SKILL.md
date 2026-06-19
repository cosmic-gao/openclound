---
name: code-review
description: Structured review of a snippet or a change. Use when the user asks to review/audit/check a piece of code or whether a PR has problems.
---

# Code review workflow

1. **Build context** — use `ls` / `glob` / `grep` / `read_file` to understand
   the changed files and their callers first; never judge a single file in
   isolation.
2. **Check by dimension**, highest severity first:
   - **Correctness**: boundary conditions, null/exception paths, concurrency
     and races, off-by-one.
   - **Security**: injection, broken access control, hardcoded secrets,
     unvalidated untrusted input.
   - **Performance**: N+1 queries, repeated computation, needless blocking.
   - **Maintainability**: naming, duplication, deep nesting, missing tests.
3. **Report per finding** — write "file:line → problem → why → suggested fix"
   and tag severity (blocker / important / nit).
4. **Disprove first** — for uncertain suspicions, verify with tools (read the
   source, run the tests) before asserting; avoid speculation.
5. **Summarize** — give a merge/no-merge call plus a list of must-fix items.

Report only real problems; if there are none, say "no blocking issues found"
rather than padding the list.
