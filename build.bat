@echo off
setlocal

rem Run from the directory this script lives in (the spec uses relative paths).
cd /d "%~dp0"

set "CONDA_ENV=cardio-signal-lab"
set "SPEC=cardio_signal_lab.spec"

echo.
echo ============================================================
echo  CardioSignalLab - PyInstaller build
echo ============================================================
echo.

rem Locate the conda environment's Python.
set "PY="
for %%D in (
    "%USERPROFILE%\miniconda3"
    "%USERPROFILE%\Miniconda3"
    "%USERPROFILE%\anaconda3"
    "%USERPROFILE%\Anaconda3"
    "C:\ProgramData\miniconda3"
    "C:\ProgramData\anaconda3"
    "C:\miniconda3"
    "C:\anaconda3"
) do (
    if not defined PY if exist "%%~D\envs\%CONDA_ENV%\python.exe" set "PY=%%~D\envs\%CONDA_ENV%\python.exe"
)

if not defined PY (
    echo Error: Could not find the "%CONDA_ENV%" conda environment.
    echo.
    echo Set it up first. Open Anaconda Prompt and run:
    echo     conda create -n %CONDA_ENV% python=3.12
    echo     conda activate %CONDA_ENV%
    echo     pip install -e .
    echo.
    pause
    exit /b 1
)

echo Using Python: %PY%
echo.

echo [1/3] Installing PyInstaller...
"%PY%" -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo.
    echo Error: Failed to install PyInstaller.
    pause
    exit /b 1
)

echo.
echo [2/3] Cleaning previous build output...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo [3/3] Running PyInstaller (%SPEC%)...
"%PY%" -m PyInstaller --noconfirm %SPEC%
if errorlevel 1 (
    echo.
    echo Error: PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Build complete: dist\CardioSignalLab\CardioSignalLab.exe
echo ============================================================
echo.
echo Next: open installer.iss in Inno Setup Compiler and compile it.
echo.
pause
