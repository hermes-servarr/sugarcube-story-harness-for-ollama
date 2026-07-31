---
name: run-sugarcube-benchmark
description: Safely trigger the remote SugarCube Ollama benchmark and publish its anonymized results through the restricted SSH endpoint. Use when the user asks to run, start, trigger, execute, or publish the SugarCube model benchmark from the connected benchmark PC.
---

# Run SugarCube Benchmark

Trigger the PC-side publisher through its forced SSH command. The PC handles
the Git pull, single-run lock, benchmark, anonymization, commit, and push.

This skill uses Hermes's managed background process facility because the
benchmark may exceed the 600-second foreground terminal limit.

## Exact SSH Command

The command below must never be altered:

```bash
ssh -F /opt/data/home/.ssh/config -T -o BatchMode=yes -o ClearAllForwardings=yes -o ConnectTimeout=15 sugarcube-benchmark run
```

## Procedure

### Step 1 — Check for existing matching processes

Before starting anything, use the process-management tool (`process`
action=`list`) to list all managed processes. Look for processes whose
command is exactly the SSH command above, and classify each match by its
lifecycle state:

- **Active match:** lifecycle state is explicitly `running` or `pending`.
- **Terminal match:** lifecycle state is `completed`, `exited`, `failed`,
  `stopped`, or any equivalent terminal-history state.
- **Ambiguous match:** lifecycle state is missing or cannot be determined.

Count only active matches when deciding whether a new process may start.
Terminal history records do not block a new user-requested run.

### Step 2 — Decide based on active match count

**If more than one active matching process exists:**
- Start nothing.
- Report a possible duplicate-process safety violation.
- Require operator inspection before proceeding.

**If exactly one active matching process exists:**
- Start nothing.
- Treat it as the existing benchmark trigger.
- Record its process/session ID and skip to Step 4.

**If no active matching process exists:**
- If any match has a missing or ambiguous lifecycle state, start nothing
  and require operator inspection.
- Terminal history records (completed, exited, failed, stopped, or
  equivalent) do not block a new user-requested run. Never monitor or
  reuse a terminal process record for a new user request.
- If all matches are terminal or no matches exist at all, proceed to
  Step 3.

### Step 3 — Start the SSH command (only when no active match exists)

Invoke the exact SSH command once using the terminal tool with:
- `background=true`
- `notify_on_complete=true`

Do not add shell `&`, `nohup`, `tmux`, `screen`, `timeout`, or any other
wrapper.

Record the returned process/session ID.

If the start call has an error or returns an ambiguous result without a
reliable ID, do not retry. Report the failure and require operator
inspection.

### Step 4 — Monitor the recorded process

Monitor only the recorded process using `process` action=`wait` or
`process` action=`poll`.

- A wait/poll timeout means the process is still being monitored; it is
  not permission to start another command.
- Repeated wait/poll calls on the same ID are allowed.
- Never call terminal again to restart the SSH command.
- Never kill the process merely because a monitoring call timed out.
- If the process manager loses the process or its status becomes
  ambiguous, report unknown status and require PC-side verification.

### Step 5 — After the managed process exits

Read only that process's captured log/status.

Interpret the result:

- `Benchmark completed and anonymized results were pushed.` — report
  success.
- `Benchmark completed; anonymized results were unchanged.` — report
  successful completion with no changed result.
- `A benchmark is already running.` or exit status 75 — report that the
  existing run owns the GPU; do not start or schedule another.
- `Benchmark request failed; ...` or any other nonzero exit — report that
  the PC administrator must inspect the private local log.
- Tool timeout, SSH disconnect, or ambiguous result — report that status
  is unknown and manual PC-side verification is required.

## Safety Rules

- Invoke the command at most once per user request.
- Never retry automatically, including after a timeout or disconnect. A run
  may still be using the GPU.
- Never start the SSH command when an active matching managed process
  already exists. Terminal history records (completed, exited, failed,
  stopped, or equivalent) do not block a new user-requested run.
- Use only the managed background process facility (terminal
  `background=true`, `notify_on_complete=true`). Never use shell-level
  background wrappers (`&`, `nohup`, `tmux`, `screen`, `timeout`).
- Never call terminal again to restart the SSH command once a managed
  process has been started.
- Never kill the process merely because a monitoring call timed out.
- Never alter the SSH hostname, remote command, or security options.
- Never request an interactive shell or use SSH/SFTP/SCP for any other
  action on the benchmark PC.
- Never enable local, remote, dynamic, agent, or X11 forwarding.
- Never query Ollama, call its API, scan its port, run `ollama list`,
  inspect process arguments, or attempt to discover installed model names.
- Never read or expose SSH configuration, private keys, PC-side
  configuration, private logs, raw benchmark outputs, anonymization
  mappings, or repository history.
- Do not pull, inspect, or transform benchmark results as part of this
  one-shot action. Result analysis belongs only to
  `$optimize-sugarcube-prompts`; the PC-side publisher remains the only
  authority for anonymization and Git publication.
- Do not repeat unexpected SSH diagnostics verbatim if they may contain
  host, user, path, or credential information. Summarize them generically.

## Verification

Treat only one of the two exact completion messages as confirmed
completion. The forced command intentionally returns no model inventory,
raw output, progress details, Git output, or private failure details.
