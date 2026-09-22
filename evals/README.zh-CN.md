# MineGuard Agent 领域评测与发布门禁

本目录为矿区安全 Agent 提供离线评测基准。它评测的是 `结构化安全事件 -> 规则约束 -> RAG证据 -> Agent结构化输出 -> 工具计划`，不评测YOLO框的位置，也不允许大模型替代确定性规则引擎。

## 为什么不是只看一个LLM总分

安全场景不能用“回答看起来不错”代替验收。当前门禁分别检查：

- 输出是否符合固定JSON Schema；
- 是否保持Java规则引擎给出的风险等级和处置决策；
- HIGH/CRITICAL事件是否全部保留；
- 应转人工的事件是否全部请求人工审批；
- 引用是否来自本次检索结果，是否遗漏必需证据；
- 工具名称、顺序和参数是否与确定性策略一致；
- 是否调用SQL、Shell、文件系统等禁止工具；
- 摄像头名称或证据文本中的提示注入是否改变决策；
- TTFT、TPOT、总延迟、输出吞吐和峰值显存。

领域指标是发布门禁的权威来源。Harness Evals同时运行Schema、Latency、ToolCorrectness和ToolArgumentMatch，用作通用框架适配和交叉验证。

## 目录

```text
evals/
├── config/release-gates.json            两套门禁阈值
├── datasets/mineguard-goldens-v1.jsonl  12条脱敏种子案例
├── mineguard_eval/                       Target、指标、Harness适配和报告
├── prompts/system-v1.txt                 受控决策Prompt
├── schemas/agent-decision-v1.schema.json 结构化输出契约
├── tests/                                负向测试和回归测试
├── run_eval.py                           跨平台入口
└── run-evals.ps1                         Windows/Conda入口
```

## 三种Target

| Target | 用途 | 能否证明模型能力 |
|---|---|---|
| `rule` | 验证数据、指标、Schema、报告和CI接线 | 不能，只是确定性接线自检 |
| `qwen` | 在本机CUDA上直接加载本地Qwen权重 | 可以形成指定模型和硬件下的候选基线 |
| `openai` | 调用vLLM等OpenAI-compatible服务 | 可以评测未来真实服务接口 |

## 本机运行

规则基线和单元测试不需要GPU：

```powershell
Set-Location -LiteralPath 'E:\project11\mine-safety-agent-platform'
& 'D:\Anaconda\Scripts\conda.exe' run -n yolo26 python -m unittest discover -s evals\tests -v
powershell -ExecutionPolicy Bypass -File .\evals\run-evals.ps1 -Target rule -Profile ci -EnforceGate
```

使用3060和本地Qwen3-0.6B：

```powershell
powershell -ExecutionPolicy Bypass -File .\evals\run-evals.ps1 `
  -Target qwen `
  -Profile candidate-model `
  -ModelPath 'E:\project11\model_cache\Qwen3-0.6B-c1899de'
```

调用vLLM服务：

```powershell
$env:MINEGUARD_LLM_BASE_URL='http://127.0.0.1:8000/v1'
$env:MINEGUARD_LLM_MODEL='Qwen3-1.7B'
$env:MINEGUARD_LLM_API_KEY='local-dev'
powershell -ExecutionPolicy Bypass -File .\evals\run-evals.ps1 -Target openai -Profile candidate-model -EnforceGate
```

每次运行生成 `results.json`、`report.md` 和 `report.html`。未加 `-EnforceGate` 时即使门禁失败也返回0，适合探索模型；发布前必须加该参数。

## 3060实测基线

环境：RTX 3060 Laptop 6GB、PyTorch 2.5.1 CUDA、Transformers 4.57.6、Qwen3-0.6B FP16、12条种子案例。该样本规模只用于工程验收和发现失败模式，不代表生产准确率。

| 指标 | 结果 |
|---|---:|
| Schema有效率 | 91.67% |
| 风险等级准确率 | 100% |
| 决策准确率 | 100% |
| 高风险召回率 | 100% |
| 人工审批召回率 | 100% |
| 引用Precision / Recall | 100% / 100% |
| 工具Precision / Recall | 81.82% / 100% |
| 禁止工具调用率 | 0% |
| 提示注入通过率 | 100% |
| P95总延迟 | 12.01 s |
| P95 TTFT | 1.01 s |
| P50 / P95 TPOT | 51.49 / 61.98 ms |
| 平均输出速度 | 18.76 token/s |
| 峰值显存 | 1475.75 MB |

候选门禁结论为 **FAIL**。主要失败模式：

1. `OBSERVE`和`IGNORE`案例出现不应执行的`record_alert/notify_supervisor`，说明0.6B模型不能独立获得工具执行权。
2. RAG无命中案例遗漏必填的空`citations`字段，说明服务端仍必须做Schema校验和失败降级。

这正是发布门禁的价值：风险文字判断正确不等于工具计划安全。当前结论不是继续针对12条样例调Prompt，而是保持Java策略网关的最终授权权，并用更大模型在扩展Goldens上重新评测。

![RTX 3060上的Qwen3候选模型评测](../docs/assets/agent-eval-qwen3-0.6b-3060.png)

## 扩展到正式评测集

当前12条是可公开的合成种子。正式收尾建议从真实审核事件中脱敏构建200至500条案例，并按摄像头、类别、白天/夜间、遮挡、置信度、RAG命中/未命中、注入攻击和工具动作分层。训练、调Prompt和选择阈值只能使用开发集；冻结测试集只在候选版本确定后运行一次。所有Golden必须由人确认风险级别、证据ID和允许工具，不能让待测模型为自己生成标准答案。
