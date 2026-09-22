param(
    [ValidateSet('rule', 'qwen', 'openai')]
    [string]$Target = 'rule',
    [ValidateSet('ci', 'candidate-model')]
    [string]$Profile = 'ci',
    [string]$CondaEnvironment = 'yolo26',
    [string]$ModelPath = 'E:\project11\model_cache\Qwen3-0.6B-c1899de',
    [ValidateSet('auto', 'float16', 'bfloat16', 'float32')]
    [string]$DType = 'float16',
    [int]$Limit = 0,
    [switch]$EnforceGate
)

$ErrorActionPreference = 'Stop'
$evalRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$conda = 'D:\Anaconda\Scripts\conda.exe'
if (-not (Test-Path -LiteralPath $conda)) {
    throw "Conda executable not found: $conda"
}

$arguments = @(
    'run', '-n', $CondaEnvironment, 'python',
    (Join-Path $evalRoot 'run_eval.py'),
    '--target', $Target,
    '--profile', $Profile
)
if ($Target -eq 'qwen') {
    $arguments += @('--model-path', $ModelPath, '--device', 'cuda', '--dtype', $DType)
}
if ($Limit -gt 0) {
    $arguments += @('--limit', $Limit)
}
if ($EnforceGate) {
    $arguments += '--enforce-gate'
}

& $conda @arguments
exit $LASTEXITCODE
