# Agent Task: Mega Milestone 14 — Actual Container Subprocess Execution

**Status:** pending  
**Approved execution order:** MM14 → MM16 → MM15  
**Prerequisite:** MM13 complete and approved  
**Reviewed by Codex:** 2026-04-27 ✅ (approved in principle; API correction applied)

---

## Review rule

After every committed step: stop, post the commit hash, and wait for human approval before continuing.

## Goal

Make container sandboxing operationally real. Right now `ContainerBackend` is a complete
scaffold that describes *where* execution would happen, but never launches a container.
After MM14, sandboxed subprocess calls issued via `SandboxBackend.run_subprocess()` will
actually execute inside a Docker container with workspace bind-mounted and env filtered to
the strict allowlist.

**API contract (mandatory):**
- Parameter: `argv: list[str]` — never a shell string. Avoids quoting/escaping ambiguity
  and injection surface.
- Return: `tuple[int, str, str]` — `(returncode, stdout, stderr)`. Both backends return
  this same normalized shape.

---

## Step order (Codex-approved)

1. ABC declaration + LocalProcessBackend implementation
2. ContainerBackend.run_subprocess() via docker run
3. SandboxExecutor.run_subprocess() delegation
4. Doctor diagnostics for container execution readiness
5. Docs alignment

---

## Step 1 — ABC + LocalProcessBackend

Add to `SandboxBackend` (`src/sandbox/backends/base.py`):

```python
@abstractmethod
def run_subprocess(
    self,
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
) -> tuple[int, str, str]:
    """Run *argv* in the sandbox substrate. Returns (returncode, stdout, stderr)."""
```

Implement in `LocalProcessBackend`:
- `subprocess.run(argv, cwd=cwd, env=env, timeout=timeout, capture_output=True, text=True)`
- Return `(result.returncode, result.stdout, result.stderr)`

**Tests first:**
- `LocalProcessBackend.run_subprocess(["echo", "hello"])` → returncode==0, "hello" in stdout
- `LocalProcessBackend.run_subprocess(["false"])` → returncode != 0
- `timeout` forwarded to `subprocess.run`
- Subclass missing `run_subprocess` raises `TypeError`

**Commit:** `feat: add run_subprocess to sandbox backend interface`  
**Stop for review.**

---

## Step 2 — ContainerBackend.run_subprocess()

Build docker argv (no shell, no string interpolation):

```python
docker_argv = [
    "docker", "run", "--rm",
    "--mount", f"type=bind,source={self._host_workspace},target={self.container_workspace},readonly=false",
]
for key, value in (env or {}).items():
    docker_argv += ["--env", f"{key}={value}"]
docker_argv += [self.image, *argv]
```

Call `subprocess.run(docker_argv, capture_output=True, text=True, timeout=timeout)`.  
Return `(result.returncode, result.stdout, result.stderr)`.

**Tests first — all mock subprocess.run; no live Docker:**
- `"--rm"` in docker argv
- `"--mount"` contains `source=<host_workspace>` and `target=<container_workspace>`
- Each env key → `["--env", "KEY=VALUE"]` pair
- `self.image` immediately before user argv; user argv follows image
- `timeout` forwarded; returncode/stdout/stderr passed through

**Commit:** `feat: implement docker run subprocess in ContainerBackend`  
**Stop for review.**

---

## Step 3 — SandboxExecutor.run_subprocess() delegation

```python
def run_subprocess(
    self,
    argv: list[str],
    *,
    timeout: float | None = None,
) -> tuple[int, str, str]:
    env = self._backend.build_environment()
    return self._backend.run_subprocess(argv, cwd=self._workspace_dir, env=env, timeout=timeout)
```

**Tests first:**
- Delegates with `cwd=workspace_dir`, env from `build_environment()`
- `build_environment()` called BEFORE `run_subprocess` (assert call order)
- Integration: `LocalProcessBackend` path → (0, contains "hi", "")
- `ContainerBackend` path (subprocess mocked): docker argv includes executor's workspace env

**Commit:** `feat: wire run_subprocess delegation into SandboxExecutor`  
**Stop for review.**

---

## Step 4 — Doctor diagnostics

Update `_tool_coverage_lines()` in `src/doctor.py`:

- `backend=container` + `is_available()=True` → `"container backend ready; run_subprocess invokes docker run"`
- `backend=container` + `is_available()=False` → `"container backend configured but Docker not found on $PATH — will raise RuntimeError at runtime"`
- `backend=local_process` → unchanged

Drop the "actual runtime guarantees depend on availability" hedge from env-shaping line when Docker is confirmed present.

**Tests first:** mock `ContainerBackend.is_available`; assert each branch; local_process unchanged.

**Commit:** `docs: update doctor container execution readiness diagnostics`  
**Stop for review.**

---

## Step 5 — Docs alignment

Update `docs/run.md`: add **Container Sandbox Backend** section covering:
- `sandbox.backend: container` YAML snippet
- Docker CLI prerequisite
- What `run_subprocess` does (the docker run invocation)
- Isolation boundary (container process + bind-mounted workspace; network still dispatch-level)

Add one CLI test: `autoresearch explain config` with container YAML → output contains `sandbox.backend` and image.

**Commit:** `docs: document container sandbox backend configuration and guarantees`  
**Stop for review (final MM14 review).**

---

## Copilot Prompt

Paste this verbatim to start MM14:

