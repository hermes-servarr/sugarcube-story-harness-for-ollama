[CmdletBinding()]
param(
    [string]$ConfigPath = "C:\ProgramData\HermesBenchmark\config.json",
    [string]$OutputPath = "C:\ProgramData\HermesBenchmark\model-aliases.private.json",
    [string]$MetadataPath = "C:\ProgramData\HermesBenchmark\model-metadata.private.json",
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

$modelProfiles = $null
$modelProfilesProperty = $config.PSObject.Properties["model_profiles"]
if ($null -ne $modelProfilesProperty) {
    $modelProfiles = $modelProfilesProperty.Value
}

$modelMetadata = $null
if (Test-Path -LiteralPath $MetadataPath -PathType Leaf) {
    $metadataDocument =
        Get-Content -Raw -LiteralPath $MetadataPath | ConvertFrom-Json
    $metadataProperty =
        $metadataDocument.PSObject.Properties["model_metadata"]

    if ($null -eq $metadataProperty -or $null -eq $metadataProperty.Value) {
        throw "Private model metadata must contain a model_metadata object."
    }

    $modelMetadata = $metadataProperty.Value
}

$mapping = for ($index = 0; $index -lt $models.Count; $index++) {
    $model = $models[$index]
    $ingestionProfile = ""
    $series = ""
    $quantization = ""
    $parameterSize = ""
    $activeParameterSize = ""
    $contextMaxAccepted = ""
    $contextMaxFullRetrieval = ""
    $contextMaxEvaluatedTokens = ""

    if ($null -ne $modelProfiles) {
        $profileProperty = $modelProfiles.PSObject.Properties[$model]
        if ($null -ne $profileProperty) {
            $ingestionProfile = [string]$profileProperty.Value
        }
    }

    if ($null -ne $modelMetadata) {
        $metadataEntryProperty = $modelMetadata.PSObject.Properties[$model]
        if ($null -ne $metadataEntryProperty) {
            $metadataEntry = $metadataEntryProperty.Value
            $seriesProperty = $metadataEntry.PSObject.Properties["series"]
            $quantizationProperty =
                $metadataEntry.PSObject.Properties["quantization"]
            $parameterSizeProperty =
                $metadataEntry.PSObject.Properties["parameter_size"]
            $activeParameterSizeProperty =
                $metadataEntry.PSObject.Properties["active_parameter_size"]
            $contextMaxAcceptedProperty =
                $metadataEntry.PSObject.Properties["context_max_accepted"]
            $contextMaxFullRetrievalProperty =
                $metadataEntry.PSObject.Properties[
                    "context_max_full_retrieval"
                ]
            $contextMaxEvaluatedTokensProperty =
                $metadataEntry.PSObject.Properties[
                    "context_max_evaluated_tokens"
                ]

            if ($null -ne $seriesProperty) {
                $series = [string]$seriesProperty.Value
            }
            if ($null -ne $quantizationProperty) {
                $quantization = [string]$quantizationProperty.Value
            }
            if ($null -ne $parameterSizeProperty) {
                $parameterSize = [string]$parameterSizeProperty.Value
            }
            if ($null -ne $activeParameterSizeProperty) {
                $activeParameterSize =
                    [string]$activeParameterSizeProperty.Value
            }
            if ($null -ne $contextMaxAcceptedProperty) {
                $contextMaxAccepted =
                    [string]$contextMaxAcceptedProperty.Value
            }
            if ($null -ne $contextMaxFullRetrievalProperty) {
                $contextMaxFullRetrieval =
                    [string]$contextMaxFullRetrievalProperty.Value
            }
            if ($null -ne $contextMaxEvaluatedTokensProperty) {
                $contextMaxEvaluatedTokens =
                    [string]$contextMaxEvaluatedTokensProperty.Value
            }
        }
    }

    [pscustomobject][ordered]@{
        alias = Get-ModelAlias -Index $index
        model = $model
        ingestion_profile = $ingestionProfile
        series = $series
        quantization = $quantization
        parameter_size = $parameterSize
        active_parameter_size = $activeParameterSize
        context_max_accepted = $contextMaxAccepted
        context_max_full_retrieval = $contextMaxFullRetrieval
        context_max_evaluated_tokens = $contextMaxEvaluatedTokens
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

$mapping |
    Select-Object alias, @{
        Name = "series"
        Expression = {
            if ([string]::IsNullOrWhiteSpace($_.series)) {
                "<not configured>"
            }
            else {
                $_.series
            }
        }
    }, @{
        Name = "quantization"
        Expression = {
            if ([string]::IsNullOrWhiteSpace($_.quantization)) {
                "<not configured>"
            }
            else {
                $_.quantization
            }
        }
    }, @{
        Name = "parameter_size"
        Expression = {
            if ([string]::IsNullOrWhiteSpace($_.parameter_size)) {
                "<not configured>"
            }
            else {
                $_.parameter_size
            }
        }
    }, @{
        Name = "active_parameter_size"
        Expression = {
            if ([string]::IsNullOrWhiteSpace($_.active_parameter_size)) {
                "-"
            }
            else {
                $_.active_parameter_size
            }
        }
    }, @{
        Name = "ingestion_profile"
        Expression = {
            if ([string]::IsNullOrWhiteSpace($_.ingestion_profile)) {
                "<not configured>"
            }
            else {
                $_.ingestion_profile
            }
        }
    }, @{
        Name = "context_accepted"
        Expression = {
            if ([string]::IsNullOrWhiteSpace($_.context_max_accepted)) {
                "<not tested>"
            }
            else {
                $_.context_max_accepted
            }
        }
    }, @{
        Name = "context_retrieved"
        Expression = {
            if (
                [string]::IsNullOrWhiteSpace(
                    $_.context_max_full_retrieval
                )
            ) {
                "<not tested>"
            }
            else {
                $_.context_max_full_retrieval
            }
        }
    }, @{
        Name = "max_evaluated_tokens"
        Expression = {
            if (
                [string]::IsNullOrWhiteSpace(
                    $_.context_max_evaluated_tokens
                )
            ) {
                "<not reported>"
            }
            else {
                $_.context_max_evaluated_tokens
            }
        }
    }, model |
    Format-Table -AutoSize |
    Out-String -Width 4096 |
    Write-Host

if (-not $NoWrite) {
    Write-Host "Private mapping saved locally to: $OutputPath"
}
