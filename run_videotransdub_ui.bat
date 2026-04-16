@echo off
setlocal EnableExtensions

set "REPO_DIR=%~dp0"
if "%REPO_DIR:~-1%"=="\" set "REPO_DIR=%REPO_DIR:~0,-1%"

set "APP_DIR=%REPO_DIR%\apps\videotransdub"
set "VENV_DIR=%APP_DIR%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "VENV_UI=%VENV_DIR%\Scripts\videotransdub-ui.exe"
set "UV_CACHE_DIR=%APP_DIR%\.uv-cache"
set "UV_LINK_MODE=copy"
set "PYTHONUTF8=1"
set "PORT=8501"
set "MODE=%~1"

if not exist "%APP_DIR%\pyproject.toml" (
    echo [ERROR] Khong tim thay project VideoTransDub tai:
    echo         %APP_DIR%
    exit /b 1
)

if exist "%REPO_DIR%\ffmpeg\ffmpeg.exe" (
    set "PATH=%REPO_DIR%\ffmpeg;%PATH%"
)

where uv >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Chua tim thay lenh ^'uv^' trong PATH.
    echo         Cai uv truoc: https://docs.astral.sh/uv/
    exit /b 1
)

if /I "%MODE%"=="--help" goto :help

if /I "%MODE%"=="--reinstall" (
    echo [INFO] Dang xoa moi truong cu de cai lai...
    if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%"
)

if not exist "%VENV_PYTHON%" goto :install
if not exist "%VENV_UI%" goto :install
goto :post_install

:install
echo [INFO] Lan dau hoac moi truong chua san sang. Dang cai dat...
pushd "%APP_DIR%"
call uv venv .venv
if errorlevel 1 goto :install_failed
call uv pip install --python ".venv\Scripts\python.exe" -e ".[ui,qwen,tts,inpaint]"
if errorlevel 1 goto :install_failed
popd
echo [OK] Cai dat xong.

:post_install
if /I "%MODE%"=="--setup-only" (
    echo [OK] Moi truong da san sang.
    echo      Chay lai file nay khong can tham so de mo giao dien.
    exit /b 0
)

where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo [WARN] Chua tim thay ffmpeg trong PATH.
    echo        Ban van mo duoc UI, nhung render video se loi cho den khi cai ffmpeg.
)

if "%QWEN_API_KEY%"=="" (
    echo [WARN] QWEN_API_KEY chua duoc dat trong environment.
    echo        Neu ban dung preset qwen_free hoac qwen_asr_free, hay dat bien nay truoc khi start pipeline.
)

echo [INFO] Dang mo VideoTransDub UI tai http://127.0.0.1:%PORT%
echo [INFO] Dong cua so nay de dung Streamlit server.
pushd "%APP_DIR%"
call "%VENV_UI%" --port %PORT%
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%

:install_failed
set "EXIT_CODE=%ERRORLEVEL%"
popd
echo [ERROR] Cai dat that bai. Ma loi: %EXIT_CODE%
exit /b %EXIT_CODE%

:help
echo Su dung:
echo   run_videotransdub_ui.bat
echo       Cai dat lan dau neu can, sau do chay UI.
echo.
echo   run_videotransdub_ui.bat --setup-only
echo       Chi cai dat / kiem tra moi truong, khong mo UI.
echo.
echo   run_videotransdub_ui.bat --reinstall
echo       Xoa .venv cu va cai dat lai tu dau.
exit /b 0
