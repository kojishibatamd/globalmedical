# Docs and AGENTS Sync Prompt

Update the project knowledge system based on the bundle below.

Scope:
- update docs/ files
- if behavior changes, update AGENTS.md
- otherwise do not modify AGENTS.md

Rules:
- keep AGENTS.md concise
- always put rules in AGENTS.md
- keep detailed knowledge in docs/
- minimal diff
- do not modify unrelated files
- preserve patent / NDA / pricing constraints

After changes:
1. list modified files
2. explain AGENTS.md changes if any
3. summarize new knowledge
4. do not commit or push
