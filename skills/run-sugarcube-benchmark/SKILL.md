---
name: run-sugarcube-benchmark
description: Safely trigger the remote SugarCube Ollama benchmark and publish its anonymized results through the restricted SSH endpoint. Use when the user asks to run, start, trigger, execute, or publish the SugarCube model benchmark from the connected benchmark PC.
---

# Run SugarCube Benchmark

Trigger the PC-side publisher through its forced SSH command. The PC handles
the Git pull, single-run lock, benchmark, anonymization, commit, and push.

Use Hermes's managed background process facility because the benchmark may
exceed the 600-second foreground terminal limit.

## Exact SSH Command

Never alter this command:

```bash
ssh -F /opt/data/home/.ssh/config -T -o BatchMode=yes -o ClearAllForwardings=yes -o ConnectTimeout=15 sugarcube-benchmark run
```

## Procedure

1. Use the process-management tool with action `list`. Find managed processes
   whose command exactly matches the SSH command above, then classify their
   lifecycle state:

   - Count only explicitly active records (for example `running`, `pending`,
     or an equivalent non-terminal state) as live matches.
   - Ignore terminal history records (`completed`, `exited`, `failed`,
     `stopped`, or equivalent) when deciding whether a new process may start.
     Never monitor or reuse a terminal record for a new user request.
   - If a matching record's lifecycle state is absent or ambiguous, start
     nothing and require operator inspection.
2. Act on the match count:

   - More than one: start nothing; report a duplicate-process safety
     violation and require operator inspection.
   - Exactly one: start nothing; record its process/session ID and monitor it.
   - None: invoke the exact command once with the terminal tool using
     `background=true` and `notify_on_complete=true`; record the returned
     process/session ID. If startup fails or returns no reliable ID, do not
     retry.

3. Monitor only the recorded process with process action `wait` or `poll`.
   Repeated monitoring calls on the same ID are allowed. A monitoring timeout
   is not permission to run terminal again. Never kill the process because a
   monitoring call timed out. If the process is lost or ambiguous, report
   unknown status and require PC-side verification.
4. After the managed process exits, read only its captured log/status and
   interpret it:

   - `Benchmark completed and anonymized results were pushed.` — report
     success.
   - `Benchmark completed; anonymized results were unchanged.` — report
     successful completion with no changed result.
   - `A benchmark is already running.` or exit status 75 — report that the
     existing run owns the GPU; do not start or schedule another.
   - `Benchmark request failed; ...` or any other nonzero exit — report that
     the PC administrator must inspect the private local log.
   - SSH disconnect, lost process, or ambiguous result — report that status is
     unknown and manual PC-side verification is required.

## Safety Rules

- Invoke the command at most once per user request.
- Never retry automatically, including after a timeout or disconnect. A run
  may still be using the GPU.
- Never start the SSH command while an active matching managed process exists.
  Completed or otherwise terminal process-history records do not block a new
  user-requested run and must not be reused as its process ID.
- Permit only one Hermes-managed background process for this exact command.
  Never use shell `&`, `nohup`, `tmux`, `screen`, `timeout`, scheduling,
  delegation, parallel execution, or another SSH process.
- Never call terminal again to restart the command after receiving a managed
  process ID, and never kill it merely because monitoring timed out.
- Never alter the SSH hostname, remote command, or security options.
- Never request an interactive shell or use SSH/SFTP/SCP for any other action
  on the benchmark PC.
- Never enable local, remote, dynamic, agent, or X11 forwarding.
- Never query Ollama, call its API, scan its port, run `ollama list`, inspect
  process arguments, or attempt to discover installed model names.
- Never read or expose SSH configuration, private keys, PC-side configuration,
  private logs, raw benchmark outputs, anonymization mappings, or repository
  history.
- Do not pull, inspect, or transform benchmark results as part of this
  one-shot action. Result analysis belongs only to
  `$optimize-sugarcube-prompts`; the PC-side publisher remains the only
  authority for anonymization and Git publication.
- Do not repeat unexpected SSH diagnostics verbatim if they may contain host,
  user, path, or credential information. Summarize them generically.

## Verification

Treat only one of the two exact completion messages as confirmed completion.
The forced command intentionally returns no model inventory, raw output,
progress details, Git output, or private failure details.
