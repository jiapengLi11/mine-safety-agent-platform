@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

call conda activate ultralytics
if errorlevel 1 exit /b 1
set CUDA_VISIBLE_DEVICES=1
set TOKENIZERS_PARALLELISM=false

echo 即将串行运行 Qwen3-1.7B、4B、8B，每个模型重复 3 次。
echo 请确认物理 GPU 1 当前没有训练任务。
choice /C YN /M "Continue"
if errorlevel 2 exit /b 0

python evals\run_model_matrix.py --config evals\config\qwen-matrix-5090.json --model-root E:\mineguard-models --device cuda --repeats 3 --enforce-one-pass
set RESULT=%ERRORLEVEL%
if not "%RESULT%"=="0" echo [WARN] 评测已结束，但没有模型满足全部发布门禁，或存在运行失败。结果仍已保留。
exit /b %RESULT%
