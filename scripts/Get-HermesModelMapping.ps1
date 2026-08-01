[CmdletBinding()]
param(
    [string]$ConfigPath = "C:\ProgramData\HermesBenchmark\config.json",
    [string]$OutputPath = "C:\ProgramData\HermesBenchmark\model-aliases.private.json",
    [switch]$NoWrite
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-ModelAlias {
    param(
        [Parameter(Mandatory)]
        [ValidateRange(0, [int]::MaxValue)]
        [int]$Index
    )

    $value = $Index + 1
    $letters = ""

    while ($value -gt 0) {
        $remainder = ($value - 1) % 26
        $letters = [char]([int][char]'A' + $remainder) + $letters
        $value = [math]::Floor(($value - 1) / 26)
    }

    return "Model_$letters"
}

if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
    throw "Benchmark configuration was not found at the requested path."
}

$config = Get-Content -Raw -LiteralPath $ConfigPath | ConvertFrom-Json
if ($null -eq $config.models -or @($config.models).Count -eq 0) {
    throw "The benchmark configuration contains no models."
}

$modelSet = [System.Collections.Generic.HashSet[string]]::new(
    [System.StringComparer]::Ordinal
)
foreach ($model in @($config.models)) {
    $name = [string]$model
    if (-not [string]::IsNullOrWhiteSpace($name)) {
        [void]$modelSet.Add($name)
    }
}

$models = [string[]]$modelSet
[System.Array]::Sort($models, [System.StringComparer]::Ordinal)

$mapping = for ($index = 0; $index -lt $models.Count; $index++) {
    [pscustomobject][ordered]@{
        alias = Get-ModelAlias -Index $index
        model = $models[$index]
    }
}

if (-not $NoWrite) {
    $parent = Split-Path -Parent $OutputPath
    if ($parent) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }

    $document = [ordered]@{
        private = $true
        generated_at = (Get-Date).ToUniversalTime().ToString("o")
        trusted_code_commit = [string]$config.trusted_code_commit
        model_aliases = @($mapping)
    }

    [System.IO.File]::WriteAllText(
        $OutputPath,
        ($document | ConvertTo-Json -Depth 10),
        [System.Text.UTF8Encoding]::new($false)
    )

    & icacls.exe $OutputPath /inheritance:r | Out-Null
    & icacls.exe $OutputPath /setowner "Administrators" | Out-Null
    & icacls.exe $OutputPath /grant:r `
        "Administrators:F" `
        "SYSTEM:F" | Out-Null
}

$mapping | Format-Table alias, model -AutoSize

if (-not $NoWrite) {
    Write-Host "Private mapping saved locally to: $OutputPath"
}

