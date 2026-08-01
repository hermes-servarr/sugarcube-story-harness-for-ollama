# Import a downloaded model into Ollama

The PowerShell script `scripts/New-OllamaModelfile.ps1` creates a minimal
`Modelfile` beside a downloaded model and prints the `ollama create` command.

> **Models imported this way are bare by default.** The generated `Modelfile`
> carries no system prompt and no chat template unless you supply one. A GGUF
> import inherits whatever `tokenizer.chat_template` is embedded in the GGUF
> itself; when that metadata is absent, Ollama falls back to a
> `{{ .Prompt }}` passthrough and the model is driven as a raw completion
> model with no instruct formatting. This materially changes how a model
> responds to the harness prompts. See
> [Check what a model was imported with](#check-what-a-model-was-imported-with)
> before comparing benchmark results across models.

From PowerShell, run:

```powershell
.\scripts\New-OllamaModelfile.ps1
```

Paste a folder or a GGUF file path when prompted. You can also pass it directly:

```powershell
.\scripts\New-OllamaModelfile.ps1 'C:\models\orinth'
.\scripts\New-OllamaModelfile.ps1 'C:\models\orinth\ornith-1.0-9b-Q4_K_M.gguf'
```

To scan an entire models tree recursively:

```powershell
.\scripts\New-OllamaModelfile.ps1 'C:\models' -Recursive
```

This prints one `ollama create` command for every discovered model. Add
`-Create` to execute all of those commands immediately. Configuration options
such as `-SystemPrompt`, `-Temperature`, and `-NumCtx` apply to every model in
the recursive run.

The script supports:

- A folder containing one `.gguf` model file
- A direct path to a `.gguf` model file
- A complete Safetensors model folder containing `config.json`
- A Safetensors adapter folder containing `adapter_config.json`

For an adapter, specify the exact base model if it cannot be inferred reliably:

```powershell
.\scripts\New-OllamaModelfile.ps1 'C:\models\my-adapter' -Base 'llama3.1:8b'
```

Useful options:

```powershell
# Choose the Ollama model name
.\scripts\New-OllamaModelfile.ps1 'C:\models\orinth' -Name 'ornith:9b-q4'

# Add common model configuration
.\scripts\New-OllamaModelfile.ps1 'C:\models\orinth' `
    -SystemPrompt 'You are a creative interactive-fiction writing assistant.' `
    -Temperature 0.7 `
    -NumCtx 8192

# Replace an existing Modelfile
.\scripts\New-OllamaModelfile.ps1 'C:\models\orinth' -Force

# Create the Ollama model immediately instead of only printing the command
.\scripts\New-OllamaModelfile.ps1 'C:\models\orinth' -Create

# Create it and run a small validation generation
.\scripts\New-OllamaModelfile.ps1 'C:\models\orinth' -Create -Validate
```

For the whole recursive tree:

```powershell
.\scripts\New-OllamaModelfile.ps1 'C:\models' -Recursive -Create -Validate
```

Validation calls Ollama's `/api/generate` endpoint with a short `OK` prompt,
the same generation API used by the SugarCube harness. A non-empty response is
a pass; a response other than exactly `OK` also produces a warning about
instruction-following or a potentially incorrect model template. Each model is
unloaded after its probe. `-Validate` must be combined with `-Create`.

Recursive runs keep a resumable status log at:

```text
C:\models\.ollama-import-status.json
```

The log is updated after every model and records its source, Ollama name,
generated Modelfile, fingerprint, outcome, error, and timestamp. Re-running the
same recursive create command skips unchanged models that previously passed and
retries failed or changed models. To ignore successful history and recreate
everything, add `-RebuildAll`:

```powershell
.\scripts\New-OllamaModelfile.ps1 'C:\models' -Recursive -Create -Validate -RebuildAll
```

If a folder contains multiple GGUF files, pass the exact GGUF file you want.
In recursive mode, every GGUF is included and receives a distinct file such as
`Modelfile.model-q4_k_m`; the script does not overwrite one quantization with
another.

The printed `ollama create` command works in both PowerShell and Command
Prompt. For example:

```cmd
ollama create orinth -f "C:\models\orinth\Modelfile"
```

## External Jinja chat templates

For a Safetensors model, the script recognizes `chat_template.jinja`,
`chat_template.jinja2`, or a Jinja file referenced by an `{% include %}` in
`tokenizer_config.json`. It embeds the template text into the
`chat_template` property that Ollama imports. Before changing an existing
tokenizer configuration, it preserves the original once as:

```text
tokenizer_config.json.ollama-backup
```

If several `.jinja` files exist, name the default one `chat_template.jinja`.
External Jinja cannot be attached to a GGUF through a Modelfile; GGUF imports
use the `tokenizer.chat_template` metadata embedded in the GGUF itself.

## Check what a model was imported with

Provisioning is easy to get inconsistent across a large local roster, and the
difference is invisible in `ollama list`. Ask the server directly:

```powershell
$body = @{ model = 'replace-with-model-tag' } | ConvertTo-Json
$info = Invoke-RestMethod -Method Post -Uri 'http://localhost:11434/api/show' -Body $body -ContentType 'application/json'
$info.template.Length
$info.template.Substring(0, [Math]::Min(120, $info.template.Length))
```

A `template` of exactly `{{ .Prompt }}` (13 characters) means **no chat
template**: the harness prompt reaches the model as raw text with no
role markers, and the model will tend to continue the text rather than follow
the instructions in it.

To audit every installed model at once:

```powershell
(Invoke-RestMethod 'http://localhost:11434/api/tags').models |
  ForEach-Object {
    $body = @{ model = $_.name } | ConvertTo-Json
    $t = (Invoke-RestMethod -Method Post -Uri 'http://localhost:11434/api/show' -Body $body -ContentType 'application/json').template
    [pscustomobject]@{ Name = $_.name; TemplateChars = $t.Length; Bare = ($t.Trim() -eq '{{ .Prompt }}') }
  } | Sort-Object Bare, Name | Format-Table -AutoSize
```

### Why this matters for the benchmark

A bare-template model and a chat-templated model are not comparable runs. In
the 2026-08-01 capability run, the bare-template model produced ordinary
narrative prose that ignored the required `DIALOGUE:` / `INNER MONOLOGUE:`
layout, which is the expected shape of raw-completion behavior rather than a
statement about the model's ability. Two failure modes look similar in the
scores but have different causes:

| Observed | Likely cause |
|----------|--------------|
| Well-formed prose that ignores the requested output structure | Bare `{{ .Prompt }}` template; no instruct formatting applied |
| Prompt analysis or reasoning emitted as passage content | Chat template present; reasoning-style model leaking its analysis into the answer |

Before attributing a benchmark result to a model or to a prompt overlay,
confirm that the models being compared were imported the same way. This is
especially important across quantizations of one base model, where a mixed
roster silently conflates quantization with template presence.

To give a bare GGUF an instruct format, either re-import from a GGUF that
embeds `tokenizer.chat_template`, or supply a system prompt at import time
with `-SystemPrompt` so the model receives at least some standing instruction.
