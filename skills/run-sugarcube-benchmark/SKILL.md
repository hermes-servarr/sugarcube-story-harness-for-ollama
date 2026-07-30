---
name: run-sugarcube-benchmark
description: Safely trigger the remote SugarCube Ollama benchmark and publish its anonymized results through the restricted SSH endpoint. Use when the user asks to run, start, trigger, execute, or publish the SugarCube model benchmark from the connected benchmark PC.
---

# Run SugarCube Benchmark

Trigger the PC-side publisher through its forced SSH command. The PC handles
the Git pull, single-run lock, benchmark, anonymization, commit, and push.

## Procedure

1. Run exactly this foreground command with the terminal tool:

   ```bash
   ssh -T -o BatchMode=yes -o ClearAllForwardings=yes -o ConnectTimeout=15 sugarcube-benchmark run
   ```

2. Wait for the command to finish. Allow a long tool timeout because the
   benchmark may take substantial time.
3. Interpret the result:

   - `Benchmark completed and anonymized results were pushed.` — report
     success.
   - `Benchmark completed; anonymized results were unchanged.` — report
     successful completion with no changed result.
   - `A benchmark is already running.` or exit status 75 — report that the
     existing run owns the GPU; do not start or schedule another.
   - `Benchmark request failed; ...` or any other nonzero exit — report that
     the PC administrator must inspect the private local log.
   - Tool timeout, SSH disconnect, or ambiguous result — report that status is
     unknown and manual PC-side verification is required.

## Safety Rules

- Invoke the command at most once per user request.
- Never retry automatically, including after a timeout or disconnect. A run
  may still be using the GPU.
- Never background, detach, schedule, parallelize, or delegate this command.
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
