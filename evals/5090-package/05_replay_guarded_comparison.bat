@echo off
setlocal
cd /d "%~dp0"

call conda activate ultralytics
if errorlevel 1 exit /b 1

set "MATRIX_DIR=%~1"
if not defined MATRIX_DIR (
  for /f "delims=" %%D in ('dir /b /ad /o-d "evals\reports\*-qwen-matrix" 2^>nul') do if not defined MATRIX_DIR set "MATRIX_DIR=evals\reports\%%D"
)
if not defined MATRIX_DIR (
  echo [ERROR] No qwen matrix result directory was found.
  echo Usage: 05_replay_guarded_comparison.bat evals\reports\YYYYMMDD-HHMMSS-qwen-matrix
  exit /b 1
)

echo Replaying saved outputs from %MATRIX_DIR% through the deterministic safety gateway.
python evals\run_guarded_replay.py --matrix-dir "%MATRIX_DIR%"
exit /b %ERRORLEVEL%
