@echo off
setlocal
cd /d "%~dp0"

call conda activate ultralytics
if errorlevel 1 exit /b 1

set HF_HOME=E:\mineguard-models\.cache
python evals\download_qwen_models.py --config evals\config\qwen-matrix-5090.json --model-root E:\mineguard-models --max-workers 4
if errorlevel 1 (
  echo [ERROR] Download incomplete. Fix the network and rerun this file to resume.
  exit /b 1
)
echo [PASS] All three models passed structural validation.
