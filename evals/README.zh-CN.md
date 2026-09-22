# MineGuard Agent 领域评测与发布门禁

本目录为矿区安全 Agent 提供离线评测基准。它评测的是 `结构化安全事件 -> 规则约束 -> RAG证据 -> Agent结构化输出 -> 工具计划`，不评测YOLO框的位置，也不允许大模型替代确定性规则引擎。

完整的方法论、5090模型矩阵、失败案例和面试讲法见 [`MineGuard LLM安全评测方法与5090模型选型记录`](../docs/evaluation/MineGuard_LLM安全评测方法与5090模型选型记录_20260922.md)。

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
├── download_qwen_models.py               5090端断点下载模型
├── run_model_matrix.py                   多模型串行重复评测与选型
├── run_guarded_replay.py                 历史原始输出的安全网关系统级重放
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

## RTX 5090轻量交接包

仓库提供 `tools/build_5090_eval_package.py`，它只打包评测代码、12条脱敏Goldens、JSON Schema、Prompt、门禁配置和四个BAT，不携带模型权重。构建命令：

```powershell
python .\tools\build_5090_eval_package.py
```

产物位于 `release/mineguard-qwen-matrix-5090.zip`。将其带到实验室后，按包内编号运行：

1. `01_install_dependencies.bat`：复用 `ultralytics` 环境中的CUDA PyTorch，只补评测依赖；
2. `02_download_models.bat`：在5090机器把Qwen3-1.7B、4B、8B下载至 `E:\mineguard-models`；
3. `03_preflight.bat`：检查物理GPU 1、BF16、模型文件和评测资产，不加载模型；
4. `04_run_matrix.bat`：三个模型各重复三次，串行运行并输出选型报告。
5. `05_replay_guarded_comparison.bat`：不重复推理，使用已保存输出比较裸模型与确定性网关后的系统结果。

每个模型和每次重复都使用独立Python进程，避免多个模型同时占用显存。每完成一次运行都会更新 `matrix-progress.json`，因此中途断电、网络中断或8B失败不会抹掉先前结果。结果目录还包含每次运行的案例级输出和指标，便于复核失败原因。

自动选型遵循保守规则：某模型三次运行必须全部通过 `candidate-model` 门禁；多个模型合格时选择参数量最小者。若没有模型全通过，报告明确输出 `NONE`，而不是以平均分掩盖安全失败。

## 安全网关系统级重放

已经有矩阵结果时，不需要重新占用GPU。以下命令会严格解析每条 `raw_output`，校验Schema、规则决策、证据引用和工具计划，并同时报告裸输出与安全计划：

```powershell
python evals\run_guarded_replay.py `
  --matrix-dir evals\reports\20260922-123311-qwen-matrix `
  --output-dir evals\reports\20260922-guarded-system-comparison
```

当前5090历史输出重放结果：1.7B裸模型三轮均失败，网关后因安全修复无证据引用而三轮均通过，拦截率为8.33%，没有新增人工复核；4B有66.67%输出被拦截并造成58.33%人工复核升级，仍不适合作为候选；8B保持零拦截和三轮全通过。该结果是保存输出上的确定性重放，不等同于已完成Java线上调用链集成。

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
