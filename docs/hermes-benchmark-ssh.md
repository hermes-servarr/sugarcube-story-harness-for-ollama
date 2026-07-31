# Restricted Hermes benchmark trigger

`scripts/hermes_benchmark_publish.py` lets a remote Hermes host trigger the
Ollama benchmark over SSH. It publishes only
`benchmark_anon/results_anonymized.json`.

Before each run it requires a clean checkout on the configured branch and runs
`git pull --ff-only <remote> <branch>`. The benchmark therefore runs against
the latest fast-forwarded code and refuses dirty checkouts, branch mismatches,
merge commits needed locally, authentication failures, or pull failures.

## Single-run GPU protection

The publisher acquires an operating-system file lock at
`<state_dir>/run.lock` before pulling or contacting Ollama and holds it through
the complete benchmark, anonymization, commit, push, and temporary-file
cleanup. If another SSH request arrives while that lock is held, it prints
`A benchmark is already running.`, exits with status 75, and does not start
another model workload.

The lock is process-owned, so Windows or Linux releases it automatically if
the publisher crashes or is terminated. All trigger installations must use
the same fixed `state_dir`; using different state directories would create
independent locks and defeat this protection.

The security boundary is a dedicated SSH account and a forced command. Give it
only the platform-specific file access documented below—never an interactive
shell, Ollama-group membership, unrestricted `sudo`, or access to unrelated
repositories. If Hermes already has a normal shell account on this PC, no
wrapper script can prevent it from querying
`http://127.0.0.1:11434/api/tags` directly.

## Trusting pulled benchmark code

The updated Python code is imported and executed after every pull. Anyone able
to push to the configured branch could modify the benchmark to query or
exfiltrate the Ollama inventory, bypassing the output scrubber. The Hermes
account/model must therefore have no write permission to that branch. Use a
private repository with a protected branch, mandatory review, and trusted
maintainers.

Signed commits and an explicit signer allowlist are enabled by default. Set
`trusted_commit_signers` to the accepted signing-key fingerprint(s) and
configure the PC's local Git trust store. The publisher runs
`git verify-commit HEAD`, reads Git's `%GF` signer fingerprint, and requires an
exact allowlist match before contacting Ollama. Keep every trusted signing
private key off the Hermes server.

Disabling `require_signed_commit` is unsafe when Hermes can push to the
configured branch: it could change the pulled Python benchmark and bypass the
anonymization layer.

### Data-only optimization commits

For the autonomous optimization skill, configure:

```json
{
  "require_signed_commit": true,
  "trusted_commit_signers": ["TRUSTED_KEY_FINGERPRINT"],
  "allow_unsigned_candidate_commits": true,
  "trusted_code_commit": "FULL_SIGNED_COMMIT_SHA",
  "candidate_paths": [
    "model_benchmark/prompt_overrides.json",
    "benchmark_anon/results_anonymized.json",
    "benchmark_optimization/**"
  ]
}
```

The trusted commit must contain the publisher, prompt-overlay loader, and both
skills and must be signed by an allowlisted key. Candidate commits may then be
unsigned only when the trusted commit is their ancestor and every accumulated
change is confined to those data/result/note paths. Any Python, scoring, test,
fixture, skill, SSH, or configuration change blocks the run before Ollama is
contacted.

## Install on a Windows benchmark PC

Use a dedicated local, non-administrator Windows account for the SSH key and a
dedicated clean clone. Run the following from an elevated PowerShell, adjusting
paths as needed:

```powershell
New-Item -ItemType Directory -Force C:\ProgramData\HermesBenchmark | Out-Null
Copy-Item scripts\hermes_benchmark_publish.py C:\ProgramData\HermesBenchmark\
Copy-Item scripts\hermes_benchmark_config.example.json C:\ProgramData\HermesBenchmark\config.json
notepad C:\ProgramData\HermesBenchmark\config.json

uv sync
```

