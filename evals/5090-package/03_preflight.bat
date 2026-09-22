@echo off
setlocal
cd /d "%~dp0"

call conda activate ultralytics
if errorlevel 1 exit /b 1
set CUDA_VISIBLE_DEVICES=1

nvidia-smi -i 1
if errorlevel 1 exit /b 1

python evals\run_model_matrix.py --config evals\config\qwen-matrix-5090.json --model-root E:\mineguard-models --device cuda --dry-run
if errorlevel 1 (
  echo [ERROR] Preflight failed. Do not start the matrix evaluation.
  exit /b 1
)
echo [PASS] Preflight passed. No model was loaded and no inference was run.
