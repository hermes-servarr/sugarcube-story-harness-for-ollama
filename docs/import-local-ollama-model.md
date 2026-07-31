# Import a downloaded model into Ollama

The PowerShell script `scripts/New-OllamaModelfile.ps1` creates a minimal
`Modelfile` beside a downloaded model and prints the `ollama create` command.

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
