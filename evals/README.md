# MineGuard Domain Evals

This module evaluates the constrained decision boundary between structured safety events, retrieved evidence and typed Agent tool plans. It does not evaluate YOLO localization and does not let an LLM override deterministic safety rules.

The authoritative gates cover JSON Schema compliance, risk/decision preservation, high-risk and human-approval recall, citation provenance, exact tool plans, forbidden tools, prompt-injection resistance and latency. Harness Evals 0.23.1 supplies framework-native Schema, latency and typed-tool checks as a second implementation.

```powershell
Set-Location -LiteralPath 'E:\project11\mine-safety-agent-platform'
powershell -ExecutionPolicy Bypass -File .\evals\run-evals.ps1 -Target rule -Profile ci -EnforceGate
powershell -ExecutionPolicy Bypass -File .\evals\run-evals.ps1 -Target qwen -Profile candidate-model
```

See [the Chinese evaluation guide](README.zh-CN.md) for the metric definitions, RTX 3060/Qwen3-0.6B result and the reviewed-Golden expansion protocol.

