# Security Policy

skillcard is a quality-scoring tool for Agent Skills. Its own security posture
matters as much as the skills it scores.

## Reporting a vulnerability

If you find a security issue — especially in the L3 injection detection, the
SKILL.md parser, or anything that could let a malicious skill manipulate its
score — please **do not open a public issue**.

Report it privately via a GitHub security advisory (the **Report a vulnerability**
button on the Security tab), or email <2408080112@hhu.edu.cn>.

Please include:

- A minimal reproducing `SKILL.md` or input file
- The `skillcard` version and Python version
- The expected vs. actual result

We will acknowledge within 3 business days and aim to resolve confirmed issues
promptly, with credit given in the changelog if you wish.

## Scope

In scope: prompt-injection / judge-gaming detection bypasses, parser
vulnerabilities, and any path that lets untrusted `SKILL.md` content cause
arbitrary code execution or file access outside the output directory.

Out of scope: issues requiring the user to already have arbitrary code
execution, and denial-of-service via unreasonably large inputs (though reports
are still welcome).

## Reporting in the tool itself

The `result.json` and warning output intentionally never echo secrets. Do not
commit a `SKILLCARD_API_KEY` to version control — it is read from the
environment only, and `.env` files are gitignored.
