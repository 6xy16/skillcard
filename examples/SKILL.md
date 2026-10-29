---
name: commit-message
description: Write conventional-commit messages from a git diff. Use when the user asks to commit, write a commit message, or summarize staged changes.
when_to_use: User asks to create a commit message or commit staged changes.
license: MIT
---

# Commit Message Writer

Generate a conventional-commit style message from the current `git diff --staged`.

## Steps

1. Run `git diff --staged` and read the changes.
2. Identify the type: feat, fix, refactor, docs, test, chore.
3. Write a one-line summary (max 72 chars), imperative mood.
4. Add a body only if the change needs context.

## Output format

Return ONLY the commit message text, no commentary.
First line: `type(scope): summary`.

## Examples

Input diff adds a login endpoint -> `feat(auth): add login endpoint with JWT`