Set the real explicit model tags, clone path, `.venv\Scripts\python.exe`, Git
executable, remote, and branch in the config. Configure non-interactive Git
pull/push credentials for the dedicated account.
The example runs all benchmark directions currently defined by the project
(A–H) and all variants, including `thinking`; reduce those lists only if you
intentionally want a smaller run.
It also enables the signed 33-case capability ladder. Those additional calls
run sequentially for each configured model and cover T0 atomic syntax through
T9 harness-scale context, including matched S/M/L/XL retrieval probes.
The ladder includes direct plain-text fallbacks at tiny, short, and medium
output budgets. Per-case caps can only reduce the configured `num_predict`;
they measure concise-answer compliance and longer explanations without
increasing GPU memory requirements.
The T0 floor asks for exactly one plain-text word under the 32-token cap,
separating basic output-control failure from retrieval or formatting failure.
Conversation-layout cases cover compact, full, JSON, thinking, and XL-context
generation. They require a standardized `DIALOGUE:` block of quoted speaker
turns followed by `INNER MONOLOGUE:` and `MC: //thoughts//` inside PROSE.
Thinking conversation cases form an S/K2, M/K3, and XL/K4 slope, increasing
context and turn requirements gradually instead of testing only the extreme.
A separate fixed-full-variant slope requires exactly 4, 8, and 16 alternating
dialogue turns. Trusted context supplies the exact first and last spoken lines,
letting the scorer distinguish endpoint retrieval, turn-count, alternation,
and layout failures in a long back-and-forth exchange.

Create the account and its authorized-key file. Use Windows account-management
policy appropriate for your machine; the account must not be an administrator.
Then add this block to `C:\ProgramData\ssh\sshd_config`:

```text
Match User hermes-benchmark
    ForceCommand "C:\benchmark\sugarcube-story-harness-for-ollama\.venv\Scripts\python.exe" "C:\ProgramData\HermesBenchmark\hermes_benchmark_publish.py"
    PermitTTY no
    AllowTcpForwarding no
    X11Forwarding no
    PermitTunnel no
    GatewayPorts no
```

Restart `sshd` after validating the configuration:

```powershell
Restart-Service sshd
```

Use NTFS ACLs so administrators and the dedicated account can read the
publisher/config/state, no other user can, and only administrators can modify
the publisher, configuration, `sshd_config`, and authorized keys. The
dedicated account needs modify permission only on its clean repository clone
and the state subdirectory.

The Hermes server triggers the run with:

```bash
ssh -T hermes-benchmark@BENCHMARK_PC run
```

`ForceCommand` ignores `run` (and any other requested command). Forwarding and
PTYs are disabled, so the account cannot tunnel to Ollama or request a shell.
Also disable password authentication for this dedicated account and install
only the Hermes trigger key.

## Install on a Linux benchmark PC

Run these steps locally as an administrator. Use a dedicated clean clone for
`repo_path`; the publisher intentionally commits the public result file.

```bash
sudo install -o root -g root -m 0755 \
  scripts/hermes_benchmark_publish.py \
  /usr/local/sbin/hermes-benchmark-publish

sudo install -d -o root -g root -m 0700 /etc/hermes-benchmark
sudo install -d -o root -g root -m 0700 /var/lib/hermes-benchmark
sudo install -o root -g root -m 0600 \
  scripts/hermes_benchmark_config.example.json \
  /etc/hermes-benchmark/config.json
sudoedit /etc/hermes-benchmark/config.json
```

Set the real, explicit model tags in `/etc/hermes-benchmark/config.json`.
An empty model list is rejected, so the benchmark never falls back to its
model-discovery CLI. Set `python_executable` to the dedicated clone's virtual
environment (run `uv sync` in that clone first), change the example's Windows
paths to Linux paths, and set `git_executable` to the Git binary. Configure
non-interactive Git pull/push credentials for root in the dedicated clone.

Create a password-locked account. It needs a real shell because `sshd` uses
the account shell to launch forced commands; the key restriction below is what
prevents interactive shell access.

```bash
sudo useradd --system --create-home --shell /bin/sh hermes-benchmark
sudo passwd -l hermes-benchmark
echo 'hermes-benchmark ALL=(root) NOPASSWD: /usr/local/sbin/hermes-benchmark-publish' |
  sudo tee /etc/sudoers.d/hermes-benchmark >/dev/null
sudo chmod 0440 /etc/sudoers.d/hermes-benchmark
sudo visudo -cf /etc/sudoers.d/hermes-benchmark
```

Put the Hermes server's public key in
`/home/hermes-benchmark/.ssh/authorized_keys` as one physical line, replacing
the placeholder key:

```text
restrict,command="sudo -n /usr/local/sbin/hermes-benchmark-publish" ssh-ed25519 AAAA... hermes-benchmark-trigger
```

Keep that file controlled by root so the restricted account cannot add an
unrestricted key:

```bash
sudo chown -R root:root /home/hermes-benchmark/.ssh
sudo chown root:root /home/hermes-benchmark
sudo chmod 0755 /home/hermes-benchmark
sudo chmod 0700 /home/hermes-benchmark/.ssh
sudo chmod 0600 /home/hermes-benchmark/.ssh/authorized_keys
```

