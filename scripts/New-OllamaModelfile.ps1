[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string] $Path,

    [string] $Name,

    [string] $Base,

    [string] $SystemPrompt,

    [double] $Temperature,

    [int] $NumCtx,

    [switch] $Recursive,

    [string] $ModelfileName = 'Modelfile',

    [switch] $Force,

    [switch] $Create,

    [switch] $Validate
)

$ErrorActionPreference = 'Stop'

function Format-ModelfileValue {
    param([Parameter(Mandatory = $true)][string] $Value)

    if ($Value -match '[\s#"]') {
        return '"' + $Value.Replace('\', '/').Replace('"', '\"') + '"'
    }
    return $Value.Replace('\', '/')
}

function Format-CommandLinePath {
    param([Parameter(Mandatory = $true)][string] $Value)

    return '"' + $Value + '"'
}

function ConvertTo-OllamaName {
    param([Parameter(Mandatory = $true)][string] $Value)

    $result = $Value.ToLowerInvariant()
    $result = $result -replace '[^a-z0-9._-]+', '-'
    $result = $result.Trim('-', '.', '_')
    if (-not $result) {
        return 'local-model'
    }
    return $result
}

function Test-OllamaModel {
    param([Parameter(Mandatory = $true)][string] $ModelName)

    $ollamaHost = $env:OLLAMA_HOST
    if (-not $ollamaHost) {
        $ollamaHost = 'http://127.0.0.1:11434'
    } elseif ($ollamaHost -notmatch '^https?://') {
        $ollamaHost = 'http://' + $ollamaHost
    }
    $uri = $ollamaHost.TrimEnd('/') + '/api/generate'
    $body = @{
        model = $ModelName
        prompt = 'Reply with exactly the word OK.'
        stream = $false
        keep_alive = 0
        options = @{
            temperature = 0
            num_predict = 16
        }
    } | ConvertTo-Json -Depth 4

    Write-Host "Validating $ModelName with a small generation request..." -ForegroundColor Cyan
    try {
        $response = Invoke-RestMethod `
            -Uri $uri `
            -Method Post `
            -ContentType 'application/json' `
            -Body $body `
            -TimeoutSec 120
    } catch {
        throw "Validation request failed for '$ModelName': $($_.Exception.Message)"
    }

    $text = [string] $response.response
    if (-not $text.Trim()) {
        throw "Validation failed for '$ModelName': Ollama returned an empty response."
    }

    $preview = ($text -replace '\s+', ' ').Trim()
    if ($preview.Length -gt 100) {
        $preview = $preview.Substring(0, 100) + '...'
    }
    if ($text.Trim() -ieq 'OK') {
        Write-Host "Validation passed: $ModelName returned OK" -ForegroundColor Green
    } else {
        Write-Host "Validation passed: $ModelName returned a non-empty response: $preview" -ForegroundColor Green
        Write-Warning "'$ModelName' did not follow the exact OK probe. It runs, but instruction-following or its chat template may need review."
    }
}

if (-not $Path) {
    $Path = Read-Host 'Paste the model file, model folder, or root models folder path'
}

# Read-Host input is often pasted with surrounding quotes.
$Path = $Path.Trim().Trim('"').Trim("'")
if (-not $Path) {
    throw 'No model path was supplied.'
}

if ($Validate -and -not $Create) {
    throw '-Validate must be used with -Create so the newly created Ollama model exists before it is tested.'
}

if ($Recursive) {
    $rootItem = Get-Item -LiteralPath $Path
    if (-not $rootItem.PSIsContainer) {
        throw '-Recursive requires a root folder, not a file.'
    }

    $targets = [System.Collections.Generic.List[object]]::new()
    $safetensorDirectories = @(
        Get-ChildItem -LiteralPath $rootItem.FullName -Recurse -File -Filter '*.safetensors' |
            ForEach-Object { $_.Directory.FullName } |
            Sort-Object -Unique
    )
    foreach ($directory in $safetensorDirectories) {
        $hasModelConfig = Test-Path -LiteralPath (Join-Path $directory 'config.json') -PathType Leaf
        $hasAdapterConfig = Test-Path -LiteralPath (Join-Path $directory 'adapter_config.json') -PathType Leaf
        if ($hasModelConfig -or $hasAdapterConfig) {
            $targets.Add([pscustomobject]@{
                Path = $directory
                Directory = $directory
                Label = 'safetensors'
                IsFile = $false
            })
        }
    }
    foreach ($file in @(Get-ChildItem -LiteralPath $rootItem.FullName -Recurse -File -Filter '*.gguf')) {
        $targets.Add([pscustomobject]@{
            Path = $file.FullName
            Directory = $file.Directory.FullName
            Label = [System.IO.Path]::GetFileNameWithoutExtension($file.Name)
            IsFile = $true
        })
    }

    if ($targets.Count -eq 0) {
        throw "No GGUF files or complete Safetensors model/adapter folders were found below '$($rootItem.FullName)'."
    }

    $directoryCounts = @{}
    foreach ($target in $targets) {
        $key = $target.Directory.ToLowerInvariant()
        if (-not $directoryCounts.ContainsKey($key)) {
            $directoryCounts[$key] = 0
        }
        $directoryCounts[$key]++
    }

    $rootPath = $rootItem.FullName.TrimEnd('\', '/')
    $processedCount = 0
    $failureCount = 0
    foreach ($target in @($targets | Sort-Object Directory, Label)) {
        $relativeDirectory = $target.Directory.Substring($rootPath.Length).TrimStart('\', '/')
        $nameSource = if ($relativeDirectory) { $relativeDirectory } else { $rootItem.Name }
        $multipleInDirectory = $directoryCounts[$target.Directory.ToLowerInvariant()] -gt 1
        if ($multipleInDirectory) {
            $nameSource += '-' + $target.Label
        }

        $childName = ConvertTo-OllamaName $nameSource
        $childModelfileName = 'Modelfile'
        if ($multipleInDirectory) {
            $childModelfileName += '.' + (ConvertTo-OllamaName $target.Label)
        }

        $childArguments = @{
            Path = $target.Path
            Name = $childName
            ModelfileName = $childModelfileName
        }
        foreach ($optionName in @('Base', 'SystemPrompt', 'Temperature', 'NumCtx')) {
            if ($PSBoundParameters.ContainsKey($optionName)) {
                $childArguments[$optionName] = $PSBoundParameters[$optionName]
            }
        }
        if ($Force) { $childArguments.Force = $true }
        if ($Create) { $childArguments.Create = $true }
        if ($Validate) { $childArguments.Validate = $true }

        try {
            & $PSCommandPath @childArguments
            $processedCount++
        } catch {
            $failureCount++
            Write-Warning "Failed '$($target.Path)': $($_.Exception.Message)"
        }
    }

    Write-Host ''
    Write-Host "Processed $processedCount model(s) below $($rootItem.FullName)" -ForegroundColor Green
    if ($failureCount -gt 0) {
        throw "$failureCount model(s) failed. Review the warnings above."
    }
    return
}

if ($ModelfileName -notmatch '^Modelfile(?:\.[a-zA-Z0-9._-]+)?$') {
    throw "Invalid ModelfileName '$ModelfileName'."
}

$inputItem = Get-Item -LiteralPath $Path
$modelDirectory = if ($inputItem.PSIsContainer) {
    $inputItem
} else {
    $inputItem.Directory
}

$kind = $null
$modelFile = $null
$adapterConfig = $null

if (-not $inputItem.PSIsContainer) {
    if ($inputItem.Extension -ine '.gguf') {
        throw "A file path must point to a .gguf file. For Safetensors, pass the containing folder."
    }
    $kind = 'GGUF model'
    $modelFile = $inputItem
} else {
    $adapterConfigPath = Join-Path $modelDirectory.FullName 'adapter_config.json'
    $safetensorFiles = @(Get-ChildItem -LiteralPath $modelDirectory.FullName -File -Filter '*.safetensors')
    $ggufFiles = @(Get-ChildItem -LiteralPath $modelDirectory.FullName -File -Filter '*.gguf')

    if (Test-Path -LiteralPath $adapterConfigPath -PathType Leaf) {
        if ($safetensorFiles.Count -eq 0) {
            throw "adapter_config.json was found, but the folder contains no .safetensors adapter weights."
        }
        $kind = 'Safetensors adapter'
        $adapterConfig = Get-Content -LiteralPath $adapterConfigPath -Raw | ConvertFrom-Json
    } elseif ($safetensorFiles.Count -gt 0) {
        $configPath = Join-Path $modelDirectory.FullName 'config.json'
        if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
            throw "Safetensors weights were found, but config.json is missing. Pass a complete Hugging Face model folder."
        }
        $kind = 'Safetensors model'
    } elseif ($ggufFiles.Count -eq 1) {
        $kind = 'GGUF model'
        $modelFile = $ggufFiles[0]
    } elseif ($ggufFiles.Count -gt 1) {
        $choices = ($ggufFiles.Name | Sort-Object) -join "`n  - "
        throw "More than one GGUF file was found. Run the script again with the exact file path:`n  - $choices"
    } else {
        throw "No .gguf file or .safetensors weights were found in '$($modelDirectory.FullName)'."
    }
}

if (-not $Name) {
    if ($inputItem.PSIsContainer) {
        $Name = ConvertTo-OllamaName $modelDirectory.Name
    } else {
        $stem = [System.IO.Path]::GetFileNameWithoutExtension($modelFile.Name)
        $stem = $stem -replace '(?i)[-_.](?:f16|f32|q\d(?:_[a-z0-9]+)+|iq\d(?:_[a-z0-9]+)+)$', ''
        $Name = ConvertTo-OllamaName $stem
    }
}

if ($Name -notmatch '^[a-zA-Z0-9][a-zA-Z0-9._-]*(?::[a-zA-Z0-9][a-zA-Z0-9._-]*)?$') {
    throw "'$Name' is not a valid local Ollama model name. Use letters, numbers, period, underscore, hyphen, and optionally :tag."
}

$lines = [System.Collections.Generic.List[string]]::new()
if ($kind -eq 'Safetensors adapter') {
    if (-not $Base -and $adapterConfig.PSObject.Properties.Name -contains 'base_model_name_or_path') {
        $Base = [string] $adapterConfig.base_model_name_or_path
        if ($Base) {
            Write-Warning "Using adapter_config.json base '$Base'. It must be an Ollama model name or an accessible local model path. Use -Base to override it."
        }
    }
    if (-not $Base) {
        throw "This is a Safetensors adapter. Supply its exact base with -Base, for example: -Base 'llama3.1:8b'."
    }

    if (Test-Path -LiteralPath $Base) {
        $Base = (Get-Item -LiteralPath $Base).FullName
    }
    $lines.Add('FROM ' + (Format-ModelfileValue $Base))
    $lines.Add('ADAPTER .')
} elseif ($kind -eq 'Safetensors model') {
    $lines.Add('FROM .')
} else {
    $relativeModelPath = './' + $modelFile.Name
    $lines.Add('FROM ' + (Format-ModelfileValue $relativeModelPath))
    if ($modelFile.Length -eq 0) {
        Write-Warning "The GGUF file is empty (0 bytes). The Modelfile will be written, but Ollama cannot import it until the download is complete."
    }
}

if ($PSBoundParameters.ContainsKey('Temperature')) {
    if ($Temperature -lt 0) {
        throw 'Temperature cannot be negative.'
    }
    $invariantTemperature = $Temperature.ToString(
        '0.################',
        [System.Globalization.CultureInfo]::InvariantCulture
    )
    $lines.Add('PARAMETER temperature ' + $invariantTemperature)
}

if ($PSBoundParameters.ContainsKey('NumCtx')) {
    if ($NumCtx -le 0) {
        throw 'NumCtx must be greater than zero.'
    }
    $lines.Add('PARAMETER num_ctx ' + $NumCtx)
}

if ($SystemPrompt) {
    if ($SystemPrompt.Contains('"""')) {
        throw 'SystemPrompt cannot contain three consecutive double-quote characters.'
    }
    $lines.Add('SYSTEM """' + $SystemPrompt + '"""')
}

$modelfilePath = Join-Path $modelDirectory.FullName $ModelfileName
if ((Test-Path -LiteralPath $modelfilePath) -and -not $Force) {
    throw "'$modelfilePath' already exists. Use -Force if you want to replace it."
}

$content = ($lines -join "`n") + "`n"
$utf8WithoutBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($modelfilePath, $content, $utf8WithoutBom)

$command = 'ollama create ' + $Name + ' -f ' + (Format-CommandLinePath $modelfilePath)

Write-Host ''
Write-Host "Created: $modelfilePath" -ForegroundColor Green
Write-Host "Detected: $kind"
Write-Host "Model name: $Name"
Write-Host ''

if ($Create) {
    Write-Host "Running: $command" -ForegroundColor Cyan
    & ollama create $Name -f $modelfilePath
    if ($LASTEXITCODE -ne 0) {
        throw "ollama create failed with exit code $LASTEXITCODE."
    }
    Write-Host "Run it with: ollama run $Name" -ForegroundColor Green
    if ($Validate) {
        Test-OllamaModel -ModelName $Name
    }
} else {
    Write-Host 'Create it in Ollama with:' -ForegroundColor Cyan
    Write-Host $command
}
