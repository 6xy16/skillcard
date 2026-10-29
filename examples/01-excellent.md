---
name: code-reviewer
description: Review a pull request for code quality bugs, security issues, and style violations. Use when the user asks to review code, check a PR, or audit changes before merging.
when_to_use: User asks for a code review, PR review, or pre-merge audit.
license: MIT
---

# Code Reviewer

Review code changes for correctness, security, and maintainability issues.

## Steps

1. Read the changed files and the diff.
2. Identify bugs, edge cases, and security vulnerabilities.
3. Check naming, structure, and adherence to project conventions.
4. Categorize findings as: blocking, warning, nitpick.

## Output format

Return a structured review:

- **Blocking issues**: must-fix bugs or security problems
- **Warnings**: likely problems or risky patterns
- **Nitpicks**: style and readability suggestions

If no issues found, say "LGTM" with a one-line summary.

## Examples

Input: a PR that adds user login with SQL queries built via string concatenation.
Output:
- Blocking: SQL injection risk in login query — use parameterized statements.
- Warning: no rate limiting on login endpoint.
- Nitpick: function name `doLogin` should be camelCase `doLogin` → `handleLogin`.
