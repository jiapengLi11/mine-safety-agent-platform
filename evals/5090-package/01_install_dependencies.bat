@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

call conda activate ultralytics
if errorlevel 1 (
  echo [ERROR] 无法激活 conda 环境 ultralytics。
  exit /b 1
)

python -m pip install -r evals\requirements-5090.txt
if errorlevel 1 (
  echo [ERROR] 依赖安装失败，请保留完整输出。
  exit /b 1
)

python -c "import torch, transformers, huggingface_hub, harness_evals, jsonschema; print('torch=', torch.__version__, 'cuda=', torch.version.cuda); print('transformers=', transformers.__version__)"
if errorlevel 1 exit /b 1
echo [PASS] 依赖安装与导入检查完成，现有 PyTorch 未被主动重装。
