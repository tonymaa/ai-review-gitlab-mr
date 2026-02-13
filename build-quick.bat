@echo off
REM 快速打包脚本 - 仅打包后端（假设前端已构建）

chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   GitLab AI Review 快速打包
echo ========================================
echo.

set PROJECT_ROOT=%~dp0
set BUILD_DIR=%PROJECT_ROOT%build_temp
set DIST_DIR=%PROJECT_ROOT%dist

REM 检查前端是否已构建
if not exist "%PROJECT_ROOT%web\dist" (
    echo 错误：前端未构建！
    echo 请先运行 web 构建命令：cd web ^&^& npm run build
    echo 或运行完整的 build.bat
    pause
    exit /b 1
)

echo [1/4] 准备构建目录...
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
mkdir "%BUILD_DIR%"
mkdir "%DIST_DIR%"

echo [2/4] 复制文件...
xcopy /s /e /y "%PROJECT_ROOT%web\dist" "%BUILD_DIR%\web\dist\" >nul
xcopy /s /e /y "%PROJECT_ROOT%server" "%BUILD_DIR%\server\" >nul
xcopy /s /e /y "%PROJECT_ROOT%src" "%BUILD_DIR%\src\" >nul
copy /y "%PROJECT_ROOT%server.py" "%BUILD_DIR%\" >nul

echo [3/4] 检查 PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo 安装 PyInstaller...
    pip install pyinstaller
)

echo [4/4] 开始打包...
cd /d "%BUILD_DIR%"
pyinstaller --onefile --console --name "GitLab-AI-Review" ^
    --add-data "web\dist;web\dist" ^
    --add-data "server;server" ^
    --add-data "src;src" ^
    --hidden-import "uvicorn.logging" ^
    --hidden-import "uvicorn.loops.auto" ^
    --hidden-import "uvicorn.protocols.http.auto" ^
    --hidden-import "uvicorn.protocols.websockets.auto" ^
    --hidden-import "passlib.hash.bcrypt" ^
    --hidden-import "passlib.handlers.bcrypt" ^
    --hidden-import "bcrypt" ^
    --hidden-import "websockets" ^
    --hidden-import "sqlalchemy.dialects.sqlite" ^
    --hidden-import "python-jose" ^
    --hidden-import "dotenv" ^
    server.py

if errorlevel 1 (
    echo 打包失败！
    pause
    exit /b 1
)

copy /y "%BUILD_DIR%\dist\GitLab-AI-Review.exe" "%PROJECT_ROOT%\"

echo.
echo ========================================
echo   打包完成！
echo ========================================
echo.
echo EXE 位置: %PROJECT_ROOT%GitLab-AI-Review.exe
echo.

REM 清理临时文件
rmdir /s /q "%BUILD_DIR%"

pause