```
You are continuing a structured hardening roadmap for this repository.
MM01–MM13 are complete and approved. Start MM14 now.

## Your working rule — applies to every step

1. Read the files listed under "Context" before writing any code.
2. Write failing tests FIRST. Run them and confirm they fail.
3. Implement the minimum code to make them pass.
4. Run the full test suite: `uv run pytest -x -q`
5. Commit with a conventional prefix (feat:, fix:, docs:, refactor:).
   No Co-authored-by trailers.
6. Post the commit hash and stop. Do NOT proceed to the next step
   until the human explicitly approves.

---

# MM14 — Actual Container Subprocess Execution

## Goal

`ContainerBackend` is a complete scaffold that describes *where* execution
would happen but never launches a container. After MM14, sandboxed subprocess
calls issued via `SandboxBackend.run_subprocess()` will actually execute
inside a Docker container with workspace bind-mounted and env filtered to
the strict allowlist.

API contract (mandatory):
- argv: list[str] — never a shell string
- Returns: tuple[int, str, str] — (returncode, stdout, stderr)
Both backends return this same normalized shape.

## Context — read before writing any code

- src/sandbox/backends/base.py — SandboxBackend ABC; add abstract method here FIRST
- src/sandbox/backends/local_process.py — implement run_subprocess here in Step 1
- src/sandbox/backends/container.py — implement docker-run version in Step 2
- src/sandbox_executor.py — SandboxExecutor; add delegation method in Step 3
- src/doctor.py — _tool_coverage_lines(); update diagnostics in Step 4
- tests/test_container_backend.py — MM13 tests; must not break
- tests/test_sandbox_backends.py — must not break
- tests/test_sandbox_executor.py — must not break

## Step 1 — ABC declaration + LocalProcessBackend implementation

Add to SandboxBackend in src/sandbox/backends/base.py:

    @abstractmethod
    def run_subprocess(
        self,
        argv: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> tuple[int, str, str]:
        """Run *argv* in the sandbox substrate. Returns (returncode, stdout, stderr)."""

Implement in LocalProcessBackend:
    subprocess.run(argv, cwd=cwd, env=env, timeout=timeout, capture_output=True, text=True)
    Return (result.returncode, result.stdout, result.stderr)

Tests first (write, confirm FAIL, then implement):
- LocalProcessBackend.run_subprocess(["echo", "hello"]) → returncode==0, "hello" in stdout
- LocalProcessBackend.run_subprocess(["false"]) → returncode != 0
- timeout forwarded to subprocess.run
- Subclass missing run_subprocess raises TypeError

Commit: feat: add run_subprocess to sandbox backend interface
Stop. Post commit hash. Wait for approval before Step 2.

## Step 2 — ContainerBackend.run_subprocess()

Implement in src/sandbox/backends/container.py.
Build docker argv (no shell, no string interpolation):

    docker_argv = [
        "docker", "run", "--rm",
        "--mount", f"type=bind,source={self._host_workspace},target={self.container_workspace},readonly=false",
    ]
    for key, value in (env or {}).items():
        docker_argv += ["--env", f"{key}={value}"]
    docker_argv += [self.image, *argv]

Call subprocess.run(docker_argv, capture_output=True, text=True, timeout=timeout).
Return (result.returncode, result.stdout, result.stderr).

Tests first — ALL mock subprocess.run; no live Docker:
- "--rm" in docker argv
- "--mount" contains source=<host_workspace> and target=<container_workspace>
- each env key → ["--env", "KEY=VALUE"] pair
- self.image before user argv; user argv follows image
- timeout forwarded; returncode/stdout/stderr passed through

Commit: feat: implement docker run subprocess in ContainerBackend
Stop. Post commit hash. Wait for approval before Step 3.

## Step 3 — SandboxExecutor.run_subprocess() delegation

Add to SandboxExecutor in src/sandbox_executor.py:

    def run_subprocess(
        self,
        argv: list[str],
        *,
        timeout: float | None = None,
    ) -> tuple[int, str, str]:
        env = self._backend.build_environment()
        return self._backend.run_subprocess(
            argv, cwd=self._workspace_dir, env=env, timeout=timeout,
        )

Tests first:
- Delegates with cwd=workspace_dir, env from build_environment()
- build_environment() called BEFORE run_subprocess (assert call order)
- Integration test with LocalProcessBackend: run_subprocess(["echo","hi"]) → (0, "hi\n", "")
- ContainerBackend (subprocess mocked): docker argv includes executor's env vars

Commit: feat: wire run_subprocess delegation into SandboxExecutor
Stop. Post commit hash. Wait for approval before Step 4.

## Step 4 — Doctor diagnostics for container execution readiness

Update _tool_coverage_lines() in src/doctor.py:

backend=container + is_available()=True:
  "container backend ready; run_subprocess invokes docker run"
  env shaping: "ACTIVE (strict allowlist; container backend ready)"

backend=container + is_available()=False:
  "container backend configured but Docker not found on $PATH — will raise RuntimeError at runtime"

backend=local_process: no change.

Tests first (mock ContainerBackend.is_available):
- is_available=True → doctor text contains "container backend ready"
- is_available=False → doctor text contains "not found on $PATH" or "RuntimeError"
- local_process output unchanged from current baseline

Commit: docs: update doctor container execution readiness diagnostics
Stop. Post commit hash. Wait for approval before Step 5.

## Step 5 — Docs alignment

Update docs/run.md. Add a "Container Sandbox Backend" section:
- sandbox.backend: container YAML example
- Docker CLI prerequisite
- What run_subprocess does (the docker run invocation)
- Isolation boundary: container process + bind-mounted workspace; network still dispatch-level

Add one CLI test: autoresearch explain config with a temp container YAML
→ output contains sandbox.backend and the image name.

Commit: docs: document container sandbox backend configuration and guarantees
Stop. Post commit hash. This is the final MM14 step.
Wait for full MM14 review before starting MM16.
```
