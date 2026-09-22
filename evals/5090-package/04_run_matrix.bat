@echo off
setlocal
cd /d "%~dp0"

call conda activate ultralytics
if errorlevel 1 exit /b 1
set CUDA_VISIBLE_DEVICES=1
set TOKENIZERS_PARALLELISM=false

echo Starting Qwen3-1.7B, Qwen3-4B, and Qwen3-8B sequentially with 3 repeats each.
python evals\run_model_matrix.py --config evals\config\qwen-matrix-5090.json --model-root E:\mineguard-models --device cuda --repeats 3 --enforce-one-pass
set RESULT=%ERRORLEVEL%
if not "%RESULT%"=="0" echo [WARN] No model passed every release gate, or a run failed. Existing results were preserved.
exit /b %RESULT%
