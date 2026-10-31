"""L4: dynamic execution check.

L1/L2/L3 only *read* the SKILL.md. L4 is the first layer that *runs* the
skill: it executes the skill's steps in a local subprocess with a hard
timeout and output cap, then records whether the run completed, how long it
took, and what it emitted. This closes the loop from static check -> LLM
paper review -> actual execution.

Security model — READ BEFORE ENABLING
-------------------------------------

Running a SKILL.md means executing arbitrary, untrusted instructions on your
machine. This layer uses a subprocess boundary, NOT a container or VM:

- it DOES impose a wall-clock timeout and an output cap;
- it does NOT isolate the filesystem, network, or environment. A malicious
  skill can read files, write files, or make network calls as *you*.

Because of this, L4 is OFF by default and must be explicitly enabled with
``--run``. Only run skills you trust. If you need to evaluate untrusted
skills, use a disposable VM / container and run skillcard inside it.

This layer does not invent a real agent runtime: it shells out to whatever
interpreter the skill declares (default: bash), running the skill's own
steps as a script. "Task completion" is a coarse, honest signal — did the
process exit 0 within the timeout? It is not a verdict on output quality.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from skillcard.parser import SkillDoc

# A single execution is killed after this many seconds.
DEFAULT_RUN_TIMEOUT_SECONDS = 30

# stdout+stderr are truncated to this many bytes so a chatty/infinite skill
# cannot blow up memory or the result.json.
MAX_OUTPUT_BYTES = 64 * 1024

# Maps a frontmatter `runtime` value (or a guess from the skill name) to the
# interpreter used to execute the skill's steps. The skill body is written to
# a temp file and run as a script. Unknown runtimes fall back to bash.
RUNTIME_CMD: dict[str, list[str]] = {
    "bash": ["bash"],
    "sh": ["sh"],
    "python": ["python"],
    "python3": ["python3"],
    "python.py": ["python"],
}


@dataclass
class ExecutionResult:
    """Outcome of running a skill's steps in a local subprocess."""

    ran: bool = False           # False when L4 was skipped/disabled or no steps found
    runtime: str = "bash"
    completed: bool = False     # process exited 0 within the timeout
    exit_code: int | None = None
    timed_out: bool = False
    duration_seconds: float = 0.0
    stdout: str = ""
    stderr: str = ""
    truncated: bool = False     # output exceeded MAX_OUTPUT_BYTES
    command: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _detect_runtime(doc: SkillDoc) -> str:
    """Pick an interpreter from frontmatter `runtime`, else a name hint, else bash."""
    fm = doc.frontmatter
    for key in ("runtime", "language", "script"):
        val = fm.get(key)
        if val:
            name = str(val).lower()
            if name in RUNTIME_CMD:
                return name
            if "python" in name:
                return "python"
            if "bash" in name or "shell" in name or "sh" in name:
                return "bash"
    # Fall back to a name hint.
    name = doc.name.lower()
    if "python" in name or ".py" in name:
        return "python"
    return "bash"


def _extract_steps(doc: SkillDoc) -> list[str]:
    """Pull executable steps from the body.

    We look for code blocks (```...```) and numbered/`$`-prefixed lines as
    the closest thing SKILL.md has to an executable script. When there are no
    code blocks, there is nothing safe to run and L4 reports ``ran=False``.
    """
    steps: list[str] = []
    for m in re.finditer(r"```[^\n]*\n(.*?)```", doc.body, re.DOTALL):
        block = m.group(1).strip()
        if block:
            steps.append(block)
    return steps


def run_l4(doc: SkillDoc, timeout: float = DEFAULT_RUN_TIMEOUT_SECONDS) -> ExecutionResult:
    """Execute the skill's steps in a subprocess and record the outcome.

    Never raises: every failure mode (no steps, interpreter missing, timeout,
    non-zero exit) is captured in the returned ``ExecutionResult``.
    """
    steps = _extract_steps(doc)
    if not steps:
        return ExecutionResult(
            ran=False,
            warnings=["no executable steps (code blocks) found in skill body"],
        )

    runtime = _detect_runtime(doc)
    result = ExecutionResult(ran=True, runtime=runtime)
    result.command = RUNTIME_CMD.get(runtime, ["bash"])

    # Check the interpreter exists before spawning, so we report a clean
    # "interpreter missing" instead of a confusing FileNotFoundError traceback.
    try:
        subprocess.run(
            result.command + ["--version"],
            capture_output=True,
            check=False,
            timeout=10,
        )
    except FileNotFoundError:
        result.warnings.append(f"interpreter '{runtime}' not found on PATH")
        return result
    except subprocess.TimeoutExpired:
        result.warnings.append(f"interpreter '{runtime}' probe timed out")
        return result

    # Write the concatenated steps to a temp file and run it.
    script = "\n\n".join(steps) + "\n"
    start = time.monotonic()
    # Run in the skill's directory when it's a real file, else the cwd.
    try:
        cwd = Path(doc.path).resolve().parent if Path(doc.path).is_file() else Path.cwd()
    except OSError:
        cwd = Path.cwd()

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh" if runtime in ("bash", "sh") else ".py",
            encoding="utf-8", delete=False,
        ) as f:
            script_path = f.name
            f.write(script)

        try:
            proc = subprocess.run(
                result.command + [script_path],
                capture_output=True,
                check=False,
                timeout=timeout,
                cwd=str(cwd),
                text=True,
                errors="replace",
            )
            result.duration_seconds = round(time.monotonic() - start, 2)
            result.exit_code = proc.returncode
            result.completed = proc.returncode == 0
            result.stdout = proc.stdout or ""
            result.stderr = proc.stderr or ""
        except subprocess.TimeoutExpired:
            result.timed_out = True
            result.duration_seconds = round(time.monotonic() - start, 2)
            result.warnings.append(f"execution timed out after {timeout}s")
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass

    # Truncate combined output to the cap and mark it.
    total = result.stdout + result.stderr
    if len(total) > MAX_OUTPUT_BYTES:
        result.truncated = True
        # Keep stdout/stderr individually bounded for display purposes.
        result.stdout = result.stdout[:MAX_OUTPUT_BYTES]
        result.stderr = result.stderr[: max(0, MAX_OUTPUT_BYTES - len(result.stdout))]

    return result