`restrict` disables forwarding, PTY allocation, agent forwarding, X11
forwarding, and `~/.ssh/rc`. The forced command ignores what the remote side
requests.

The Hermes server can then trigger a run:

```bash
ssh -T hermes-benchmark@BENCHMARK_PC run
```

The SSH response is deliberately generic. Model names, benchmark progress,
Git output, tracebacks, and raw results go only to the root-readable
`/var/lib/hermes-benchmark/last-run.log` on Linux or
`C:\ProgramData\HermesBenchmark\state\last-run.log` on Windows. Temporary
internal results are deleted after every attempt.

## Additional host hardening

The model tags never appear in the publisher process command line or
environment. On a multi-user Linux host, also mount `/proc` with `hidepid=2`
or use an equivalent systemd setting so unrelated users cannot inspect other
processes. On either platform, bind Ollama only to loopback and firewall port
11434 from the Hermes server.

Before pushing, the publisher privately queries Ollama for every installed
tag, recursively scrubs all of those tags (including tags embedded in
`test_id`), and performs a case-insensitive leak scan. If inventory lookup,
anonymization, the benchmark, commit, or push fails, it fails closed and
publishes nothing.

The repository previously contained model tags in the Git history of
`benchmark_anon/results_anonymized.json`; the working-tree copy is scrubbed by
this change, but normal commits cannot erase old objects. If the Hermes server
can browse this repository's history, publish results to a fresh private
repository or deliberately purge the old history before granting it access.

## Enable the skill on Hermes

This repository includes `skills/run-sugarcube-benchmark/SKILL.md`. On the
Hermes server, add the checkout's `skills` directory to
`~/.hermes/config.yaml`:

```yaml
skills:
  external_dirs:
    - /absolute/path/to/sugarcube-story-harness-for-ollama/skills
  write_approval: true
```

Install the restricted `sugarcube-benchmark` host entry and its pinned
`known_hosts` file under `/opt/data/home/.ssh`. The run skill passes
`-F /opt/data/home/.ssh/config` explicitly: Hermes terminal tools can run with
`HOME=/opt/data`, so relying on SSH's default `~/.ssh/config` lookup can skip
the agent's persistent configuration and incorrectly treat the alias as a DNS
hostname.

Hermes scans external skill directories and exposes each skill as a slash
command. After reloading Hermes, verify that `run-sugarcube-benchmark` appears
in `hermes skills list`, then invoke:

```text
/run-sugarcube-benchmark
```

Keep the checkout and skill files read-only to the Hermes process if practical.
If Hermes needs repository write access for other work, retain
`write_approval: true` and review skill edits before committing them. The
PC-side forced SSH command and signed-commit allowlist remain the enforcement
boundaries even if the model ignores or edits skill instructions.

For a bounded optimization loop, invoke the second included skill through a
persistent goal:

```text
/goal Use /optimize-sugarcube-prompts to run at most five sequential experiments. Stop at the first of: target pass rate reached, two non-improving experiments, any regression that is not reverted, or any safety/verification failure.
```

Hermes persistent goals automatically continue across turns and enforce their
configured turn budget. Keep `goals.max_turns` finite; the skill additionally
caps itself at five expensive GPU experiments.

The optimization skill analyzes the `thinking` variant separately. It may tune
only the declarative thinking prompt for reasoning-quality or final-passage
format failures, while checking that `compact`, `full`, and `json` do not
regress. It never records chain-of-thought. A missing or truncated final passage
is treated as possible output-budget exhaustion; the goal stops for operator
review instead of automatically raising `num_predict`, because that setting is
GPU-sensitive and the anonymized result cannot establish the cause.

Hermes may add one data-only diagnostic probe per optimization experiment
under `benchmark_optimization/candidate_tests/`. The PC validates these JSON
files against a signed closed schema: they select trusted contexts and
deterministic check primitives, but cannot add code, regex evaluators,
thresholds, verdicts, model identities, or scoring changes. Candidate metrics
are reported separately and excluded from the optimization pass rate and stop
conditions, so adding easy probes cannot inflate the objective.

Potential tests that are not ready to execute belong in
`benchmark_optimization/test-proposals.md`. Hermes can accumulate and update
that review backlog without consuming GPU time. Each proposal records the
capability and context axes, a paired control, deterministic checks, expected
resource cost, and the evidence required before operator-reviewed promotion.
