@echo off
setlocal
cd /d "%~dp0"

call conda activate ultralytics
if errorlevel 1 (
  echo [ERROR] Cannot activate conda environment: ultralytics
  exit /b 1
)

python -m pip install -r evals\requirements-5090.txt
if errorlevel 1 (
  echo [ERROR] Dependency installation failed. Keep the full console output.
  exit /b 1
)

python -c "import torch, transformers, huggingface_hub, harness_evals, jsonschema; print('torch=', torch.__version__, 'cuda=', torch.version.cuda); print('transformers=', transformers.__version__)"
if errorlevel 1 exit /b 1
echo [PASS] Dependencies imported successfully. Existing PyTorch was not reinstalled.
