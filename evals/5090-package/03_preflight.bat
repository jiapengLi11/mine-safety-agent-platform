@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

call conda activate ultralytics
if errorlevel 1 exit /b 1
set CUDA_VISIBLE_DEVICES=1

nvidia-smi -i 1
if errorlevel 1 exit /b 1

python evals\run_model_matrix.py --config evals\config\qwen-matrix-5090.json --model-root E:\mineguard-models --device cuda --dry-run
if errorlevel 1 (
  echo [ERROR] 预检失败，不要开始正式评测。
  exit /b 1
)
echo [PASS] 预检通过：没有加载模型，也没有执行推理。
