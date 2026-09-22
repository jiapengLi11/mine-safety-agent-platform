@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

call conda activate ultralytics
if errorlevel 1 exit /b 1

set HF_HOME=E:\mineguard-models\.cache
python evals\download_qwen_models.py --config evals\config\qwen-matrix-5090.json --model-root E:\mineguard-models --max-workers 4
if errorlevel 1 (
  echo [ERROR] 下载未完成。修复网络后重新运行本脚本即可断点续传。
  exit /b 1
)
echo [PASS] 三个模型已下载并通过结构完整性检查。
